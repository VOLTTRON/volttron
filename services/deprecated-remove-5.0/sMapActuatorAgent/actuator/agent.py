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


import datetime
import sys
import time
import logging

from collections import OrderedDict
from dateutil.rrule import DAILY, rruleset, rrule

import requests

from volttron.platform.agent import BaseAgent, PublishMixin
from volttron.platform.agent import matching, utils
from volttron.platform.agent.utils import jsonapi
from volttron.platform.messaging import topics
from volttron.platform.agent import utils
from volttron.platform.messaging.utils import normtopic
from volttron.platform.agent.sched import EventWithTime
from scheduler import ScheduleManager



VALUE_RESPONSE_PREFIX = topics.ACTUATOR_VALUE()
ERROR_RESPONSE_PREFIX = topics.ACTUATOR_ERROR()

SCHEDULE_ACTION_NEW = 'NEW_SCHEDULE'
SCHEDULE_ACTION_CANCEL = 'CANCEL_SCHEDULE'

SCHEDULE_RESPONSE_SUCCESS = 'SUCCESS'
SCHEDULE_RESPONSE_FAILURE = 'FAILURE'

SCHEDULE_CANCEL_PREEMPTED = 'PREEMPTED'

ACTUATOR_COLLECTION = 'actuators'


utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.1'

