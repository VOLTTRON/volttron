import unittest
import subprocess
import time
from datetime import datetime, timedelta
import volttron.platform.messaging.topics
from volttron.platform.agent import utils, matching
from volttron.platform.agent import PublishMixin, BaseAgent

"""
Test 
"""
# 
# def setup_func():
#     "set up test fixtures"
# 
# def teardown_func():
#     "tear down test fixtures"
# 
# @with_setup(setup_func, teardown_func)
# def test():

# print subprocess.check_output(["./bootstrap"])

p_process = None
t_process = None

#All paths relative to proj-dir/volttron
VSTART = "env/bin/volttron"
VCTRL = "env/bin/volttron-ctrl"
INST_EXEC = "install-executable"
REM_EXEC = "remove-executable"
LOAD_AGENT = "load-agent"
UNLOAD_AGENT = "unload-agent"
LIST_AGENTS = "list-agents"
STOP_AGENT = "stop-agent"
START_AGENT = "start-agent"
BUILD_AGENT = "volttron/scripts/build-agent.sh"
CONFIG_FILE = "test-config.ini"

PUBLISH_ADDRESS = "ipc:///tmp/volttron-platform-agent-publish"
SUBSCRIBE_ADDRESS = "ipc:///tmp/volttron-lite-agent-subscribe"
actuator_dict = {"executable": "actuatoragent-0.1-py2.7.egg",
                 "launch_file": "Agents/ActuatorAgent/actuator-test-deploy.service",
                 "agent_config": "actuator-test-deploy.service",
                 "agent_dir": "ActuatorAgent"}



def setup_module():
    global p_process, t_process
    #assumes it's running from proj-dir/volttron
    p_process =  subprocess.Popen([VSTART, "-c", CONFIG_FILE, "-v", "-l", "volttron.log"])
#     t_process = subprocess.Popen(["twistd", "-n", "smap", "test-smap.ini"])
    time.sleep(3)
    build_and_setup_agent()

    
def teardown_module():
    try:
        print subprocess.check_output([VCTRL,REM_EXEC,actuator_dict["executable"]])
        print subprocess.check_output([VCTRL,UNLOAD_AGENT,actuator_dict["agent_name"]])
        print subprocess.check_output([VCTRL,LIST_AGENTS])
    except Exception as e:
        pass
        
    global p_process
    if p_process != None:
        p_process.kill()
    else: 
        print "NULL"
        
    if t_process != None:
        t_process.kill()
    else: 
        print "NULL"
    
def build_and_setup_agent():
    print "build_and_setup_agent"
    print subprocess.check_output([BUILD_AGENT, actuator_dict["agent_dir"]])
    print subprocess.check_output(["chmod","+x", "Agents/"+actuator_dict["executable"]])
    # Shut down and remove in case it's hanging around
    print subprocess.check_output([VCTRL,STOP_AGENT,actuator_dict["agent_config"]])
    try:
        print subprocess.check_output([VCTRL,REM_EXEC,actuator_dict["executable"]])
    except Exception as e:
        pass
    try:
        print subprocess.check_output([VCTRL,UNLOAD_AGENT,actuator_dict["agent_config"]])
    except Exception as e:
        pass
    #Install egg and config file
    print subprocess.check_output([VCTRL,INST_EXEC,"Agents/"+actuator_dict["executable"]])
    print subprocess.check_output([VCTRL,LOAD_AGENT,actuator_dict["launch_file"]])

def startup_agent():
    print "startup agent"
    #Stop agent so we have a fresh start
    print subprocess.check_output([VCTRL,"stop-agent",actuator_dict["agent_config"]])
    time.sleep(3)
    print subprocess.check_output([VCTRL,"start-agent",actuator_dict["agent_config"]])
    time.sleep(3)
    list_output = subprocess.check_output([VCTRL,"list-agents"])
    found_archiver = False
    for line in list_output.split('\n'):
        bits = line.split()
        if len(bits) > 0 and bits[0] == (actuator_dict["agent_config"]):
            found_archiver = True
            assert(bits[2].startswith('running'))
    assert(found_archiver)

def shutdown_agent():
    print subprocess.check_output([VCTRL,"stop-agent",actuator_dict["agent_config"]])

class TestBuildAndInstallAgent(unittest.TestCase):

    def setUp(self):
        startup_agent()
        print "setup test"
        self.publisher = PublishMixin(PUBLISH_ADDRESS)
        self.subagent = BaseAgent(SUBSCRIBE_ADDRESS)
        print "hello"
        self._agent_id = "ActuatorTest"
        
    def tearDown(self):
        shutdown_agent()
        print "teardown test"
        
    def test_something(self):
        print "test something"
        self.publish_schedule()
        
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
        print "**********************************JHELLO"
 
