# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
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

# }}}

from __future__ import absolute_import, print_function

import argparse
import collections
import json
import logging
import logging.handlers
import os
import re
import shutil
import sys
import tempfile
import traceback
import StringIO
import uuid
import base64
import hashlib

import gevent
import gevent.event
from volttron.platform.vip.agent.subsystems.query import Query
from volttron.platform import get_home, get_address

from .agent import utils
from .agent.known_identities import CONTROL_CONNECTION, CONFIGURATION_STORE
from .vip.agent import Agent as BaseAgent, Core, RPC
from . import aip as aipmod
from . import config
from .jsonrpc import RemoteError
from .auth import AuthEntry, AuthFile, AuthException
from .keystore import KeyStore, KnownHostsStore

try:
    import volttron.restricted
except ImportError:
    HAVE_RESTRICTED = False
else:
    from volttron.restricted import cgroups

    HAVE_RESTRICTED = True

_stdout = sys.stdout
_stderr = sys.stderr

_log = logging.getLogger(os.path.basename(sys.argv[0])
                         if __name__ == '__main__' else __name__)

CHUNK_SIZE = 4096


class ControlService(BaseAgent):
    def __init__(self, aip, *args, **kwargs):
        tracker = kwargs.pop('tracker', None)
        kwargs["enable_store"] = False
        super(ControlService, self).__init__(*args, **kwargs)
        self._aip = aip
        self._tracker = tracker

    @Core.receiver('onsetup')
    def _setup(self, sender, **kwargs):
        if not self._tracker:
            return
        self.vip.rpc.export(lambda: self._tracker.enabled, 'stats.enabled')
        self.vip.rpc.export(self._tracker.enable, 'stats.enable')
        self.vip.rpc.export(self._tracker.disable, 'stats.disable')
        self.vip.rpc.export(lambda: self._tracker.stats, 'stats.get')

    @RPC.export
    def serverkey(self):
        q = Query(self.core)
        pk = q.query('serverkey').get(timeout=1)
        del q
        return pk

    @RPC.export
    def clear_status(self, clear_all=False):
        self._aip.clear_status(clear_all)

    @RPC.export
    def agent_status(self, uuid):
        if not isinstance(uuid, basestring):
            identity = bytes(self.vip.rpc.context.vip_message.peer)
            raise TypeError("expected a string for 'uuid';"
                            "got {!r} from identity: {}".format(
                type(uuid).__name__, identity))
        return self._aip.agent_status(uuid)

    @RPC.export
    def agent_name(self, uuid):
        if not isinstance(uuid, basestring):
            identity = bytes(self.vip.rpc.context.vip_message.peer)
            raise TypeError("expected a string for 'uuid';"
                            "got {!r} from identity: {}".format(
                type(uuid).__name__, identity))
        return self._aip.agent_name(uuid)

    @RPC.export
    def status_agents(self):
        return self._aip.status_agents()

    @RPC.export
    def start_agent(self, uuid):
        if not isinstance(uuid, basestring):
            identity = bytes(self.vip.rpc.context.vip_message.peer)
            raise TypeError("expected a string for 'uuid';"
                            "got {!r} from identity: {}".format(
                type(uuid).__name__, identity))
        self._aip.start_agent(uuid)

    @RPC.export
    def stop_agent(self, uuid):
        if not isinstance(uuid, basestring):
            identity = bytes(self.vip.rpc.context.vip_message.peer)
            raise TypeError("expected a string for 'uuid';"
                            "got {!r} from identity: {}".format(
                type(uuid).__name__, identity))
        self._aip.stop_agent(uuid)

    @RPC.export
    def restart_agent(self, uuid):
        self.stop_agent(uuid)
        self.start_agent(uuid)

    @RPC.export
    def shutdown(self):
        self._aip.shutdown()

    @RPC.export
    def stop_platform(self):
        # XXX: Restrict call as it kills the process
        self.core.socket.send_vip(b'', b'quit')

    @RPC.export
    def list_agents(self):
        tag = self._aip.agent_tag
        priority = self._aip.agent_priority
        return [{'name': name, 'uuid': uuid,
                 'tag': tag(uuid), 'priority': priority(uuid)}
                for uuid, name in self._aip.list_agents().iteritems()]

    @RPC.export
    def tag_agent(self, uuid, tag):
        if not isinstance(uuid, basestring):
            identity = bytes(self.vip.rpc.context.vip_message.peer)
            raise TypeError("expected a string for 'uuid';"
                            "got {!r} from identity: {}".format(
                type(uuid).__name__, identity))
        if not isinstance(tag, (type(None), basestring)):
            identity = bytes(self.vip.rpc.context.vip_message.peer)
            raise TypeError("expected a string for 'tag';"
                            "got {!r} from identity: {}".format(
                type(uuid).__name__, identity))
        return self._aip.tag_agent(uuid, tag)

    @RPC.export
    def remove_agent(self, uuid, remove_auth=True):
        if not isinstance(uuid, basestring):
            identity = bytes(self.vip.rpc.context.vip_message.peer)
            raise TypeError("expected a string for 'uuid';"
                            "got {!r} from identity: {}".format(
                type(uuid).__name__, identity))
        self._aip.remove_agent(uuid, remove_auth=remove_auth)

    @RPC.export
    def prioritize_agent(self, uuid, priority='50'):
        if not isinstance(uuid, basestring):
            identity = bytes(self.vip.rpc.context.vip_message.peer)
            raise TypeError("expected a string for 'uuid';"
                            "got {!r} from identity: {}".format(
                type(uuid).__name__, identity))
        if not isinstance(priority, (type(None), basestring)):
            identity = bytes(self.vip.rpc.context.vip_message.peer)
            raise TypeError("expected a string or null for 'priority';"
                            "got {!r} from identity: {}".format(
                type(uuid).__name__, identity))
        self._aip.prioritize_agent(uuid, priority)

    @RPC.export
    def agent_vip_identity(self, uuid):
        """ Lookup the agent's vip identity based upon it's uuid.

        @param uuid:
        @return:
        """
        if not isinstance(uuid, basestring):
            identity = bytes(self.vip.rpc.context.vip_message.peer)
            raise TypeError("expected a string for 'uuid';"
                            "got {!r} from identity: {}".format(
                type(uuid).__name__, identity))
        return self._aip.agent_identity(uuid)

    @RPC.export
    def install_agent_local(self, filename, vip_identity=None, publickey=None,
                            secretkey=None, add_auth=True):
        return self._aip.install_agent(filename, vip_identity=vip_identity,
                                       publickey=publickey,
                                       secretkey=secretkey,
                                       add_auth=add_auth)

    @RPC.export
    def install_agent(self, filename, channel_name, vip_identity=None,
                      publickey=None, secretkey=None, add_auth=True):
        """
        Installs an agent on the instance instance.

        The installation of an agent through this method involves sending
        the binary data of the agent file through a channel.  The following
        example is the protocol for sending the agent across the wire:

        Example Protocol:

        .. code-block:: python

            # client creates channel to this agent (control)
            channel = agent.vip.channel('control', 'channel_name')

            # Begin sending data
            sha512 = hashlib.sha512()
            while True:
                request, file_offset, chunk_size = channel.recv_multipart()

                # Control has all of the file. Send hash for for it to verify.
                if request == b'checksum':
                    channel.send(hash)
                assert request == b'fetch'

                # send a chunk of the file
                file_offset = int(file_offset)
                chunk_size = int(chunk_size)
                file.seek(file_offset)
                data = file.read(chunk_size)
                sha512.update(data)
                channel.send(data)

            agent_uuid = agent_uuid.get(timeout=10)
            # close and delete the channel
            channel.close(linger=0)
            del channel

        :param:string:filename:
            The name of the agent packaged file that is being written.
        :param:string:channel_name:
            The name of the channel that the agent file will be sent on.
        :param:string:publickey:
            Encoded public key the installed agent will use
        :param:string:secretkey:
            Encoded secret key the installed agent will use
        :param:bool:add_auth:
            Add the agent's credentials to the authorized-agent list
        """

        peer = bytes(self.vip.rpc.context.vip_message.peer)
        channel = self.vip.channel(peer, channel_name)
        try:
            tmpdir = tempfile.mkdtemp()
            path = os.path.join(tmpdir, os.path.basename(filename))
            store = open(path, 'wb')
            file_offset = 0
            sha512 = hashlib.sha512()

            try:
                while True:
                    # request a chunk of the file
                    channel.send_multipart([
                        b'fetch',
                        bytes(file_offset),
                        bytes(CHUNK_SIZE)
                    ])

                    # get the requested data
                    with gevent.Timeout(30):
                        data = channel.recv()
                    sha512.update(data)
                    store.write(data)
                    size = len(data)
                    file_offset += size

                    # let volttron-ctl know that we have everything
                    if size < CHUNK_SIZE:
                        channel.send_multipart([b'checksum', b'', b''])
                        with gevent.Timeout(30):
                            checksum = channel.recv()
                        assert checksum == sha512.digest()
                        break

            except AssertionError:
                _log.warning("Checksum mismatch on received file")
                raise
            except gevent.Timeout:
                _log.warning("Gevent timeout trying to receive data")
                raise
            finally:
                store.close()
                _log.debug('Closing channel on server')
                channel.close(linger=0)
                del channel

            agent_uuid = self._aip.install_agent(path,
                                                 vip_identity=vip_identity,
                                                 publickey=publickey,
                                                 secretkey=secretkey,
                                                 add_auth=add_auth)
            return agent_uuid
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


