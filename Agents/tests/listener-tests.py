import unittest
import subprocess
import time
import base
from wheel.install import WheelFile
from wheel.tool import unpack


from volttron.platform.agent import PublishMixin

"""
Test 
"""
AGENT_DIR = "Agents/ListenerAgent"
AGENT_NAME = "listeneragent-0.1"
WHEEL_NAME = "listeneragent-0.1-py2-none-any.whl"

class ListenerTests(base.BasePlatformTest):

    def setUp(self):
        super(ListenerTests, self).setUp()
        self.startup_platform("base-platform-test.json")
        self.setup_connector()
        
    def tearDown(self):
        super(ListenerTests, self).tearDown()
    
#     def test_build(self):
#         agent_wheel = self.build_agentpackage(AGENT_DIR)
#         self.assertIsNotNone(agent_wheel,"Agent wheel was not built")
#         self.assertTrue(agent_wheel.endswith(WHEEL_NAME))
#      
#     def test_build_and_install(self):
#         uuid = self.direct_install_agent(AGENT_DIR)
#         self.direct_start_agent(uuid)
#         print "started"

    def test_direct_build_and_install(self):
        self.direct_buid_install_agent(AGENT_DIR)

    def test_direct_install_and_start(self):
        self.direct_build_install_run_agent(AGENT_DIR)

