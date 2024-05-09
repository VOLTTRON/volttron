# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

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
#}}}

'''Utilities for tracking VIP message statistics at the router.'''




import gevent

from .router import UNROUTABLE, ERROR, INCOMING

__all__ = ['Tracker']


def pick(frames, index):
    '''Return the frame at index, converted to bytes, or None.'''
    try:
        return bytes(frames[index])
    except IndexError:
        return None


def increment(prop, key):
    '''Increment or set to 1 the value in prop[key].'''
    try:
        prop[key] += 1
    except KeyError:
        prop[key] = 1


class Tracker:
    '''Object for sharing data between the router and control objects.'''

    def __init__(self):
        self._reset()
        self.enabled = False

    def reset(self):
        '''Reset all counters to default values and set start time.'''
        self._reset()
        self.stats['start'] = gevent.get_hub().loop.now()

    def _reset(self):
        '''Initialize statistics counters.'''
        self.stats = {
            'error': {'error': {}, 'peer': {}, 'user': {}, 'subsystem': {}},
            'unroutable': {'error': {}, 'peer': {}},
            'incoming': {'peer': {}, 'user': {}, 'subsystem': {}},
            'outgoing': {'peer': {}, 'user': {}, 'subsystem': {}},
        }

    def hit(self, topic, frames, extra):
        '''Increment counters for given topic and frames.'''
        if self.enabled:
            if topic == UNROUTABLE:
                stat = self.stats['unroutable']
                increment(stat['error'], extra)
            else:
                user = pick(frames, 3)
                subsystem = pick(frames, 5)
                if topic == ERROR:
                    stat = self.stats['error']
                    increment(stat['error'], bytes(extra[0]))
                else:
                    stat = self.stats[
                        'incoming' if topic == INCOMING else 'outgoing']
                increment(stat['user'], user)
                increment(stat['subsystem'], subsystem)
            increment(stat['peer'], pick(frames, 0))

    def enable(self):
        '''Enable tracking.'''
        if not self.enabled:
            self.reset()
            self.enabled = True

    def disable(self):
        '''Disable tracking.'''
        if self.enabled:
            self.enabled = False
            self.stats['end'] = gevent.get_hub().loop.now()
