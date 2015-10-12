# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2015, Battelle Memorial Institute
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
import logging
import sys
import math
import greenlet
from zmq.utils import jsonapi

from volttron.platform.agent import BaseAgent, PublishMixin, periodic
from volttron.platform.agent import green, utils, matching, sched
from volttron.platform.messaging import headers as headers_mod, topics

#Import all afdd algorithms
import afdd
import datetime

def AFDDAgent(config_path, **kwargs):
    config = utils.load_config(config_path)
    agent_id = config['agentid']
    
    termination_window = config.get('termination_window', 600)
    min_run_window = config.get('min_run_window', 3600 + termination_window)    
    
    rtu_path = dict((key, config[key])
                    for key in ['campus', 'building', 'unit'])
    
    
    day_run_interval = config.get('day_run_interval')
    
    start_hour = config.get('start_hour')
    
    start_minute = config.get('start_minute')
    
    volttron_flag = config.get('volttron_flag')
    
    debug_flag = True

    zip_code = config.get('zip_code')
    
    utils.setup_logging()
    _log = logging.getLogger(__name__)
    logging.basicConfig(level=logging.debug,
                        format='%(asctime)s   %(levelname)-8s %(message)s',
                        datefmt='%m-%d-%y %H:%M:%S')
  
    class Agent(PublishMixin, BaseAgent):
        def __init__(self, **kwargs):
            super(Agent, self).__init__(**kwargs)
            self.lock_timer = None
            self.lock_acquired = False
            self.tasklet = None
            self.data_queue = green.WaitQueue(self.timer)
            self.value_queue = green.WaitQueue(self.timer)
            self.weather_data_queue = green.WaitQueue(self.timer)
            
            self.last_run_time = None
            self.is_running = False 
            self.remaining_time = None
            self.task_id= agent_id
            self.retry_schedule = None
            self.start = None
            self.end = None
            
        def setup(self):
            super(Agent, self).setup()
            self.scheduled_task()

        def startrun(self, algo=None):
            _log.debug('start diagnostic')
            if algo is None:
                algo = afdd.AFDD(self,config_path).run_all
            self.tasklet = greenlet.greenlet(algo)
            self.is_running = True
            self.last_run_time = datetime.datetime.now()
            self.tasklet.switch()
        
        def scheduled_task(self):
            '''
            Schedule re-occuring diagnostics
            '''
            _log.debug('Schedule Dx')
            headers = {         
                                'type':  'NEW_SCHEDULE',
                               'requesterID': agent_id,
                               'taskID': agent_id,
                               'priority': 'LOW_PREEMPT'
                               }

            min_run_hour = math.floor(min_run_window/3600)
            min_run_minute = int((min_run_window/3600 - min_run_hour)*60)

            self.start = datetime.datetime.now().replace(hour=start_hour, minute=start_minute)
            self.end = self.start + datetime.timedelta(hours=2,minutes=30)
            run_start = self.end - datetime.datetime.now()
            required_diagnostic_time = datetime.timedelta(hours = min_run_hour, minutes=min_run_minute)

            if run_start < required_diagnostic_time:
                self.start = self.start + datetime.timedelta(days=1)
                self.end = self.start + datetime.timedelta(hours=2,minutes=30)
                sched_time = datetime.datetime.now() + datetime.timedelta(days=day_run_interval + 1)
                sched_time = sched_time.replace(hour=0,minute=1)
            else:
                sched_time = datetime.datetime.now() + datetime.timedelta(days=day_run_interval)


            self.start = str(self.start)
            self.end = str(self.end)
            self.task_timer = self.periodic_timer(60, self.publish_json,
                                      topics.ACTUATOR_SCHEDULE_REQUEST(), headers,[["{campus}/{building}/{unit}".format(**rtu_path),self.start,self.end]])
            event = sched.Event(self.scheduled_task)
            self.next = self.schedule(sched_time, event)
            
        @matching.match_headers({headers_mod.REQUESTER_ID: agent_id,'type': 'CANCEL_SCHEDULE'})  
        @matching.match_exact(topics.ACTUATOR_SCHEDULE_RESULT())
        def preempt(self):
            if self.is_running:
                self.cancel_greenlet()
        
        @matching.match_headers({headers_mod.REQUESTER_ID: agent_id})   
        @matching.match_exact(topics.ACTUATOR_SCHEDULE_ANNOUNCE(**rtu_path))
        def on_schedule(self, topic, headers, message, match):
            msg = jsonapi.loads(message[0])
            now = datetime.datetime.now()
            self.remaining_time = headers.get('window', 0)
            if self.task_id == headers.get('taskID', ''):
                if self.remaining_time < termination_window:
                    if self.is_running:
                        self.cancel_greenlet()
                elif (self.remaining_time > min_run_window and
                (self.last_run_time is None or 
                (now - self.last_run_time) > datetime.timedelta(hours=23, minutes=50))):
                    self.startrun()
                         
        @matching.match_headers({headers_mod.REQUESTER_ID: agent_id})                   
        @matching.match_exact(topics.ACTUATOR_SCHEDULE_RESULT())
        def schedule_result(self, topic, headers, message, match):
            msg = jsonapi.loads(message[0])
            _log.debug('Actuator response received')
            self.task_timer.cancel()

        @matching.match_exact(topics.DEVICES_VALUE(point='all', **rtu_path))
        def on_new_data(self, topic, headers, message, match):
            data = jsonapi.loads(message[0])
            #Check override status
            if int(data["VoltronPBStatus"]) == 1:
                if self.is_running:
                    _log.debug("User override is initiated...")
                    headers = {
                               'Content-Type': 'text/plain',
                               'requesterID': agent_id,
                               }
                    self.publish(topics.ACTUATOR_SET(point="VoltronFlag", **rtu_path),
                                 headers, str(0.0))
                    self.cancel_greenlet()
            else:
                self.data_queue.notify_all(data)
                
        @matching.match_headers({headers_mod.REQUESTER_ID: agent_id})
        @matching.match_glob(topics.ACTUATOR_VALUE(point='*', **rtu_path))
        def on_set_result(self, topic, headers, message, match):
            self.value_queue.notify_all((match.group(1), True))
            
        @matching.match_headers({headers_mod.REQUESTER_ID: agent_id}) 
        @matching.match_glob(topics.ACTUATOR_ERROR(point='*', **rtu_path))
        def on_set_error(self, topic, headers, message, match):
            self.value_queue.notify_all((match.group(1), False))
            
        def cancel_greenlet(self):
            #kill all tasks currently in the queue
            self.data_queue.kill_all()
            self.value_queue.kill_all()
            #kill current tasklet
            self.tasklet.throw()
            self.is_running = False
            
            
        def sleep(self, timeout):
            _log.debug('wait for steady state({})'.format(timeout))
            green.sleep(timeout, self.timer)

        def get_new_data(self, timeout=None):
            _log.debug('get_new_data({})'.format(timeout))
            return self.data_queue.wait(timeout)

        def command_equip(self, point_name, value, timeout=None):
            _log.debug('set_point({}, {}, {})'.format(point_name, value, timeout))
            headers = {
                    'Content-Type': 'text/plain',
                    'requesterID': agent_id,
            }
            self.publish(topics.ACTUATOR_SET(point=point_name, **rtu_path),
                         headers, str(value))
            try:
                return self.value_queue.wait(timeout)
            except green.Timeout:
                return True
            
        def weather_request(self,timeout=None):
            _log.debug('weather request for {}'.format(zip_code))
            headers = {
                       'Content-Type': 'text/plain',
                       'requesterID': agent_id
                    }
            msg = {'zipcode': str(zip_code)}
            self.publish_json('weather/request',headers, msg)
            try:
                return self.weather_data_queue.wait(timeout)
            except green.Timeout:
                return 'INCONCLUSIVE'

        matching.match_headers({headers_mod.REQUESTER_ID: agent_id})
        @matching.match_exact('weather/response/temperature/temp_f')
        def weather_response(self, topic, headers, message, match):
            data = float(jsonapi.loads(message[0]))
            print data
            self.weather_data_queue.notify_all(data)
        

    Agent.__name__ = 'AFDDAgent'
    return Agent(**kwargs)


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.default_main(AFDDAgent,
                       description='VOLTTRON platform™ AFDD agent',
                       argv=argv)
if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
