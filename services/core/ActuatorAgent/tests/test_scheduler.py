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

import os
import sys
from datetime import datetime, timedelta
from dateutil.parser import parse

test_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(test_dir + '/../actuator')

from scheduler import ScheduleManager, DeviceState, PRIORITY_HIGH, PRIORITY_LOW, PRIORITY_LOW_PREEMPT

test_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(test_dir + '/../actuator')


def verify_add_task(schedule_manager, agent_id, task_id, requests, priority, now):
    schedule_manager.get_schedule_state(now)

    result = schedule_manager.request_slots(agent_id, task_id, requests, priority, now)
    schedule_manager.get_schedule_state(now)
    schedule_next_event_time = schedule_manager.get_next_event_time(now)
    return result, schedule_next_event_time


now = datetime(year=2013, month=11, day=27, hour=11, minute=30)


def test_basic():
    print('Basic Test', now)
    sch_man = ScheduleManager(60, now=now)
    ag = ('Agent1', 'Task1',
          (['campus/building/rtu1', parse('2013-11-27 12:00:00'), parse('2013-11-27 13:00:00')],),
          PRIORITY_HIGH,
          now)
    result1, event_time1 = verify_add_task(sch_man, *ag)
    success, data, info_string = result1
    assert all((success, not data, not info_string, event_time1 == parse('2013-11-27 12:00:00')))

    state = sch_man.get_schedule_state(now + timedelta(minutes=30))
    assert state == {'campus/building/rtu1': DeviceState('Agent1', 'Task1', 3600.0)}
    state = sch_man.get_schedule_state(now + timedelta(minutes=60))
    assert state == {'campus/building/rtu1': DeviceState('Agent1', 'Task1', 1800.0)}


def test_two_devices():
    print('Basic Test: Two devices', now)
    sch_man = ScheduleManager(60, now=now)
    ag = ('Agent1', 'Task1',
          (['campus/building/rtu1', parse('2013-11-27 12:00:00'), parse('2013-11-27 13:00:00')],
           ['campus/building/rtu2', parse('2013-11-27 12:00:00'), parse('2013-11-27 13:00:00')]),
          PRIORITY_HIGH,
          now)
    result1, event_time1 = verify_add_task(sch_man, *ag)
    success, data, info_string = result1
    assert all((success, not data, not info_string, event_time1 == parse('2013-11-27 12:00:00')))

    state = sch_man.get_schedule_state(now + timedelta(minutes=30))
    assert state == {
        'campus/building/rtu1': DeviceState('Agent1', 'Task1', 3600.0),
        'campus/building/rtu2': DeviceState('Agent1', 'Task1', 3600.0)}
    state = sch_man.get_schedule_state(now + timedelta(minutes=60))
    assert state == {
        'campus/building/rtu1': DeviceState('Agent1', 'Task1', 1800.0),
        'campus/building/rtu2': DeviceState('Agent1', 'Task1', 1800.0)}


def test_two_agents_two_devices():
    print('Test requests: Two agents different devices', now)
    sch_man = ScheduleManager(60, now=now)
    ag1 = ('Agent1', 'Task1',
           (['campus/building/rtu1', parse('2013-11-27 12:00:00'), parse('2013-11-27 12:30:00')],),
           PRIORITY_HIGH,
           now)
    ag2 = ('Agent2', 'Task2',
           (['campus/building/rtu2', parse('2013-11-27 12:00:00'), parse('2013-11-27 13:00:00')],),
           PRIORITY_HIGH,
           now)
    result1, event_time1 = verify_add_task(sch_man, *ag1)
    success, data, info_string = result1
    assert all((success, not data, not info_string, event_time1 == parse('2013-11-27 12:00:00')))
    result2, event_time2 = verify_add_task(sch_man, *ag2)
    success2, data2, info_string2 = result2
    assert all((success2, not data2, not info_string2, event_time2 == parse('2013-11-27 12:00:00')))

    state = sch_man.get_schedule_state(now + timedelta(minutes=30))
    assert state == {
        'campus/building/rtu1': DeviceState('Agent1', 'Task1', 1800.0),
        'campus/building/rtu2': DeviceState('Agent2', 'Task2', 3600.0)}
    state = sch_man.get_schedule_state(now + timedelta(minutes=60))
    assert state == {
        'campus/building/rtu2': DeviceState('Agent2', 'Task2', 1800.0)}


