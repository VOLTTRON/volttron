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

'''VOLTTRON platform™ base RPC agent and helper classes/functions.'''

from __future__ import absolute_import, print_function

import functools
import inspect
import logging
import os
import sys
import weakref

#import monotonic

import gevent
from gevent.event import AsyncResult
import zmq.green as zmq
from zmq import EAGAIN, ZMQError
from zmq.utils import jsonapi

# Import gevent-friendly version of vip
from ..vip import green as vip
from .. import jsonrpc

import volttron

_VOLTTRON_PATH = os.path.dirname(volttron.__path__[-1]) + os.sep
del volttron


_log = logging.getLogger(__name__)


class periodic(object):
    def __init__(self, period, args=None, kwargs=None, wait=False):
        '''Decorator to set a method up as a periodic callback.

        The decorated method will be called with the given arguments every
        period seconds while the agent is executing its run loop.
        '''

        self.period = period
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.wait = wait

    def __call__(self, method):
        try:
            periodics = method._periodics
        except AttributeError:
            method._periodics = periodics = []
        periodics.append(self)
        return method

    def _loop(self, method):
        if self.wait:
            gevent.sleep(self.period)
        while True:
            method(*self.args, **self.kwargs)
            gevent.sleep(self.period)

    def get(self, method):
        return gevent.Greenlet(self._loop, method)


def subsystem(name):
    '''Decorator to set a method as a subsystem callback.'''
    def decorate(method):
        try:
            subsystems = method._vip_subsystems
        except AttributeError:
            method._vip_subsystems = subsystems = []
        subsystems.append(name)
        return method
    return decorate


def onevent(event, args=None, kwargs=None):
    assert event in ['setup', 'connect', 'start', 'stop', 'disconnect', 'finish']
    def decorate(method):
        try:
            events = method._event_callbacks
        except AttributeError:
            method._event_callbacks = events = []
        events.append((event, args or (), kwargs or {}))
        return method
    return decorate


class VIPAgent(object):
    '''Base class for creating VOLTTRON platform™ agents.

    This class can be used as is, but it won't do much.  It will sit and
    do nothing but listen for messages and exit when the platform
    shutdown message is received.  That is it.
    '''

    def __init__(self, vip_address, vip_identity=None, **kwargs):
        super(VIPAgent, self).__init__(**kwargs)
        self.vip_address = vip_address
        self.vip_identity = vip_identity
        self._periodics = []
        self._event_callbacks = {}
        self._vip_subsystems = {}
        def setup(member):
            for periodic in getattr(member, '_periodics', ()):
                self._periodics.append(periodic.get(member))
            for event, args, kwargs in getattr(member, '_event_callbacks', ()):
                try:
                    evlist = self._event_callbacks[event]
                except KeyError:
                    self._event_callbacks[event] = evlist = []
                evlist.append((member, args, kwargs))
            for name in getattr(member, '_vip_subsystems', ()):
                self._vip_subsystems[name] = member
        inspect.getmembers(self, setup)

    def run(self):
        '''Entry point for running agent.

        Subclasses should not override this method. Instead, the setup
        and finish methods should be overridden to customize behavior.
        '''
        def _trigger_event(event):
            for callback, args, kwargs in self._event_callbacks.get(event, ()):
                callback(*args, **kwargs)
        self.vip_socket = vip.Socket()
        if self.vip_identity:
            self.vip_socket.identity = self.vip_identity
        _trigger_event('setup')
        self.vip_socket.connect(self.vip_address)
        _trigger_event('connect')
        # Start periodic callbacks
        for periodic in self._periodics:
            periodic.start()
        _trigger_event('start')
        try:
            self._vip_loop()
        finally:
            _trigger_event('stop')
            gevent.killall(self._periodics)
            _trigger_event('disconnect')
            try:
                self.vip_socket.disconnect(self.vip_address)
            except ZMQError:
                pass
            _trigger_event('finish')

    def _vip_loop(self):
        socket = self.vip_socket
        while True:
            try:
                message = socket.recv_vip_object()
            except ZMQError as exc:
                if exc.errno == EAGAIN:
                    continue
                raise

            try:
                method = self._vip_subsystems[message.subsystem]
            except KeyError:
                _log.error('peer %r requested unknown subsystem %r',
                           bytes(message.peer), bytes(message.subsystem))
                message.user = b''
                message.args = [b'51', b'unknown subsystem', message.subsystem]
                message.subsystem = b'error'
                socket.send_vip_object(message)
            else:
                method(message)

    @subsystem('pong')
    def handle_pong_subsystem(self, message):
        print('Pong:', message)

    @subsystem('ping')
    def handle_ping_subsystem(self, message):
        message.subsystem = b'pong'
        message.user = b''
        self.vip_socket.send_vip_object(message)

    @subsystem('error')
    def handle_error_subsystem(self, message):
        print('VIP error', message)


