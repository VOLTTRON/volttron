import unittest
import subprocess
import time

import base
from platform_wrapper import PlatformWrapper

from wheel.install import WheelFile
from wheel.tool import unpack


from volttron.platform.agent import PublishMixin

RESTRICTED = False

try:
    from volttron.restricted import (auth, certs)
    RESTRICTED = True
except ImportError:
    RESTRICTED = False
    auth = None
    certs = None

"""
Test 
"""

AGENT_DIR = 'Agents/PingPongAgent'
CONFIG_FILE = 'Agents/PingPongAgent/config.json'
EXECREQS_FILE = 'Agents/PingPongAgent/execreqs.json'


class MobileTests(unittest.TestCase):

    def setUp(self):
        
        self.platform1 = PlatformWrapper(volttron_home='../volttron-testing/config/setup-restricted/mobility-tests/.platform1')
        self.platform1.startup_platform("mobile-platform1-test.json",
                                        mode=base.RESTRICTED, use_twistd=False)
        
        self.platform2 = PlatformWrapper(volttron_home='../volttron-testing/config/setup-restricted/mobility-tests/.platform2')
        self.platform2.startup_platform("mobile-platform2-test.json",
                                        mode=base.RESTRICTED, use_twistd=False)
        
        self.assertIsNone(self.platform1.p_process.poll(), "Platform1 did not start")
        self.assertIsNone(self.platform2.p_process.poll(), "Platform2 did not start")
        
        
    def tearDown(self):
        print ("Tearing down mobility test")
        self.platform1.cleanup()
        self.platform2.cleanup()
        
    def test_build_and_sign(self):
        print ("TESTING build and sign")
        if not RESTRICTED:
            print("NOT RESTRICTED")
            return
        package = self.platform1.direct_build_agentpackage(AGENT_DIR)
        self.platform1.direct_sign_agentpackage_creator(package)
        self.platform1.direct_sign_agentpackage_soi(package)
        self.platform1.direct_sign_agentpackage_initiator(package, 
                            config_file=CONFIG_FILE, contract=EXECREQS_FILE)
 
    def test_build_sign_and_start(self):
        print ("TESTING build, sign, and start")
        if not RESTRICTED:
            print("NOT RESTRICTED")
            return
        package = self.platform1.direct_build_agentpackage(AGENT_DIR)
        self.platform1.direct_sign_agentpackage_creator(package)
        self.platform1.direct_sign_agentpackage_soi(package)
        self.platform1.direct_sign_agentpackage_initiator(package, 
                            config_file=CONFIG_FILE, contract=EXECREQS_FILE)

        
        self.platform1.direct_send_agent(package, '127.0.1.1')
        
        #check the status on each platform until we see the agent a certain number
        #of times both places
        agent_is_running = self.platform2.confirm_agent_running('pingpongagent-0.1')
        
        self.assertTrue(agent_is_running, "Agent not running on 2")
        
        agent_is_running = self.platform1.confirm_agent_running('pingpongagent-0.1')
                                    
        self.assertTrue(agent_is_running, "Agent not running on 1")

        