def test_touching_requests():
    print('Test touching requests: Two agents', now)
    sch_man = ScheduleManager(60, now=now)
    ag1 = ('Agent1', 'Task1',
           (['campus/building/rtu1', parse('2013-11-27 12:00:00'), parse('2013-11-27 12:30:00')],),
           PRIORITY_HIGH,
           now)
    ag2 = ('Agent2', 'Task2',
           (['campus/building/rtu1', parse('2013-11-27 12:30:00'), parse('2013-11-27 13:00:00')],),
           PRIORITY_HIGH,
           now)
    result1, event_time1 = verify_add_task(sch_man, *ag1)
    success1, data1, info_string1 = result1
    assert all((success1, not data1, not info_string1, event_time1 == parse('2013-11-27 12:00:00')))
    result2, event_time2 = verify_add_task(sch_man, *ag2)
    success2, data2, info_string2 = result2
    assert all((success2, not data2, not info_string2, event_time2 == parse('2013-11-27 12:00:00')))

    state = sch_man.get_schedule_state(now + timedelta(minutes=30))
    assert state == {'campus/building/rtu1': DeviceState('Agent1', 'Task1', 1800.0)}
    state = sch_man.get_schedule_state(now + timedelta(minutes=60))
    assert state == {'campus/building/rtu1': DeviceState('Agent2', 'Task2', 1800.0)}


def test_schedule_self_conflict():
    print('Testing self conflicting schedule', now)
    sch_man = ScheduleManager(60, now=now)
    ag = ('Agent1', 'Task1',
          (['campus/building/rtu1', parse('2013-11-27 12:00:00'), parse('2013-11-27 12:45:00')],
           ['campus/building/rtu1', parse('2013-11-27 12:30:00'), parse('2013-11-27 13:00:00')]),
          PRIORITY_HIGH,
          now)

    result1, event_time1 = verify_add_task(sch_man, *ag)
    success1, data1, info_string1 = result1
    print(not success1)
    print(data1 == {})
    print(info_string1.startswith('REQUEST_CONFLICTS_WITH_SELF'))
    assert all((not success1, data1 == {}, info_string1.startswith('REQUEST_CONFLICTS_WITH_SELF')))


def test_malformed_schedule():
    print('Testing malformed schedule: Empty', now)
    sch_man = ScheduleManager(60, now=now)
    ag = ('Agent1', 'Task1',
          (),
          PRIORITY_HIGH,
          now)

    result1, event_time1 = verify_add_task(sch_man, *ag)
    success1, data1, info_string1 = result1
    assert all((not success1, data1 == {}, info_string1.startswith('MALFORMED_REQUEST')))


def test_malformed_schdeule_bad_timestr():
    print('Testing malformed schedule: Bad time strings', now)
    sch_man = ScheduleManager(60, now=now)
    ag = ('Agent1', 'Task1',
          (['campus/building/rtu1', 'fdhkdfyug', 'Twinkle, twinkle, little bat...'],),
          PRIORITY_HIGH,
          now)

    result1, event_time1 = verify_add_task(sch_man, *ag)
    success1, data1, info_string1 = result1
    assert all((not success1, data1 == {}, info_string1.startswith('MALFORMED_REQUEST')))


def test_malformed_bad_device():
    print('Testing malformed schedule: Bad device', now)
    sch_man = ScheduleManager(60, now=now)
    ag = ('Agent1', 'Task1',
          ([1, parse('2013-11-27 12:00:00'), parse('2013-11-27 12:35:00')],),
          PRIORITY_HIGH,
          now)
    result1, event_time1 = verify_add_task(sch_man, *ag)
    success1, data1, info_string1 = result1
    assert all((not success1, data1 == {}, info_string1.startswith('MALFORMED_REQUEST')))


