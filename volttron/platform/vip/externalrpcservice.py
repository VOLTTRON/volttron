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
from zmq.utils import jsonapi
from zmq import SNDMORE, EHOSTUNREACH, ZMQError, EAGAIN, NOBLOCK

_log = logging.getLogger(__name__)
# Optimizing by pre-creating frames
_ROUTE_ERRORS = {
    errnum: (zmq.Frame(str(errnum).encode('ascii')),
             zmq.Frame(os.strerror(errnum).encode('ascii')))
    for errnum in [zmq.EHOSTUNREACH, zmq.EAGAIN]
}

class ExternalRPCService(object):
    def __init__(self, socket, routing_service, *args, **kwargs):
        self._ext_router = routing_service
        self._vip_sock = socket
        _log.debug("ExternalRPCService")

    def handle_subsystem(self, frames):
        response = []
        result = None

        try:
            sender, recipient, proto, usr_id, msg_id, subsystem, op, msg = frames[:9]
        except IndexError:
            return False
        subsystem = bytes(subsystem)
        op = bytes(op)

        if subsystem == b'EXT_RPC':
            if op == b'send_platform':
                result = self._send_to_platform(frames)
            elif op == b'send_peer':
                result = self._send_to_peer(frames)
            if not result:
                response = result
            elif result is not None:
                # Form response frame
                response = [sender, recipient, proto, usr_id, msg_id, subsystem]
                response.append(zmq.Frame(b'request_response'))
                response.append(zmq.Frame(bytes(result)))
        return response

    def _send_to_platform(self, frames):
        try:
            # Reframe the frames
            sender, recipient, proto, usr_id, msg_id, subsystem, op, msg = frames[:9]
            msg_data = jsonapi.loads(bytes(msg))
            to_platform = msg_data['to_platform']

            msg_data['from_platform'] = self._ext_router.my_instance_name()
            msg_data['from_peer'] = bytes(sender)
            msg = jsonapi.dumps(msg_data)
            op = b'send_peer'
            # frames[7] = msg
            # _log.debug(
            #     "ROUTER: EXT RPC _send_to_platform : sender {0}, recipient {1}, proto {2}, usr_id {3}, msg_id {4}, subsystem {5}, op {6}, msg {7}".
            #         format(bytes(sender), bytes(recipient), bytes(proto), bytes(usr_id), bytes(msg_id),
            #                bytes(subsystem), bytes(op), msg))
            frames = [b'', proto, usr_id, msg_id, subsystem, op, msg]
            #_log.debug("ROUTER: Sending EXT RPC message to: {}".format(to_platform))
            self._ext_router.send_external(to_platform, frames)
            return False
        except IndexError:
            _log.error("Invalid EXT RPC message")

    def _send_to_peer(self, frames):
        try:
            # Reframe the frames
            sender, recipient, proto, usr_id, msg_id, subsystem, op, msg = frames[:9]
            msg_data = jsonapi.loads(bytes(msg))
            peer = msg_data['to_peer']
            #_log.debug("EXT ROUTER::Send to peer : {}".format(peer))
            # Form new frame for local
            frames[0] = bytes(peer)
            drop = self._send_internal(frames)
            return False
            #return frames
        except IndexError:
            _log.error("Invalid EXT RPC message")

    def _send_internal(self, frames):
        drop = []
        peer = bytes(frames[0])
        # Expecting outgoing frames:
        #   [RECIPIENT, SENDER, PROTO, USER_ID, MSG_ID, SUBSYS, ...]

        try:
            # Try sending the message to its recipient
            self._vip_sock.send_multipart(frames, flags=NOBLOCK, copy=False)
        except ZMQError as exc:
            try:
                errnum, errmsg = error = _ROUTE_ERRORS[exc.errno]
            except KeyError:
                error = None
            if exc.errno == EHOSTUNREACH:
                _log.debug("Host unreachable {}".format(peer))
                drop.append(bytes(peer))
            elif exc.errno == EAGAIN:
                _log.debug("EAGAIN error {}".format(peer))
        return drop
