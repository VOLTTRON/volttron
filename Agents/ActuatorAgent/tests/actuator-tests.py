import unittest
import subprocess
import time
from datetime import datetime, timedelta
import volttron.platform.messaging.topics
from volttron.platform.agent import utils, matching
from volttron.platform.agent import PublishMixin, BaseAgent
from volttron.tests import base
 
"""
Test 
"""
 
AGENT_DIR = "Agents/ActuatorAgent"
CONFIG_FILE = "Agents/ActuatorAgent/actuator-deploy.service"

class ActuatorTests(base.BasePlatformTest):

    def setUp(self):
        super(ActuatorTests, self).setUp()
        self.startup_platform("base-platform-test.json")
        
    def tearDown(self):
        super(ActuatorTests, self).tearDown()
    
#     def test_direct_build_and_install(self):
#         self.direct_buid_install_agent(AGENT_DIR)
# 
#     def test_direct_install_and_start(self):
#         self.direct_build_install_run_agent(AGENT_DIR)

    def test_direct_install_and_start(self):
        self.direct_build_install_run_agent(AGENT_DIR, CONFIG_FILE)

         
#     def test_schedule(self):
#         print "test something"
# #         self.publish_schedule()
         
    def publish_schedule(self):
     
        headers = {
                    'AgentID': self._agent_id,
                    'type': 'NEW_SCHEDULE',
                    'requesterID': self._agent_id, #The name of the requesting agent.
                    'taskID': self._agent_id + "-TASK", #The desired task ID for this task. It must be unique among all other scheduled tasks.
                    'priority': 'LOW', #The desired task priority, must be 'HIGH', 'LOW', or 'LOW_PREEMPT'
                } 
         
        now = datetime.now()
        start =  now.strftime("%Y-%m-%d %H:%M:00")
        end = (now + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:00")
        msg = [
                ["campus/building/device1", #First time slot.
                 start,     #Start of time slot.
                 end],     #End of time slot.
                #etc...
            ]
         
        self.subagent.subscribe(self, prefix='',callback=self.on_match)
        self.publish_json(topics.ACTUATOR_SCHEDULE_REQUEST, headers, msg)
        time.sleep(20)
         
    def on_match(self, topic, headers, message, match):
        print "**********************************Match"
  
