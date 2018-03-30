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
from ..dispatch import Signal
from ..results import ResultsDictionary


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
        socket = self.core().socket
        result = next(self._results)
        socket.send_vip(b'', b'peerlist', [b'list'], result.ident)
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
            getattr(self, 'on' + op).send(self, peer=peer)
        elif op == b'listing':
            try:
                result = self._results.pop(bytes(message.id))
            except KeyError:
                return
            result.set([bytes(arg) for arg in message.args[1:]])
        else:
            _log.error('unknown peerlist subsystem operation')

    def _handle_error(self, sender, message, error, **kwargs):
        try:
            result = self._results.pop(bytes(message.id))
        except KeyError:
            return
        result.set_exception(error)
