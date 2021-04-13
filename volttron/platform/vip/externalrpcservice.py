# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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



import os
import zmq
import logging
from volttron.platform import jsonapi
from zmq import SNDMORE, EHOSTUNREACH, ZMQError, EAGAIN, NOBLOCK
from volttron.utils.frame_serialization import serialize_frames

_log = logging.getLogger(__name__)
# Optimizing by pre-creating frames
_ROUTE_ERRORS = {
    errnum: (zmq.Frame(str(errnum).encode('ascii')),
             zmq.Frame(os.strerror(errnum).encode('ascii')))
    for errnum in [zmq.EHOSTUNREACH, zmq.EAGAIN]
}


class ExternalRPCService(object):
    """
    Class to manage routing of RPC calls between external platforms and internal agents(peers).
    """
    def __init__(self, socket, routing_service, *args, **kwargs):
        self._ext_router = routing_service
        self._vip_sock = socket
        #_log.debug("ExternalRPCService")

    def handle_subsystem(self, frames):
        """
         EXT_RPC subsystem handler on the server end.
        :frames list of frames
        :type frames list
        """
        response = []
        result = None

        try:
            sender, recipient, proto, usr_id, msg_id, subsystem, op, msg = frames[:9]
        except IndexError:
            return False

        if subsystem == 'external_rpc':
            #If operation is to send to external platform
            if op == 'send_platform':
                result = self._send_to_platform(frames)
            #If operation is to send to internal peer, use the internal router socket to send the frames
            elif op == 'send_peer':
                result = self._send_to_peer(frames)
            if not result:
                response = result
            elif result is not None:
                # Form response frame
                response = [sender, recipient, proto, usr_id, msg_id, subsystem]
                response.append('request_response')
                response.append(result)
        return response

    def _send_to_platform(self, frames):
        """
        Send frames to external platform
        :param frames: frames following VIP format
        :return:
        """
        try:
            #Extract the frames and reorganize to add external platform and peer information
            sender, recipient, proto, usr_id, msg_id, subsystem, op, msg = frames[:9]
            #msg_data = jsonapi.loads(msg)
            msg_data = msg
            to_platform = msg_data['to_platform']

            msg_data['from_platform'] = self._ext_router.my_instance_name()
            msg_data['from_peer'] = sender
            msg = jsonapi.dumps(msg_data)
            op = 'send_peer'

            frames = ['', proto, usr_id, msg_id, subsystem, op, msg]
            #_log.debug("ROUTER: Sending EXT RernalPC message to: {}".format(to_platform))
            #Use external socket to send the message
            self._ext_router.send_external(to_platform, frames)
            return False
        except KeyError as exc:
            _log.error("Missing instance name in external RPC message: {}".format(exc))
        except IndexError:
            _log.error("Invalid EXT RPC message")

    def _send_to_peer(self, frames):
        """
        Send the external RPC message to local peer
        :param frames: Frames following VIP format
        :return: frames list
        """
        try:
            # Extract the frames and reorganize to send to local peer
            sender, recipient, proto, usr_id, msg_id, subsystem, op, msg = frames[:9]
            #msg_data = jsonapi.loads(msg)
            msg_data = msg
            peer = msg_data['to_peer']
            frames[0] = peer
            drop = self._send_internal(frames)
            return False
        except KeyError as exc:
            _log.error("Missing agent name in external RPC message: {}".format(exc))
        except IndexError:
            _log.error("Invalid EXT RPC message")

    def _send_internal(self, frames):
        """
        Send message to internal/local peer
        :param frames: frames
        :return: peer to be dropped if not reachable
        """
        drop = []
        peer = frames[0]
        # Expecting outgoing frames:
        #   [RECIPIENT, SENDER, PROTO, USER_ID, MSG_ID, SUBSYS, ...]
        frames = serialize_frames(frames)
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
                drop.append(peer)
            elif exc.errno == EAGAIN:
                _log.debug("EAGAIN error {}".format(peer))
        return drop
