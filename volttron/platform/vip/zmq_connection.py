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

import zmq
import gevent
import logging
import green as vip

from volttron.platform.vip.mbconnection import BaseConnection
from volttron.platform.vip.socket import Message

class ZMQConnection(BaseConnection):
    def __init__(self, url, instance_name, identity, *args, **kwargs):
        super(BaseConnection, self).__init__(url, instance_name, identity, args, kwargs)
        self.socket = None
        self.context = zmq.Context.instance()
        self._logger = logging.getLogger(__name__)

    def open_connection(self, connection_type):
        if connection_type == zmq.DEALER:
            self.socket = vip.Socket(self.context)
            self.socket.set_hwm(6000)
            if self.reconnect_interval:
                self.socket.setsockopt(zmq.RECONNECT_IVL, self.reconnect_interval)
            if self._identity:
                self.socket.identity = self._identity
        else:
            self.socket = zmq.Socket()

    def connect(self, callback=None):
        self.socket.connect(self._url)
        if callback:
            callback(True)

    def bind(self):
        self._logger("inside logger")

    def register(self, handler):
        self._vip_handler = handler

    def send_vip_object(self, vip_message):
        self.socket.send_vip_object(vip_message)

    def recv_vip_object(self):
        return self.socket.recv_vip_object()

    def disconnect(self):
        self.socket.disconnect(self._url)

    def close_connection(self):
        """This method closes ZeroMQ socket"""
        self.socket.close()

