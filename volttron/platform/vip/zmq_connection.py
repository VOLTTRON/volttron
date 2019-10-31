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
import logging

from .green import Socket as GreenSocket
from .rmq_connection import BaseConnection
_log = logging.getLogger(__name__)


class ZMQConnection(BaseConnection):
    """
    Maintains ZMQ socket connection
    """
    def __init__(self, url, identity, instance_name, context):
        super(ZMQConnection, self).__init__(url, identity, instance_name)

        self.socket = None
        self.context = context
        self._identity = identity
        self._logger = logging.getLogger(__name__)
        self._logger.debug("ZMQ connection {}".format(identity))

    def open_connection(self, type):
        if type == zmq.DEALER:
            self.socket = GreenSocket(self.context)
            if self._identity:
                self.socket.identity = self._identity.encode('utf-8')
        else:
            self.socket = zmq.Socket()

    def set_properties(self,flags):
        hwm = flags.get('hwm', 6000)
        self.socket.set_hwm(hwm)
        reconnect_interval = flags.get('reconnect_interval', None)
        if reconnect_interval:
            self.socket.setsockopt(zmq.RECONNECT_IVL, reconnect_interval)

    def connect(self, callback=None):
        _log.debug(f"connecting to url {self._url}")
        _log.debug(f"url type is {type(self._url)}")

        self.socket.connect(self._url)
        if callback:
            callback(True)

    def bind(self):
        pass

    def register(self, handler):
        self._vip_handler = handler

    def send_vip_object(self, message, flags=0, copy=True, track=False):
        self.socket.send_vip_object(message, flags, copy, track)

    def send_vip(self, peer, subsystem, args=None, msg_id: bytes = b'',
                 user=b'', via=None, flags=0, copy=True, track=False):
        self.socket.send_vip(peer, subsystem, args=args, msg_id=msg_id, user=user,
                             via=via, flags=flags, copy=copy, track=track)

    def recv_vip_object(self, flags=0, copy=True, track=False):
        return self.socket.recv_vip_object(flags, copy, track)

    def disconnect(self):
        self.socket.disconnect(self._url)

    def close_connection(self, linger=5):
        """This method closes ZeroMQ socket"""
        self.socket.close(linger)
        _log.debug("********************************************************************")
        _log.debug("Closing connection to ZMQ: {}".format(self._identity))
        _log.debug("********************************************************************")