def log_to_file(file, level=logging.WARNING,
                handler_class=logging.StreamHandler):
    '''Direct log output to a file (or something like one).'''
    handler = handler_class(file)
    handler.setLevel(level)
    handler.setFormatter(utils.AgentFormatter(
        '%(asctime)s %(composite_name)s %(levelname)s: %(message)s'))
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)


Agent = collections.namedtuple('Agent', 'name tag uuid vip_identity')


def _list_agents(aip):
    return [Agent(name, aip.agent_tag(uuid), uuid, aip.agent_identity(uuid))
            for uuid, name in aip.list_agents().iteritems()]


def escape(pattern):
    strings = re.split(r'([*?])', pattern)
    if len(strings) == 1:
        return re.escape(pattern), False
    return ''.join('.*' if s == '*' else '.' if s == '?' else
        s if s in [r'\?', r'\*'] else re.escape(s)
                   for s in strings), True


def filter_agents(agents, patterns, opts):
    by_name, by_tag, by_uuid = opts.by_name, opts.by_tag, opts.by_uuid
    for pattern in patterns:
        regex, _ = escape(pattern)
        result = set()
        if not (by_uuid or by_name or by_tag):
            reobj = re.compile(regex)
            matches = [agent for agent in agents if reobj.match(agent.uuid)]
            if len(matches) == 1:
                result.update(matches)
        else:
            reobj = re.compile(regex + '$')
            if by_uuid:
                result.update(
                    agent for agent in agents if reobj.match(agent.uuid))
            if by_name:
                result.update(
                    agent for agent in agents if reobj.match(agent.name))
            if by_tag:
                result.update(
                    agent for agent in agents if reobj.match(agent.tag or ''))
        yield pattern, result


def filter_agent(agents, pattern, opts):
    return next(filter_agents(agents, [pattern], opts))[1]


def upgrade_agent(opts):
    publickey = None
    secretkey = None
    add_auth = False

    identity = opts.vip_identity
    if not identity:
        raise ValueError("Missing required VIP IDENTITY option")

    identity_to_uuid = opts.aip.get_agent_identity_to_uuid_mapping()
    agent_uuid = identity_to_uuid.get(identity, None)
    if agent_uuid:
        keystore = opts.aip.get_agent_keystore(agent_uuid)
        publickey = keystore.public
        secretkey = keystore.secret
        _stdout.write('Removing previous version of agent "{}"\n'
                .format(identity))
        opts.connection.call('remove_agent', agent_uuid, remove_auth=False)
    else:
        _stdout.write(('Could not find agent with VIP IDENTITY "{}". '
                       'Installing as new agent\n').format(identity))

    if secretkey is None or publickey is None:
        publickey = None
        secretkey = None
        add_auth = True

    install_agent(opts, publickey=publickey, secretkey=secretkey,
                  add_auth=add_auth)


