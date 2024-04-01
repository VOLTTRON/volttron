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

'''Run gevent Greenlets in their own threads.

Supports killing threads and executing callbacks from other threads.
'''



import functools
import sys
import threading

import gevent
from gevent import GreenletExit


__all__ = ['AsyncCall', 'GreenletExit']

__author__ = 'Brandon Carpenter <brandon.carpenter@pnnl.gov>'

class AsyncCall:
    '''Send functions to another thread's gevent hub for execution.'''

    def __init__(self, hub=None):
        '''Install this async handler in a hub.

        If hub is None, the current thread's hub is used.
        '''
        if hub is None:
            hub = gevent.get_hub()
        self.calls = calls = []
        self.__async = hub.loop.async_()
        self.__async.start(functools.partial(self._run_calls, calls))

    def __del__(self):
        '''Stop the async handler on deletion.'''
        print('deleted')
        self.__async.stop()

    def send(self, receiver, func, *args, **kwargs):
        '''Send a function to the hub to be called there.

        All the arguments to this method are placed in a queue and the
        hub is signaled that a function is ready. When the hub switches
        to this handler, the functions are iterated over, each being
        called with its results sent to the receiver.

        func is called with args and kwargs in the thread of the
        associated hub. If receiver is None, results are ignored and
        errors are printed when exceptions occur. Otherwise, receiver is
        called with the 2-tuple (exc_info, result). If an unhandled
        exception occurred, exc_info is the 3-tuple returned by
        sys.exc_info() and result is None. Otherwise exc_info is None
        and the result is func's return value.

        Note that receiver is called from the hub's thread and may
        need to be injected into the thread of the receiver.
        '''
        self.calls.append((receiver, func, args, kwargs))
        self.__async.send()

    @staticmethod
    def _run_call(receiver, func, args, kwargs):
        '''Run a pending call in its own greenlet.'''
        try:
            exc_info, result = None, func(*args, **kwargs)   # pylint: disable=star-args
        except Exception:   # pylint: disable=broad-except
            exc_info, result = sys.exc_info(), None
        if receiver is not None:
            receiver((exc_info, result))
        elif exc_info:
            hub = gevent.get_hub()
            hub.handle_error(func, *exc_info)   # pylint: disable=star-args

    # This method is static to prevent a reference loop so the object
    # can be garbage collected without stopping the async handler.
    @classmethod
    def _run_calls(cls, calls):
        '''Execute pending calls.'''
        while calls:
            args = calls.pop()
            gevent.spawn(cls._run_call, *args)   # pylint: disable=star-args