def ActuatorAgent(config_path, **kwargs):
    config = utils.load_config(config_path)
    url = config['url']
    schedule_publish_interval = int(config.get('schedule_publish_interval', 60))
    heartbeat_interval = int(config.get('heartbeat_interval', 60))
    points = config.get('points', {})
    schedule_state_file = config.get('schedule_state_file')
    preempt_grace_time = config.get('preempt_grace_time', 60)
    minimum_slot_time = config.get('preempt_grace_time', preempt_grace_time*2)
    connection_timeout=config.get('connection-timeout', 10)
    
    class Agent(PublishMixin, BaseAgent):
        '''Agent to listen for requests to talk to the sMAP driver.'''

        def __init__(self, **kwargs):
            super(Agent, self).__init__(**kwargs)
            
            self._update_event = None
            self._update_event_time = None
            self._device_states = {}
            
            self.setup_schedule()
            
            self.setup_heartbeats()
            
        def setup_heartbeats(self):
            for point in points:
                heartbeat_point = points[point].get("heartbeat_point")
                if heartbeat_point is None:
                    continue
                
                heartbeat_handler = self.heartbeat_factory(point, heartbeat_point)
                self.periodic_timer(heartbeat_interval, heartbeat_handler)
        
        def heartbeat_factory(self, point, actuator):
            #Stupid lack on nonlocal in 2.x
            value = [False]
            request_url = '/'.join([url, point,
                                    ACTUATOR_COLLECTION, actuator])
            
            publish_topic = '/'.join([point, actuator])
            
            def update_heartbeat_value():
                _log.debug('update_heartbeat')
                value[0] = not value[0]
                payload = {'state': str(int(value[0]))}
                try:
                    _log.debug('About to publish actuation')
                    r = requests.put(request_url, params=payload, timeout=connection_timeout)
                    self.process_smap_request_result(r, publish_topic, None)
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as ex:
                    print "Warning: smap driver not running."
                    _log.error("Connection error: "+str(ex))
            
            return update_heartbeat_value
        
        def setup_schedule(self):
            now = datetime.datetime.now()
            self._schedule_manager = ScheduleManager(preempt_grace_time, now=now,
                                                     state_file_name=schedule_state_file)
            
            self.update_device_state_and_schedule(now)
            
        def update_device_state_and_schedule(self, now):
            _log.debug("update_device_state_and schedule")
            self._device_states = self._schedule_manager.get_schedule_state(now)
            schedule_next_event_time = self._schedule_manager.get_next_event_time(now)
            new_update_event_time = self._get_ajusted_next_event_time(now, schedule_next_event_time)
            
            for device, state in self._device_states.iteritems():
                header = self.get_headers(state.agent_id, time=str(now), task_id=state.task_id)
                header['window'] = state.time_remaining
                topic = topics.ACTUATOR_SCHEDULE_ANNOUNCE_RAW.replace('{device}', device)
                self.publish_json(topic, header, {})
                
            if self._update_event is not None:
                #This won't hurt anything if we are canceling ourselves.
                self._update_event.cancel()
            self._update_event_time = new_update_event_time
            self._update_event = EventWithTime(self._update_schedule_state)
            self.schedule(self._update_event_time, self._update_event)  
            
            
        def _get_ajusted_next_event_time(self, now, next_event_time):
            _log.debug("_get_adjusted_next_event_time")
            latest_next = now + datetime.timedelta(seconds=schedule_publish_interval)
            #Round to the next second to fix timer goofyness in agent timers.
            if latest_next.microsecond:
                latest_next = latest_next.replace(microsecond=0) + datetime.timedelta(seconds=1)
            if next_event_time is None or latest_next < next_event_time:
                return latest_next
            return next_event_time
        
            
        def _update_schedule_state(self, unix_time):
            #Find the current slot and update the state
            now = datetime.datetime.fromtimestamp(unix_time)
            
            self.update_device_state_and_schedule(now)
                            

        @matching.match_regex(topics.ACTUATOR_GET() + '/(.+)')
        def handle_get(self, topic, headers, message, match):
            point = match.group(1)
            collection_tokens, point_name = point.rsplit('/', 1)
            requester = headers.get('requesterID')
            if self.check_lock(collection_tokens, requester):
                request_url = '/'.join([url, collection_tokens,
                                        ACTUATOR_COLLECTION, point_name])
                try:
                    r = requests.get(request_url, timeout=connection_timeout)
                    self.process_smap_request_result(r, point, requester)
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as ex:
                    error = {'type': ex.__class__.__name__, 'value': str(ex)}
                    self.push_result_topic_pair(ERROR_RESPONSE_PREFIX,
                                                point, headers, error)
            else:
                error = {'type': 'LockError',
                         'value': 'does not have this lock'}
                self.push_result_topic_pair(ERROR_RESPONSE_PREFIX, point,
                                            headers, error)

        @matching.match_regex(topics.ACTUATOR_SET() + '/(.+)')
        def handle_set(self, topic, headers, message, match):
            _log.debug('handle_set: {topic},{headers}, {message}'.
                       format(topic=topic, headers=headers, message=message))
            point = match.group(1)
            collection_tokens, point_name = point.rsplit('/', 1)
            requester = headers.get('requesterID')
            headers = self.get_headers(requester)
            if not message:
                error = {'type': 'ValueError', 'value': 'missing argument'}
                _log.debug('ValueError: '+str(error))
                self.push_result_topic_pair(ERROR_RESPONSE_PREFIX,
                                            point, headers, error)
                return
            else:
                try:
                    message = jsonapi.loads(message[0])
                    if isinstance(message, bool):
                        message = int(message)
                except ValueError as ex:
                    # Could be ValueError of JSONDecodeError depending
                    # on if simplesjson was used.  JSONDecodeError
                    # inherits from ValueError
                    _log.debug('ValueError: '+message)
                    error = {'type': 'ValueError', 'value': str(ex)}
                    self.push_result_topic_pair(ERROR_RESPONSE_PREFIX,
                                                point, headers, error)
                    return

            if self.check_lock(collection_tokens, requester):
                request_url = '/'.join([url, collection_tokens,
                                        ACTUATOR_COLLECTION, point_name])
                payload = {'state': str(message)}
                try:
                    r = requests.put(request_url, params=payload, timeout=connection_timeout)
                    self.process_smap_request_result(r, point, requester)
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as ex:
                    
                    error = {'type': ex.__class__.__name__, 'value': str(ex)}
                    self.push_result_topic_pair(ERROR_RESPONSE_PREFIX,
                                                point, headers, error)
                    _log.debug('ConnectionError: '+str(error))
            else:
                error = {'type': 'LockError',
                         'value': 'does not have this lock'}
                _log.debug('LockError: '+str(error))
                self.push_result_topic_pair(ERROR_RESPONSE_PREFIX,
                                            point, headers, error)

        def check_lock(self, device, requester):
            _log.debug('check_lock: {device}, {requester}'.format(device=device, 
                                                                  requester=requester))
            device = device.strip('/')
            if device in self._device_states:
                device_state = self._device_states[device]
                return device_state.agent_id == requester
            return False

        @matching.match_exact(topics.ACTUATOR_SCHEDULE_REQUEST())
        def handle_schedule_request(self, topic, headers, message, match):
            request_type = headers.get('type')
            now = datetime.datetime.now()
            _log.debug('handle_schedule_request: {topic}, {headers}, {message}'.
                       format(topic=topic, headers=str(headers), message=str(message)))
            
            if request_type == SCHEDULE_ACTION_NEW:
                self.handle_new(headers, message, now)
                
            elif request_type == SCHEDULE_ACTION_CANCEL:
                self.handle_cancel(headers, now)
                
            else:
                _log.debug('handle-schedule_request, invalid request type')
                self.publish_json(topics.ACTUATOR_SCHEDULE_RESULT(), headers,
                                  {'result':SCHEDULE_RESPONSE_FAILURE, 
                                   'data': {},
                                   'info': 'INVALID_REQUEST_TYPE'})
            
            
        def handle_new(self, headers, message, now):
            requester = headers.get('requesterID')
            taskID = headers.get('taskID')
            priority = headers.get('priority')
            
            _log.debug("Got new schedule request: {headers}, {message}".
                       format(headers = str(headers), message = str(message)))
            
            try:
                requests = jsonapi.loads(message[0])
            except (ValueError, IndexError) as ex:
                # Could be ValueError of JSONDecodeError depending
                # on if simplesjson was used.  JSONDecodeError
                # inherits from ValueError
                
                #We let the schedule manager tell us this is a bad request.
                _log.error('bad request: {request}, {error}'.format(request=requests, error=str(ex)))
                requests = []
                
            
            result = self._schedule_manager.request_slots(requester, taskID, requests, priority, now)
            success = SCHEDULE_RESPONSE_SUCCESS if result.success else SCHEDULE_RESPONSE_FAILURE
            
            #If we are successful we do something else with the real result data
            data = result.data if not result.success else {}
            
            topic = topics.ACTUATOR_SCHEDULE_RESULT()
            headers = self.get_headers(requester, task_id=taskID)
            headers['type'] = SCHEDULE_ACTION_NEW
            self.publish_json(topic, headers, {'result':success, 
                                               'data': data, 
                                               'info':result.info_string})
            
            #Dealing with success and other first world problems.
            if result.success:
                self.update_device_state_and_schedule(now)
                for preempted_task in result.data:
                    topic = topics.ACTUATOR_SCHEDULE_RESULT()
                    headers = self.get_headers(preempted_task[0], task_id=preempted_task[1])
                    headers['type'] = SCHEDULE_ACTION_CANCEL
                    self.publish_json(topic, headers, {'result':SCHEDULE_CANCEL_PREEMPTED,
                                                       'info': '',
                                                       'data':{'agentID': requester,
                                                               'taskID': taskID}})
                    
                    
        def handle_cancel(self, headers, now):
            requester = headers.get('requesterID')
            taskID = headers.get('taskID')
            
            result = self._schedule_manager.cancel_task(requester, taskID, now)
            success = SCHEDULE_RESPONSE_SUCCESS if result.success else SCHEDULE_RESPONSE_FAILURE
            
            topic = topics.ACTUATOR_SCHEDULE_RESULT()
            self.publish_json(topic, headers, {'result':success,  
                                               'info': result.info_string,
                                               'data':{}})
            
            if result.success:
                self.update_device_state_and_schedule(now)            
            

        def get_headers(self, requester, time=None, task_id=None):
            headers = {}
            if time is not None:
                headers['time'] = time
            else:
                headers = {'time': str(datetime.datetime.utcnow())}
            if requester is not None:
                headers['requesterID'] = requester
            if task_id is not None:
                headers['taskID'] = task_id
            return headers

        def process_smap_request_result(self, request, point, requester):
            _log.debug('Start of process_smap: \n{request}, \n{point}, \n{requester}'.
                       format(request=request,point=point,requester=requester))
            headers = self.get_headers(requester)
            try:
                
                request.raise_for_status()
                results = request.json()
                readings = results['Readings']
                _log.debug('Readings: {readings}'.format(readings=readings))
                reading = readings[0][1]
                self.push_result_topic_pair(VALUE_RESPONSE_PREFIX,
                                            point, headers, reading)
            except requests.exceptions.HTTPError as ex:
                error = {'type': ex.__class__.__name__, 'value': str(request.text)}
                _log.error('process_smap HTTPError: '+str(error))
                self.push_result_topic_pair(ERROR_RESPONSE_PREFIX,
                                            point, headers, error)
            except (ValueError, IndexError, KeyError,
                        requests.exceptions.ConnectionError) as ex:
                error = {'type': ex.__class__.__name__, 'value': str(ex)}
                _log.error('process_smap RequestError: '+str(error))
                self.push_result_topic_pair(ERROR_RESPONSE_PREFIX,
                                            point, headers, error)
                
            _log.debug('End of process_smap: \n{request}, \n{point}, \n{requester}'.
                       format(request=request,point=point,requester=requester))

        def push_result_topic_pair(self, prefix, point, headers, *args):
            topic = normtopic('/'.join([prefix, point]))
            self.publish_json(topic, headers, *args)

    Agent.__name__ = 'ActuatorAgent'
    return Agent(**kwargs)


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(ActuatorAgent,
                       description='Example VOLTTRON platform™ actuator agent',
                       argv=argv)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
