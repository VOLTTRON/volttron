# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2013, Battelle Memorial Institute
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

# pylint: disable=W0142,W0403
#}}}

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

