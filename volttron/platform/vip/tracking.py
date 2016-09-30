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

'''Utilities for tracking VIP message statistics at the router.'''


from __future__ import absolute_import, print_function

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


class Tracker(object):
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
