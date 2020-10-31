# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}


from __future__ import absolute_import

import errno
import logging
import os
from queue import Queue
from typing import Optional

from volttron.platform import is_rabbitmq_available
from volttron.platform import jsonapi
from volttron.utils.rmq_mgmt import RabbitMQMgmt
from .rmq_connection import RMQRouterConnection
from .router import BaseRouter
from .servicepeer import ServicePeerNotifier
from .socket import Message, Address
from ..keystore import KeyStore
from ..main import __version__

if is_rabbitmq_available():
    import pika

__all__ = ['RMQRouter']

_log = logging.getLogger(__name__)


class RMQRouter(object):
    """
    Concrete VIP Router for RabbitMQ message bus. It handles router specific
    messages and unrouteable messages.
    """

    def __init__(self, address, local_address, instance_name,
                 addresses=(), identity='router', default_user_id=None,
                 volttron_central_address=None,
                 volttron_central_serverkey=None,
                 bind_web_address=None,
                 service_notifier=Optional[ServicePeerNotifier]
                 ):
        """
        Initialize the object instance.
        :param instance_name: Name of VOLTTRON instance
        :param identity: Identity for router
        :param default_user_id: Default user id
        """
        self.default_user_id = default_user_id
        self._peers = set()
        self._peers_with_messagebus = dict()
        self.addresses = [Address(addr) for addr in set(addresses)]
        self.local_address = Address(local_address)
        self._address = address
        self._volttron_central_address = volttron_central_address
        self._volttron_central_serverkey = volttron_central_serverkey
        self._bind_web_address = bind_web_address
        self._instance_name = instance_name
        self._identity = identity
        self.rmq_mgmt = RabbitMQMgmt()
        self.event_queue = Queue()
        self._service_notifier = service_notifier
        param = self._build_connection_parameters()
        self.connection = RMQRouterConnection(param,
                                              identity,
                                              instance_name,
                                              reconnect_delay=self.rmq_mgmt.rmq_config.reconnect_delay()
                                              )

    def _build_connection_parameters(self):

        if self._identity is None:
            raise ValueError("Agent's VIP identity is not set")
        else:
            param = self.rmq_mgmt.build_router_connection(self._identity,
                                                          self._instance_name)
        return param

    def start(self):
        """
        Register VIP message handler with connection object and create
        connection to RabbitMQ broker.
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
            self.connection.loop()
        except KeyboardInterrupt:
            pass
        except (pika.exceptions.AMQPConnectionError,
                pika.exceptions.AMQPChannelError) as exc:
            _log.error("RabbitMQ Connection Error. {}".format(exc))
        finally:
            self.stop()

    def connection_open_callback(self):
        _log.debug("Received connection callback")

    def connection_close_callback(self):
        _log.debug("Received connection callback")

    def issue(self, topic, frames, extra=None):
        pass

    def _add_peer(self, peer, message_bus='rmq'):
        if peer == self._identity:
            return
        if peer in self._peers:
            return
        self._distribute('peerlist', 'add', peer, message_bus)
        self._peers.add(peer)
        self._peers_with_messagebus[peer] = message_bus
        self._service_notifier.peer_added(peer)

    def _drop_peer(self, peer, message_bus='rmq'):
        try:
            self._peers.remove(peer)
            self._service_notifier.peer_dropped(peer)
            del self._peers_with_messagebus[peer]
        except KeyError:
            return
        self._distribute('peerlist', 'drop', peer, message_bus)

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
        # [SENDER, RECIPIENT, PROTOCOL, USER_ID, MSG_ID, SUBSYSTEM, ...]

        sender = message.peer  # source
        subsystem = message.subsystem
        self._add_peer(sender)
        if subsystem == 'hello':
            self.authenticate(sender)
            # send welcome message back
            message.args = ['welcome', '1.0', self._identity, sender]
        elif subsystem == 'ping':
            message.args = ['pong']
        elif subsystem == 'peerlist':
            try:
                op = message.args[0]
            except IndexError:
                op = None
            except ValueError:
                op = None
            if op == 'list':
                del message.args[:]
                message.args = ['listing']
                message.args.extend(self._peers)
            elif op == 'list_with_messagebus':
                _log.debug("Router peerlist request op: list_with_messagebus, {}, {}".format(sender, self._peers))
                del message.args[:]
                message.args = ['listing_with_messagebus']
                message.args.append(jsonapi.dumps(self._peers_with_messagebus))
                _log.debug("Router peerlist request op: list_with_messagebus, {}, {}".format(sender, self._peers))
            elif op == 'add':
                peer = message.args[1]
                try:
                    message_bus = message.args[2]
                except IndexError:
                    message_bus = 'rmq'
                self._add_peer(peer=peer, message_bus=message_bus)
            elif op == 'drop':
                peer = message.args[1]
                try:
                    message_bus = message.args[2]
                except IndexError:
                    message_bus = 'rmq'
                self._drop_peer(peer=peer, message_bus=message_bus)
            else:
                error = ('unknown' if op else 'missing') + ' operation'
                message.args.extend(['error', error])
        elif subsystem == 'quit':
            if sender == 'control':
                self.stop()
                raise KeyboardInterrupt()
        elif subsystem == 'agentstop':
            _log.debug("ROUTER received agent stop {}".format(sender))
            try:
                drop = message.args[0]
                self._drop_peer(drop)
            except IndexError:
                pass
            except ValueError:
                pass
            return False
        elif subsystem == 'query':
            try:
                name = message.args[0]
            except IndexError:
                value = None
            except ValueError:
                value = None
            else:
                if name == 'addresses':
                    if self.addresses:
                        value = [addr.base for addr in self.addresses]
                    else:
                        value = [self.local_address.base]
                elif name == 'local_address':
                    value = self.local_address.base
                # Allow the agents to know the serverkey.
                elif name == 'serverkey':
                    keystore = KeyStore()
                    value = keystore.public
                elif name == 'volttron-central-address':
                    value = self._volttron_central_address
                elif name == 'volttron-central-serverkey':
                    value = self._volttron_central_serverkey
                elif name == 'instance-name':
                    value = self._instance_name
                elif name == 'bind-web-address':
                    value = self._bind_web_address
                elif name == 'platform-version':
                    value = __version__
                elif name == 'message-bus':
                    value = os.environ.get('MESSAGEBUS', 'zmq')
                else:
                    value = None
            message.args = ['', value]
            message.args.append('')
        elif subsystem == 'error':
            try:
                errnum = message.args[0]
                if errnum == errno.EHOSTUNREACH:
                    recipient = message.args[2]
                    self._drop_peer(recipient)
                return
            except IndexError:
                _log.error("ROUTER unable to parse error message {}".format(message.args))
        else:
            # Router does not know of the subsystem
            message.type = 'error'
            errnum = errno.EPROTONOSUPPORT
            errmsg = os.strerror(errnum).encode('ascii')  # str(errnum).encode('ascii')
            _log.debug("ROUTER proto unsupported {}, sender {}".format(subsystem, sender))
            message.args = [errnum, errmsg, '', subsystem]

        # Send the message back to the sender
        self.connection.send_vip_object(message)

    def _distribute(self, *parts):
        message = Message(peer=None, subsystem=parts[0], args=parts[1:])
        for peer in self._peers:
            message.peer = peer
            _log.debug(f"Distributing to peers {peer}")
            if self._peers_with_messagebus[peer] == 'rmq':
                self.connection.send_vip_object(message)

    def _make_user_access_tokens(self, identity):
        tokens = dict()
        tokens["configure"] = tokens["read"] = tokens["write"] = [identity,
                                                                  identity + ".pubsub.*",
                                                                  identity + ".zmq.*"]
        tokens["read"].append("volttron")
        tokens["write"].append("volttron")

        return tokens

    def _check_user_access_token(self, actual, allowed):
        pending = actual[:]
        for tk in actual:
            if tk in allowed:
                pending.remove(tk)
        return pending

    def _make_topic_permission_tokens(self, identity):
        """
        Make tokens for read and write permission on topic (routing key) for an agent
        :param identity:
        :return:
        """
        tokens = dict()
        # Exclusive read access ( topic consumption ) to it's VIP routing key and any pubsub routing key
        tokens["read"] = ["{0}.{1}".format(self._instance_name, identity),
                          "__pubsub__.*"]
        # Write access to any VIP routing key and application specific topics within this instance
        tokens["write"] = ["{0}.*".format(self._instance_name),
                           "__pubsub__.{0}.*".format(self._instance_name)]
        if identity == "proxy_router":
            tokens["read"] = ".*"
            tokens["write"] = ".*"
        return tokens

    def _check_token(self, actual, allowed):
        """
        Check if actual permission string matches the allowed permission
        :param actual: actual permission
        :param allowed: allowed permission
        :return: returns missing permissions
        """
        pending = actual[:]
        for tk in actual:
            if tk in allowed:
                pending.remove(tk)
        return pending

    def authenticate(self, identity):
        """
        Check the permissions set for the agent
        1. Check the permissions for user
            - to access the "volttron" exchange
            - to access it's VIP queue and pubsub queues
        2. Check/Set the topic permissions for the user

        :param user: Agent identity
        :return:
        """
        user_error_msg = self._check_user_permissions(self._instance_name +
                                                      "." + identity)
        return user_error_msg

    def _check_user_permissions(self, identity):
        msg = None
        user_permission = self.rmq_mgmt.get_user_permissions(identity)
        # Check user access permissions for the agent
        allowed_tokens = self._make_user_access_tokens(identity)
        # _log.debug("Identity: {0}, User permissions: {1}".format(identity, user_permission))
        if user_permission:
            config_perms = user_permission.get("configure", "").split("|")
            read_perms = user_permission.get("read", "").split("|")
            write_perms = user_permission.get("write", "").split("|")
            config_chk = self._check_token(config_perms, allowed_tokens["configure"])
            read_chk = self._check_token(read_perms, allowed_tokens["read"])
            write_chk = self._check_token(write_perms, allowed_tokens["write"])
            if config_chk or read_chk or write_chk:
                msg = "Agent has invalid user permissions to "
                if config_chk: msg += "CONFIGURE: {} , ".format(config_chk)
                if read_chk: msg += "READ: {} ".format(read_chk)
                if write_chk: msg += "WRITE: {}".format(write_chk)
        else:
            # Setting default user access control
            common_access = "{identity}|{identity}.pubsub.*|{identity}.zmq.*".format(identity=identity)
            # Rabbit user for the agent should have access to limited resources (exchange, queues)
            config_access = common_access
            read_access = "volttron|{}".format(common_access)
            write_access = "volttron|{}".format(common_access)
            permissions = dict(configure=config_access, read=read_access, write=write_access)
            self.rmq_mgmt.set_user_permissions(permissions, identity)
        return msg
