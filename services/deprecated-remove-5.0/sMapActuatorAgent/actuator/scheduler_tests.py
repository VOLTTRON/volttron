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

from scheduler import ScheduleManager, DeviceState, PRIORITY_HIGH, PRIORITY_LOW, PRIORITY_LOW_PREEMPT
from datetime import datetime, timedelta
from dateutil.parser import parse 

import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Test the scheduler.')
    parser.add_argument('--verbose', '-v', action='store_true', default=False,
                        help = 'Verbose test output.')
    args = parser.parse_args()
    
    verbose = args.verbose
    
    def print_task(agent_id, requests, priority):
        print 'Agent:', agent_id
        print 'Priority:', priority
        print 'Request List:'
        for request in requests:
            print ' ', request
        print  
        
    def print_state(state):
        print 'Schedule state:'
        for device_name, device_state in state.items():
            print ' ', device_name, ' '.join(str(x) for x in device_state)  
        
    def print_add_task_result(result):
        success, data, info_string = result
        print 'Success:', success
#         print 'Task ID:', result.task_id
        print 'Data: ', data
        print 'Info:', info_string
        if success:
            event_time, preemted_task_ids, state = data
            print 'Next event time:', event_time
            print 'Preempted task IDs: ', ' '.join(str(x) for x in preemted_task_ids)
            print_state(state)
            
            
        else:
            if result.data:
                print 'Conflicts:'
                for agent, conflict in result.data.iteritems():
                    print ' ', agent, '->', conflict
            
    def test_add_task(schedule_manager, agent_id, task_id, requests, priority, now):
        if verbose:
            print_task(agent_id, requests, priority)
        state = schedule_manager.get_schedule_state(now)
        
        result = schedule_manager.request_slots(agent_id, task_id, requests, priority, now)
        schedule_manager.get_schedule_state(now)
        schedule_next_event_time = schedule_manager.get_next_event_time(now)
        if verbose:
            print_add_task_result(result)
        return result, schedule_next_event_time
    
    def print_test_header(name, time):
        if verbose:
            print
            print '**************************'
            print name
            print 'Start time:', time
            print '**************************'
            print
        else:
            print name
        
    
    
    now = datetime(year=2013, month=11, day=27, hour=11, minute=30)
    
    
    print_test_header('Basic Test', now)
    sch_man = ScheduleManager(60, now=now)
    ag = ('Agent1', 'Task1',
          (['campus/building/rtu1','2013-11-27 12:00:00','2013-11-27 13:00:00'],),
          PRIORITY_HIGH,
          now)    
    result1, event_time1= test_add_task(sch_man, *ag)
    success, data, info_string = result1
#     success1, data1, info_string1 = result1
    assert all((success, not data, not info_string, event_time1 == parse('2013-11-27 12:00:00')))
#   dict: {'campus/building/rtu1': DeviceState(agent_id='Agent1', task_id='Task1', time_remaining=3600.0)}    
    
    state = sch_man.get_schedule_state(now + timedelta(minutes=30))
    assert state == {'campus/building/rtu1': DeviceState('Agent1', 'Task1', 3600.0)}
    state = sch_man.get_schedule_state(now + timedelta(minutes=60))
    assert state == {'campus/building/rtu1': DeviceState('Agent1', 'Task1', 1800.0)}
        
    
    print_test_header('Basic Test: Two devices', now)
    sch_man = ScheduleManager(60, now=now)
    ag = ('Agent1', 'Task1',
          (['campus/building/rtu1','2013-11-27 12:00:00','2013-11-27 13:00:00'],
          ['campus/building/rtu2','2013-11-27 12:00:00','2013-11-27 13:00:00']),
          PRIORITY_HIGH,
          now)
    result1, event_time1= test_add_task(sch_man, *ag)
    success, data, info_string = result1
    assert all((success, not data, not info_string, event_time1 == parse('2013-11-27 12:00:00')))
    
    state = sch_man.get_schedule_state(now + timedelta(minutes=30))
    assert state == {'campus/building/rtu1': DeviceState('Agent1', 'Task1', 3600.0),
                     'campus/building/rtu2': DeviceState('Agent1', 'Task1', 3600.0)}
    state = sch_man.get_schedule_state(now + timedelta(minutes=60))
    assert state == {'campus/building/rtu1': DeviceState('Agent1', 'Task1', 1800.0),
                     'campus/building/rtu2': DeviceState('Agent1', 'Task1', 1800.0)}
 
 
    print_test_header('Test requests: Two agents different devices', now) 
    sch_man = ScheduleManager(60, now=now)      
    ag1 = ('Agent1','Task1',
          (['campus/building/rtu1','2013-11-27 12:00:00','2013-11-27 12:30:00'],),
          PRIORITY_HIGH,
          now)    
    ag2 = ('Agent2','Task2',
          (['campus/building/rtu2','2013-11-27 12:00:00','2013-11-27 13:00:00'],),
          PRIORITY_HIGH,
          now)
    result1, event_time1 = test_add_task(sch_man, *ag1)
    success1, data1, info_string1 = result1
    success, data, info_string = result1
