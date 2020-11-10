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

'''VOLTTRON platform™ greenlet coroutine helper classes/functions.

These utilities are meant to be used with the BaseAgent and greenlet to
provide synchronization between light threads (coroutines).
'''


import greenlet


class Timeout(Exception):
    '''Raised in the greenlet when waiting on a channel times out.'''


def sleep(timeout, create_timer):
    '''Yield execution for timeout seconds.'''
    current = greenlet.getcurrent()
    timer = create_timer(timeout, current.switch)
    current.parent.switch()


class WaitQueue(object):
    '''A holder for tasklets waiting on asynchronous data.'''

    def __init__(self, create_timer):
        '''create_timer will be used to create timeouts.'''
        self.tasks = []
        self._timer = create_timer

    def wait(self, timeout=None):
        '''Wait for data to become available and return it

        If timeout is None, wait indefinitely.  Otherwise, timeout if
        the task hasn't been notified within timeout seconds.
        '''
        current = greenlet.getcurrent()
        tasks = self.tasks
        tasks.append(current)
        if timeout:
            timer = self._timer(timeout, current.throw, Timeout)
        try:
            return current.parent.switch()
        finally:
            if timeout:
                timer.cancel()
            tasks.remove(current)

    def notify_all(self, data):
        '''Notify all waiting tasks of the arrival of data.'''
        self.notify(data, None)

    def notify(self, data, n=1):
        '''Notify n waiting tasks of the arrival of data.'''
        if n is None or n < 0:
            tasks, self.tasks = self.tasks, []
        else:
            tasks, self.tasks = self.tasks[:n], self.tasks[n:]
        for task in list(tasks):
            task.switch(data)

    def kill_all(self):
        '''Kill all the tasks in the queue.'''
        tasks, self.tasks = self.tasks, []
        for task in tasks:
            task.throw()

