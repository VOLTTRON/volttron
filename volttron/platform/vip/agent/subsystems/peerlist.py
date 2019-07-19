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



import logging
import weakref

from .base import SubsystemBase
from ..dispatch import Signal
from ..results import ResultsDictionary
from volttron.platform import jsonapi
from zmq import ZMQError
from zmq.green import ENOTSOCK

__all__ = ['PeerList']


_log = logging.getLogger(__name__)


class PeerList(SubsystemBase):
    def __init__(self, core):
        self.core = weakref.ref(core)
        self._results = ResultsDictionary()
        core.register('peerlist', self._handle_subsystem, self._handle_error)
        self.onadd = Signal()
        self.ondrop = Signal()

    def list(self):
        connection = self.core().connection
        result = next(self._results)

        try:
            connection.send_vip(b'',
                                b'peerlist',
                                args=[b'list'],
                                msg_id=result.ident)
        except ZMQError as exc:
            if exc.errno == ENOTSOCK:
                _log.error("Socket send on non socket {}".format(self.core().identity))
        return result

    def add_peer(self, peer, message_bus=None):
        connection = self.core().connection
        result = next(self._results)
        if not message_bus:
            message_bus = self.core().messagebus
        try:
            connection.send_vip(b'',
                                b'peerlist',
                                args=[b'add', bytes(peer), bytes(message_bus)],
                                msg_id=result.ident)
        except ZMQError as exc:
            if exc.errno == ENOTSOCK:
                _log.error("Socket send on non socket {}".format(self.core().identity))
        return result

    def drop_peer(self, peer, message_bus=None):
        connection = self.core().connection
        result = next(self._results)
        if not message_bus:
            message_bus = self.core().messagebus
        try:
            connection.send_vip(b'',
                                b'peerlist',
                                args=[b'drop', bytes(peer), bytes(message_bus)],
                                msg_id=result.ident.encode('utf-8'),)
        except ZMQError as exc:
            if exc.errno == ENOTSOCK:
                _log.error("Socket send on non socket {}".format(self.core().identity))
        return result

    def list_with_messagebus(self):
        connection = self.core().connection
        result = next(self._results)

        try:
            connection.send_vip(b'',
                                b'peerlist',
                                args=[b'list_with_messagebus'],
                                msg_id=result.ident)
        except ZMQError as exc:
            if exc.errno == ENOTSOCK:
                _log.error("Socket send on non socket {}".format(self.core().identity))
        return result

    __call__ = list

    def _handle_subsystem(self, message):
        try:
            op = bytes(message.args[0])
        except IndexError:
            _log.error('missing peerlist subsystem operation')
            return

        if op in [b'add', b'drop']:
            try:
                peer = bytes(message.args[1])
            except IndexError:
                _log.error('missing peerlist identity in %s operation', op)
                return
            message_bus = None
            try:
                message_bus = bytes(message.args[2])
            except IndexError:
                pass
            # getattr requires a string
            onop = 'on' + op.decode('utf-8')
            if message_bus:
                getattr(self, onop).send(self, peer=peer, message_bus=message_bus)
            else:
                getattr(self, onop).send(self, peer=peer)
        elif op == b'listing':
            try:
                result = self._results.pop(bytes(message.id).decode('utf-8'))
            except KeyError:
                return
            # The response will have frames, we convert to bytes and then from bytes
            # we decode to strings for the final response.
            result.set([bytes(arg).decode('utf-8') for arg in message.args[1:]])
        elif op == b'listing_with_messagebus':
            try:
                result = self._results.pop(bytes(message.id))
            except KeyError:
                return
            result.set(jsonapi.loads(message.args[1]))
        else:
            _log.error('unknown peerlist subsystem operation == {}'.format(op))

    def _handle_error(self, sender, message, error, **kwargs):
        try:
            result = self._results.pop(bytes(message.id).decode('utf-8'))
        except KeyError:
            return
        result.set_exception(error)
