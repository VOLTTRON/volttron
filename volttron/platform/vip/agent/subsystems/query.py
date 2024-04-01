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



import re
import weakref

from volttron.platform import jsonapi

from .base import SubsystemBase
from ..errors import VIPError
from ..results import ResultsDictionary
from volttron.platform.vip.socket import Message

__all__ = ['Query']


class Query(SubsystemBase):
    def __init__(self, core):
        self.core = weakref.ref(core)
        self._results = ResultsDictionary()
        core.register('query', self._handle_result, self._handle_error)

    def query(self, prop: str, peer: str = ''):
        """ query a specific peer for a property value

        This method is very useful for retrieving configuration data from the core platform.  When
        peer is not specified it is defaulted to the router.

        :param prop:
            The property to query for.
        :param peer:
            The query to query upon
        :return:
        """
        connection = self.core().connection
        result = next(self._results)
        connection.send_vip(peer, 'query', args=[prop],
                            msg_id=result.ident)
        return result

    __call__ = query

    def _handle_result(self, message):
        if message.args and not message.args[0]:
            try:
                result = self._results.pop(message.id)
            except KeyError:
                return
            try:
                value = message.args[1]
            except IndexError:
                value = None
            result.set(value)

    def _handle_error(self, sender, message, error, **kwargs):
        try:
            result = self._results.pop(message.id)
        except KeyError:
            return
        result.set_exception(error)
