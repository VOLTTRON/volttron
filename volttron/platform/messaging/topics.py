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

'''VOLTTRON platform™ topic templates.

Templates of standard topics.  Fields in the templates are replaced by
calling the template with the field value included in the keyword
arguments.  Fields are replaced from left to right as long as a
replacement can be made.  Once a field is reached which cannot be
replaced, everything in the replaced portion up to the last double slash
is returned.  Fields cannot be skipped, but may be included
unsubstituted by using None for the field value.  Below are some
examples to demonstrate.

    >>> T = _('root/{top}//{middle}//{bottom}')
    >>> T()
    Topic(u'root')
    >>> T(top='first')
    Topic(u'root/first')
    >>> T(top='first', middle='second')
    Topic(u'root/first/second')
    >>> T(top='first', middle='second', bottom='third')
    Topic(u'root/first/second/third')
    >>> unicode(T(top='first', middle='second', bottom='third'))
    u'root/first/second/third'
    >>> T(top='first', bottom='third')
    ValueError: unused keyword argument: bottom
    >>> T(top='first', middle=None, bottom='third')
    Topic(u'root/first/{middle}/third')
    >>> T(top='first', middle=None, bottom='third')(middle='.')
    Topic(u'root/first/third')
    >>> T(top='first', middle=None, bottom='third')(middle='..')
    Topic(u'root/third')
    >>> T._(top='first', middle=None, bottom='third')
    Topic(u'root/first//{middle}//third')
'''

import os

from .utils import Topic as _


__author__ = 'Brandon Carpenter <brandon.carpenter@pnnl.gov>'
__copyright__ = 'Copyright (c) 2013, Battelle Memorial Institute'
__license__ = 'FreeBSD'


PLATFORM = _('platform/{subtopic}')
PLATFORM_SHUTDOWN = PLATFORM(subtopic='shutdown')

AGENT_SHUTDOWN = _('agent/{agent}/shutdown')
AGENT_PING = _('agent/ping/{}/{}/{{cookie}}'.format(os.uname()[1], os.getpid()))

DRIVER_TOPIC_BASE = 'devices'
DEVICES_PATH = _('{base}//{node}//{campus}//{building}//{unit}//{point}')
_DEVICES_VALUE = _(DEVICES_PATH.replace('{base}',DRIVER_TOPIC_BASE))
DEVICES_VALUE = _(_DEVICES_VALUE.replace('{node}/', ''))

ACTUATOR_GET = _(_DEVICES_VALUE.replace('{node}', 'actuators/get'))
ACTUATOR_SET = _(_DEVICES_VALUE.replace('{node}', 'actuators/set'))

_ACTUATOR_SCHEDULE = _(('{base}/actuators/schedule/{op}').replace('{base}',DRIVER_TOPIC_BASE))
ACTUATOR_SCHEDULE_REQUEST = _(_ACTUATOR_SCHEDULE.replace('{op}', 'request'))
ACTUATOR_SCHEDULE_RESULT = _(_ACTUATOR_SCHEDULE.replace('{op}', 'result'))
ACTUATOR_SCHEDULE_ANNOUNCE_RAW = _(_ACTUATOR_SCHEDULE.replace('{op}','announce/{device}'))

#This is a convenience topic for agent listening for announcements
# and want to use the {campus}//{building}//{unit} style replacement
ACTUATOR_SCHEDULE_ANNOUNCE = _(ACTUATOR_SCHEDULE_ANNOUNCE_RAW.replace('{device}','{campus}//{building}//{unit}'))

ACTUATOR_ERROR = _(_DEVICES_VALUE.replace('{node}', 'actuators/error'))
ACTUATOR_VALUE = _(_DEVICES_VALUE.replace('{node}', 'actuators/value'))

BASE_ARCHIVER_REQUEST = _('archiver/request')
BASE_ARCHIVER_FULL_REQUEST = _('archiver/full/request')
BASE_ARCHIVER_RESPONSE = _('archiver/response')

_ARCHIVER = _('{base}/{campus}//{building}//{unit}//{point}')
_ARCHIVER_UNIT = _('{base}/{campus}//{building}//{unit}')
ARCHIVER_REQUEST = _(_ARCHIVER.replace('{base}', BASE_ARCHIVER_REQUEST))
ARCHIVER_RESPONSE = _(_ARCHIVER.replace('{base}', BASE_ARCHIVER_RESPONSE))

ARCHIVER_FULL_UNIT_REQUEST = _(_ARCHIVER_UNIT.replace('{base}', BASE_ARCHIVER_FULL_REQUEST))

OPENADR_STATUS = _('openadr/status') 
OPENADR_EVENT = _('openadr/event') 

_SUBSCRIPTIONS = _('subscriptions/{op}/{{topic}}')
SUBSCRIPTIONS_LIST = _(_SUBSCRIPTIONS.format(op='list'))
SUBSCRIPTIONS_ADD = _(_SUBSCRIPTIONS.format(op='add'))
SUBSCRIPTIONS_REMOVE = _(_SUBSCRIPTIONS.format(op='remove'))

_BUILDING = _('building/{op}/{{campus}}//{{building}}//{{topic}}')
BUILDING_SEND = _(_BUILDING.format(op='send'))
BUILDING_RECV = _(_BUILDING.format(op='recv'))
BUILDING_ERROR = _(_BUILDING.format(op='error'))
