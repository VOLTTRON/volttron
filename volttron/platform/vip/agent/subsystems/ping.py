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
from ..errors import VIPError
from ..results import ResultsDictionary
from volttron.platform.vip.socket import Message
from zmq import ZMQError
from zmq.green import ENOTSOCK

__all__ = ['Ping']


_log = logging.getLogger(__name__)


class Ping(SubsystemBase):
    def __init__(self, core):
        self.core = weakref.ref(core)
        self._results = ResultsDictionary()
        core.register('ping', self._handle_ping, self._handle_error)

    def ping(self, peer, *args):
        result = next(self._results)
        args = list(args)
        args.insert(0, 'ping')
        connection = self.core().connection
        try:
            connection.send_vip('',
                                'ping',
                                args=['drop', peer],
                                msg_id=result.ident)
        except ZMQError as exc:
            if exc.errno == ENOTSOCK:
                _log.debug("Socket send on non socket {}".format(self.core().identity))
        return result

    __call__ = ping

    def _handle_ping(self, message):
        connection = self.core().connection
        try:
            op = message.args[0]
        except IndexError:
            _log.error('missing ping subsystem operation')
            return
        if op == 'ping':
            message.user = ''
            message.args[0] = 'pong'
            connection.send_vip_object(message, copy=False)
        elif op == 'pong':
            try:
                result = self._results.pop(message.id)
            except KeyError:
                return
            result.set([arg for arg in message.args[1:]])
        else:
            _log.error('unknown ping subsystem operation')

    def _handle_error(self, sender, message, error, **kwargs):
        try:
            result = self._results.pop(message.id)
        except KeyError:
            return
        result.set_exception(error)
