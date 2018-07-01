# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
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
__copyright__ = 'Copyright (c) 2016, Battelle Memorial Institute'
__license__ = 'FreeBSD'

ALERTS_BASE = _('alerts')
ALERTS = _('alerts/{agent_class}/{agent_uuid}') #/{agent_class}/{publickey}/{alert_key}')

HEARTBEAT = _('heartbeats')
PLATFORM_BASE = _('platform')
PLATFORM_SEND_EMAIL = _('platform/send_email')
PLATFORM = _('platform/{subtopic}')
PLATFORM_SHUTDOWN = PLATFORM(subtopic='shutdown')
PLATFORM_VCP_DEVICES = _('platforms/{platform_uuid}/devices/{topic}')

RECORD_BASE = _('record')
RECORD = _('record/{subtopic}')

MARKET_BASE = _('market/{subtopic}')
MARKET_RESERVE = _(MARKET_BASE.replace('{subtopic}', 'reserve'))
MARKET_BID = _(MARKET_BASE.replace('{subtopic}', 'bid'))
MARKET_CLEAR = _(MARKET_BASE.replace('{subtopic}', 'cleared_price'))
MARKET_AGGREGATE = _(MARKET_BASE.replace('{subtopic}', 'aggregate'))
MARKET_ERROR = _(MARKET_BASE.replace('{subtopic}', 'error'))
MARKET_RECORD = _(RECORD.replace('{subtopic}', MARKET_CLEAR))

AGENT_SHUTDOWN = _('agent/{agent}/shutdown')
AGENT_PING = _('agent/ping/{}/{}/{{cookie}}'.format(os.uname()[1], os.getpid()))

LOGGER_BASE =_('datalogger')
LOGGER = _('datalogger/{subtopic}')
LOGGER_LOG = LOGGER(subtopic='log')
LOGGER_STATUS = LOGGER(subtopic='status')

DRIVER_TOPIC_BASE = 'devices'
DRIVER_TOPIC_ALL = 'all'
DEVICES_PATH = _('{base}//{node}//{campus}//{building}//{unit}//{path!S}//{point}')
_DEVICES_VALUE = _(DEVICES_PATH.replace('{base}',DRIVER_TOPIC_BASE))
DEVICES_VALUE = _(_DEVICES_VALUE.replace('{node}/', ''))

#For use with RPC calls that require a device path. A plain device path with no prefix.
#Should be used when working with devices via the actuator agent RPC calls:
# get_point, set_point, revert_point, revert_device, and request_new_schedule.
RPC_DEVICE_PATH = _(DEVICES_PATH.replace('{base}//{node}//', ''))

ANALYSIS_PATH = _('{base}//{analysis_name}//{campus}//{building}//{unit}//{point}')
ANALYSIS_TOPIC_BASE = 'analysis'
ANALYSIS_VALUE = _(ANALYSIS_PATH.replace('{base}', ANALYSIS_TOPIC_BASE))


ACTUATOR_GET = _(_DEVICES_VALUE.replace('{node}', 'actuators/get'))
ACTUATOR_SET = _(_DEVICES_VALUE.replace('{node}', 'actuators/set'))
ACTUATOR_REVERT_POINT = _(_DEVICES_VALUE.replace('{node}', 'actuators/revert/point'))
ACTUATOR_REVERT_DEVICE = _(_DEVICES_VALUE.replace('{node}', 'actuators/revert/device'))

_ACTUATOR_SCHEDULE = _(('{base}/actuators/schedule/{op}').replace('{base}',DRIVER_TOPIC_BASE))
ACTUATOR_SCHEDULE_REQUEST = _(_ACTUATOR_SCHEDULE.replace('{op}', 'request'))
ACTUATOR_SCHEDULE_RESULT = _(_ACTUATOR_SCHEDULE.replace('{op}', 'result'))
ACTUATOR_SCHEDULE_ANNOUNCE_RAW = _(_ACTUATOR_SCHEDULE.replace('{op}','announce/{device}'))

#This is a convenience topic for agent listening for announcements
# and want to use the {campus}//{building}//{unit} style replacement
ACTUATOR_SCHEDULE_ANNOUNCE = _(ACTUATOR_SCHEDULE_ANNOUNCE_RAW.replace('{device}','{campus}//{building}//{unit}'))

# Added by CHA to be used as the root of all actuators for working within
# base_historian.py.
ACTUATOR_BASE = _('actuators')
ACTUATOR = _(_DEVICES_VALUE.replace('{node}', ACTUATOR_BASE))
ACTUATOR_ERROR = _(_DEVICES_VALUE.replace('{node}', 'actuators/error'))
ACTUATOR_VALUE = _(_DEVICES_VALUE.replace('{node}', 'actuators/value'))


#Ragardless of the interface used (RPC vs pubsub) when an agent 
# attempts to set a point it is announced on this topic.
#This is intended to inable a historian to capture all attempted writes.
ACTUATOR_WRITE = _(_DEVICES_VALUE.replace('{node}', 'actuators/write'))
ACTUATOR_REVERTED_POINT = _(_DEVICES_VALUE.replace('{node}', 'actuators/reverted/point'))
ACTUATOR_REVERTED_DEVICE = _(_DEVICES_VALUE.replace('{node}', 'actuators/reverted/device'))

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

CONFIG_TOPIC_BASE = 'config'
CONFIG_PATH = _('{base}//{action}//{category}//{name}')
_CONFIG_VALUE = _(CONFIG_PATH.replace('{base}',CONFIG_TOPIC_BASE))
CONFIG_ADD = _(_CONFIG_VALUE.replace('{action}', 'add'))
CONFIG_REMOVE = _(_CONFIG_VALUE.replace('{action}', 'remove'))
CONFIG_UPDATE = _(_CONFIG_VALUE.replace('{action}', 'update'))

DRIVER_CONFIG_ADD = _(_CONFIG_VALUE.replace('{category}', 'driver'))
DRIVER_CONFIG_REMOVE = _(_CONFIG_VALUE.replace('{category}', 'driver'))
DRIVER_CONFIG_UPDATE = _(_CONFIG_VALUE.replace('{category}', 'driver'))

WEATHER_BASE = 'weather'
WEATHER_REQUEST = 'weather/request'

WEATHER2_BASE = 'weather2'
WEATHER2_REQUEST = 'weather2/request'
WEATHER2_POLL = 'weather2/polling'
WEATHER2_RESPONSE = 'weather2/response'
WEATHER2_ERROR = 'weather2/error'

BACNET_INFO_BASE = _('bacnet/{indication}')
BACNET_I_AM = _(BACNET_INFO_BASE.replace('{indication}', 'i_am'))
