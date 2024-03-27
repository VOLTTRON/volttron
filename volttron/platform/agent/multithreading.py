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

'''VOLTTRON platform™ multi-threaded agent helper classes/functions.

These utilities are meant to be used with the BaseAgent and threading to
provide synchronization between threads and the main agent loop.
'''


import threading


class Timeout(Exception):
    '''Raised in the thread when waiting on a queue times out.'''


class WaitQueue:
    '''A holder for threads waiting on asynchronous data.'''

    def __init__(self, lock=None):
        self.condition = threading.Condition(lock)
        self.counter = 0
        self.data = None

    def wait(self, timeout=None):
        '''Wait for data to become available and return it

        If timeout is None, wait indefinitely.  Otherwise, timeout if
        the thread hasn't been notified within timeout seconds.
        '''
        with self.condition:
            return self._wait(timeout)

    def _wait(self, timeout=None):
        counter = self.counter
        self.condition.wait(timeout)
        if counter != self.counter:
            return self.data
        raise Timeout

    def notify_all(self, data):
        '''Notify all waiting threads of the arrival of data.'''
        with self.condition:
            self.data = data
            self.counter += 1
            self.condition.notify_all()

    def notify(self, data, n=1):
        '''Notify n waiting threads of the arrival of data.'''
        with self.condition:
            self.data = data
            self.counter += 1
            self.condition.notify(n)