class Dispatcher(jsonrpc.Dispatcher):
    def __init__(self, call, traceback_limit=0):
        super(Dispatcher, self).__init__(traceback_limit=traceback_limit)
        self._call = call
        self._results = weakref.WeakValueDictionary()

    def add_result(self):
        result = AsyncResult()
        ident = id(result)
        self._results[ident] = result
        return ident, result

    def serialize(self, msg):
        return jsonapi.dumps(msg)

    def deserialize(self, json_string):
        return jsonapi.loads(json_string)

    def handle_method(self, msg, ident, method, args, kwargs):
        return self._call(method, args, kwargs)
        #raise NotImplementedError()

    def handle_result(self, msg, ident, value):
        try:
            result = self._results.pop(ident)
        except KeyError:
            return
        result.set(value)

    def handle_error(self, msg, ident, code, message, data=None):
        try:
            result = self._results.pop(ident)
        except KeyError:
            return
        result.set_exception(jsonrpc.make_exception(code, message, data))

    def handle_exception(self, msg, ident, message):
        exc_type, exc, exc_tb = sys.exc_info()
        try:
            result = self._results.pop(ident)
        except KeyError:
            return
        result.set_exception(exc)


def spawn(method):
    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        gevent.spawn(method, *args, **kwargs)
    return wrapper


def export(name=None):
    def decorate(method):
        try:
            exports = method._rpc_exports
        except AttributeError:
            method._rpc_exports = exports = []
        exports.append(name or method.__name__)
        return method
    return decorate


class RPCMixin(object):
    @onevent('setup')
    def setup_rpc_subsystem(self):
        self._rpc_exports = {}
        def setup(member):
            for name in getattr(member, '_rpc_exports', ()):
                self._rpc_exports[name] = member
        inspect.getmembers(self, setup)
        self._rpc_dispatcher = Dispatcher(self._call_rpc_method)

    @subsystem('RPC')
    @spawn
    def handle_rpc_message(self, message):
        dispatch = self._rpc_dispatcher.dispatch
        responses = filter(None, (dispatch(arg) for arg in message.args))
        if responses:
            message.user = ''
            message.args = responses
            self.vip_socket.send_vip_object(message)

    def rpc_call(self, peer, method, args=None, kwargs=None):
        rpc = self._rpc_dispatcher
        ident, result = rpc.add_result()
        args = [rpc.serialize(jsonrpc._method(ident, method, args, kwargs))]
        self.vip_socket.send_vip(peer, 'RPC', args, msg_id=str(ident))
        return result

    def rpc_notify(self, peer, method, args, kwargs):
        rpc = self._rpc_dispatcher
        args = [rpc.serialize(jsonrpc._method(None, method, args, kwargs))]
        self.vip_socket.send_vip(peer, 'RPC', args)

    def _introspect(self, method):
        #import pdb; pdb.set_trace()
        params = inspect.getargspec(method)
        if hasattr(method, 'im_self'):
            params.args.pop(0)
        response = {'params': params}
        doc = inspect.getdoc(method)
        if doc:
            response['doc'] = doc
        try:
            source = inspect.getsourcefile(method)
            cut = len(os.path.commonprefix([_VOLTTRON_PATH, source]))
            source = source[cut:]
            lineno = inspect.getsourcelines(method)[1]
        except IOError:
            pass
        else:
            response['source'] = source, lineno
        try:
            response['return'] = method._returns
        except AttributeError:
            pass
        return response

    def _call_rpc_method(self, method_name, args, kwargs):
        try:
            method = self._rpc_exports[method_name]
        except KeyError:
            if method_name == 'introspect':
                return {'methods': self._rpc_exports.keys()}
            elif method_name.endswith('.introspect'):
                base_name = method_name[:-11]
                try:
                    method = self._rpc_exports[base_name]
                except KeyError:
                    pass
                else:
                    return self._introspect(method)
            raise NotImplementedError(method_name)
        return method(*args, **kwargs)


class RPCAgent(VIPAgent, RPCMixin):
    pass

