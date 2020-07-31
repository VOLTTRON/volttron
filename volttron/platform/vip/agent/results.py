# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
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



import random
from weakref import WeakValueDictionary

from gevent.event import AsyncResult
import sys
from datetime import datetime

__all__ = ['counter', 'ResultsDictionary']


class AsyncResult(AsyncResult):
    __slots__ = AsyncResult.__slots__ + ('ident',)


def counter(start=None, minimum=0, maximum=sys.maxsize-1):
    #count = random.randint(minimum, maximum) if start is None else start
    count = int(datetime.now().timestamp()) if start is None else start
    while True:
        yield count
        count += 1
        if count >= maximum:
            count = int(datetime.now().timestamp())


class ResultsDictionary(WeakValueDictionary):
    def __init__(self):
        WeakValueDictionary.__init__(self)
        self._counter = counter()

    def pop(self, key, *args):
        if isinstance(key, bytes):
            key = key.decode("utf-8")
        return WeakValueDictionary.pop(self, key, *args)

    def __contains__(self, key):
        if isinstance(key, bytes):
            key = key.decode("utf-8")
        return WeakValueDictionary.__contains__(self, key)

    def __getitem__(self, key):
        if isinstance(key, bytes):
            key = key.decode("utf-8")
        return WeakValueDictionary.__getitem__(self, key)

    def get(self, key, default=None):
        if isinstance(key, bytes):
            key = key.decode("utf-8")
        return WeakValueDictionary.get(self, key, default=default)

    def __next__(self):
        result = AsyncResult()
        result.ident = ident = '%f.%f' % (next(self._counter), hash(result))
        self[ident] = result
        return result