def install_agent(opts, publickey=None, secretkey=None, add_auth=True):
    aip = opts.aip
    filename = opts.wheel
    tag = opts.tag
    vip_identity = opts.vip_identity

    if opts.vip_address.startswith('ipc://'):
        _log.info("Installing wheel locally without channel subsystem")
        filename = config.expandall(filename)
        agent_uuid = opts.connection.call('install_agent_local',
                                          filename,
                                          vip_identity=vip_identity,
                                          publickey=publickey,
                                          secretkey=secretkey,
                                          add_auth=add_auth)

        if tag:
            opts.connection.call('tag_agent', agent_uuid, tag)

    else:
        try:
            _log.debug('Creating channel for sending the agent.')
            channel_name = str(uuid.uuid4())
            channel = opts.connection.server.vip.channel('control',
                                                          channel_name)
            _log.debug('calling control install agent.')
            agent_uuid = opts.connection.call_no_get('install_agent',
                                                     filename,
                                                     channel_name,
                                                     vip_identity=vip_identity,
                                                     publickey=publickey,
                                                     secretkey=secretkey,
                                                     add_auth=add_auth)

            _log.debug('Sending wheel to control')
            sha512 = hashlib.sha512()
            with open(filename, 'rb') as wheel_file_data:
                while True:
                    # get a request
                    with gevent.Timeout(30):
                        request, file_offset, chunk_size = channel.recv_multipart()
                    if request == b'checksum':
                        channel.send(sha512.digest())
                        break

                    assert request == b'fetch'

                    # send a chunk of the file
                    file_offset = int(file_offset)
                    chunk_size = int(chunk_size)
                    wheel_file_data.seek(file_offset)
                    data = wheel_file_data.read(chunk_size)
                    sha512.update(data)
                    channel.send(data)

            agent_uuid = agent_uuid.get(timeout=10)

        except Exception as exc:
            if opts.debug:
                traceback.print_exc()
            _stderr.write(
                '{}: error: {}: {}\n'.format(opts.command, exc, filename))
            return 10
        else:
            if tag:
                opts.connection.call('tag_agent',
                                     agent_uuid,
                                     tag)
        finally:
            _log.debug('closing channel')
            channel.close(linger=0)
            del channel

    name = opts.connection.call('agent_name', agent_uuid)
    _stdout.write('Installed {} as {} {}\n'.format(filename, agent_uuid, name))


def tag_agent(opts):
    agents = filter_agent(_list_agents(opts.aip), opts.agent, opts)
    if len(agents) != 1:
        if agents:
            msg = 'multiple agents selected'
        else:
            msg = 'agent not found'
        _stderr.write(
            '{}: error: {}: {}\n'.format(opts.command, msg, opts.agent))
        return 10
    agent, = agents
    if opts.tag:
        _stdout.write('Tagging {} {}\n'.format(agent.uuid, agent.name))
        opts.aip.tag_agent(agent.uuid, opts.tag)
    elif opts.remove:
        if agent.tag is not None:
            _stdout.write(
                'Removing tag for {} {}\n'.format(agent.uuid, agent.name))
            opts.aip.tag_agent(agent.uuid, None)
    else:
        if agent.tag is not None:
            _stdout.writelines([agent.tag, '\n'])


def remove_agent(opts, remove_auth=True):
    agents = _list_agents(opts.aip)
    for pattern, match in filter_agents(agents, opts.pattern, opts):
        if not match:
            _stderr.write(
                '{}: error: agent not found: {}\n'.format(opts.command,
                                                          pattern))
        elif len(match) > 1 and not opts.force:
            _stderr.write(
                '{}: error: pattern returned multiple agents: {}\n'.format(
                    opts.command, pattern))
            _stderr.write(
                'Use -f or --force to force removal of multiple agents.\n')
            return 10
        for agent in match:
            _stdout.write('Removing {} {}\n'.format(agent.uuid, agent.name))
            opts.connection.call('remove_agent', agent.uuid,
                                 remove_auth=remove_auth)


def _calc_min_uuid_length(agents):
    n = 0
    for agent1 in agents:
        for agent2 in agents:
            if agent1 is agent2:
                continue
            common_len = len(os.path.commonprefix([agent1.uuid, agent2.uuid]))
            if common_len > n:
                n = common_len
    return n + 1


def list_agents(opts):
    agents = _list_agents(opts.aip)
    if opts.pattern:
        filtered = set()
        for pattern, match in filter_agents(agents, opts.pattern, opts):
            if not match:
                _stderr.write(
                    '{}: error: agent not found: {}\n'.format(opts.command,
                                                              pattern))
            filtered |= match
        agents = list(filtered)
    if not agents:
        return
    if not opts.min_uuid_len:
        n = None
    else:
        n = max(_calc_min_uuid_length(agents), opts.min_uuid_len)
    agents.sort()
    name_width = max(5, max(len(agent.name) for agent in agents))
    tag_width = max(3, max(len(agent.tag or '') for agent in agents))
    identity_width = max(3, max(len(agent.vip_identity or '') for agent in agents))
    fmt = '{} {:{}} {:{}} {:{}} {:>3}\n'
    _stderr.write(
        fmt.format(' ' * n, 'AGENT', name_width, 'IDENTITY', identity_width, 'TAG', tag_width, 'PRI'))
    for agent in agents:
        priority = opts.aip.agent_priority(agent.uuid) or ''
        _stdout.write(fmt.format(agent.uuid[:n], agent.name, name_width,
                                 agent.vip_identity, identity_width,
                                 agent.tag or '', tag_width, priority))


def status_agents(opts):
    agents = {agent.uuid: agent for agent in _list_agents(opts.aip)}
    status = {}
    for uuid, name, stat in opts.connection.call('status_agents'):
        try:
            agent = agents[uuid]
        except KeyError:
            agents[uuid] = agent = Agent(name, None, uuid)
        status[uuid] = stat
    agents = agents.values()
    if opts.pattern:
        filtered = set()
        for pattern, match in filter_agents(agents, opts.pattern, opts):
            if not match:
                _stderr.write(
                    '{}: error: agent not found: {}\n'.format(opts.command,
                                                              pattern))
            filtered |= match
        agents = list(filtered)
    if not agents:
        return
    agents.sort()
    if not opts.min_uuid_len:
        n = 36
    else:
        n = max(_calc_min_uuid_length(agents), opts.min_uuid_len)
    name_width = max(5, max(len(agent.name) for agent in agents))
    tag_width = max(3, max(len(agent.tag or '') for agent in agents))
    identity_width = max(3, max(len(agent.vip_identity or '') for agent in agents))
    fmt = '{} {:{}} {:{}} {:{}} {:>6}\n'
    _stderr.write(
        fmt.format(' ' * n, 'AGENT', name_width, 'IDENTITY', identity_width, 'TAG', tag_width, 'STATUS'))
    for agent in agents:
        try:
            pid, stat = status[agent.uuid]
        except KeyError:
            pid = stat = None
        _stdout.write(fmt.format(agent.uuid[:n], agent.name, name_width,
                                 agent.vip_identity, identity_width,
                                 agent.tag or '', tag_width,
                                 ('running [{}]'.format(pid)
                                  if stat is None else str(
                                     stat)) if pid else ''))


def clear_status(opts):
    opts.connection.call('clear_status', opts.clear_all)


