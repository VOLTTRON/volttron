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
import clock
import logging
import sys

import greenlet
from zmq.utils import jsonapi

from volttron.platform.agent import BaseAgent, PublishMixin, periodic
from volttron.platform.agent import green, utils, matching, sched
from volttron.platform.messaging import headers as headers_mod, topics

#Import all afdd algorithms
import afdd
import datetime


#_log = logging.getLogger(__name__)
#logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)

def AFDDAgent(config_path, **kwargs):
    config = utils.load_config(config_path)
    agent_id = config['agentid']
    
    termination_window = config.get('termination_window', 600)
    min_run_window = config.get('min_run_window', 3600 + termination_window)    
    
    rtu_path = dict((key, config[key])
                    for key in ['campus', 'building', 'unit'])
    
    log_filename = config.get('file_name')
    
    day_run_interval = config.get('day_run_interval')
    
    start_hour = config.get('start_hour')
    
    start_minute = config.get('start_minute')
    
    volttron_flag = config.get('volttron_flag')
    
    debug_flag = True
    
    
    if not debug_flag:
        _log = logging.getLogger(__name__)
        logging.basicConfig(level=logging.DEBUG, stream=sys.stderr,
                            format='%(asctime)s   %(levelname)-8s %(message)s',
                            datefmt='%m-%d-%y %H:%M:%S')
    else:
        _log = logging.getLogger(__name__)
        logging.basicConfig(level=logging.NOTSET, stream=sys.stderr,
                        format='%(asctime)s   %(levelname)-8s %(message)s',
                        datefmt= '%m-%d-%y %H:%M:%S',
                        filename=log_filename,
                        filemode='a+')
        fmt_str = '%(asctime)s   %(levelname)-8s    %(message)s'
        formatter = logging.Formatter(fmt_str,datefmt = '%m-%d-%y %H:%M:%S')
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        console.setFormatter(formatter)
        logging.getLogger("").addHandler(console)
        _log.debug(rtu_path)
        
    class Agent(PublishMixin, BaseAgent):
        def __init__(self, **kwargs):
            super(Agent, self).__init__(**kwargs)
            self.lock_timer = None
            self.lock_acquired = False
            self.tasklet = None
            self.data_queue = green.WaitQueue(self.timer)
            self.value_queue = green.WaitQueue(self.timer)
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
            if algo is None:
                algo = afdd.AFDD(self,config_path).run_all
            self.tasklet = greenlet.greenlet(algo)
            self.is_running = True
            self.last_run_time = datetime.datetime.now()
            self.tasklet.switch()
        
        def scheduled_task(self):
            headers = {         
                                'type':  'NEW_SCHEDULE',
                               'requesterID': agent_id,
                               'taskID': agent_id,
                               'priority': 'LOW_PREEMPT'
                               }
            if datetime.datetime.now().hour > start_hour:
                self.start = datetime.datetime.now().replace(hour=start_hour, minute=start_minute)
                self.start = self.start + datetime.timedelta(days=1)
                self.end = self.start + datetime.timedelta(hours=2,minutes=30)
                sched_time = datetime.datetime.now() + datetime.timedelta(days=day_run_interval + 1)
                sched_time=sched_time.replace(hour=0,minute=1)
            else:
                self.start = datetime.datetime.now().replace(hour=start_hour, minute=start_minute)
                self.end = self.start + datetime.timedelta(hours=2,minutes=30)
                sched_time = datetime.datetime.now() + datetime.timedelta(days=day_run_interval)
            self.start = str(self.start)
            self.end = str(self.end)
            self.task_timer = self.periodic_timer(60, self.publish_json,
                                      topics.ACTUATOR_SCHEDULE_REQUEST(), headers,[["{campus}/{building}/{unit}".format(**rtu_path),self.start,self.end]])
            self.next = self.schedule(sched_time, self.scheduled_task)
            
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
            print 'response received'
            self.task_timer.cancel()

        @matching.match_exact(topics.DEVICES_VALUE(point='all', **rtu_path))
        def on_new_data(self, topic, headers, message, match):
            data = jsonapi.loads(message[0])
            #Check override status
            if int(data["VoltronPBStatus"]) == 1:
                if self.is_running:
                    _log.debug("AFDD is overridden...")
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
    

#         def setup(self):
#             super(Agent, self).setup()
#             headers = {
#                     'Content-Type': 'text/plain',
#                     'requesterID': agent_id,
#             }
#             self.lock_timer = self.periodic_timer(2, self.publish,
#                     topics.ACTUATOR_LOCK_ACQUIRE(**rtu_path), headers)

#Testing functions
# def test():
#     import threading, time
#     from volttron.platform.agent import periodic
# 
#     def TestAgent(config_path, condition, **kwargs):
#         config = utils.load_config(config_path)
#         agent_id = config['agentid']
#         rtu_path = dict((key, config[key])
#                         for key in ['campus', 'building', 'unit'])
# 
#         class Agent(PublishMixin, BaseAgent):
#             def __init__(self, **kwargs):
#                 super(Agent, self).__init__(**kwargs)
#                 
#             def setup(self):
#                 super(Agent, self).setup()
#                 self.damper = 0
#                 with condition:
#                     condition.notify()                
# 
#             @matching.match_regex(topics.ACTUATOR_LOCK_ACQUIRE() + '(/.*)')
#             def on_lock_result(self, topic, headers, message, match):
#                 _log.debug("Topic: {topic}, {headers}, Message: {message}".format(
#                         topic=topic, headers=headers, message=message))
#                 self.publish(topics.ACTUATOR_LOCK_RESULT() + match.group(0),
#                              headers, jsonapi.dumps('SUCCESS'))
# 
#             @matching.match_regex(topics.ACTUATOR_SET() + '(/.*/([^/]+))')
#             def on_new_data(self, topic, headers, message, match):
#                 _log.debug("Topic: {topic}, {headers}, Message: {message}".format(
#                         topic=topic, headers=headers, message=message))
#                 if match.group(2) == 'Damper':
#                     self.damper = int(message[0])
#                 self.publish(topics.ACTUATOR_VALUE() + match.group(0),
#                              headers, message[0])
# 
#            # @periodic(5)
#             def send_data(self):
#                 data = {
#                     'ReturnAirTemperature': 78,
#                     'OutsideAirTemperature': 71,
#                     'DischargeAirTemperature': 76,
#                     'MixedAirTemperature': 72,
#                     'DamperSignal': 0,
#                     'CoolCommand1': 0,
#                     'CoolCommand2':0,
#                     'OutsideAirVirtualPoint': 75-10,
#                     'CoolCall1':1,
#                     'HeatCommand1':0,
#                     'HeatCommand2':0,
#                     'SupplyFanSpeed':75,
#                     'ReturnAirCO2Stpt': 65,
#                     'FanStatus': 1
#                 }
#                 self.publish_ex(topics.DEVICES_VALUE(point='all', **rtu_path),
#                                 {}, ('application/json', jsonapi.dumps(data)))
# 
#         Agent.__name__ = 'TestAgent'
#         return Agent(**kwargs)
# 
#     #settings.afdd2_seconds_to_steady_state = 3
#     #settings.sync_trial_time = 10
#     condition = threading.Condition()
#     t = threading.Thread(target=utils.default_main, args=(TestAgent, 'test'),
#                          kwargs={'condition': condition})
#     t.daemon = True
#     t.start()
#     with condition:
#         condition.wait()
#     main()


