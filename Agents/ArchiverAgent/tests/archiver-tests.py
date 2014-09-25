import unittest
import subprocess
import time

from wheel.install import WheelFile
from wheel.tool import unpack

from volttron.tests import base
from volttron.platform.agent import PublishMixin

"""
Test 
"""

AGENT_CONFIG = """
{{
    "archiver_url": "/{smap-uri}/api/query",
    "agentid": "SMAP Archiver",
    "source_name": "{smap-source}"
}}

"""


# 
# archiver_dict = {"executable": "archiveragent-0.1-py2.7.egg",
#                  "launch_file": "Agents/ArchiverAgent/archiver-test-deploy.service",
#                  "agent_name": "archiver-test-deploy.service"}
AGENT_DIR = "Agents/ArchiverAgent"
CONFIG_FILE_NAME = "archiveragent.service"

class ArchiverTests(base.BasePlatformTest):

    def setUp(self):
        super(ArchiverTests, self).setUp()
        self.startup_platform("base-platform-test.json")
        
    def tearDown(self):
        super(ArchiverTests, self).tearDown()
#     
#     def test_build(self):
#         agent_wheel = self.build_agentpackage("Agents/ArchiverAgent")
#         self.assertIsNotNone(agent_wheel,"Agent wheel was not built")
#         self.assertTrue(agent_wheel.endswith("archiveragent-0.1-py2-none-any.whl"))
#      
     
    def test_direct_install_and_start(self):
        config = self.fillout_file(CONFIG_FILE_NAME, AGENT_CONFIG, "base-platform-test.json")
        
        self.direct_build_install_run_agent(AGENT_DIR, config)
     
#     def test_direct_build_and_install(self):
#         self.direct_buid_install_agent("Agents/ArchiverAgent")
# 
#     def direct_build_install_run_agent(self):
#         self.direct_build_install_run_agent("Agents/ArchiverAgent")

# def build_and_setup_archiver():
#     print "build_and_setup_archiver"
#     print subprocess.check_output([BUILD_AGENT, "ArchiverAgent"])
#     print subprocess.check_output(["chmod","+x", "Agents/archiveragent-0.1-py2.7.egg"])
#     # Shut down and remove in case it's hanging around
#     print subprocess.check_output([VCTRL,STOP_AGENT,"archiver-test-deploy.service"])
#     try:
#         print subprocess.check_output([VCTRL,REM_EXEC,"archiveragent-0.1-py2.7.egg"])
#     except Exception as e:
#         pass
#     try:
#         print subprocess.check_output([VCTRL,UNLOAD_AGENT,"archiver-test-deploy.service"])
#     except Exception as e:
#         pass
#     #Install egg and config file
#     print subprocess.check_output([VCTRL,INST_EXEC,"Agents/archiveragent-0.1-py2.7.egg"])
#     print subprocess.check_output([VCTRL,LOAD_AGENT,"Agents/ArchiverAgent/archiver-test-deploy.service"])
# 
# def startup_archiver():
#     print "startup archiver"
#     #Stop agent so we have a fresh start
#     print subprocess.check_output([VCTRL,"stop-agent","archiver-test-deploy.service"])
#     time.sleep(3)
#     print subprocess.check_output([VCTRL,"start-agent","archiver-test-deploy.service"])
#     time.sleep(3)
#     list_output = subprocess.check_output([VCTRL,"list-agents"])
#     found_archiver = False
#     for line in list_output.split('\n'):
#         bits = line.split()
#         if len(bits) > 0 and bits[0] == ("archiver-test-deploy.service"):
#             found_archiver = True
#             assert(bits[2].startswith('running'))
#     assert(found_archiver)
# 
# def shutdown_archiver():
#     print subprocess.check_output([VCTRL,"stop-agent","archiver-test-deploy.service"])
# 
# class TestBuildAndInstallArchiver(unittest.TestCase):
# # 
# #     @classmethod
# #     def setup_class(cls):
# #         startup_archiver()
# #         print "setup class"
# # 
# #     @classmethod
# #     def teardown_class(cls):
# #         shutdown_archiver()
# #         print "teardown_class"
# 
#     def setUp(self):
#         startup_archiver()
#         print "setup test"
#         publisher = PublishMixin(PUBLISH_ADDRESS)
#         print "hello"
# #         --config Agents/ListenerAgent/listeneragent.launch.json --pub ipc:///tmp/volttron-platform-agent-publish --sub ipc:///tmp/volttron-platform-agent-subscribe
#         
#     def tearDown(self):
#         shutdown_archiver()
#         print "teardown test"
#         
#     def test_something(self):
#         print "test something"
#          
