# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
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

from __future__ import print_function, absolute_import

import os
import re
import zmq
import logging
from zmq import SNDMORE, EHOSTUNREACH, ZMQError, EAGAIN, NOBLOCK
from ..keystore import KeyStore
from zmq.utils import jsonapi
from ..vip.socket import Address
from zmq.utils.monitor import recv_monitor_message
import random
from zmq.green import ENOTSOCK

STATUS_CONNECTING = "CONNECTING"
STATUS_CONNECTED = "CONNECTED"
STATUS_CONNECTION_DELAY = "CONNECTION_DELAY"
STATUS_DISCONNECTED = "DISCONNECTED"

# Optimizing by pre-creating frames
_ROUTE_ERRORS = {
    errnum: (zmq.Frame(str(errnum).encode('ascii')),
             zmq.Frame(os.strerror(errnum).encode('ascii')))
    for errnum in [zmq.EHOSTUNREACH, zmq.EAGAIN]
}

_log = logging.getLogger(__name__)

class RoutingService(object):
    """
    This class maintains connection with external platforms.
    """
    def __init__(self, socket, context, socket_class, poller, my_addr, instance_name, *args, **kwargs):
        self._routing_table = dict()
        self._poller = poller
        self._instances = dict()
        self._context = context
        self._socket = socket
        self._socket_class = socket_class
        self._my_addr = my_addr
        self._my_instance_name = instance_name
        self._onconnect_pubsub_handler = None
        self._ondisconnect_pubsub_handler = None
        self._vip_sockets = set()
        self._monitor_sockets = set()
        self._socket_identities = dict()
        self._web_addresses = []

    def handle_subsystem(self, frames):
        """
         Handler for incoming routing table frames. It calls appropriate action handler based on operation request.
        :param frames list of frames
        :type frames list
        :returns: response frame to be sent back to the sender
        :rtype: list

        :Return Values:
        response frame to be sent back to the sender
        """
        response = []
        result = False

        try:
            sender, recipient, proto, usr_id, msg_id, subsystem, op = frames[:7]
        except IndexError:
            return False
        subsystem = bytes(subsystem)
        op = bytes(op)
        # for f in frames:
        #     _log.debug("ROUTINGSERVICE handle subsystem {}".format(bytes(f)))

        if subsystem == b'routing_table':
            #If Setup mode of operation, setup authorization
            if op == b'setupmode_platform_connection':
                instance_config = bytes(frames[7])
                instance_config = jsonapi.loads(instance_config)
                self._setup_authorization(instance_config)
            # If Normal mode of operation, build authorized connection
            elif op == b'normalmode_platform_connection':
                instance_config = bytes(frames[7])
                instance_config = jsonapi.loads(instance_config)
                self._build_connection(instance_config)
                return False
            #Respond to Hello/Welcome messages from other instances
            elif op == b'hello':
                handshake_request = bytes(frames[7])
                try:
                    #Respond to 'hello' request with 'welcome'
                    if handshake_request == b'hello':
                        name = bytes(frames[8])
                        frames.pop(0)
                        _log.debug("HELLO Recieved hello, sending welcome to {}".format(name))
                        frames[6] = 'welcome'
                        frames[7] = self._my_instance_name
                        try:
                            _log.debug("Sending welcome message to sender {}".format(name))
                            self.send_external(name, frames)
                        except ZMQError as exc:
                            _log.error("ZMQ error: ")
                    #Respond to 'welcome' response by sending Pubsub subscription list
                    elif handshake_request == b'welcome':
                        name = bytes(frames[8])
                        _log.debug("HELLO Received welcome. Connection established with: {}".format(name))
                        try:
                            self._instances[name]['status'] = STATUS_CONNECTED
                            self._onconnect_pubsub_handler(name)
                        except KeyError as exc:
                            _log.error("Welcome message received from unknown platform: {}".format(name))
                except IndexError as exc:
                    _log.error("Insufficient frames in hello message {}".format(exc))
            elif op == b"web-addresses":
                self._web_addresses = bytes(frames[7])
                self._web_addresses = jsonapi.loads(self._web_addresses)
            #Update routing table entry
            elif op == b'update':
                result = self._update_entry(frames)
            elif op == b'request_response':
                pass
            else:
                _log.error("Unknown operation: {}".format(op))
        if result:
            #Form response frame
            response = [sender, recipient, proto, usr_id, msg_id, subsystem]
            response.append(zmq.Frame(b'request_response'))
            response.append(zmq.Frame(bytes(result)))
        else:
            response = False

        return response

    def _setup_authorization(self, instance_info):
        """
        Setup authorized connection with remote instance
        :param instance_name: dicovery information(server key, name, vip-address) of remote instance
        :return:
        """
        try:
            instance_name = instance_info['instance-name']
            serverkey = instance_info['serverkey']
            address = instance_info['vip-address']
            web_address = instance_info['web-address']
        except KeyError as exc:
            _log.error("Missing parameter in instance info message {}".format(exc))
            return

        sock = zmq.Socket(zmq.Context(), zmq.DEALER)
        num = random.random()
        sock.identity = 'platform-' + '-' + instance_name + '-' + str(num)
        sock.zap_domain = 'vip'
        self._poller.register(sock, zmq.POLLIN)
        keystore = KeyStore()
        vip_address = "{0}?serverkey={1}&publickey={2}&secretkey={3}".format(
            address, str(serverkey),
            str(keystore.public), str(keystore.secret)
        )

        ext_platform_address = Address(vip_address)
        ext_platform_address.identity = sock.identity
        try:
            ext_platform_address.connect(sock)
        except zmq.error.ZMQError as ex:
            _log.error("ZMQ error on external connection {}".format(ex))
        self._web_addresses.remove(web_address)
        if not self._web_addresses:
            _log.debug("MULTI_PLATFORM SETUP MODE COMPLETED")

    def _build_connection(self, instance_info):
        """
        Build connection with remote instance and send initial "hello" message.
        :param instance_name: name of remote instance
        :param serverkey: serverkey for establishing connection with remote instance
        :return:
        """
        _log.debug("instance_info {}".format(instance_info))
        try:
            instance_name = instance_info['instance-name']
            serverkey = instance_info['serverkey']
            address = instance_info['vip-address']
        except KeyError as exc:
            _log.error("Missing parameter in instance info message {}".format(exc))
            return

        #Return immediately if vip_address of external instance is same as self address
        if address in self._my_addr:
            _log.debug("Same instance: {}".format(address))
            return
        sock = zmq.Socket(zmq.Context(), zmq.DEALER)
        sock.sndtimeo = 0
        sock.tcp_keepalive = True
        sock.tcp_keepalive_idle = 180
        sock.tcp_keepalive_intvl = 20
        sock.tcp_keepalive_cnt = 6

        num = random.random()
        sock.identity = 'instance-'+ instance_name + '-' + str(num)
        sock.zap_domain = 'vip'
        mon_sock = sock.get_monitor_socket(
                zmq.EVENT_CONNECTED | zmq.EVENT_DISCONNECTED | zmq.EVENT_CONNECT_DELAYED)

        self._poller.register(mon_sock, zmq.POLLIN)
        self._monitor_sockets.add(mon_sock)

        self._instances[instance_name] = dict(platform_identity=sock.identity,
                                     status=STATUS_CONNECTING,
                                     socket=sock,
                                     monitor_socket=mon_sock
                                     )

        self._socket_identities[sock.identity] = instance_name
        self._vip_sockets.add(sock)

        self._poller.register(sock, zmq.POLLIN)

        self._routing_table[instance_name] = [instance_name]

        keystore = KeyStore()
        sock = self._instances[instance_name]['socket']

        vip_address = "{0}?serverkey={1}&publickey={2}&secretkey={3}".format(
                        address,
                        str(serverkey),
                        str(keystore.public),
                        str(keystore.secret)
                        )

        ext_platform_address = Address(vip_address)
        ext_platform_address.identity = sock.identity
        try:
            ext_platform_address.connect(sock)
            # Form VIP message to send to remote instance
            frames = [b'', 'VIP1', b'', b'', b'routing_table', b'hello', b'hello', self._my_instance_name]
            _log.debug("HELLO Sending hello to: {}".format(instance_name))
            self.send_external(instance_name, frames)
        except zmq.error.ZMQError as ex:
            _log.error("ZMQ error on external connection {}".format(ex))

    def handle_monitor_event(self, monitor_sock):
        """
        Monitor external platform socket connections
        :param monitor_sock: socket to monitor
        :return:
        """
        try:
            message = recv_monitor_message(monitor_sock)
            event = message['event']
            instance_name = [name for name, instance_info in self._instances.items()
                             if instance_info['monitor_socket'] == monitor_sock]

            if event & zmq.EVENT_CONNECTED:
                _log.debug(
                    "CONNECTED to external platform: {}!! Sending MY subscriptions !!".format(instance_name[0]))
                self._instances[instance_name[0]]['status'] = STATUS_CONNECTED
                self._onconnect_pubsub_handler(instance_name[0])
            elif event & zmq.EVENT_CONNECT_DELAYED:
                # _log.debug("ROUTINGSERVICE socket DELAYED...Lets wait")
                self._instances[instance_name[0]]['status'] = STATUS_CONNECTION_DELAY
            elif event & zmq.EVENT_DISCONNECTED:
                _log.debug("DISCONNECTED from external platform: {}. "
                           "Subscriptions will be resent on reconnect".format(instance_name[0]))
                self._instances[instance_name[0]]['status'] = STATUS_DISCONNECTED
        except ZMQError as exc:
            if exc.errno == ENOTSOCK:
                _log.error("Trying to use a non socket {}".format(exc))
        except KeyError as exc:
            _log.error("Unknown external instance: {}".format(instance_name))


    def register(self, type, handler):
        """
        Used by PubSubService to register for onconnect and ondisconnect handlers.
        :param type: on_connect/on_disconnect
        :param handler: handler function
        :return:
        """
        if type == 'on_connect':
            self._onconnect_pubsub_handler = handler
        else:
            self._ondisconnect_pubsub_handler = handler

    def my_instance_name(self):
        """
        Name of my instance/platform.
        :return:
        """
        return self._my_instance_name

    def disconnect_external_instances(self, instance_name):
        """
        Close socket connections to remote platform
        :param instance_name:
        :return:
        """
        try:
            self._ondisconnect_pubsub_handler(instance_name)
            instance_info = self._instances[instance_name]
            sock = instance_info['socket']
            mon_sock = instance_info['monitor_socket']
            mon_sock.close()
        except KeyError as exc:
            _log.error("Unknown external instance name: {}".format(instance_name))

    def get_connected_platforms(self):
        """
        Get list of connected instances
        :return:
        """
        names = []

        for name in self._instances:
            if self._instances[name]['status'] == STATUS_CONNECTED:
                names.append(name)

        return names

    def get_name_for_identity(self, identity):
        """
        Get instance name
        :param identity: platform identity
        :return:
        """
        if self._socket_identities[identity]:
            return self._socket_identities[identity]
        else: return None

    def send_external(self, instance_name, frames):
        """
        Send frames to external instance
        :param instance_name: name of remote instance
        :param frames: frames to send
        :return:
        """
        success = False
        instance_info = dict()

        try:
            instance_info = self._instances[instance_name]

            try:
                #Send using external socket
                success = self._send(instance_info['socket'], frames)
            except ZMQError as exc:
                _log.error("Could not send to {} using new socket".format(instance_name))
                success = False
            # if not success:
            #     #Try sending through router socket
            #     if bytes(frames[0]) == b'' and instance_info['status'] == STATUS_CONNECTING:
            #         frames[:0] = [self._my_instance_name]
            #
            #         try:
            #             _log.debug("Trying to send with router socket")
            #             #success = self._send(self._socket, frames)
            #         except ZMQError as exc:
            #             _log.debug("Dropping or setting to disconnected {}".format(instance_name))
            #             # Let's just update status as 'DISCONNECTED' for now
            #             self._instances[instance_name]['status'] = STATUS_DISCONNECTED
            #             raise
        except KeyError:
            frames[:0] = [self._my_instance_name]
            #_log.debug("Key error for platform {0}".format(instance_name))
            #success = self._send(self._socket, frames)
        return success

    def _send(self, sock, frames):
        """
        Socket send function
        :param sock: socket
        :param frames: frames to send
        :return:
        """
        success = True

        try:
            # Try sending the message to its recipient
            sock.send_multipart(frames, flags=NOBLOCK, copy=False)
        except ZMQError as exc:
            try:
                errnum, errmsg = error = _ROUTE_ERRORS[exc.errno]
            except KeyError:
                success = False
                error = None
            if exc.errno == EHOSTUNREACH or exc.errno == EAGAIN:
                success = False
                raise
        return success

    def _update_entry(self, frames):
        """
        NOT USED - FOR FUTURE
        Update routing table entries.
        :param frames:
        :return:
        """
        if len(frames) > 6:
            sender = bytes(frames[0])
            routing_table = bytes(frames[7])
            routing_table = jsonapi.loads(routing_table)
            _log.debug("ROUTING SERVICE Ext routing TABLE: {0}, MY {1} ".format(routing_table, self._routing_table))
            for vip_id in routing_table:
                if vip_id in self._routing_table.keys():
                    if vip_id != self._my_vip_id:
                        my_route_list = self._routing_table[vip_id]
                        if len(routing_table[vip_id]) > 0 and len(routing_table[vip_id]) < len(my_route_list):
                            my_route_list = [sender]
                            self._routing_table[vip_id] = my_route_list.extend(routing_table[vip_id])
                else:
                    route_list = [sender]
                    self._routing_table[vip_id] = route_list.extend(routing_table[vip_id])
            _log.debug("ROUTING SERVICE my routing TABLE: {} ".format(self._routing_table))
            return True
        else:
            return False

    def close_external_connections(self):
        """
        Close external platform socket connections
        :return:
        """
        for name in self._instances:
            self.disconnect_external_instances(name)