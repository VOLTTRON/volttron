import os
import time

from volttron.tests import base
from volttron.platform.agent.base import PublishMixin

"""
Test
"""
AGENT_DIR = "Agents/DrivenLoggerAgent"
CONFIG_FILE = "Agents/DrivenLoggerAgent/config"
SLEEP_TIME = 2

class DrivenLoggerTests(base.BasePlatformTest):

    def setUp(self):
        super(DrivenLoggerTests, self).setUp()
        self.cleanup_tempdir = False
        self.startup_platform("base-platform-test.json", use_twistd=False)

    def tearDown(self):
        super(DrivenLoggerTests, self).tearDown()

    def test_direct_install_start_stop_start(self):
        uuid = self.direct_build_install_run_agent(AGENT_DIR, CONFIG_FILE)
        time.sleep(SLEEP_TIME)
        self.direct_stop_agent(uuid)
        time.sleep(SLEEP_TIME)
        self.direct_start_agent(uuid)


    def test_logger_agent_started(self):
        os.environ['AGENT_PUB_ADDR'] = os.path.join("ipc:///",
                                                    os.environ['VOLTTRON_HOME'],
                                            'run/publish')
        uuid = self.direct_build_install_run_agent(AGENT_DIR, CONFIG_FILE)
        time.sleep(SLEEP_TIME)
        self.assertIsNotNone(os.environ['AGENT_PUB_ADDR'])
        msg = {"oat1": "50", "oat2":"20.5"}
        pub = PublishMixin("ipc://"+os.environ['AGENT_PUB_ADDR'])
        pub.publish_json('pnnl/isb1/oat',{}, msg)
        time.sleep(SLEEP_TIME)

