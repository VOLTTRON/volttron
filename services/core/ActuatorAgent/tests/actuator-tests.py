'''
Copyright (c) 2016, Battelle Memorial Institute
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met: 

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer. 
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution. 

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

The views and conclusions contained in the software and documentation are those
of the authors and should not be interpreted as representing official policies, 
either expressed or implied, of the FreeBSD Project.
'''

'''
This material was prepared as an account of work sponsored by an 
agency of the United States Government.  Neither the United States 
Government nor the United States Department of Energy, nor Battelle,
nor any of their employees, nor any jurisdiction or organization 
that has cooperated in the development of these materials, makes 
any warranty, express or implied, or assumes any legal liability 
or responsibility for the accuracy, completeness, or usefulness or 
any information, apparatus, product, software, or process disclosed,
or represents that its use would not infringe privately owned rights.

Reference herein to any specific commercial product, process, or 
service by trade name, trademark, manufacturer, or otherwise does 
not necessarily constitute or imply its endorsement, recommendation, 
r favoring by the United States Government or any agency thereof, 
or Battelle Memorial Institute. The views and opinions of authors 
expressed herein do not necessarily state or reflect those of the 
United States Government or any agency thereof.

PACIFIC NORTHWEST NATIONAL LABORATORY
operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
under Contract DE-AC05-76RL01830
'''

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
  
