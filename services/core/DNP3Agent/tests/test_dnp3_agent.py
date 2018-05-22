# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2018, SLAC / Kisensum.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor SLAC, nor Kisensum, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# SLAC, or Kisensum. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
# }}}

import gevent
from multiprocessing import Manager, Process
import pytest
import time

try:
    from pydnp3 import asiodnp3, asiopal, opendnp3, openpal
    FILTERS = opendnp3.levels.NORMAL | opendnp3.levels.ALL_COMMS
except ImportError as exc:
    # The pydnp3 library must be loaded for these tests to pass.
    # They're currently marked skip, though, so this import needs to work only if the tests are re-enabled later.
    pass

from volttron.platform import get_services_core


HOST = "127.0.0.1"
LOCAL = "0.0.0.0"
PORT = 20000

DNP3_AGENT_ID = 'dnp3agent'

TEST_GET_POINT_NAME = 'DCHD.VArAct'
TEST_SET_POINT_NAME = 'DCHD.WTgt-In'

DNP3_AGENT_CONFIG = {
    "point_definitions_path": "~/repos/volttron/services/core/DNP3Agent/opendnp3_data.config",
    "point_topic": "dnp3/point",
    "outstation_config": {
        "log_levels": ["NORMAL", "ALL_APP_COMMS"]
    },
    "local_ip": "0.0.0.0",
    "port": 20000
}

POINT_CONFIG = {
    "DCHD.WTgt": {"group": 41, "index": 65},
    "DCHD.WTgt-In": {"group": 30, "index": 90},
    "DCHD.WinTms": {"group": 41, "index": 66},
    "DCHD.RmpTms": {"group": 41, "index": 67},
    "DCHD.RevtTms": {"group": 41, "index": 68},
    "DCHD.RmpUpRte": {"group": 41, "index": 69},
    "DCHD.RmpDnRte": {"group": 41, "index": 70},
    "DCHD.ChaRmpUpRte": {"group": 41, "index": 71},
    "DCHD.ChaRmpDnRte": {"group": 41, "index": 72},
    "DCHD.ModPrty": {"group": 41, "index": 9},
    "DCHD.VArAct": {"group": 41, "index": 10},
    "DCHD.ModEna": {"group": 12, "index": 5}
}

web_address = ""


@pytest.fixture(scope="module")
def agent(request, volttron_instance_module_web):
    test_agent = volttron_instance_module_web.build_agent()

    print('Installing DNP3Agent')
    agent_id = volttron_instance_module_web.install_agent(agent_dir=get_services_core("DNP3Agent"),
                                                          config_file=DNP3_AGENT_CONFIG,
                                                          vip_identity=DNP3_AGENT_ID,
                                                          start=True)

    global web_address
    web_address = volttron_instance_module_web.bind_web_address

    def stop():
        volttron_instance_module_web.stop_agent(agent_id)
        test_agent.core.stop()

    gevent.sleep(3)        # wait for agents and devices to start

    request.addfinalizer(stop)

    return test_agent


def run_master():
    manager = asiodnp3.DNP3Manager(1, asiodnp3.ConsoleLogger().Create())
    channel = manager.AddTCPClient("tcpclient",
                                   FILTERS,
                                   asiopal.ChannelRetry(),
                                   HOST,
                                   LOCAL,
                                   PORT,
                                   asiodnp3.PrintingChannelListener().Create())
    stack_config = asiodnp3.MasterStackConfig()
    stack_config.master.responseTimeout = openpal.TimeDuration().Seconds(2)
    stack_config.link.RemoteAddr = 10
    master = channel.AddMaster("master",
                               asiodnp3.PrintingSOEHandler().Create(),
                               asiodnp3.DefaultMasterApplication().Create(),
                               stack_config)

    # Enable the master. This will start communications.
    master.Enable()
    time.sleep(1000)


# Skip these tests for now -- they rely on an installed pydnp3 library that's not available to Travis.
@pytest.mark.skip()
class TestDNP3Agent:
    """Regression tests for the DNP3 Agent."""

    @staticmethod
    def run_master_subprocess():
        exit_dict = Manager().dict()
        master_subprocess = Process(target=run_master)
        master_subprocess.start()
        master_subprocess.join(timeout=2)
        master_subprocess.terminate()
        assert exit_dict.get("AssertionError", None) is None

    @staticmethod
    def config_points(agent, point_config):
        return agent.vip.rpc.call(DNP3_AGENT_ID, 'config_points', point_config).get(timeout=10)

    @staticmethod
    def get_point(agent, point_name):
        """Ask DNP3Agent for a point value for a DNP3 resource."""
        return agent.vip.rpc.call(DNP3_AGENT_ID, 'get_point', point_name).get(timeout=10)

    @staticmethod
    def set_point(agent, point_name, value):
        """Use DNP3Agent to set a point value for a DNP3 resource."""
        return agent.vip.rpc.call(DNP3_AGENT_ID, 'set_point', point_name, value).get(timeout=10)

    @pytest.mark.skip(reason='Dependency on pydnp3 library')
    def test_get_point(self, agent):
        self.run_master_subprocess()
        self.config_points(agent, POINT_CONFIG)
        self.get_point(agent, TEST_GET_POINT_NAME)

    @pytest.mark.skip(reason='Dependency on pydnp3 library')
    def test_set_point(self, agent):
        self.run_master_subprocess()
        self.config_points(agent, POINT_CONFIG)
        self.set_point(agent, TEST_SET_POINT_NAME, 10)