def enable_agent(opts):
    agents = _list_agents(opts.aip)
    for pattern, match in filter_agents(agents, opts.pattern, opts):
        if not match:
            _stderr.write(
                '{}: error: agent not found: {}\n'.format(opts.command,
                                                          pattern))
        for agent in match:
            _stdout.write('Enabling {} {} with priority {}\n'.format(
                agent.uuid, agent.name, opts.priority))
            opts.aip.prioritize_agent(agent.uuid, opts.priority)


def disable_agent(opts):
    agents = _list_agents(opts.aip)
    for pattern, match in filter_agents(agents, opts.pattern, opts):
        if not match:
            _stderr.write(
                '{}: error: agent not found: {}\n'.format(opts.command,
                                                          pattern))
        for agent in match:
            priority = opts.aip.agent_priority(agent.uuid)
            if priority is not None:
                _stdout.write(
                    'Disabling {} {}\n'.format(agent.uuid, agent.name))
                opts.aip.prioritize_agent(agent.uuid, None)


def start_agent(opts):
    call = opts.connection.call
    agents = _list_agents(opts.aip)
    for pattern, match in filter_agents(agents, opts.pattern, opts):
        if not match:
            _stderr.write(
                '{}: error: agent not found: {}\n'.format(opts.command,
                                                          pattern))
        for agent in match:
            pid, status = call('agent_status', agent.uuid)
            if pid is None or status is not None:
                _stdout.write(
                    'Starting {} {}\n'.format(agent.uuid, agent.name))
                call('start_agent', agent.uuid)


def stop_agent(opts):
    call = opts.connection.call
    agents = _list_agents(opts.aip)
    for pattern, match in filter_agents(agents, opts.pattern, opts):
        if not match:
            _stderr.write(
                '{}: error: agent not found: {}\n'.format(opts.command,
                                                          pattern))
        for agent in match:
            pid, status = call('agent_status', agent.uuid)
            if pid and status is None:
                _stdout.write(
                    'Stopping {} {}\n'.format(agent.uuid, agent.name))
                call('stop_agent', agent.uuid)


def restart_agent(opts):
    stop_agent(opts)
    start_agent(opts)


def run_agent(opts):
    call = opts.connection.call
    for directory in opts.directory:
        call('run_agent', directory)


def shutdown_agents(opts):
    opts.connection.call('shutdown')
    if opts.platform:
        opts.connection.notify('stop_platform')


def create_cgroups(opts):
    try:
        cgroups.setup(user=opts.user, group=opts.group)
    except ValueError as exc:
        _stderr.write('{}: error: {}\n'.format(opts.command, exc))
        return os.EX_NOUSER


def _send_agent(connection, peer, path):
    wheel = open(path, 'rb')
    channel = connection.vip.channel(peer)

    def send():
        try:
            # Wait for peer to open compliment channel
            channel.recv()
            while True:
                data = wheel.read(8192)
                channel.send(data)
                if not data:
                    break
            # Wait for peer to signal all data received
            channel.recv()
        finally:
            wheel.close()
            channel.close(linger=0)

    result = connection.vip.rpc.call(
        peer, 'install_agent', os.path.basename(path), channel.name)
    task = gevent.spawn(send)
    result.rawlink(lambda glt: task.kill(block=False))
    return result


def send_agent(opts):
    connection = opts.connection
    for wheel in opts.wheel:
        uuid = _send_agent(connection.server, connection.peer, wheel).get()
        connection.call('start_agent', uuid)
        _stdout.write('Agent {} started as {}\n'.format(wheel, uuid))


def gen_keypair(opts):
    if os.path.isfile(opts.keystore_file):
        _stdout.write('{} already exists.\n'.format(opts.keystore_file))
        if not _ask_yes_no('Overwrite?', default='no'):
            return
    keystore = KeyStore(opts.keystore_file)
    keystore.generate()  # call generate to force new keys to be generated
    _stdout.write('public key: {}\n'.format(keystore.public))
    _stdout.write('keys written to {}\n'.format(opts.keystore_file))


def add_server_key(opts):
    store = KnownHostsStore()
    store.add(opts.host, opts.serverkey)
    _stdout.write('server key written to {}\n'.format(store.filename))


def do_stats(opts):
    call = opts.connection.call
    if opts.op == 'status':
        _stdout.write(
            '%sabled\n' % ('en' if call('stats.enabled') else 'dis'))
    elif opts.op in ['dump', 'pprint']:
        stats = call('stats.get')
        if opts.op == 'pprint':
            import pprint
            pprint.pprint(stats, _stdout)
        else:
            _stdout.writelines([str(stats), '\n'])
    else:
        call('stats.' + opts.op)
        _stdout.write(
            '%sabled\n' % ('en' if call('stats.enabled') else 'dis'))


def show_serverkey(opts):
    """ 
    write serverkey to standard out.

    return 0 if success, 1 if false
    """
    q = Query(opts.connection.server.core)
    pk = q.query('serverkey').get(timeout=2)
    del q
    if pk is not None:
        _stdout.write('%s\n' % pk)
	return 0

    return 1


def _get_auth_file(volttron_home):
    path = os.path.join(volttron_home, 'auth.json')
    return AuthFile(path)


def list_auth(opts, indices=None):
    auth_file = _get_auth_file(opts.volttron_home)
    entries = auth_file.read_allow_entries()
    print_out = []
    if entries:
        for index, entry in enumerate(entries):
            if indices is None or index in indices:
                _stdout.write('\nINDEX: {}\n'.format(index))
                _stdout.write(
                    '{}\n'.format(json.dumps(vars(entry), indent=2)))
    else:
        _stdout.write('No entries in {}\n'.format(auth_file.auth_file))