def test_schedule_conflict():
    print('Test conflicting requests: Two agents', now)
    sch_man = ScheduleManager(60, now=now)
    ag1 = ('Agent1', 'Task1',
           (['campus/building/rtu1', parse('2013-11-27 12:00:00'), parse('2013-11-27 12:35:00')],),
           PRIORITY_HIGH,
           now)
    ag2 = ('Agent2', 'Task2',
           (['campus/building/rtu1', parse('2013-11-27 12:30:00'), parse('2013-11-27 13:00:00')],),
           PRIORITY_HIGH,
           now)
    result1, event_time1 = verify_add_task(sch_man, *ag1)
    success1, data1, info_string1 = result1

    assert all((success1, not data1, not info_string1, event_time1 == parse('2013-11-27 12:00:00')))
    result2, event_time2 = verify_add_task(sch_man, *ag2)
    success2, data2, info_string2 = result2
    conflicts2 = data2
    assert not success2
    assert conflicts2 == {'Agent1': {'Task1': [
        ['campus/building/rtu1', '2013-11-27 12:00:00', '2013-11-27 12:35:00']]}}


def test_conflict_override():
    print('Test conflicting requests: Agent2 overrides Agent1', now)
    sch_man = ScheduleManager(60, now=now)
    ag1 = ('Agent1', 'Task1',
           (['campus/building/rtu1', parse('2013-11-27 12:00:00'), parse('2013-11-27 12:35:00')],),
           PRIORITY_LOW,
           now)
    ag2 = ('Agent2', 'Task2',
           (['campus/building/rtu1', parse('2013-11-27 12:30:00'), parse('2013-11-27 13:00:00')],),
           PRIORITY_HIGH,
           now)
    result1, event_time1 = verify_add_task(sch_man, *ag1)
    success1, data1, info_string1 = result1
    assert all((success1, not data1, not info_string1, event_time1 == parse('2013-11-27 12:00:00')))
    result2, event_time2 = verify_add_task(sch_man, *ag2)
    success2, data2, info_string2 = result2
    assert success2
    assert data2 == {('Agent1', 'Task1')}
    assert not info_string2
    assert event_time2 == parse('2013-11-27 12:30:00')


def test_conflict_override_fail_on_running_agent():
    print('Test conflicting requests: Agent2 fails to override running Agent1', now)
    sch_man = ScheduleManager(60, now=now)
    ag1 = ('Agent1', 'Task1',
           (['campus/building/rtu1', parse('2013-11-27 12:00:00'), parse('2013-11-27 12:35:00')],),
           PRIORITY_LOW,
           now)
    ag2 = ('Agent2', 'Task2',
           (['campus/building/rtu1', parse('2013-11-27 12:30:00'), parse('2013-11-27 13:00:00')],),
           PRIORITY_HIGH,
           now + timedelta(minutes=45))
    result1, event_time1 = verify_add_task(sch_man, *ag1)
    success1, data1, info_string1 = result1

    assert all((success1, not data1, not info_string1, event_time1 == parse('2013-11-27 12:00:00')))
    result2, event_time2 = verify_add_task(sch_man, *ag2)
    success2, data2, info_string2 = result2
    conflicts2 = data2
    assert not success2
    assert conflicts2 == {'Agent1': {'Task1': [
        ['campus/building/rtu1', '2013-11-27 12:00:00', '2013-11-27 12:35:00']]}}


def test_conflict_override_success_running_agent():
    print('Test conflicting requests: Agent2 overrides running Agent1', now)
    sch_man = ScheduleManager(60, now=now)
    ag1 = ('Agent1', 'Task1',
           (['campus/building/rtu1', parse('2013-11-27 12:00:00'), parse('2013-11-27 12:35:00')],),
           PRIORITY_LOW_PREEMPT,
           now)
    now2 = now + timedelta(minutes=45)
    ag2 = ('Agent2', 'Task2',
           (['campus/building/rtu1', parse('2013-11-27 12:05:00'), parse('2013-11-27 13:00:00')],),
           PRIORITY_HIGH,
           now2)
    result1, event_time1 = verify_add_task(sch_man, *ag1)
    success1, data1, info_string1 = result1
    assert all((success1, not data1, not info_string1, event_time1 == parse('2013-11-27 12:00:00')))
    result2, event_time2 = verify_add_task(sch_man, *ag2)
    success2, data2, info_string2 = result2
    assert success2
    assert data2 == {('Agent1', 'Task1')}
    assert info_string2 == ''
    assert event_time2 == parse('2013-11-27 12:16:00')

    state = sch_man.get_schedule_state(now2 + timedelta(seconds=30))
    assert state == {'campus/building/rtu1': DeviceState('Agent1', 'Task1', 30.0)}
    state = sch_man.get_schedule_state(now2 + timedelta(seconds=60))
    assert state == {'campus/building/rtu1': DeviceState('Agent2', 'Task2', 2640.0)}


