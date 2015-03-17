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
import logging
import sys
import weakref

#import monotonic

import gevent
from gevent.event import AsyncResult
import zmq.green as zmq
from zmq import EAGAIN, ZMQError
from zmq.utils import jsonapi

# Override the zmq module imported by ..vip
sys.modules['_vip_zmq'] = zmq
from .. import vip
from .. import jsonrpc


_log = logging.getLogger(__name__)


class PeriodicCallback(gevent.Greenlet):
    def __init__(self, definition, instance):
        super(PeriodicCallback, self).__init__()
        self.definition = definition
        self.instance = instance

    def __repr__(self):
        return '{0.__class__.__name__}({0.definition!r}, {0.instance!r})'.format(self)

    def _run(self):
        calldef, instance = self.definition, self.instance
        period = calldef.period
        method, args, kwargs = calldef.method, calldef.args, calldef.kwargs
        if calldef.wait:
            gevent.sleep(period)
        while True:
            method(instance, *args, **kwargs)
            gevent.sleep(period)


class PeriodicDefinition(object):
    def __init__(self, period, method, args, kwargs, wait=False):
        self.period = period
        self.method = method
        self.args = args
        self.kwargs = kwargs
        self.wait = wait

    def __repr__(self):
        return ('{0.__class__.__name__}({0.period!r}, {0.method!r}, '
                '{0.args!r}, {0.kwargs!r}, wait={0.wait!r})'.format(self))

    def callback(self, instance):
        return PeriodicCallback(self, instance)


def periodic(period, args=None, kwargs=None, wait=False):
    '''Decorator to set a method up as a periodic callback.

    The decorated method will be called with the given arguments every
    period seconds while the agent is executing its run loop.
    '''

    if args is None:
        args = ()
    if kwargs is None:
        kwargs = {}

    def decorate(method):
        try:
            periodics = method._periodic_definitions
        except AttributeError:
            method._periodic_definitions = periodics = []
        periodics.append(
            PeriodicDefinition(period, method, args, kwargs, wait=wait))
        return method
    return decorate


def subsystem(name):
    '''Decorator to set a method as a subsystem callback.'''
    def decorate(method):
        method._vip_subsystem = name
        return method
    return decorate


def onevent(event):
    assert event in ['setup', 'connect', 'start', 'stop', 'disconnect', 'finish']
    def decorate(method):
        try:
            events = method._event_callbacks
        except AttributeError:
            method._event_callbacks = events = []
        events.append((event, method))
        return method
    return decorate


class AgentMeta(type):
    class Meta(object):
        def __init__(self):
            self.rpc_exports = {}
            self.subsystems = {}
            self.periodics = []
            self.event_callbacks = []

    def __new__(mcs, cls, bases, attrs):
        #import pdb; pdb.set_trace()
        attrs['_meta'] = meta = AgentMeta.Meta()
        for base in reversed(bases):
            try:
                if base.__metaclass__ is not mcs:
                    continue
            except AttributeError:
                continue
            meta.rpc_exports.update(base._meta.rpc_exports)
            meta.subsystems.update(base._meta.subsystems)
            meta.periodics = list(
                set(meta.periodics) | set(base._meta.periodics))
            meta.event_callbacks = list(
                set(meta.event_callbacks) | set(base._meta.event_callbacks))
        for name, attr in attrs.iteritems():
            name = getattr(attr, '_export', None)
            if name:
                meta.rpc_exports[name] = attr
            subsystem = getattr(attr, '_vip_subsystem', None)
            if subsystem:
                meta.subsystems[subsystem] = attr
            periodics = getattr(attr, '_periodic_definitions', None)
            if periodics:
                meta.periodics = list(set(meta.periodics) | set(periodics))
            events = getattr(attr, '_event_callbacks', None)
            if events:
                meta.event_callbacks = list(
                    set(meta.event_callbacks) | set(events))
        return super(AgentMeta, mcs).__new__(mcs, cls, bases, attrs)


class VIPAgent(object):
    '''Base class for creating VOLTTRON platform™ agents.

    This class can be used as is, but it won't do much.  It will sit and
    do nothing but listen for messages and exit when the platform
    shutdown message is received.  That is it.
    '''

    __metaclass__ = AgentMeta

    def __init__(self, vip_address, vip_identity=None, **kwargs):
        super(VIPAgent, self).__init__(**kwargs)
        self.vip_address = vip_address
        self.vip_socket = vip.Socket()
        if vip_identity:
            self.vip_socket.identity = vip_identity
        self._periodics = []

    def run(self):
        '''Entry point for running agent.

        Subclasses should not override this method. Instead, the setup
        and finish methods should be overridden to customize behavior.
        '''
        def _trigger_event(trigger):
            for event, callback in self._meta.event_callbacks:
                if event == trigger:
                    callback(self)
        _log.debug('generating periodic callbacks')
        for definition in self._meta.periodics:
            callback = definition.callback(self)
            self._periodics.append(callback)
        _log.debug('trigging setup events')
        _trigger_event('setup')
        _log.debug('setup events complete')
        _log.debug('connecting')
        self.vip_socket.connect(self.vip_address)
        _log.debug('triggering connect events')
        _trigger_event('connect')
        _log.debug('connect events complete')
        _log.debug('starting periodics')
        # Start periodic callbacks
        for periodic in self._periodics:
            periodic.start()
        _log.debug('triggering start events')
        _trigger_event('start')
        _log.debug('start events complete')
        _log.debug('entering main loop')
        try:
            self._vip_loop()
        finally:
            _log.debug('main loop complete')
            _log.debug('triggering stop events')
            _trigger_event('stop')
            _log.debug('stop events complete')
            _log.debug('stopping periodics')
            for periodic in self._periodics:
                periodic.kill()
            _log.debug('triggering disconnect events')
            _trigger_event('disconnect')
            _log.debug('disconnect events complete')
            _log.debug('disconnecting')
            self.vip_socket.disconnect(self.vip_address)
            _log.debug('triggering finish events')
            _trigger_event('finish')
            _log.debug('finish events complete')

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
                method = self._meta.subsystems[message.subsystem]
            except KeyError:
                _log.error('peer %r requested unknown subsystem %r',
                           bytes(message.peer), bytes(message.subsystem))
                message.user = b''
                message.args = [b'51', b'unknown subsystem', message.subsystem]
                message.subsystem = b'error'
                socket.send_vip_object(message)
            else:
                method(self, message)

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
        method._export = name or method.__name__
        return method
    return decorate


class RPCMixin(object):
    __metaclass__ = AgentMeta

    @onevent('setup')
    def setup_rpc_subsystem(self):
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

    def _call_rpc_method(self, method_name, args, kwargs):
        try:
            method = self._meta.rpc_exports[method_name]
        except KeyError:
            raise NotImplementedError(method_name)
        return method(self, *args, **kwargs)
    

class RPCAgent(VIPAgent, RPCMixin):
    pass