def _ask_for_auth_fields(domain=None, address=None, user_id=None,
                         capabilities=None, roles=None, groups=None,
                         mechanism='CURVE', credentials=None, comments=None,
                         enabled=True, **kwargs):
    class Asker(object):
        def __init__(self):
            self._fields = collections.OrderedDict()

        def add(self, name, default=None, note=None, callback=lambda x: x,
                validate=lambda x,y: (True, '')):
            self._fields[name] = {'note': note, 'default': default,
                                  'callback': callback, 'validate': validate}

        def ask(self):
            for name in self._fields:
                note = self._fields[name]['note']
                default = self._fields[name]['default']
                callback = self._fields[name]['callback']
                validate = self._fields[name]['validate']
                if isinstance(default, list):
                    default_str = '{}'.format(','.join(default))
                elif default is None:
                    default_str = ''
                else:
                    default_str = default
                note = '({}) '.format(note) if note else ''
                question = '{} {}[{}]: '.format(name, note, default_str)
                valid = False
                while not valid:
                    response = raw_input(question).strip()
                    if response == '':
                        response = default
                    if response == 'clear':
                        if _ask_yes_no('Do you want to clear this field?'):
                            response = None
                    valid, msg = validate(response, self._fields)
                    if not valid:
                        _stderr.write('{}\n'.format(msg))

                self._fields[name]['response'] = callback(response)
            return {k: self._fields[k]['response'] for k in self._fields}

    def comma_split(response):
        if not isinstance(response, basestring):
            return response
        response = response.strip()
        if not response:
            return []
        return [word.strip() for word in response.split(',')]

    def to_true_or_false(response):
        if isinstance(response, basestring):
            return {'true': True, 'false': False}[response.lower()]
        return response

    def is_true_or_false(x, fields):
        if x is not None:
            if isinstance(x, bool) or x.lower() in ['true', 'false']:
                return True, None
        return False, 'Please enter True or False'

    def valid_creds(creds, fields):
        try:
            mechanism = fields['mechanism']['response']
            AuthEntry.valid_credentials(creds, mechanism=mechanism)
        except AuthException as e:
            return False, e.message
        return True, None

    def valid_mech(mech, fields):
        try:
            AuthEntry.valid_mechanism(mech)
        except AuthException as e:
            return False, e.message
        return True, None

    asker = Asker()
    asker.add('domain', domain)
    asker.add('address', address)
    asker.add('user_id', user_id)
    asker.add('capabilities', capabilities,
              'delimit multiple entries with comma', comma_split)
    asker.add('roles', roles, 'delimit multiple entries with comma',
              comma_split)
    asker.add('groups', groups, 'delimit multiple entries with comma',
              comma_split)
    asker.add('mechanism', mechanism, validate=valid_mech)
    asker.add('credentials', credentials, validate=valid_creds)
    asker.add('comments', comments)
    asker.add('enabled', enabled, callback=to_true_or_false,
              validate=is_true_or_false)

    return asker.ask()


def add_auth(opts):
    responses = _ask_for_auth_fields()
    entry = AuthEntry(**responses)
    auth_file = _get_auth_file(opts.volttron_home)
    try:
        auth_file.add(entry, overwrite=False)
        _stdout.write('added entry {}\n'.format(entry))
    except AuthException as err:
        _stderr.write('ERROR: %s\n' % err.message)


def _ask_yes_no(question, default='yes'):
    yes = set(['yes', 'ye', 'y'])
    no = set(['no', 'n'])
    y = 'y'
    n = 'n'
    if default in yes:
        y = 'Y'
    elif default in no:
        n = 'N'
    else:
        raise ValueError("invalid default answer: '%s'" % default)
    while True:
        choice = raw_input('{} [{}/{}] '.format(question, y, n)).lower()
        if choice == '':
            choice = default
        if choice in yes:
            return True
        if choice in no:
            return False
        _stderr.write("Please respond with 'yes' or 'no'\n")


def remove_auth(opts):
    auth_file = _get_auth_file(opts.volttron_home)
    entry_count = len(auth_file.read_allow_entries())

    for i in opts.indices:
        if i < 0 or i >= entry_count:
            _stderr.write('ERROR: invalid index {}\n'.format(i))
            return

    _stdout.write('This action will delete the following:\n')
    list_auth(opts, opts.indices)
    if not _ask_yes_no('Do you wish to delete?'):
        return
    try:
        auth_file.remove_by_indices(opts.indices)
        if len(opts.indices) > 1:
            msg = 'removed entries at indices {}'.format(opts.indices)
        else:
            msg = msg = 'removed entry at index {}'.format(opts.indices)
        _stdout.write(msg + '\n')
    except AuthException as err:
        _stderr.write('ERROR: %s\n' % err.message)


def update_auth(opts):
    auth_file = _get_auth_file(opts.volttron_home)
    entries = auth_file.read_allow_entries()
    try:
        if opts.index < 0:
            raise IndexError
        entry = entries[opts.index]
        _stdout.write('(For any field type "clear" to clear the value.)\n')
        response = _ask_for_auth_fields(**entry.__dict__)
        updated_entry = AuthEntry(**response)
        auth_file.update_by_index(updated_entry, opts.index)
        _stdout.write('updated entry at index {}\n'.format(opts.index))
    except IndexError:
        _stderr.write('ERROR: invalid index %s\n' % opts.index)
    except AuthException as err:
        _stderr.write('ERROR: %s\n' % err.message)


def _show_filtered_agents(opts, field_name, field_callback, agents=None):
    """Provides generic way to filter and display agent information.

    The agents will be filtered by the provided opts.pattern and the
    following fields will be displayed:
      * UUID (or part of the UUID)
      * agent name
      * VIP identiy
      * tag
      * field_name

    @param:Namespace:opts:
        Options from argparse
    @param:string:field_name:
        Name of field to display about agents
    @param:function:field_callback:
        Function that takes an Agent as an argument and returns data
        to display
    @param:list:agents:
        List of agents to filter and display
    """
    if not agents:
        agents = _list_agents(opts.aip)
    if opts.pattern:
        filtered = set()
        for pattern, match in filter_agents(agents, opts.pattern, opts):
            if not match:
                _stderr.write(
                    '{}: error: agent not found: {}\n'.format(opts.command,
                                                              pattern))
            filtered |= match
        agents = list(filtered)
    if not agents:
        return
    agents.sort()
    if not opts.min_uuid_len:
        n = 36
    else:
        n = max(_calc_min_uuid_length(agents), opts.min_uuid_len)
    name_width = max(5, max(len(agent.name) for agent in agents))
    tag_width = max(3, max(len(agent.tag or '') for agent in agents))
    identity_width = max(3, max(len(agent.vip_identity or '') for agent in agents))
    fmt = '{} {:{}} {:{}} {:{}} {:>6}\n'
    _stderr.write(
        fmt.format(' ' * n, 'AGENT', name_width, 'IDENTITY', identity_width,
            'TAG', tag_width, field_name))
    for agent in agents:
        _stdout.write(fmt.format(agent.uuid[:n], agent.name, name_width,
                                 agent.vip_identity, identity_width,
                                 agent.tag or '', tag_width,
                                 field_callback(agent)))


def get_agent_publickey(opts):

    def get_key(agent):
        return opts.aip.get_agent_keystore(agent.uuid).public

    _show_filtered_agents(opts, 'PUBLICKEY', get_key)


