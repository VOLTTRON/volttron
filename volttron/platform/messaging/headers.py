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

'''VOLTTRON platform™ messaging header name constants.'''


__author__ = 'Brandon Carpenter <brandon.carpenter@pnnl.gov>'
__copyright__ = 'Copyright (c) 2016, Battelle Memorial Institute'
__license__ = 'Apache 2.0'


CONTENT_TYPE = type('ContentTypeStr', (str,),
                    {'JSON': 'application/json',
                     'PLAIN_TEXT': 'text/plain'})('Content-Type')

DATE = 'Date'

TIMESTAMP = 'TimeStamp'

SYNC_TIMESTAMP = 'SynchronizedTimeStamp'

FROM = 'From'
TO = 'To'

REQUESTER_ID = 'requesterID'
COOKIE = 'Cookie'


class Headers(dict):
    '''Case-insensitive dictionary for HTTP-like headers.'''

    class Key(str):
        def __new__(cls, value):
            string = str(value)
            obj = str.__new__(cls, string.lower())
            obj._orig = string
            return obj
        def __str__(self):
            return self._orig
        def __repr__(self):
            return repr(self._orig)

    def __init__(self, *args, **kwargs):
        Key = self.__class__.Key
        obj = super(Headers, self).__init__(((Key(key), value)
               for key, value in dict(*args, **kwargs).items()))
    def __contains__(self, key):
        return super(Headers, self).__contains__(str(key).lower())
    def get(self, key, default=None):
        return super(Headers, self).get(str(key).lower(), default)
    def __getitem__(self, key):
        return super(Headers, self).__getitem__(str(key).lower())
    def __setitem__(self, key, value):
        super(Headers, self).__setitem__(self.__class__.Key(key), value)
    def __delitem__(self, key):
        super(Headers, self).__delitem__(str(key).lower())
    def copy(self):
        return Headers(super(Headers, self).copy())
    @property
    def dict(self):
        '''Return a dictionary with originally-cased keys.'''
        return {str(k): v for k, v in self.items()}
    def setdefault(self, key, value):
        return super(Headers, self).setdefault(self.__class__.Key(key), value)
    def update(self, *args, **kwargs):
        Key = self.__class__.Key
        obj = super(Headers, self).update(((Key(key), value)
               for key, value in dict(*args, **kwargs).items()))
    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__,
                           super(Headers, self).__repr__())
