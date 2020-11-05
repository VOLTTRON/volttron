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

'''VOLTTRON platform™ multi-threaded agent helper classes/functions.

These utilities are meant to be used with the BaseAgent and threading to
provide synchronization between threads and the main agent loop.
'''


import threading


class Timeout(Exception):
    '''Raised in the thread when waiting on a queue times out.'''


class WaitQueue(object):
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

