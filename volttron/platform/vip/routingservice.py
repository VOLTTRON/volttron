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

import argparse
import errno
import logging
from logging import handlers
import logging.config
from urlparse import urlparse

import os
import sys
import threading
import uuid
import re

import gevent
from gevent.fileobject import FileObject
import zmq
import logging
from zmq import SNDMORE, EHOSTUNREACH, ZMQError, EAGAIN, NOBLOCK
from zmq import green
from collections import defaultdict
from ..keystore import KeyStore
from .socket import decode_key, encode_key, Address
from zmq.utils import jsonapi
from ..vip.socket import Address
from zmq.utils.monitor import recv_monitor_message

_log = logging.getLogger(__name__)

# Optimizing by pre-creating frames
_ROUTE_ERRORS = {
    errnum: (zmq.Frame(str(errnum).encode('ascii')),
             zmq.Frame(os.strerror(errnum).encode('ascii')))
    for errnum in [zmq.EHOSTUNREACH, zmq.EAGAIN]
}

class RoutingService(object):
    def __init__(self, socket, context, socket_class, poller, ext_address_file, my_addr, *args, **kwargs):
        self._routing_table = dict()
        self._poller = poller
        self._external_address_file = ext_address_file
        self._ext_addresses = {}
        self._socket_id_mapping = {}
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

    def setup(self):
        def build_vip_address(external_platform_address, serverkey):
            """
            Create a usable vip address with zap parameters embedded in the uri.

            :return:
            """
            keystore = KeyStore()
            return "{0}?serverkey={1}&publickey={2}&secretkey={3}".format(
                external_platform_address, str(serverkey),
                str(keystore.public), str(keystore.secret)
            )

        thread = threading.Thread(target=self.monitor_external_sockets)
        thread.daemon = True
        thread.start()
        for name in self._ext_addresses:
            _log.debug("my address: {0}, external {1}".format(self._my_addr, self._ext_addresses[name]['address']))
            # Start monitor sockets in separate threads to remain responsive

            if self._ext_addresses[name]['address'] not in self._my_addr:
                sock = zmq.Socket(zmq.Context(), zmq.DEALER)
                sock.sndtimeo = 0
                sock.tcp_keepalive = True
                sock.tcp_keepalive_idle = 180
                sock.tcp_keepalive_intvl = 20
                sock.tcp_keepalive_cnt = 6

                addr = self._ext_addresses[name]['address']
                serverkey = self._ext_addresses[name]['serverkey']
                _log.debug("ZMQ External serverkey: {}".format(serverkey))
                sock.identity = self._ext_addresses[name]['platform_identity']
                _log.debug("ROUTINGSERVICE CONNECTED TO EXTERNAL PLATFORM {}".format(sock.identity))
                sock.zap_domain = 'vip'
                self._monitor_poller.register(sock.get_monitor_socket(zmq.EVENT_CONNECTED), zmq.POLLIN)
                address = build_vip_address(addr, serverkey)

                ext_platform_address = Address(address)
                _log.debug("ZMQ External server key: {}".format(ext_platform_address.serverkey))
                try:
                    ext_platform_address.connect(sock)
                except zmq.error.ZMQError as ex:
                    _log.error("ZMQ error on external connection {}".format(ex))
                    break

                self._socket_id_mapping[name] = dict(platform_identity=sock.identity,
                                                     socket=sock, monitor_socket=sock.get_monitor_socket())
                self._ext_sockets.append(sock)
                self._poller.register(sock, zmq.POLLIN)
                self._routing_table[name] = [name]
            else:
                # self._socket_id_mapping[name] = dict(platform_identity= self._ext_addresses[name]['platform_identity'],
                #                                      socket=None, monitor_socket=None)
                self._my_instance_name = name
                self._routing_table[name] = []

            for name in self._socket_id_mapping:
                sock = self._socket_id_mapping[name]['socket']
                _log.debug("ROUTINGSERVICE CONNECTED TO EXTERNAL PLATFORM {}".format(sock.identity))
        #
        # for vip_id, sock in self._socket_id_mapping.iteritems():
        #     routing_msg = jsonapi.dumps(self._routing_table)
        #     frames = [b'', b'VIP1', b'', b'', b'routing_table', b'update', routing_msg]
        #     sock.send_multipart(frames, copy=False)

    def _read_platform_address_file(self):
        #Read protected topics file and send to router
        try:
            with open(self._external_address_file) as fil:
                # Use gevent FileObject to avoid blocking the thread
                data = FileObject(fil, close=False).read()
                self._ext_addresses = jsonapi.loads(data) if data else {}
        except Exception:
            _log.exception('error loading %s', self._external_address_file)

    def monitor_external_sockets(self):
        """

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
                    #_log.debug("ROUTING SERVICE RECEIVING EVENT: {0}, {1}".format(message, events[event]))
                    if event & zmq.EVENT_CONNECTED:
                        _log.debug("ROUTINGSERVICE socket CONNECTED!! send local subscriptions !!")
                        instance_name = {name for name, instance_info in self._socket_id_mapping.items()
                                       if instance_info['monitor_socket'] == monitor_sock}
                        gevent.sleep(1)
                        self._onconnect_pubsub_handler(instance_name)
                    elif event & zmq.EVENT_CONNECT_DELAYED:
                        _log.debug("ROUTINGSERVICE socket DELAYED...Lets wait")
                    if event & zmq.EVENT_DISCONNECTED:
                        instance_name = {name for name, instance_info in self._socket_id_mapping.items()
                                       if instance_info['monitor_socket'] == monitor_sock}
                        #self._onconnect_pubsub_handler(instance_name)
                        #_log.debug("ROUTINGSERVICE socket DISCONNECTED, remove all subscriptions !!")
                #gevent.sleep(1)
        finally:
            _log.debug("Reached finally")
            for name, instance_info in self._socket_id_mapping.items():
                instance_info['socket'].close()
                instance_info['monitor_socket'].close()

    def register(self, type, handler):
        if type == 'on_connect':
            self._onconnect_pubsub_handler = handler
        else:
            self._ondisconnect_pubsub_handler = handler

    def my_instance_name(self):
        return self._my_instance_name

    def disconnect_external_platform(self, vip_ids):
        for id in vip_ids:
            sock = self._socket_id_mapping[id]
            sock.close()

    def get_connected_platforms(self):
        _log.debug(
            "ROUTINGSERVICE: get connected platforms{}".format(self._socket_id_mapping.keys()))
        return list(self._socket_id_mapping.keys())
        #return list(self._routing_table.keys())

    def send_external(self, instance_name, frames):
        try:
            instance_info = self._socket_id_mapping[instance_name]
            self._send(instance_info['socket'], frames)
            _log.debug("ROUTING SERVICE sending to {}".format(instance_info['socket'].identity))
        except KeyError:
            _log.error("Invalid socket connection {}".format(instance_name))

    def _send(self, sock, frames):
        drop = []
        peer_platform = frames[0]
        # Expecting outgoing frames:
        #   [RECIPIENT, SENDER, PROTO, USER_ID, MSG_ID, SUBSYS, ...]

        try:
            # Try sending the message to its recipient
            sock.send_multipart(frames, flags=NOBLOCK, copy=False)
        except ZMQError as exc:
            try:
                errnum, errmsg = error = _ROUTE_ERRORS[exc.errno]
            except KeyError:
                error = None
            if exc.errno == EHOSTUNREACH:
                _log.debug("Host unreachable {}".format(peer_platform.bytes))
                drop.append(bytes(peer_platform))
            elif exc.errno == EAGAIN:
                _log.debug("EAGAIN error {}".format(peer_platform.bytes))
        return drop

    def handle_subsystem(self, frames, user_id):
        """
         Handler for incoming routing table frames. It checks operation frame and directs it to appropriate action handler.
        :param frames list of frames
        :type frames list
        :param user_id user id of the publishing agent. This is required for protected topics check.
        :type user_id  UTF-8 encoded User-Id property
        :returns: response frame to be sent back to the sender
        :rtype: list

        :Return Values:
        response frame to be sent back to the sender
        """
        response = []
        result = None
        sender, recipient, proto, usr_id, msg_id, subsystem = frames[:6]

        if subsystem.bytes == b'routing_table':
            try:
                op = bytes(frames[6])
            except IndexError:
                return False

            if op == b'update':
                result = self._update_entry(frames)
            elif op == b'request_response':
                _log.debug("Resonse to request")
        if result is not None:
            #Form response frame
            response = [sender, recipient, proto, user_id, msg_id, subsystem]
            response.append(zmq.Frame(b'request_response'))
            response.append(zmq.Frame(bytes(result)))

        return response

    def _update_entry(self, frames):
        if len(frames) > 6:
            sender = bytes(frames[0])
            routing_table = bytes(frames[7])
            routing_table = jsonapi.loads(routing_table)
            _log.debug("ROUTING SERVICE Ext routing TABLE: {0}, MY {1} ".format(routing_table, self._routing_table))
            for vip_id in routing_table:
                if vip_id in self._routing_table.keys():
                    if vip_id != self._my_vip_id:
                        _log.debug("ROUTING SERVICE {}".format(vip_id))
                        my_route_list = self._routing_table[vip_id]
                        if len(routing_table[vip_id]) > 0 and len(routing_table[vip_id]) < len(my_route_list):
                            _log.debug("kdldkfldfkl")
                            my_route_list = [sender]
                            self._routing_table[vip_id] = my_route_list.extend(routing_table[vip_id])
                else:
                    _log.debug("here??")
                    route_list = [sender]
                    self._routing_table[vip_id] = route_list.extend(routing_table[vip_id])
            _log.debug("ROUTING SERVICE my routing TABLE: {} ".format(self._routing_table))
            return True
        else:
            return False