# XXX: reimplement over VIP
# def send_agent(opts):
#    _log.debug("send_agent: "+ str(opts))
#    ssh_dir = os.path.join(opts.volttron_home, 'ssh')
#    _log.debug('ssh_dir: ' + ssh_dir)
#    try:
#        host_key, client = comms.client(ssh_dir, opts.host, opts.port)
#    except (OSError, IOError, PasswordRequiredException, SSHException) as exc:
#        if opts.debug:
#            traceback.print_exc()
#        _stderr.write('{}: error: {}\n'.format(opts.command, exc))
#        if isinstance(exc, OSError):
#            return os.EX_OSERR
#        if isinstance(exc, IOError):
#            return os.EX_IOERR
#        return os.EX_SOFTWARE
#    if host_key is None:
#        _stderr.write('warning: no public key found for remote host\n')
#    with client:
#        for wheel in opts.wheel:
#            with open(wheel) as file:
#                client.send_and_start_agent(file)

def add_config_to_store(opts):
    opts.connection.peer = CONFIGURATION_STORE
    call = opts.connection.call

    file_contents = opts.infile.read()

    call("manage_store", opts.identity, opts.name, file_contents, config_type=opts.config_type)

def delete_config_from_store(opts):
    opts.connection.peer = CONFIGURATION_STORE
    call = opts.connection.call
    if opts.delete_store:
        call("manage_delete_store", opts.identity)
        return

    if opts.name is None:
        _stderr.write('ERROR: must specify a configuration when not deleting entire store\n')
        return

    call("manage_delete_config", opts.identity, opts.name)


def list_store(opts):
    opts.connection.peer = CONFIGURATION_STORE
    call = opts.connection.call
    results = []
    if opts.identity is None:
        results = call("manage_list_stores")
    else:
        results = call("manage_list_configs", opts.identity)

    for item in results:
        _stdout.write(item+"\n")

def get_config(opts):
    opts.connection.peer = CONFIGURATION_STORE
    call = opts.connection.call
    results = call("manage_get", opts.identity, opts.name, raw=opts.raw)

    if opts.raw:
        _stdout.write(results)
    else:
        if isinstance(results, str):
            _stdout.write(results)
        else:
            _stdout.write(json.dumps(results, indent=2))
            _stdout.write("\n'")


class ControlConnection(object):
    def __init__(self, address, peer='control', developer_mode=False,
                 publickey=None, secretkey=None, serverkey=None):
        self.address = address
        self.peer = peer
        self._server = BaseAgent(address=self.address, publickey=publickey,
                                 secretkey=secretkey, serverkey=serverkey,
                                 enable_store=False,
                                 identity=CONTROL_CONNECTION,
                                 developer_mode=developer_mode,
                                 enable_channel=True)
        self._greenlet = None

    @property
    def server(self):
        if self._greenlet is None:
            event = gevent.event.Event()
            self._greenlet = gevent.spawn(self._server.core.run, event)
            event.wait()
        return self._server

    def call(self, method, *args, **kwargs):
        return self.server.vip.rpc.call(
            self.peer, method, *args, **kwargs).get()

    def call_no_get(self, method, *args, **kwargs):
        return self.server.vip.rpc.call(
            self.peer, method, *args, **kwargs)

    def notify(self, method, *args, **kwargs):
        return self.server.vip.rpc.notify(
            self.peer, method, *args, **kwargs)

    def kill(self, *args, **kwargs):
        if self._greenlet is not None:
            self._greenlet.kill(*args, **kwargs)


def priority(value):
    n = int(value)
    if not 0 <= n < 100:
        raise ValueError('invalid priority (0 <= n < 100): {}'.format(n))
    return '{:02}'.format(n)


def get_keys(opts):
    '''Gets keys from keystore and known-hosts store'''
    hosts = KnownHostsStore()
    serverkey = hosts.serverkey(opts.vip_address)
    key_store = KeyStore()
    publickey = key_store.public
    secretkey = key_store.secret
    return {'publickey': publickey, 'secretkey': secretkey,
            'serverkey': serverkey}


