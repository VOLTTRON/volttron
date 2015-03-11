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

import logging
import sys

#import monotonic

import gevent
import zmq.green as zmq
from zmq import EAGAIN, NOBLOCK, POLLIN, POLLOUT, ZMQError
from zmq.utils import jsonapi

# Override the zmq module imported by ..vip
sys.modules['_vip_zmq'] = zmq
from .. import vip


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


class AgentMeta(type):
    class Meta(object):
        def __init__(self):
            self.subsystems = {}
            self.periodics = []

    def __new__(mcs, cls, bases, attrs):
        #import pdb; pdb.set_trace()
        attrs['_meta'] = meta = AgentMeta.Meta()
        for base in reversed(bases):
            try:
                if base.__metaclass__ is not mcs:
                    continue
            except AttributeError:
                continue
            meta.subsystems.update(base._meta.subsystems)
            meta.periodics = list(
                set(meta.periodics) | set(base._meta.periodics))
        for name, attr in attrs.iteritems():
            subsystem = getattr(attr, '_vip_subsystem', None)
            if subsystem:
                meta.subsystems[subsystem] = attr
            periodics = getattr(attr, '_periodic_definitions', None)
            if periodics:
                meta.periodics = list(set(meta.periodics) | set(periodics))
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
        self.vip_socket = zmq.Context.instance().socket(zmq.DEALER)
        if vip_identity:
            self.vip_socket.identity = vip_identity
        self._periodics = []

    def run(self):
        '''Entry point for running agent.

        Subclasses should not override this method. Instead, the setup
        and finish methods should be overridden to customize behavior.
        '''
        for definition in self._meta.periodics:
            callback = definition.callback(self)
            self._periodics.append(callback)
        self.setup()
        # Start periodic callbacks
        for periodic in self._periodics:
            periodic.start()
        self.connect()
        try:
            self._loop()
        finally:
            for periodic in self._periodics:
                periodic.kill()
            self.disconnect()
            self.finish()

    def setup(self):
        '''Setup for the agent execution loop.

        Implement this method with code that must run once before the
        main loop.
        '''
        pass

    def finish(self):
        '''Finish for the agent execution loop.

        Implement this method with code that must run once after the
        main loop.
        '''
        pass

    def connect(self):
        self.vip_socket.connect(self.vip_address)

    def disconnect(self):
        self.vip_socket.disconnect(self.vip_address)

    def _loop(self):
        socket = self.vip_socket
        while True:
            try:
                message = vip.recv_message(socket)
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
                message.subsystem = vip.F_ERROR
                vip.send_message(socket, message)
            else:
                method(self, message)

    @subsystem('pong')
    def handle_pong_subsystem(self, message):
        print('Pong:', message)

    @subsystem('ping')
    def handle_ping_subsystem(self, message):
        message.subsystem = vip.F_PONG
        message.user = b''
        vip.send_message(self.vip_socket, message)

    @subsystem('error')
    def handle_error_subsystem(self, message):
        print('VIP error', message)


class RPCMixin(object):
    __metaclass__ = AgentMeta

    @subsystem('RPC')
    def handle_rpc_message(self, message):
        print(message)


class RPCAgent(VIPAgent, RPCMixin):
    pass