#     success1, data1, info_string1 = result1
    assert all((success, not data, not info_string, event_time1 == parse('2013-11-27 12:00:00')))
    result2, event_time2 = test_add_task(sch_man, *ag2)
    success2, data2, info_string2 = result2
    assert all((success2, not data2, not info_string2, event_time2 == parse('2013-11-27 12:00:00')))
    
    state = sch_man.get_schedule_state(now + timedelta(minutes=30))
    assert state == {'campus/building/rtu1': DeviceState('Agent1', 'Task1', 1800.0),
                     'campus/building/rtu2': DeviceState('Agent2', 'Task2', 3600.0)}
    state = sch_man.get_schedule_state(now + timedelta(minutes=60))
    assert state == {'campus/building/rtu2': DeviceState('Agent2', 'Task2', 1800.0)}

        
    print_test_header('Test touching requests: Two agents', now) 
    sch_man = ScheduleManager(60, now=now)      
    ag1 = ('Agent1','Task1',
          (['campus/building/rtu1','2013-11-27 12:00:00','2013-11-27 12:30:00'],),
          PRIORITY_HIGH,
          now)    
    ag2 = ('Agent2','Task2',
          (['campus/building/rtu1','2013-11-27 12:30:00','2013-11-27 13:00:00'],),
          PRIORITY_HIGH,
          now)
    result1, event_time1 = test_add_task(sch_man, *ag1)
    success1, data1, info_string1 = result1
    assert all((success1, not data1, not info_string1, event_time1 == parse('2013-11-27 12:00:00')))
    result2, event_time2 = test_add_task(sch_man, *ag2)
    success2, data2, info_string2 = result2
    assert all((success2, not data2, not info_string2, event_time2 == parse('2013-11-27 12:00:00')))
    
    state = sch_man.get_schedule_state(now + timedelta(minutes=30))
    assert state == {'campus/building/rtu1': DeviceState('Agent1', 'Task1', 1800.0)}
    state = sch_man.get_schedule_state(now + timedelta(minutes=60))
    assert state == {'campus/building/rtu1': DeviceState('Agent2', 'Task2', 1800.0)}
       

    print_test_header('Testing self conflicting schedule', now)  
    sch_man = ScheduleManager(60, now=now)  
    ag = ('Agent1','Task1',
          (['campus/building/rtu1','2013-11-27 12:00:00','2013-11-27 12:45:00'],
          ['campus/building/rtu1','2013-11-27 12:30:00','2013-11-27 13:00:00']),
          PRIORITY_HIGH,
          now)
    
    result1, event_time1 = test_add_task(sch_man, *ag)
    success1, data1, info_string1 = result1 
    print (not success1)
    print (data1 == {})
    print (info_string1.startswith('REQUEST_CONFLICTS_WITH_SELF'))
    assert all((not success1, data1 == {}, info_string1.startswith('REQUEST_CONFLICTS_WITH_SELF')))
    
    print_test_header('Testing malformed schedule: Empty', now)  
    sch_man = ScheduleManager(60, now=now)  
    ag = ('Agent1','Task1',
          (),
          PRIORITY_HIGH,
          now)
    
    result1, event_time1 = test_add_task(sch_man, *ag)
    success1, data1, info_string1 = result1
    assert all((not success1, data1 == {}, info_string1.startswith('MALFORMED_REQUEST')))
    
    
    print_test_header('Testing malformed schedule: Bad time strings', now)  
    sch_man = ScheduleManager(60, now=now)  
    ag = ('Agent1','Task1',
          (['campus/building/rtu1','fdhkdfyug', 'Twinkle, twinkle, little bat...'],),
          PRIORITY_HIGH,
          now)
    
    result1, event_time1 = test_add_task(sch_man, *ag)
    success1, data1, info_string1 = result1
    assert all((not success1, data1 == {}, info_string1.startswith('MALFORMED_REQUEST')))
    
        
    print_test_header('Testing malformed schedule: Bad device', now)  
    sch_man = ScheduleManager(60, now=now)  
    ag = ('Agent1','Task1',
          ([1,'2013-11-27 12:00:00','2013-11-27 12:35:00'],),
          PRIORITY_HIGH,
          now)
    result1, event_time1 = test_add_task(sch_man, *ag)
    success1, data1, info_string1 = result1
    assert all((not success1, data1 == {}, info_string1.startswith('MALFORMED_REQUEST')))
    
    
    print_test_header('Test conflicting requests: Two agents', now)
    sch_man = ScheduleManager(60, now=now)    
    ag1 = ('Agent1','Task1',
          (['campus/building/rtu1','2013-11-27 12:00:00','2013-11-27 12:35:00'],),
          PRIORITY_HIGH,
          now)    
    ag2 = ('Agent2','Task2',
          (['campus/building/rtu1','2013-11-27 12:30:00','2013-11-27 13:00:00'],),
          PRIORITY_HIGH,
          now)
    result1, event_time1 = test_add_task(sch_man, *ag1)
    success1, data1, info_string1 = result1
    
    assert all((success1, not data1, not info_string1, event_time1 == parse('2013-11-27 12:00:00')))
    result2, event_time2 = test_add_task(sch_man, *ag2)
    success2, data2, info_string2 = result2
    conflicts2 = data2
    assert not success2
    assert conflicts2 == {'Agent1':{'Task1': [['campus/building/rtu1','2013-11-27 12:00:00','2013-11-27 12:35:00']]}}

    
    print_test_header('Test conflicting requests: Agent2 overrides Agent1', now)    
    sch_man = ScheduleManager(60, now=now)
    ag1 = ('Agent1','Task1',
          (['campus/building/rtu1','2013-11-27 12:00:00','2013-11-27 12:35:00'],),
          PRIORITY_LOW,
          now)    
    ag2 = ('Agent2','Task2',
          (['campus/building/rtu1','2013-11-27 12:30:00','2013-11-27 13:00:00'],),
          PRIORITY_HIGH,
          now)
    result1, event_time1 = test_add_task(sch_man, *ag1)
    success1, data1, info_string1 = result1
    success1, data1, info_string1 = result1
    assert all((success1, not data1, not info_string1, event_time1 == parse('2013-11-27 12:00:00')))
    result2, event_time2 = test_add_task(sch_man, *ag2)
    success2, data2, info_string2 = result2
    assert success2
    assert data2 == set([('Agent1', 'Task1')])
    assert not info_string2
    assert event_time2 == parse('2013-11-27 12:30:00')
    
    print_test_header('Test conflicting requests: Agent2 fails to override running Agent1', now)    
    sch_man = ScheduleManager(60, now=now)
    ag1 = ('Agent1','Task1',
          (['campus/building/rtu1','2013-11-27 12:00:00','2013-11-27 12:35:00'],),
          PRIORITY_LOW,
          now)    
    ag2 = ('Agent2','Task2',
          (['campus/building/rtu1','2013-11-27 12:30:00','2013-11-27 13:00:00'],),
          PRIORITY_HIGH,
          now+timedelta(minutes=45))
    result1, event_time1 = test_add_task(sch_man, *ag1)
    success1, data1, info_string1 = result1
    
    assert all((success1, not data1, not info_string1, event_time1 == parse('2013-11-27 12:00:00')))
    result2, event_time2 = test_add_task(sch_man, *ag2)
    success2, data2, info_string2 = result2
    conflicts2 = data2
    assert not success2
    assert conflicts2 == {'Agent1':{'Task1': [['campus/building/rtu1','2013-11-27 12:00:00','2013-11-27 12:35:00']]}}

    
    print_test_header('Test conflicting requests: Agent2 overrides running Agent1', now)    
    sch_man = ScheduleManager(60, now=now)
    ag1 = ('Agent1','Task1',
          (['campus/building/rtu1','2013-11-27 12:00:00','2013-11-27 12:35:00'],),
          PRIORITY_LOW_PREEMPT,
          now)    
    now2 = now+timedelta(minutes=45)
    ag2 = ('Agent2','Task2',
          (['campus/building/rtu1','2013-11-27 12:05:00','2013-11-27 13:00:00'],),
          PRIORITY_HIGH,
          now2)
    result1, event_time1 = test_add_task(sch_man, *ag1)
    success1, data1, info_string1 = result1
    assert all((success1, not data1, not info_string1, event_time1 == parse('2013-11-27 12:00:00')))
    result2, event_time2 = test_add_task(sch_man, *ag2)
    success2, data2, info_string2 = result2
    assert success2
    assert data2 == set([('Agent1','Task1')])
    assert info_string2 == ''
    assert event_time2 == parse('2013-11-27 12:16:00')
    
    state = sch_man.get_schedule_state(now2 + timedelta(seconds=30))
    assert state == {'campus/building/rtu1': DeviceState('Agent1', 'Task1', 30.0)}
    state = sch_man.get_schedule_state(now2 + timedelta(seconds=60))
    assert state == {'campus/building/rtu1': DeviceState('Agent2', 'Task2', 2640.0)}
        
    print_test_header('Test conflicting requests: Agent2 fails to override running Agent1 because of non high priority.', now)    
    sch_man = ScheduleManager(60, now=now)
    ag1 = ('Agent1','Task1',
          (['campus/building/rtu1','2013-11-27 12:00:00','2013-11-27 12:35:00'],),
          PRIORITY_LOW_PREEMPT,
          now)    
    ag2 = ('Agent2','Task2',
          (['campus/building/rtu1','2013-11-27 12:30:00','2013-11-27 13:00:00'],),
          PRIORITY_LOW,
          now)
    result1, event_time1 = test_add_task(sch_man, *ag1)
    success1, data1, info_string1 = result1
    assert all((success1, not data1, not info_string1, event_time1 == parse('2013-11-27 12:00:00')))
    result2, event_time2 = test_add_task(sch_man, *ag2)
    success2, data2, info_string2 = result2
    conflicts2 = data2
    assert not success2
    assert conflicts2 == {'Agent1':{'Task1': [['campus/building/rtu1','2013-11-27 12:00:00','2013-11-27 12:35:00']]}}
        
    print_test_header('Test non-conflicting requests: Agent2 and Agent1 live in harmony', now)    
    sch_man = ScheduleManager(60, now=now)
    ag1 = ('Agent1','Task1',
          (['campus/building/rtu1','2013-11-27 12:00:00','2013-11-27 12:15:00'],
           ['campus/building/rtu2','2013-11-27 12:00:00','2013-11-27 13:00:00'],
           ['campus/building/rtu3','2013-11-27 12:45:00','2013-11-27 13:00:00'],),
          PRIORITY_LOW_PREEMPT,
          now)    
    now2 = now+timedelta(minutes=55)
    ag2 = ('Agent2','Task2',
          (['campus/building/rtu1','2013-11-27 12:30:00','2013-11-27 13:00:00'],),
          PRIORITY_HIGH,
          now2)
    result1, event_time1 = test_add_task(sch_man, *ag1)
    success1, data1, info_string1 = result1
    success1, data1, info_string1 = result1
    assert all((success1, not data1, not info_string1, event_time1 == parse('2013-11-27 12:00:00')))
    result2, event_time2 = test_add_task(sch_man, *ag2)
    success2, data2, info_string2 = result2
    assert success2
    assert not data2
    assert info_string2 == ''
    assert event_time2 == parse('2013-11-27 12:30:00')
    
    print_test_header('Test conflicting requests: Agent2 overrides running Agent1 which has more than one device', now)    
    sch_man = ScheduleManager(60, now=now)
    ag1 = ('Agent1','Task1',
          (['campus/building/rtu1','2013-11-27 12:00:00','2013-11-27 12:15:00'],
           ['campus/building/rtu2','2013-11-27 12:00:00','2013-11-27 13:00:00'],
           ['campus/building/rtu3','2013-11-27 12:45:00','2013-11-27 13:00:00'],),
          PRIORITY_LOW_PREEMPT,
          now)    
    now2 = now+timedelta(minutes=55)
    ag2 = ('Agent2','Task2',
          (['campus/building/rtu3','2013-11-27 12:30:00','2013-11-27 13:00:00'],),
          PRIORITY_HIGH,
          now2)
    result1, event_time1 = test_add_task(sch_man, *ag1)
    success1, data1, info_string1 = result1
    success1, data1, info_string1 = result1
    assert all((success1, not data1, not info_string1, event_time1 == parse('2013-11-27 12:00:00')))
    result2, event_time2 = test_add_task(sch_man, *ag2)
    success2, data2, info_string2 = result2
    assert success2
    assert data2 == set([('Agent1','Task1')])
    assert info_string2 == ''
    assert event_time2 == parse('2013-11-27 12:26:00')
