# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2015, Battelle Memorial Institute
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

from __future__ import print_function, absolute_import

import os
import threading

import requests
import random
import gevent
from gevent.fileobject import FileObject
import zmq
import logging
from zmq import SNDMORE, EHOSTUNREACH, ZMQError, EAGAIN, NOBLOCK
from ..keystore import KeyStore
from zmq.utils import jsonapi
from ..vip.socket import Address
from zmq.utils.monitor import recv_monitor_message
from requests.packages.urllib3.connection import (ConnectionError,
                                                  NewConnectionError)
from urlparse import urlparse, urljoin
import random

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
    def __init__(self, socket, context, socket_class, poller, ext_address_file, my_addr, *args, **kwargs):
        self._routing_table = dict()
        self._poller = poller
        self._external_address_file = ext_address_file
        self._ext_addresses = dict()
        self._instances = dict()
        self._context = context
        self._socket = socket
        self._socket_class = socket_class
        self._read_platform_address_file()
        self._my_addr = my_addr
        self._my_instance_name = ''
        self._monitor_poller = zmq.Poller()
        self._onconnect_pubsub_handler = None
        self._ondisconnect_pubsub_handler = None
        self._ext_sockets = []
        self._socket_identities = dict()

    def setup(self):
        """
        Creates monitor thread to monitor all remote socket connections. Creates sockets for each remote instance
        connection.
        :return:
        """
        # Start monitor sockets in separate thread to remain responsive
        thread = threading.Thread(target=self._monitor_external_sockets)
        thread.daemon = True
        thread.start()

        for name in self._ext_addresses:
            _log.debug(
                "my address: {0}, external {1}".format(self._my_addr, self._ext_addresses[name]['vip-address']))

            if self._ext_addresses[name]['vip-address'] not in self._my_addr:
                sock = zmq.Socket(zmq.Context(), zmq.DEALER)
                self._monitor_poller.register(
                    sock.get_monitor_socket(
                        zmq.EVENT_CONNECTED | zmq.EVENT_DISCONNECTED | zmq.EVENT_CONNECT_DELAYED),
                    zmq.POLLIN)
                sock.sndtimeo = 0
                sock.tcp_keepalive = True
                sock.tcp_keepalive_idle = 180
                sock.tcp_keepalive_intvl = 20
                sock.tcp_keepalive_cnt = 6
                num = random.random()
                sock.identity = self._ext_addresses[name]['instance-name'] + '-'+ str(num)
                self._instances[name] = dict(platform_identity=sock.identity,
                                              status=STATUS_CONNECTING,
                                              socket=sock,
                                              monitor_socket=sock.get_monitor_socket()
                                              )
                sock.zap_domain = 'vip'

                self._socket_identities[sock.identity] = name
                self._ext_sockets.append(sock)
                self._poller.register(sock, zmq.POLLIN)
                self._routing_table[name] = [name]
            else:
                self._my_instance_name = name
                self._routing_table[name] = []

    def _build_connection(self, instance_name, serverkey):
        """
        Build connection with remote instance and send initial "hello" message.
        :param instance_name: name of remote instance
        :param serverkey: serverkey for establishing connection with remote instance
        :return:
        """
        def build_vip_address(vip_address, serverkey):
            """
            Create a usable vip address with zap parameters embedded in the uri.

            :return:
            """
            keystore = KeyStore()
            return "{0}?serverkey={1}&publickey={2}&secretkey={3}".format(
                vip_address, str(serverkey),
                str(keystore.public), str(keystore.secret)
            )

        sock = self._instances[instance_name]['socket']
        address = self._ext_addresses[instance_name]['vip-address']
        address = build_vip_address(address, serverkey)

        ext_platform_address = Address(address)

        try:
            #self._instances[instance_name] = address
            ext_platform_address.connect(sock)
            #Form VIP message to send to remote instance
            frames = [b'', 'VIP1', b'', b'', b'routing_table', b'hello', b'hello', self._my_instance_name]
            self.send_external(instance_name, frames)
        except zmq.error.ZMQError as ex:
            _log.error("ZMQ error on external connection {}".format(ex))

    def _read_platform_address_file(self):
        """
        Read external address file
        :return:
        """
        try:
            with open(self._external_address_file) as fil:
                # Use gevent FileObject to avoid blocking the thread
                data = FileObject(fil, close=False).read()
                self._ext_addresses = jsonapi.loads(data) if data else {}
        except IOError:
            _log.exception("Error opening %s", self._external_address_file)
        except Exception:
            _log.exception('error loading %s', self._external_address_file)

    def _monitor_external_sockets(self):
        """
        Poll the status of external socket connections using monitor sockets. Set the status based on the monitor socket
        poll result.
        :return:
        """
        try:
            events = {value: name[6:] for name, value in vars(zmq).iteritems()
                      if name.startswith('EVENT_') and name != 'EVENT_ALL'}
            while True:
                try:
                    sockets = dict(self._monitor_poller.poll())
                except ZMQError as ex:
                    _log.error("ZMQ Error while polling monitor sockets: {}".format(ex))

                for monitor_sock in sockets:
                    message = recv_monitor_message(monitor_sock)
                    event = message['event']
                    instance_name = [name for name, instance_info in self._instances.items()
                                     if instance_info['monitor_socket'] == monitor_sock]

                    if event & zmq.EVENT_CONNECTED:
                        _log.debug("ROUTINGSERVICE socket CONNECTED to {}!! send local subscriptions !!".format(instance_name[0]))

                        self._instances[instance_name[0]]['status'] = STATUS_CONNECTED
                        self._onconnect_pubsub_handler(instance_name[0])
                    elif event & zmq.EVENT_CONNECT_DELAYED:
                        #_log.debug("ROUTINGSERVICE socket DELAYED...Lets wait")
                        self._instances[instance_name[0]]['status'] = STATUS_CONNECTION_DELAY
                    elif event & zmq.EVENT_DISCONNECTED:
                        _log.debug("ROUTINGSERVICE socket DISCONNECTED...remove subscriptions")
                        self._instances[instance_name[0]]['status'] = STATUS_DISCONNECTED
                        self._ondisconnect_pubsub_handler(instance_name[0])
        finally:
            _log.debug("Reached monitor socket Finally")
            #Close all sockets
            for name, instance_info in self._instances.items():
                instance_info['monitor_socket'].disable_monitor()
                instance_info['socket'].close(1)
                instance_info['monitor_socket'].close()

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
        self._ondisconnect_pubsub_handler(instance_name)
        instance_info = self._instances[instance_name]
        sock = instance_info['socket']
        mon_sock = instance_info['monitor_socket']
        mon_sock.close()
        #sock.disconnect(instance_info['address'])
        #sock.close()
        #del self._instances[instance_name]

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
        return self._socket_identities[identity]

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
                _log.debug("Could not send to {} using new socket".format(instance_name))
                success = False
            if not success:
                #Try sending through router socket
                if bytes(frames[0]) == b'' and instance_info['status'] == STATUS_CONNECTING:
                    frames[:0] = [self._my_instance_name]
                    _log.debug("Trying to send with router socket")
                    try:
                        success = self._send(self._socket, frames)
                    except ZMQError as exc:
                        _log.debug("Dropping or setting to disconnected {}".format(instance_name))
                        # Let's just update status as 'DISCONNECTED' for now
                        self._instances[instance_name]['status'] = STATUS_DISCONNECTED
                        raise
        except KeyError:
            frames[:0] = [self._my_instance_name]
            _log.debug("Key error for platform {0}, list: {1}".format(instance_name, self._instances))
            success = self._send(self._socket, frames)
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
                error = None
            if exc.errno == EHOSTUNREACH or exc.errno == EAGAIN:
                success = False
                raise
        return success

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
        sender, recipient, proto, usr_id, msg_id, subsystem = frames[:6]
        # for f in frames:
        #     _log.debug("ROUTINGSERVICE handle subsystem {}".format(bytes(f)))

        if subsystem.bytes == b'routing_table':
            try:
                op = bytes(frames[6])
            except IndexError:
                return False
            #If serverkey received from KeyDiscoveryService, build connection with remote instance
            if op == b'external_serverkey':
                serverkey = bytes(frames[7])
                name = bytes(frames[8])
                self._build_connection(name, serverkey)
            if op == b'hello':
                handshake_request = bytes(frames[7])
                #Respond to 'hello' request with 'welcome'
                if handshake_request == b'hello':
                    name = bytes(frames[8])
                    frames.pop(0)
                    _log.debug("Recieved hello, sending welcome to {}".format(name))
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
                    _log.debug("Received welcome. Connection established with: {}".format(name))
                    self._instances[name]['status'] = STATUS_CONNECTED
                    _log.debug("Onconnect pubsub handler: {}".format(name))
                    self._onconnect_pubsub_handler(name)
            #Update routing table entry
            if op == b'update':
                result = self._update_entry(frames)
            elif op == b'request_response':
                pass
        if result:
            #Form response frame
            response = [sender, recipient, proto, usr_id, msg_id, subsystem]
            response.append(zmq.Frame(b'request_response'))
            response.append(zmq.Frame(bytes(result)))
        else:
            response = False

        return response

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
        for name in self._instances:
            self.disconnect_external_instances(name)