def main(argv=sys.argv):
    # Refuse to run as root
    if not getattr(os, 'getuid', lambda: -1)():
        sys.stderr.write('%s: error: refusing to run as root to prevent '
                         'potential damage.\n' % os.path.basename(argv[0]))
        sys.exit(77)

    volttron_home = get_home()
    os.environ['VOLTTRON_HOME'] = volttron_home

    global_args = config.ArgumentParser(description='global options',
                                        add_help=False)
    global_args.add_argument('-c', '--config', metavar='FILE',
                             action='parse_config', ignore_unknown=True,
                             sections=[None, 'global', 'volttron-ctl'],
                             help='read configuration from FILE')
    global_args.add_argument('--debug', action='store_true',
                             help='show tracbacks for errors rather than a brief message')
    global_args.add_argument('--developer-mode', action='store_true',
                             help='run in insecure developer mode')
    global_args.add_argument('-t', '--timeout', type=float, metavar='SECS',
                             help='timeout in seconds for remote calls (default: %(default)g)')
    global_args.add_argument(
        '--vip-address', metavar='ZMQADDR',
        help='ZeroMQ URL to bind for VIP connections')
    global_args.set_defaults(
        vip_address=get_address(),
        timeout=30,
    )

    filterable = config.ArgumentParser(add_help=False)
    filterable.add_argument('--name', dest='by_name', action='store_true',
                            help='filter/search by agent name')
    filterable.add_argument('--tag', dest='by_tag', action='store_true',
                            help='filter/search by tag name')
    filterable.add_argument('--uuid', dest='by_uuid', action='store_true',
                            help='filter/search by UUID (default)')
    filterable.set_defaults(by_name=False, by_tag=False, by_uuid=False)

    parser = config.ArgumentParser(
        prog=os.path.basename(argv[0]), add_help=False,
        description='Manage and control VOLTTRON agents.',
        usage='%(prog)s command [OPTIONS] ...',
        argument_default=argparse.SUPPRESS,
        parents=[global_args]
    )
    parser.add_argument('-l', '--log', metavar='FILE', default=None,
                        help='send log output to FILE instead of stderr')
    parser.add_argument('-L', '--log-config', metavar='FILE',
                        help='read logging configuration from FILE')
    parser.add_argument('-q', '--quiet', action='add_const', const=10,
                        dest='verboseness',
                        help='decrease logger verboseness; may be used multiple times')
    parser.add_argument('-v', '--verbose', action='add_const', const=-10,
                        dest='verboseness',
                        help='increase logger verboseness; may be used multiple times')
    parser.add_argument('--verboseness', type=int, metavar='LEVEL',
                        default=logging.WARNING,
                        help='set logger verboseness')
    parser.add_argument(
        '--show-config', action='store_true',
        help=argparse.SUPPRESS)

    parser.add_help_argument()
    parser.set_defaults(
        log_config=None,
        volttron_home=volttron_home,
    )

    top_level_subparsers = parser.add_subparsers(title='commands', metavar='',
                                       dest='command')

    def add_parser(*args, **kwargs):
        parents = kwargs.get('parents', [])
        parents.append(global_args)
        kwargs['parents'] = parents
        subparser = kwargs.pop("subparser", top_level_subparsers)
        return subparser.add_parser(*args, **kwargs)

    install = add_parser('install', help='install agent from wheel',
                         epilog='Optionally you may specify the --tag argument to tag the '
                                'agent during install without requiring a separate call to '
                                'the tag command. ')
    install.add_argument('wheel', help='path to agent wheel')
    install.add_argument('--tag', help='tag for the installed agent')
    install.add_argument('--vip-identity', help='VIP IDENTITY for the installed agent. '
                         'Overrides any previously configured VIP IDENTITY.')
    if HAVE_RESTRICTED:
        install.add_argument('--verify', action='store_true',
                             dest='verify_agents',
                             help='verify agent integrity during install')
        install.add_argument('--no-verify', action='store_false',
                             dest='verify_agents',
                             help=argparse.SUPPRESS)
    install.set_defaults(func=install_agent, verify_agents=True)

    tag = add_parser('tag', parents=[filterable],
                     help='set, show, or remove agent tag')
    tag.add_argument('agent', help='UUID or name of agent')
    group = tag.add_mutually_exclusive_group()
    group.add_argument('tag', nargs='?', const=None, help='tag to give agent')
    group.add_argument('-r', '--remove', action='store_true',
                       help='remove tag')
    tag.set_defaults(func=tag_agent, tag=None, remove=False)

    remove = add_parser('remove', parents=[filterable],
                        help='remove agent')
    remove.add_argument('pattern', nargs='+', help='UUID or name of agent')
    remove.add_argument('-f', '--force', action='store_true',
                        help='force removal of multiple agents')
    remove.set_defaults(func=remove_agent, force=False)

    list_ = add_parser('list', parents=[filterable],
                       help='list installed agent')
    list_.add_argument('pattern', nargs='*',
                       help='UUID or name of agent')
    list_.add_argument('-n', dest='min_uuid_len', type=int, metavar='N',
                       help='show at least N characters of UUID (0 to show all)')
    list_.set_defaults(func=list_agents, min_uuid_len=1)

    status = add_parser('status', parents=[filterable],
                        help='show status of agents')
    status.add_argument('pattern', nargs='*',
                        help='UUID or name of agent')
    status.add_argument('-n', dest='min_uuid_len', type=int, metavar='N',
                        help='show at least N characters of UUID (0 to show all)')
    status.set_defaults(func=status_agents, min_uuid_len=1)

    clear = add_parser('clear', help='clear status of defunct agents')
    clear.add_argument('-a', '--all', dest='clear_all', action='store_true',
                       help='clear the status of all agents')
    clear.set_defaults(func=clear_status, clear_all=False)

    enable = add_parser('enable', parents=[filterable],
                        help='enable agent to start automatically')
    enable.add_argument('pattern', nargs='+', help='UUID or name of agent')
    enable.add_argument('-p', '--priority', type=priority,
                        help='2-digit priority from 00 to 99')
    enable.set_defaults(func=enable_agent, priority='50')

    disable = add_parser('disable', parents=[filterable],
                         help='prevent agent from start automatically')
    disable.add_argument('pattern', nargs='+', help='UUID or name of agent')
    disable.set_defaults(func=disable_agent)

    start = add_parser('start', parents=[filterable],
                       help='start installed agent')
    start.add_argument('pattern', nargs='+', help='UUID or name of agent')
    if HAVE_RESTRICTED:
        start.add_argument('--verify', action='store_true',
                           dest='verify_agents',
                           help='verify agent integrity during start')
        start.add_argument('--no-verify', action='store_false',
                           dest='verify_agents',
                           help=argparse.SUPPRESS)
    start.set_defaults(func=start_agent)

    stop = add_parser('stop', parents=[filterable],
                      help='stop agent')
    stop.add_argument('pattern', nargs='+', help='UUID or name of agent')
    stop.set_defaults(func=stop_agent)

    restart = add_parser('restart', parents=[filterable],
                         help='restart agent')
    restart.add_argument('pattern', nargs='+', help='UUID or name of agent')
    restart.set_defaults(func=restart_agent)

    run = add_parser('run',
                     help='start any agent by path')
    run.add_argument('directory', nargs='+', help='path to agent directory')
    if HAVE_RESTRICTED:
        run.add_argument('--verify', action='store_true',
                         dest='verify_agents',
                         help='verify agent integrity during run')
        run.add_argument('--no-verify', action='store_false',
                         dest='verify_agents',
                         help=argparse.SUPPRESS)
    run.set_defaults(func=run_agent)

    upgrade = add_parser('upgrade', help='upgrade agent from wheel',
                         epilog='Optionally you may specify the --tag argument to tag the '
                                'agent during upgrade without requiring a separate call to '
                                'the tag command. ')
    upgrade.add_argument('vip_identity', metavar='vip-identity',
            help='VIP IDENTITY of agent to upgrade')
    upgrade.add_argument('wheel', help='path to new agent wheel')
    upgrade.add_argument('--tag', help='tag for the upgraded agent')
    if HAVE_RESTRICTED:
        upgrade.add_argument('--verify', action='store_true',
                             dest='verify_agents',
                             help='verify agent integrity during upgrade')
        upgrade.add_argument('--no-verify', action='store_false',
                             dest='verify_agents',
                             help=argparse.SUPPRESS)
    upgrade.set_defaults(func=upgrade_agent, verify_agents=True)

    auth_cmds = add_parser("auth",
            help="manage authorization entries and encryption keys")

    auth_subparsers = auth_cmds.add_subparsers(title='subcommands',
            metavar='', dest='store_commands')

    auth_add = add_parser('add', help='add new authentication record',
            subparser=auth_subparsers)
    auth_add.set_defaults(func=add_auth)

    auth_add_known_host = add_parser('add-known-host', subparser=auth_subparsers,
            help='add server public key to known-hosts file')
    auth_add_known_host.add_argument('--host', required=True,
            help='hostname or IP address with optional port')
    auth_add_known_host.add_argument('--serverkey', required=True)
    auth_add_known_host.set_defaults(func=add_server_key)

    auth_keypair = add_parser('keypair', subparser=auth_subparsers,
            help='generate CurveMQ keys for encrypting VIP connections')
    auth_keypair.add_argument('keystore_file', metavar='keystore-file',
            help='path to save keystore file', nargs='?')
    auth_keypair.set_defaults(func=gen_keypair,
            keystore_file=KeyStore.get_default_path())

    auth_list = add_parser('list', help='list authentication records',
            subparser=auth_subparsers)
    auth_list.set_defaults(func=list_auth)

    auth_publickey = add_parser('publickey', parents=[filterable],
            subparser=auth_subparsers, help='show public key for each agent')
    auth_publickey.add_argument('pattern', nargs='*',
                       help='UUID or name of agent')
    auth_publickey.add_argument('-n', dest='min_uuid_len', type=int, metavar='N',
                       help='show at least N characters of UUID (0 to show all)')
    auth_publickey.set_defaults(func=get_agent_publickey, min_uuid_len=1)

    auth_remove = add_parser('remove', subparser=auth_subparsers,
            help='removes one or more authentication records by indices')
    auth_remove.add_argument('indices', nargs='+', type=int,
            help='index or indices of record(s) to remove')
    auth_remove.set_defaults(func=remove_auth)

    auth_serverkey = add_parser('serverkey', subparser=auth_subparsers,
            help="show the serverkey for the instance")
    auth_serverkey.set_defaults(func=show_serverkey)

    auth_update = add_parser('update', subparser=auth_subparsers,
            help='updates one authentication record by index')
    auth_update.add_argument('index', type=int,
            help='index of record to update')
    auth_update.set_defaults(func=update_auth)


    config_store = add_parser("config",
                              help="manage the platform configuration store")

    config_store_subparsers = config_store.add_subparsers(title='subcommands', metavar='',
                                                          dest='store_commands')

    config_store_store = add_parser("store",
                                    help="store a configuration",
                                    subparser=config_store_subparsers)

    config_store_store.add_argument('identity',
                                    help='VIP IDENTITY of the store')
    config_store_store.add_argument('name',
                                    help='name used to reference the configuration by in the store')
    config_store_store.add_argument('infile', nargs='?', type=argparse.FileType('r'), default=sys.stdin,
                                    help='file containing the contents of the configuration')
    config_store_store.add_argument('--raw', const="raw", dest="config_type" , action="store_const",
                                    help='interpret the input file as raw data')
    config_store_store.add_argument('--json', const="json", dest="config_type", action="store_const",
                                    help='interpret the input file as json')
    config_store_store.add_argument('--csv', const="csv", dest="config_type", action="store_const",
                                    help='interpret the input file as csv')

    config_store_store.set_defaults(func=add_config_to_store,
                                    config_type="json")

    config_store_delete = add_parser("delete",
                                    help="delete a configuration",
                                    subparser=config_store_subparsers)
    config_store_delete.add_argument('identity',
                                    help='VIP IDENTITY of the store')
    config_store_delete.add_argument('name', nargs='?',
                                    help='name used to reference the configuration by in the store')
    config_store_delete.add_argument('--all', dest="delete_store", action="store_true",
                                    help='delete all configurations in the store')

    config_store_delete.set_defaults(func=delete_config_from_store)

    config_store_list = add_parser("list",
                                     help="list stores or configurations in a store",
                                     subparser=config_store_subparsers)

    config_store_list.add_argument('identity', nargs='?',
                                    help='VIP IDENTITY of the store to list')

    config_store_list.set_defaults(func=list_store)

    config_store_get = add_parser("get",
                                    help="get the contents of a configuration",
                                    subparser=config_store_subparsers)

    config_store_get.add_argument('identity',
                                    help='VIP IDENTITY of the store')
    config_store_get.add_argument('name',
                                    help='name used to reference the configuration by in the store')
    config_store_get.add_argument('--raw', action="store_true",
                                    help='get the configuration as raw data')
    config_store_get.set_defaults(func=get_config)

    shutdown = add_parser('shutdown',
                          help='stop all agents')
    shutdown.add_argument('--platform', action='store_true',
                          help='also stop the platform process')
    shutdown.set_defaults(func=shutdown_agents, platform=False)

    send = add_parser('send',
                      help='send agent and start on a remote platform')
    send.add_argument('wheel', nargs='+', help='agent package to send')
    send.set_defaults(func=send_agent)

    stats = add_parser('stats',
                       help='manage router message statistics tracking')
    op = stats.add_argument(
        'op', choices=['status', 'enable', 'disable', 'dump', 'pprint'],
        nargs='?')
    stats.set_defaults(func=do_stats, op='status')

    if HAVE_RESTRICTED:
        cgroup = add_parser('create-cgroups',
                            help='setup VOLTTRON control group for restricted execution')
        cgroup.add_argument('-u', '--user', metavar='USER',
                            help='owning user name or ID')
        cgroup.add_argument('-g', '--group', metavar='GROUP',
                            help='owning group name or ID')
        cgroup.set_defaults(func=create_cgroups, user=None, group=None)

    # Parse and expand options
    args = argv[1:]
    conf = os.path.join(volttron_home, 'config')
    if os.path.exists(conf) and 'SKIP_VOLTTRON_CONFIG' not in os.environ:
        args = ['--config', conf] + args
    opts = parser.parse_args(args)

    if opts.log:
        opts.log = config.expandall(opts.log)
    if opts.log_config:
        opts.log_config = config.expandall(opts.log_config)
    opts.vip_address = config.expandall(opts.vip_address)
    if getattr(opts, 'show_config', False):
        for name, value in sorted(vars(opts).iteritems()):
            print(name, repr(value))
        return

    # Configure logging
    level = max(1, opts.verboseness)
    if opts.log is None:
        log_to_file(sys.stderr, level)
    elif opts.log == '-':
        log_to_file(sys.stdout, level)
    elif opts.log:
        log_to_file(
            opts.log, level,
            handler_class=logging.handlers.WatchedFileHandler)
    else:
        log_to_file(None, 100, handler_class=lambda x: logging.NullHandler())
    if opts.log_config:
        logging.config.fileConfig(opts.log_config)

    opts.aip = aipmod.AIPplatform(opts)
    opts.aip.setup()
    opts.connection = ControlConnection(opts.vip_address,
                                        developer_mode=opts.developer_mode,
                                        **get_keys(opts))

    try:
        with gevent.Timeout(opts.timeout):
            return opts.func(opts)
    except gevent.Timeout:
        _stderr.write('{}: operation timed out\n'.format(opts.command))
        return 75
    except RemoteError as exc:
        print_tb = exc.print_tb
        error = exc.message
    except Exception as exc:
        print_tb = traceback.print_exc
        error = str(exc)
    else:
        return 0
    if opts.debug:
        print_tb()
    _stderr.write('{}: error: {}\n'.format(opts.command, error))
    return 20


def _main():
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)


if __name__ == '__main__':
    _main()
