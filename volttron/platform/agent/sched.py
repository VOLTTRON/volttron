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

'''VOLTTRON platform™ agent event scheduling classes.'''


import heapq
import time as time_mod


class Event(object):
    '''Base class for schedulable objects.'''

    __slots__ = ['function', 'args', 'kwargs', 'canceled', 'finished']

    def __init__(self, function, args=None, kwargs=None):
        self.function = function
        self.args = args or []
        self.kwargs = kwargs or {}
        self.canceled = False
        self.finished = False

    def cancel(self):
        '''Mark the timer as canceled to avoid a callback.'''
        self.canceled = True

    def __call__(self, deadline):
        if not self.canceled:
            self.function(*self.args, **self.kwargs)
        self.finished = True
        
class EventWithTime(Event): 
    '''Event that passes deadline to event handler.'''
    def __call__(self, deadline):
        if not self.canceled:
            self.function(deadline, *self.args, **self.kwargs)
        self.finished = True


class RecurringEvent(Event):
    __slots__ = ['period']

    def __init__(self, period, function, args=None, kwargs=None):
        super(RecurringEvent, self).__init__(function, args, kwargs)
        self.period = period

    def __call__(self, deadline):
        if not self.canceled:
            self.function(*self.args, **self.kwargs)
            if not self.canceled:
                return deadline + self.period
        self.finished = True


class Queue(object):
    def __init__(self):
        self._queue = []

    def schedule(self, time, event):
        heapq.heappush(self._queue, (time, event))

    def execute(self, time):
        if not self._queue:
            return
        deadline, callback = event = self._queue[0]
        if deadline > time:
            return
        assert heapq.heappop(self._queue) == event
        time = callback(deadline)
        if time is not None:
            if hasattr(time, 'timetuple'):
                time = time_mod.mktime(time.timetuple())
            heapq.heappush(self._queue, (time, callback))
        return True

    def delay(self, time):
        if not self._queue:
            return
        deadline, _ = self._queue[0]
        return deadline - time if deadline > time else 0

    def __bool__(self):
        return bool(self._queue)

