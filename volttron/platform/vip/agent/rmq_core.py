# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2017, Battelle Memorial Institute
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


import logging
import os
import uuid

import gevent.event
from gevent.queue import Queue

from volttron.platform import get_address
from .dispatch import Signal
from .errors import VIPError
from .. import router
from .... import platform
from .core import BasicCore
from ..rmq_connection import RMQConnection
from ..socket import Message

__all__ = ['RMQCore']

_log = logging.getLogger(__name__)


class RMQCore(BasicCore):
    # We want to delay the calling of "onstart" methods until we have
    # confirmation from the server that we have a connection. We will fire
    # the event when we hear the response to the hello message.
    delay_onstart_signal = True

    # Agents started before the router can set this variable
    # to false to keep from blocking. AuthService does this.
    delay_running_event_set = True

    def __init__(self, owner, address=None, identity=None, context=None,
                 publickey=None, secretkey=None, serverkey=None,
                 volttron_home=os.path.abspath(platform.get_home()),
                 agent_uuid=None, reconnect_interval=None,
                 version='0.1', instance_name=None, messagebus='rmq'):

        self.volttron_home = volttron_home

        # These signals need to exist before calling super().__init__()
        self.onviperror = Signal()
        self.onsockevent = Signal()
        self.onconnected = Signal()
        self.ondisconnected = Signal()
        self.configuration = Signal()
        super(RMQCore, self).__init__(owner)
        self.address = address if address is not None else get_address()
        self.identity = str(identity) if identity is not None else str(uuid.uuid4())
        self.agent_uuid = agent_uuid
        self.publickey = publickey
        self.secretkey = secretkey
        self.serverkey = serverkey
        self.reconnect_interval = reconnect_interval
        self._reconnect_attempt = 0
        self.instance_name = instance_name
        self.state = type('HelloState', (), {'count': 0, 'ident': None})
        self._set_keys()
        self._event_queue = gevent.queue.Queue

        _log.debug('address: %s', address)
        _log.debug('identity: %s', identity)
        _log.debug('agent_uuid: %s', agent_uuid)
        _log.debug('serverkey: %s', serverkey)

        self.subsystems = {'error': self.handle_error}
        self.__connected = False
        self._version = version
        self._messagebus = messagebus

    def version(self):
        return self._version

    @property
    def connected(self):
        return self.__connected

    def register(self, name, handler, error_handler=None):
        self.subsystems[name] = handler
        if error_handler:
            def onerror(sender, error, **kwargs):
                if error.subsystem == name:
                    error_handler(sender, error=error, **kwargs)

            self.onviperror.connect(onerror)

    def handle_error(self, message):
        if len(message.args) < 4:
            _log.debug('unhandled VIP error %s', message)
        elif self.onviperror:
            args = [bytes(arg) for arg in message.args]
            error = VIPError.from_errno(*args)
            self.onviperror.send(self, error=error, message=message)

    def loop(self, running_event):
        # pre-setup
        self.connection = RMQConnection(self.address, self.identity, self.instance_name)
        yield

        # pre-start
        flags = dict(durable=True, exclusive=False, auto_delete=True)
        self.connection.set_properties(flags)
        # Register callback handler for VIP messages
        self.connection.register(self.vip_message_handler)

        hello_response_event = gevent.event.Event()

        def connection_failed_check():
            # If we don't have a verified connection after 10.0 seconds
            # shut down.
            if hello_response_event.wait(10.0):
                return
            _log.error("No response to hello message after 10 seconds.")
            _log.error("A common reason for this is a conflicting VIP IDENTITY.")
            _log.error("Another common reason is not having an auth entry on"
                       "the target instance.")
            _log.error("Shutting down agent.")
            _log.error("Possible conflicting identity is: {}".format(
                self.identity
            ))

            self.stop(timeout=5.0)

        def hello():
            #Send hello message to VIP router to confirm connection with platform
            self.state.ident = ident = b'connect.hello.%d' % self.state.count
            self.state.count += 1
            self.spawn(connection_failed_check)
            message = Message(peer=b'',subsystem=b'hello',id=ident,args=[b'hello'])
            self.connection.send_vip_object(message)

        def hello_response(sender, version='',
                           router='', identity=''):
            _log.info("Connected to platform: "
                      "router: {} version: {} identity: {}".format(
                router, version, identity))
            _log.debug("Running onstart methods.")
            hello_response_event.set()
            self.onstart.sendby(self.link_receiver, self)
            self.configuration.sendby(self.link_receiver, self)
            if running_event is not None:
                running_event.set()

        # Connect to RMQ broker. Also a callback to get notified when connection is confirmed
        self.connection.connect(hello)

        self.onconnected.connect(hello_response)
        self.ondisconnected.connect(self.connection.close_connection)

        def vip_loop():
            wait_period = 1  # 1 second
            while True:
                try:
                    message = self._event_queue.get(wait_period)
                except gevent.Timeout:
                    pass
                except Exception as exc:
                    _log.error(exc.args)
                    raise
            subsystem = bytes(message.subsystem)

            if subsystem == b'hello':
                _log.debug("Hello subsystem")
                if (subsystem == b'hello' and
                            bytes(message.id) == self.state.ident and
                            len(message.args) > 3 and
                            bytes(message.args[0]) == b'welcome'):
                    version, server, identity = [
                        bytes(x) for x in message.args[1:4]]
                    self.__connected = True
                    self.onconnected.send(self, version=version,
                                          router=server, identity=identity)
            try:
                handle = self.subsystems[subsystem]
            except KeyError:
                _log.error('peer %r requested unknown subsystem %r',
                           bytes(message.peer), subsystem)
                message.user = b''
                message.args = list(router._INVALID_SUBSYSTEM)
                message.args.append(message.subsystem)
                message.subsystem = b'error'
                self.connection.send_vip_object(message)
            else:
                handle(message)

        yield gevent.spawn(vip_loop)
        # pre-stop
        yield
        # pre-finish
        self.connection.close_connection()
        yield

    def vip_message_handler(self, message):
        self._event_queue.put(message)


