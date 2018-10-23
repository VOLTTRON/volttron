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


from __future__ import absolute_import
import logging
import pika
import os
import errno

from .rmq_connection import RMQRouterConnection
from .socket import Message, Address
from ..main import __version__
from .router import BaseRouter
from Queue import Queue
from ..keystore import KeyStore
from volttron.utils.rmq_mgmt import RabbitMQMgmt
from volttron.platform.agent import json as jsonapi

__all__ = ['RMQRouter']

_log = logging.getLogger(__name__)


class RMQRouter(BaseRouter):
    """
    Concrete VIP Router for RabbitMQ message bus. It handles router specific
    messages and unrouteable messages.
    """

    def __init__(self, address, local_address, instance_name,
                 addresses=(), identity='router', default_user_id=None,
                 volttron_central_address=None,
                 volttron_central_serverkey=None,
                 bind_web_address=None
                 ):
        """
        Initialize the object instance.
        :param instance_name: Name of VOLTTRON instance
        :param identity: Identity for router
        :param default_user_id: Default user id
        """
        self.default_user_id = default_user_id
        self._peers = set()
        self.addresses = [Address(addr) for addr in set(addresses)]
        self._address = address
        self._volttron_central_address = volttron_central_address
        self._volttron_central_serverkey = volttron_central_serverkey
        self._bind_web_address = bind_web_address
        self._instance_name = instance_name
        self._identity = identity
        self.rmq_mgmt = RabbitMQMgmt()
        self.event_queue = Queue()
        param = self._build_connection_parameters()
        self.connection = RMQRouterConnection(param,
                                              identity,
                                              instance_name
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

    def _add_peer(self, peer):
        if peer == self._identity:
            return
        if peer in self._peers:
            return
        self._distribute(b'peerlist', b'add', peer)
        self._peers.add(peer)

    def _drop_peer(self, peer):
        try:
            self._peers.remove(peer)
        except KeyError:
            return
        self._distribute(b'peerlist', b'drop', peer)

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
        if subsystem == b'hello':
            self.authenticate(sender)
            # send welcome message back
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
                del message.args[:]
                message.args = [b'listing']
                message.args.extend(self._peers)
            else:
                error = (b'unknown' if op else b'missing') + b' operation'
                message.args.extend([b'error', error])
        elif subsystem == b'quit':
            if sender == b'control':
                self.stop()
                raise KeyboardInterrupt()
        elif subsystem == b'agentstop':
            try:
                drop = message.args[0]
                self._drop_peer(drop)
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
                elif name == b'message-bus':
                    value = os.environ.get('MESSAGEBUS', 'zmq')
                else:
                    value = None
            message.args = [b'', jsonapi.dumps(value)]
            message.args.append(b'')
        elif subsystem == b'error':
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
            message.type = b'error'
            errnum = errno.EPROTONOSUPPORT
            errmsg = os.strerror(errnum).encode('ascii')  # str(errnum).encode('ascii')
            _log.debug("ROUTER proto unsupported {}, sender {}".format(subsystem, sender))
            message.args = [errnum, errmsg, b'', subsystem]

        # Send the message back to the sender
        self.connection.send_vip_object(message)

    def _distribute(self, *parts):
        message = Message(peer=None, subsystem=parts[0], args=parts[1:])
        for peer in self._peers:
            message.peer = peer
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