def test_conflict_override_error():
    print('Test conflicting requests: Agent2 fails to override running Agent1 because of non high priority.', now)
    sch_man = ScheduleManager(60, now=now)
    ag1 = ('Agent1', 'Task1',
           (['campus/building/rtu1', parse('2013-11-27 12:00:00'), parse('2013-11-27 12:35:00')],),
           PRIORITY_LOW_PREEMPT,
           now)
    ag2 = ('Agent2', 'Task2',
           (['campus/building/rtu1', parse('2013-11-27 12:30:00'), parse('2013-11-27 13:00:00')],),
           PRIORITY_LOW,
           now)
    result1, event_time1 = verify_add_task(sch_man, *ag1)
    success1, data1, info_string1 = result1
    assert all((success1, not data1, not info_string1, event_time1 == parse('2013-11-27 12:00:00')))
    result2, event_time2 = verify_add_task(sch_man, *ag2)
    success2, data2, info_string2 = result2
    conflicts2 = data2
    assert not success2
    assert conflicts2 == {'Agent1': {'Task1': [
        ['campus/building/rtu1', '2013-11-27 12:00:00', '2013-11-27 12:35:00']]}}


def test_non_conflict_schedule():
    print(
        'Test non-conflicting requests: Agent2 and Agent1 live in harmony',
        now)
    sch_man = ScheduleManager(60, now=now)
    ag1 = ('Agent1', 'Task1',
           (['campus/building/rtu1', parse('2013-11-27 12:00:00'), parse('2013-11-27 12:15:00')],
            ['campus/building/rtu2', parse('2013-11-27 12:00:00'), parse('2013-11-27 13:00:00')],
            ['campus/building/rtu3', parse('2013-11-27 12:45:00'), parse('2013-11-27 13:00:00')],),
           PRIORITY_LOW_PREEMPT,
           now)
    now2 = now + timedelta(minutes=55)
    ag2 = ('Agent2', 'Task2',
           (['campus/building/rtu1', parse('2013-11-27 12:30:00'), parse('2013-11-27 13:00:00')],),
           PRIORITY_HIGH,
           now2)
    result1, event_time1 = verify_add_task(sch_man, *ag1)
    success1, data1, info_string1 = result1
    assert all((success1, not data1, not info_string1, event_time1 == parse('2013-11-27 12:00:00')))
    result2, event_time2 = verify_add_task(sch_man, *ag2)
    success2, data2, info_string2 = result2
    assert success2
    assert not data2
    assert info_string2 == ''
    assert event_time2 == parse('2013-11-27 12:30:00')


def test_conflict_override_success_running_agent2():
    print('Test conflicting requests: '
          'Agent2 overrides running Agent1 which has more than one device',
          now)
    sch_man = ScheduleManager(60, now=now)
    ag1 = ('Agent1', 'Task1',
           (['campus/building/rtu1', parse('2013-11-27 12:00:00'), parse('2013-11-27 12:15:00')],
            ['campus/building/rtu2', parse('2013-11-27 12:00:00'), parse('2013-11-27 13:00:00')],
            ['campus/building/rtu3', parse('2013-11-27 12:45:00'), parse('2013-11-27 13:00:00')],),
           PRIORITY_LOW_PREEMPT,
           now)
    now2 = now + timedelta(minutes=55)
    ag2 = ('Agent2', 'Task2',
           (['campus/building/rtu3', parse('2013-11-27 12:30:00'), parse('2013-11-27 13:00:00')],),
           PRIORITY_HIGH,
           now2)
    result1, event_time1 = verify_add_task(sch_man, *ag1)
    success1, data1, info_string1 = result1
    assert all((success1, not data1, not info_string1, event_time1 == parse('2013-11-27 12:00:00')))
    result2, event_time2 = verify_add_task(sch_man, *ag2)
    success2, data2, info_string2 = result2
    assert success2
    assert data2 == {('Agent1', 'Task1')}
    assert info_string2 == ''
    assert event_time2 == parse('2013-11-27 12:26:00')
