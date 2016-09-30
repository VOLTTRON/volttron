# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met: 
# 
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer. 
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution. 
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# 
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
# 
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
# 
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
#}}}

'''VOLTTRON platform™ messaging header name constants.'''


__author__ = 'Brandon Carpenter <brandon.carpenter@pnnl.gov>'
__copyright__ = 'Copyright (c) 2016, Battelle Memorial Institute'
__license__ = 'FreeBSD'


CONTENT_TYPE = type('ContentTypeStr', (str,),
                    {'JSON': 'application/json',
                     'PLAIN_TEXT': 'text/plain'})('Content-Type')

DATE = 'Date'

TIMESTAMP = 'TimeStamp'

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
               for key, value in dict(*args, **kwargs).iteritems()))
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
        return {str(k): v for k, v in self.iteritems()}
    def setdefault(self, key, value):
        return super(Headers, self).setdefault(self.__class__.Key(key), value)
    def update(self, *args, **kwargs):
        Key = self.__class__.Key
        obj = super(Headers, self).update(((Key(key), value)
               for key, value in dict(*args, **kwargs).iteritems()))
    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__,
                           super(Headers, self).__repr__())
