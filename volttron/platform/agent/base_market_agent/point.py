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

from builtins import property as _property, tuple as _tuple
from operator import itemgetter as _itemgetter
from collections import OrderedDict

class Point(tuple):
    'Point(quantity, price)'
    __slots__ = ()

    _fields = ('quantity', 'price')

    def __new__(_cls, quantity, price):
        """Create new instance of Point(quantity, price)"""
#        if (quantity < 0 or quantity is None):
#            raise ValueError('The quantity provided ({}) is an invalid value.'.format(quantity))
#        if (price < 0 or price is None):
#            raise ValueError('The price provided ({}) is an invalid value.'.format(price))
        # Catch exception to
        float_quantity = float(quantity)
        float_price = float(price)
        return _tuple.__new__(_cls, (float_quantity, float_price))

    @classmethod
    def _make(cls, iterable, new=tuple.__new__, len=len):
        """Make a new Point object from a sequence or iterable"""
        result = new(cls, iterable)
        if len(result) != 2:
            raise TypeError('Expected 2 arguments, got %d' % len(result))
        return result

    def __repr__(self):
        """Return a nicely formatted representation string"""
        return 'Point(quantity=%r, price=%r)' % self

    def _asdict(self):
        """Return a new OrderedDict which maps field names to their values"""
        return OrderedDict(zip(self._fields, self))

    def _replace(_self, **kwds):
        """Return a new Point object replacing specified fields with new values"""
        result = _self._make(map(kwds.pop, ('quantity', 'price'), _self))
        if kwds:
            raise ValueError('Got unexpected field names: %r' % kwds.keys())
        return result

    def __getnewargs__(self):
        """Return self as a plain tuple.  Used by copy and pickle."""
        return tuple(self)

    __dict__ = _property(_asdict)

    def __getstate__(self):
        """Exclude the OrderedDict from pickling"""
        pass

    def tuppleize(self):
        return (self.quantity, self.price)

    quantity = _property(_itemgetter(0), doc='Alias for field number 0')
    x = _property(_itemgetter(0), doc='Alias for field number 0')

    price = _property(_itemgetter(1), doc='Alias for field number 1')
    y = _property(_itemgetter(1), doc='Alias for field number 1')
