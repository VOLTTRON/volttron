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

#}}}


import datetime
import sys
import time
import logging

from volttron.platform.vip.agent import Agent, Core, RPC, PubSub
from volttron.platform.messaging import topics
from volttron.platform.agent import utils
from volttron.platform.messaging.utils import normtopic
from volttron.platform.agent.sched import EventWithTime
from actuator.scheduler import ScheduleManager

from dateutil.parser import parse 

VALUE_RESPONSE_PREFIX = topics.ACTUATOR_VALUE()
ERROR_RESPONSE_PREFIX = topics.ACTUATOR_ERROR()

WRITE_ATTEMPT_PREFIX = topics.ACTUATOR_WRITE()

SCHEDULE_ACTION_NEW = 'NEW_SCHEDULE'
SCHEDULE_ACTION_CANCEL = 'CANCEL_SCHEDULE'

SCHEDULE_RESPONSE_SUCCESS = 'SUCCESS'
SCHEDULE_RESPONSE_FAILURE = 'FAILURE'

SCHEDULE_CANCEL_PREEMPTED = 'PREEMPTED'

ACTUATOR_COLLECTION = 'actuators'


utils.setup_logging()
_log = logging.getLogger(__name__)

class LockError(StandardError):
    pass


def actuator_agent(config_path, **kwargs):
    config = utils.load_config(config_path)
    schedule_publish_interval = int(config.get('schedule_publish_interval', 60))
    schedule_state_file = config.get('schedule_state_file')
    preempt_grace_time = config.get('preempt_grace_time', 60)
    master_driver_agent_address=config.get('master_driver_agent_address')
    vip_identity = config.get('vip_identity')
    
    class ActuatorAgent(Agent):
        '''Agent to listen for requests to talk to the sMAP driver.'''

        def __init__(self, **kwargs):
            super(ActuatorAgent, self).__init__(identity=vip_identity, **kwargs)
            
            self._update_event = None
            self._device_states = {}
                    
        @RPC.export
        def heart_beat(self):
            self.vip.rpc.call(master_driver_agent_address, 'heart_beat')
        
        @Core.receiver('onstart')
        def on_start(self, sender, **kwargs):
            self.setup_schedule()
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=topics.ACTUATOR_GET(), 
                                      callback=self.handle_get)

            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=topics.ACTUATOR_SET(),
                                      callback=self.handle_set)
            
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=topics.ACTUATOR_SCHEDULE_REQUEST(), 
                                      callback=self.handle_schedule_request)
            
        
        def setup_schedule(self):
            now = datetime.datetime.now()
            self._schedule_manager = ScheduleManager(preempt_grace_time, now=now,
                                                     state_file_name=schedule_state_file)
            
            self.update_device_state_and_schedule(now)
            
        def update_device_state_and_schedule(self, now):
            _log.debug("update_device_state_and schedule")
            #Sanity check now.
            #This is specifically for when this is running in a VM that gets suspeded and then resumed.
            #If we don't make this check a resumed VM will publish one event per minute of 
            # time the VM was suspended for. 
            test_now = datetime.datetime.now()
            if test_now - now > datetime.timedelta(minutes=3):
                now = test_now
            
            self._device_states = self._schedule_manager.get_schedule_state(now)
            schedule_next_event_time = self._schedule_manager.get_next_event_time(now)
            new_update_event_time = self._get_ajusted_next_event_time(now, schedule_next_event_time)
            
            for device, state in self._device_states.iteritems():
                header = self.get_headers(state.agent_id, time=str(now), task_id=state.task_id)
                header['window'] = state.time_remaining
                topic = topics.ACTUATOR_SCHEDULE_ANNOUNCE_RAW.replace('{device}', device)
                self.vip.pubsub.publish('pubsub', topic, header=header, message={})
                
            if self._update_event is not None:
                #This won't hurt anything if we are canceling ourselves.
                self._update_event.cancel()
            self._update_event = self.core.schedule(new_update_event_time, 
                                                    self._update_schedule_state,
                                                    new_update_event_time)  
            
            
        def _get_ajusted_next_event_time(self, now, next_event_time):
            _log.debug("_get_adjusted_next_event_time")
            latest_next = now + datetime.timedelta(seconds=schedule_publish_interval)
            #Round to the next second to fix timer goofyness in agent timers.
            if latest_next.microsecond:
                latest_next = latest_next.replace(microsecond=0) + datetime.timedelta(seconds=1)
            if next_event_time is None or latest_next < next_event_time:
                return latest_next
            return next_event_time
        
            
        def _update_schedule_state(self, now):            
            self.update_device_state_and_schedule(now)
                            

        def handle_get(self, peer, sender, bus, topic, headers, message):
            point = topic.replace(topics.ACTUATOR_GET()+'/', '', 1)
            try:
                value = self.get_point(point)
                self.push_result_topic_pair(VALUE_RESPONSE_PREFIX,
                                            point, headers, value)
            except StandardError as ex:
                error = {'type': ex.__class__.__name__, 'value': str(ex)}
                self.push_result_topic_pair(ERROR_RESPONSE_PREFIX,
                                            point, headers, error)


        def handle_set(self, peer, sender, bus, topic, headers, message):
            _log.debug('handle_set: {topic},{headers}, {message}'.
                       format(topic=topic, headers=headers, message=message))
            point = topic.replace(topics.ACTUATOR_SET()+'/', '', 1)
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
                    message = message[0]
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
            
            try:
                self.set_point(requester, point, message)
            except StandardError as ex:
                
                error = {'type': ex.__class__.__name__, 'value': str(ex)}
                self.push_result_topic_pair(ERROR_RESPONSE_PREFIX,
                                            point, headers, error)
                _log.debug('Actuator Agent Error: '+str(error))
                
                
        @RPC.export        
        def get_point(self, topic):
            topic = topic.strip('/')
            path, point_name = topic.rsplit('/', 1)
            return self.vip.rpc.call(master_driver_agent_address, 'get_point', path, point_name).get()
        
        @RPC.export
        def set_point(self, requester_id, topic, value):  
            topic = topic.strip('/')
            _log.debug('handle_set: {topic},{requester_id}, {value}'.
                       format(topic=topic, requester_id=requester_id, value=value))
            
            path, point_name = topic.rsplit('/', 1)
            self.vip.rpc.call(master_driver_agent_address, 'set_point', path, point_name, value)
            
            headers = self.get_headers(requester_id)
            self.push_result_topic_pair(WRITE_ATTEMPT_PREFIX,
                                        topic, headers, value)
            
            if self.check_lock(path, requester_id):
                result = self.vip.rpc.call(master_driver_agent_address, 'set_point', path, point_name, value).get()
        
                headers = self.get_headers(requester_id)
                self.push_result_topic_pair(WRITE_ATTEMPT_PREFIX,
                                            topic, headers, value)
                self.push_result_topic_pair(VALUE_RESPONSE_PREFIX,
                                            topic, headers, result)
            else:
                raise LockError("caller does not have this lock")
                
            return result

        def check_lock(self, device, requester):
            _log.debug('check_lock: {device}, {requester}'.format(device=device, 
                                                                  requester=requester))
            device = device.strip('/')
            if device in self._device_states:
                device_state = self._device_states[device]
                return device_state.agent_id == requester
            return False

        #@PubSub.subscribe("pubsub", topics.ACTUATOR_SCHEDULE_REQUEST())
        def handle_schedule_request(self, peer, sender, bus, topic, headers, message):
            request_type = headers.get('type')
            _log.debug('handle_schedule_request: {topic}, {headers}, {message}'.
                       format(topic=topic, headers=str(headers), message=str(message)))
            
            requester_id = headers.get('requesterID')
            task_id = headers.get('taskID')
            priority = headers.get('priority')
                   
            if request_type == SCHEDULE_ACTION_NEW:
                try:
                    requests = message[0]
                except IndexError as ex:
                    # Could be ValueError of JSONDecodeError depending
                    # on if simplesjson was used.  JSONDecodeError
                    # inherits from ValueError
                    
                    #We let the schedule manager tell us this is a bad request.
                    _log.error('bad request: {request}, {error}'.format(request=requests, error=str(ex)))
                    requests = []
                
                try: 
                    self.request_new_schedule(requester_id, task_id, priority, requests)
                except StandardError as ex:
                    _log.error('bad request: {request}, {error}'.format(request=requests, error=str(ex)))
                    self.publish_json(topics.ACTUATOR_SCHEDULE_RESULT(), headers,
                                      {'result':SCHEDULE_RESPONSE_FAILURE, 
                                       'data': {},
                                       'info': 'INVALID_REQUEST_TYPE'})
                    
            elif request_type == SCHEDULE_ACTION_CANCEL:
                try:
                    self.request_cancel_schedule(requester_id, task_id)
                except StandardError as ex:
                    _log.error('bad request: {request}, {error}'.format(request=requests, error=str(ex)))
                    self.publish_json(topics.ACTUATOR_SCHEDULE_RESULT(), headers,
                                      {'result':SCHEDULE_RESPONSE_FAILURE, 
                                       'data': {},
                                       'info': 'INVALID_REQUEST_TYPE'})
                
            else:
                _log.debug('handle-schedule_request, invalid request type')
                self.publish_json(topics.ACTUATOR_SCHEDULE_RESULT(), headers,
                                  {'result':SCHEDULE_RESPONSE_FAILURE, 
                                   'data': {},
                                   'info': 'INVALID_REQUEST_TYPE'})
            
        
        @RPC.export    
        def request_new_schedule(self, requester_id, task_id, priority, requests):
            now = datetime.datetime.now()
            
            requests = [[r[0].strip('/'),parse(r[1]),parse(r[2])] for r in requests]
                
            
            _log.debug("Got new schedule request: {}, {}, {}, {}".
                       format(requester_id, task_id, priority, requests))
            
            result = self._schedule_manager.request_slots(requester_id, task_id, requests, priority, now)
            success = SCHEDULE_RESPONSE_SUCCESS if result.success else SCHEDULE_RESPONSE_FAILURE
            
            #Dealing with success and other first world problems.
            if result.success:
                self.update_device_state_and_schedule(now)
                for preempted_task in result.data:
                    topic = topics.ACTUATOR_SCHEDULE_RESULT()
                    headers = self.get_headers(preempted_task[0], task_id=preempted_task[1])
                    headers['type'] = SCHEDULE_ACTION_CANCEL
                    self.publish_json(topic, headers=headers, 
                                      message={'result':SCHEDULE_CANCEL_PREEMPTED,
                                               'info': '',
                                               'data':{'agentID': requester_id,
                                                       'taskID': task_id}})
            
            #If we are successful we do something else with the real result data
            data = result.data if not result.success else {}        
            topic = topics.ACTUATOR_SCHEDULE_RESULT()
            headers = self.get_headers(requester_id, task_id=task_id)
            headers['type'] = SCHEDULE_ACTION_NEW
            results = {'result':success, 
                       'data': data, 
                       'info':result.info_string}
            self.vip.pubsub.publish('pubsub', topic, headers=headers, message=results)
            
            return results
                    
        @RPC.export 
        def request_cancel_schedule(self, requester_id, task_id):
            now = datetime.datetime.now()
            headers = self.get_headers(requester_id, task_id=task_id)
            
            result = self._schedule_manager.cancel_task(requester_id, task_id, now)
            success = SCHEDULE_RESPONSE_SUCCESS if result.success else SCHEDULE_RESPONSE_FAILURE
            
            topic = topics.ACTUATOR_SCHEDULE_RESULT()
            message = {'result':success,  
                       'info': result.info_string,
                       'data':{}}
            self.vip.pubsub.publish('pubsub', topic, 
                                    headers=headers, 
                                    message=message)
            
            if result.success:
                self.update_device_state_and_schedule(now) 
                
            return message           
            

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


        def push_result_topic_pair(self, prefix, point, headers, *args):
            topic = normtopic('/'.join([prefix, point]))
            self.vip.pubsub.publish('pubsub', topic, headers, message = args)

    return ActuatorAgent(**kwargs)


def main(argv=sys.argv):
    '''Main method called to start the agent.'''
    utils.setup_logging()
    utils.vip_main(actuator_agent)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
