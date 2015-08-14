# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2013, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

#}}}


from __future__ import absolute_import, print_function

import bisect
import errno
import logging
import os
import random
import re

import gevent
from gevent.fileobject import FileObject
from zmq import green as zmq
from zmq.utils import jsonapi

from .agent.utils import strip_comments
from .lib.inotify.green import inotify, IN_MODIFY
from .vip.agent import Agent, Core, RPC
from .vip.socket import encode_key


_log = logging.getLogger(__name__)


_SAMPLE_AUTH_FILE = '''{
    "allow": [
        # {"credentials": "CURVE:wk2BXQdHkAlMIoXthOPhFOqWpapD1eWsBQYY7h4-bXw", "domain": "vip", "address": "/192\\.168\\.1\\..*/"}
    ]
}
'''

_dump_re = re.compile(r'([,\\])')
_load_re = re.compile(r'\\(.)|,')

def dump_user(*args):
    return ','.join([_dump_re.sub(r'\\\1', arg) for arg in args])

def load_user(string):
    def sub(match):
        return match.group(1) or '\x00'
    return _load_re.sub(sub, string).split('\x00')


class AuthService(Agent):
    def __init__(self, auth_file, *args, **kwargs):
        super(AuthService, self).__init__(*args, **kwargs)
        self.auth_file = os.path.abspath(auth_file)
        self.zap_socket = None
        self._zap_greenlet = None
        self.auth_entries = []

    @Core.receiver('onsetup')
    def setup_zap(self, sender, **kwargs):
        self.zap_socket = zmq.Socket(zmq.Context.instance(), zmq.ROUTER)
        self.zap_socket.bind('inproc://zeromq.zap.01')
        self.read_auth_file()
        self.core.spawn(self._watch_auth_file)

    def read_auth_file(self):
        _log.info('loading auth file %s', self.auth_file)
        try:
            try:
                fil = open(self.auth_file)
            except IOError as exc:
                if exc.errno != errno.ENOENT:
                    raise
                _log.debug('missing auth file %s', self.auth_file)
                _log.info('creating auth file %s', self.auth_file)
                fd = os.open(self.auth_file, os.O_CREAT|os.O_WRONLY, 0o660)
                try:
                    os.write(fd, _SAMPLE_AUTH_FILE)
                finally:
                    os.close(fd)
                self.auth_entries = []
            with open(self.auth_file) as fil:
                # Use gevent FileObject to avoid blocking the thread
                data = strip_comments(FileObject(fil, close=False).read())
                auth_data = jsonapi.loads(data)
        except Exception:
            _log.exception('error loading %s', self.auth_file)
        else:
            try:
                allowed = auth_data['allow']
            except KeyError:
                _log.warn("missing 'allow' key in auth file %s", self.auth_file)
                allowed = []
            entries = []
            for entry in allowed:
                try:
                    entries.append(AuthEntry(**entry))
                except TypeError:
                    _log.warn('invalid entry %r in auth file %s',
                              entry, self.auth_file)
            self.auth_entries = entries
            _log.info('auth file %s loaded', self.auth_file)

    def _watch_auth_file(self):
        dirname, filename = os.path.split(self.auth_file)
        with inotify() as inot:
            inot.add_watch(dirname, IN_MODIFY)
            for event in inot:
                if event.name == filename and event.mask & IN_MODIFY:
                    self.read_auth_file()

    @Core.receiver('onstop')
    def stop_zap(self, sender, **kwargs):
        if self._zap_greenlet is not None:
            self._zap_greenlet.kill()

    @Core.receiver('onfinish')
    def unbind_zap(self, sender, **kwargs):
        if self.zap_socket is not None:
            self.zap_socket.unbind('inproc://zeromq.zap.01')

    @Core.receiver('onstart')
    def zap_loop(self, sender, **kwargs):
        self._zap_greenlet = gevent.getcurrent()
        sock = self.zap_socket
        time = gevent.core.time
        blocked = {}
        wait_list = []
        timeout = None
        while True:
            events = sock.poll(timeout)
            now = time()
            if events:
                zap = sock.recv_multipart()
                version = zap[2]
                if version != b'1.0':
                    continue
                domain, address, _, kind = zap[4:8]
                credentials = zap[8:]
                if kind == b'CURVE':
                    credentials[0] = encode_key(credentials[0])
                elif kind not in [b'NULL', b'PLAIN']:
                    continue
                response = zap[:4]
                user = self.authenticate(domain, address, kind, credentials)
                if user:
                    _log.info('authentication success: domain=%r, address=%r, '
                              'mechanism=%r, credentials=%r, user_id=%r',
                          domain, address, kind, credentials[:1], user)
                    response.extend([b'200', b'SUCCESS', user, b''])
                    sock.send_multipart(response)
                else:
                    _log.info('authentication failure: domain=%r, address=%r, '
                              'mechanism=%r, credentials=%r',
                              domain, address, kind, credentials)
                    try:
                        expire, delay = blocked[address]
                    except KeyError:
                        delay = random.random()
                    else:
                        if now >= expire:
                            delay = random.random()
                        else:
                            delay *= 2
                            if delay > 100:
                                delay = 100
                    expire = now + delay
                    bisect.bisect(wait_list, (expire, address, response))
                    blocked[address] = expire, delay
            while wait_list:
                expire, address, response = wait_list[0]
                if now < expire:
                    break
                wait_list.pop(0)
                response.extend([b'400', b'FAIL', b'', b''])
                sock.send_multipart(response)
                try:
                    if now >= blocked[address][0]:
                        blocked.pop(address)
                except KeyError:
                    pass
            timeout = (wait_list[0][0] - now) if wait_list else None

    def authenticate(self, domain, address, mechanism, credentials):
        for entry in self.auth_entries:
            if entry.match(domain, address, mechanism, credentials):
                return entry.user_id or dump_user(
                    domain, address, mechanism, *credentials[:1])
        if mechanism == 'NULL' and address.startswith('localhost:'):
            if int(address.split(':', 2)[1]) == os.getuid():
                return dump_user(domain, address, mechanism, *credentials[:1])


