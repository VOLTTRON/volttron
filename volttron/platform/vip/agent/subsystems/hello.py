# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
# }}}



import logging
import weakref

from .base import SubsystemBase
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

    def hello(self, peer=''):
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
                connection.send_vip(peer, 'hello', args=['hello'], msg_id=result.ident)
            except ZMQError as exc:
                if exc.errno == ENOTSOCK:
                    _log.error("Socket send on non socket {}".format(self.core().identity))

        return result

    __call__ = hello

    def _handle_hello(self, message):
        _log.info('Handling hello message {}'.format(message))
        try:
            # zmq
            op = message.args[0]
        except IndexError:
            _log.error('missing hello subsystem operation')
            return
        if op == 'hello':
            message.user = ''
            message.args = ['welcome', '1.0', self.core().identity, message.peer]
            self.core().connection.send_vip_object(message, copy=False)
        elif op == 'welcome':
            try:
                result = self._results.pop(message.id)
            except KeyError:
                return
            result.set([arg for arg in message.args[1:]])
        else:
            _log.error('unknown hello subsystem operation')

    def _handle_error(self, sender, message, error, **kwargs):
        try:
            result = self._results.pop(message.id)
        except KeyError:
            return
        result.set_exception(error)
