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
#}}}


from __future__ import absolute_import

import os
import pika
import logging
from .rmq_connection import RMQConnection
from .socket import Message
from ..main import __version__
from volttron.platform.agent import json as jsonapi
from .zmq_router import BaseRouter
import errno
from Queue import Queue
from ..keystore import KeyStore

__all__ = ['RMQRouter']

_log = logging.getLogger(__name__)


class RMQRouter(BaseRouter):
    """
    Concrete VIP Router for RabbitMQ message bus.
    """

    def __init__(self, address, instance_name, identity='router', default_user_id=None):
        """
        Initialize the object instance.
        :param instance_name: Name of VOLTTRON instance
        :param identity: Identity for router
        :param default_user_id: Default user id
        """
        self.default_user_id = default_user_id
        self._peers = set()
        self._address = address
        self._instance_name = 'volttron1'
        self._identity = identity
        self.event_queue = Queue()
        _log.debug("INSTANCE: {0}".format(instance_name))
        self.connection = RMQConnection(address, identity, self._instance_name, type='platform')

    def start(self):
        """
        Register VIP message handler with connection object. And create connection to RabbitMQ broker.
        :return:
        """
        self.connection.register(self.handle_system)
        self.setup()

    def stop(self, linger=1):
        """
        Close the connection to RabbitMQ broker.
        :param linger:
        :return:
        """
        self.connection.disconnect()

    def setup(self):
        """
        Called from start() method to set connection properties.
        :return:
        """
        # set properties for VIP queue
        flags = dict(durable=False, exclusive=True, auto_delete=True)
        self.connection.set_properties(flags)

    def run(self):
        """
        RabbitMQ router loop to keep the connection running.
        :return:
        """
        self.start()
        try:
            # for message in self.event_queue:
            #     self.handle_system(message)
            self.connection.loop()
        except (pika.exceptions.AMQPConnectionError, pika.exceptions.AMQPChannelError):
            _log.debug("Unable to connect to the RabbitMQ broker")
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def callback(self):
        _log.debug("Received connection callback")

    def issue(self, topic, frames, extra=None):
        pass

    def _add_peer(self, peer):
        if peer in self._peers:
            return
        self._distribute(b'peerlist', b'add', peer)
        self._peers.add(peer)
        self._add_pubsub_peers(peer)

    def _drop_peer(self, peer):
        try:
            self._peers.remove(peer)
        except KeyError:
            return
        #self._distribute(b'peerlist', b'drop', peer)
        #self._drop_pubsub_peers(peer)

    def route(self, message):
        '''Route one message and return.

        One message is read from the socket and processed. If the
        recipient is the router (empty recipient), the standard hello
        and ping subsystems are handled. Other subsystems are sent to
        handle_subsystem() for processing. Messages destined for other
        entities are routed appropriately.
        '''
        self.handle_system(message)

    def handle_system(self, message):
        """
        Handles messages intended for router. Standard hello, ping, peerlist subsystems
        are handled.
        :param props: properties associated with incoming message
        :param message: actual message
        :return:
        """
        #[SENDER, RECIPIENT, PROTOCOL, USER_ID, MSG_ID, SUBSYSTEM, ...]
        # sender = props.app_id #source
        sender = message.peer #source
        subsystem = message.subsystem

        if subsystem == b'hello':
            message.args = [b'welcome', b'1.0', self._identity, sender]
        elif subsystem == b'ping':
            message.args = [b'pong']
        elif subsystem == b'peerlist':
            try:
                op = message.args[0]
            except IndexError:
                op = None
            except ValueError:
                op = None
            if op == b'list':
                message.args.append(b'listing')
                message.args.extend(self._peers)
            else:
                error = (b'unknown' if op else b'missing') + b' operation'
                message.args.extend([b'error', error])
        elif subsystem == b'error':
            return
        elif subsystem == b'quit':
            if sender == b'control':
                self.stop()
                raise KeyboardInterrupt()
        elif subsystem == b'agentstop':
            try:
                drop = message.args[0]
                self._drop_peer(drop)
                _log.debug("ROUTER received agent stop message. dropping peer: {}".format(drop))
            except IndexError:
                pass
            except ValueError:
                pass
            return False
        elif subsystem == b'query':
            try:
                name = bytes(message.args[0])
            except IndexError:
                value = None
            except ValueError:
                value = None
            else:
                if name == b'addresses':
                    if self.addresses:
                        value = [addr.base for addr in self.addresses]
                    else:
                        value = [self.local_address.base]
                elif name == b'local_address':
                    value = self.local_address.base
                # Allow the agents to know the serverkey.
                elif name == b'serverkey':
                    keystore = KeyStore()
                    value = keystore.public
                elif name == b'volttron-central-address':
                    value = self._volttron_central_address
                elif name == b'volttron-central-serverkey':
                    value = self._volttron_central_serverkey
                elif name == b'instance-name':
                    value = self._instance_name
                elif name == b'bind-web-address':
                    value = self._bind_web_address
                elif name == b'platform-version':
                    value = __version__
                else:
                    value = None
            message.args = [b'', jsonapi.dumps(value)]
            message.args.append(b'')
        else:
            # Router does not know of the subsystem
            message.type = b'error'
            errnum = errno.EPROTONOSUPPORT
            errmsg = os.strerror(errnum).encode('ascii')#str(errnum).encode('ascii')
            _log.debug("ROUTER proto unsupported {}".format(subsystem))
            message.args = [errnum, errmsg, b'', subsystem]

        # Send the message back to the sender
        self.connection.send_vip_object(message)