class String(unicode):
    def __new__(cls, value):
        obj = super(String, cls).__new__(cls, value)
        if len(obj) > 1 and obj[0] == obj[-1] == '/':
            obj.regex = regex = re.compile('^' + obj[1:-1] + '$')
            obj.match = lambda val: bool(regex.match(val))
        return obj

    def match(self, value):
        return value == self


class List(list):
    def match(self, value):
        for elem in self:
            if elem.match(value):
                return True
        return False


class AuthEntry(object):
    def __init__(self, domain=None, address=None, credentials=None,
                 user_id=None, groups=None, roles=None,
                 capabilities=None, **kwargs):
        def build(value, list_class=List, str_class=String):
            if not value:
                return None
            if isinstance(value, basestring):
                return String(value)
            return List(String(elem) for elem in value)

        self.domain = build(domain)
        self.address = build(address)
        self.credentials = build(credentials)
        self.groups = build(groups, list, str) or []
        self.roles = build(roles, list, str) or []
        self.capabilities = build(capabilities, list, str) or []
        self.user_id = None if user_id is None else user_id.encode('utf-8')
        if kwargs:
            _log.debug(
                'auth record has unrecognized keys: %r' % (kwargs.keys(),))

    def match(self, domain, address, mechanism, credentials):
        creds = ':'.join([mechanism] + credentials)
        return ((self.domain is None or self.domain.match(domain)) and
                (self.address is None or self.address.match(address)) and
                (self.credentials and self.credentials.match(creds)))

    def __str__(self):
        return (u'domain={0.domain!r}, address={0.address!r}, '
                'credentials={0.credentials!r}, user_id={0.user_id!r}'.format(
                    self))

    def __repr__(self):
        cls = self.__class__
        return '%s.%s(%s)' % (cls.__module__, cls.__name__, self)
