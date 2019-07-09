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

from __future__ import absolute_import

import logging
import weakref

from .base import SubsystemBase
from ..errors import VIPError
from ..results import ResultsDictionary
from zmq import ZMQError
from zmq.green import ENOTSOCK
from volttron.platform.vip.socket import Message

__all__ = ['Hello']


_log = logging.getLogger(__name__)


class Hello(SubsystemBase):
    """ The hello subsystem allows an agent to determine its identity.

    The identity is possibly a dynamically generated uuid from which the
    executing agent does not know.  This subsystem allows the agent to be
    able to determine it's identity from a peer.  By default that peer is
    the connected router, however this could be another agent.
    """

    def __init__(self, core):
        self.core = weakref.ref(core)
        self._results = ResultsDictionary()
        core.register('hello', self._handle_hello, self._handle_error)

    def hello(self, peer=b''):
        """ Receives a welcome message from the peer (default to '' router)

         The welcome message will respond with a 3 element list:

         - The vip version (default 1.0)
         - The peer who responded (should be the same as `peer` argument
           to this function.
         - The id of the requester (i.e. this object).  This will be the
           identity when the agent connects to the router or the specified
           identity when the `Agent` is constructed.

        :param peer: The peer to receive the response from.
        :return: [version, peer, identity]
        """
        _log.info('{0} Requesting hello from peer ({1})'.format(self.core().identity, peer))
        result = next(self._results)
        connection = self.core().connection
        if not connection:
            _log.error("Connection object not yet created".format(self.core().identity))
        else:
            try:
                connection.send_vip(peer, b'hello', args=[b'hello'], msg_id=result.ident)
            except ZMQError as exc:
                if exc.errno == ENOTSOCK:
                    _log.error("Socket send on non socket {}".format(self.core().identity))

        return result

    __call__ = hello

    def _handle_hello(self, message):
        _log.info('Handling hello message {}'.format(message))
        try:
            op = bytes(message.args[0])
        except IndexError:
            _log.error('missing hello subsystem operation')
            return
        if op == b'hello':
            message.user = b''
            message.args = [b'welcome', b'1.0', self.core.identity, message.peer]
            self.core().connection.send_vip_object(message, copy=False)
        elif op == b'welcome':
            try:
                result = self._results.pop(bytes(message.id))
            except KeyError:
                return
            result.set([bytes(arg) for arg in message.args[1:]])
        else:
            _log.error('unknown hello subsystem operation')

    def _handle_error(self, sender, message, error, **kwargs):
        try:
            result = self._results.pop(bytes(message.id))
        except KeyError:
            return
        result.set_exception(error)
