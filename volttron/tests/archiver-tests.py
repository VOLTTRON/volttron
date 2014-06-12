import unittest
import subprocess
import time

from volttron.platform.agent import PublishMixin

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

archiver_dict = {"executable": "archiveragent-0.1-py2.7.egg",
                 "launch_file": "Agents/ArchiverAgent/archiver-test-deploy.service",
                 "agent_name": "archiver-test-deploy.service"}



def setup_module():
    global p_process, t_process
    #assumes it's running from proj-dir/volttron
    p_process =  subprocess.Popen([VSTART, "-c", CONFIG_FILE, "-v", "-l", "volttron.log"])
    t_process = subprocess.Popen(["twistd", "-n", "smap", "test-smap.ini"])
    time.sleep(3)
    build_and_setup_archiver()

    
def teardown_module():
    try:
        print subprocess.check_output([VCTRL,REM_EXEC,"archiveragent-0.1-py2.7.egg"])
        print subprocess.check_output([VCTRL,UNLOAD_AGENT,"archiver-test-deploy.service"])
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
    
def build_and_setup_archiver():
    print "build_and_setup_archiver"
    print subprocess.check_output([BUILD_AGENT, "ArchiverAgent"])
    print subprocess.check_output(["chmod","+x", "Agents/archiveragent-0.1-py2.7.egg"])
    # Shut down and remove in case it's hanging around
    print subprocess.check_output([VCTRL,STOP_AGENT,"archiver-test-deploy.service"])
    try:
        print subprocess.check_output([VCTRL,REM_EXEC,"archiveragent-0.1-py2.7.egg"])
    except Exception as e:
        pass
    try:
        print subprocess.check_output([VCTRL,UNLOAD_AGENT,"archiver-test-deploy.service"])
    except Exception as e:
        pass
    #Install egg and config file
    print subprocess.check_output([VCTRL,INST_EXEC,"Agents/archiveragent-0.1-py2.7.egg"])
    print subprocess.check_output([VCTRL,LOAD_AGENT,"Agents/ArchiverAgent/archiver-test-deploy.service"])

def startup_archiver():
    print "startup archiver"
    #Stop agent so we have a fresh start
    print subprocess.check_output(["env/bin/volttron-ctrl","stop-agent","archiver-test-deploy.service"])
    time.sleep(3)
    print subprocess.check_output(["env/bin/volttron-ctrl","start-agent","archiver-test-deploy.service"])
    time.sleep(3)
    list_output = subprocess.check_output(["env/bin/volttron-ctrl","list-agents"])
    found_archiver = False
    for line in list_output.split('\n'):
        bits = line.split()
        if len(bits) > 0 and bits[0] == ("archiver-test-deploy.service"):
            found_archiver = True
            assert(bits[2].startswith('running'))
    assert(found_archiver)

def shutdown_archiver():
    print subprocess.check_output(["env/bin/volttron-ctrl","stop-agent","archiver-test-deploy.service"])

class TestBuildAndInstallArchiver(unittest.TestCase):
# 
#     @classmethod
#     def setup_class(cls):
#         startup_archiver()
#         print "setup class"
# 
#     @classmethod
#     def teardown_class(cls):
#         shutdown_archiver()
#         print "teardown_class"

    def setUp(self):
        startup_archiver()
        print "setup test"
        publisher = PublishMixin(PUBLISH_ADDRESS)
        print "hello"
#         --config Agents/ListenerAgent/listeneragent.launch.json --pub ipc:///tmp/volttron-platform-agent-publish --sub ipc:///tmp/volttron-platform-agent-subscribe
        
    def tearDown(self):
        shutdown_archiver()
        print "teardown test"
        
    def test_something(self):
        print "test something"
         
