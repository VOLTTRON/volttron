# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

import logging
import pytest
import gevent
import gevent.subprocess as subprocess
from gevent.subprocess import Popen
from mock import MagicMock
from volttron.platform.agent import utils
from volttron.platform import get_services_core
from volttron.platform.agent.known_identities import PLATFORM_DRIVER

utils.setup_logging()
_log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def test_agent(request, volttron_instance):
    """Dynamic agent for sending rpc calls and listening to the bus"""
    agent = volttron_instance.build_agent()
    agent.cov_callback = MagicMock(name="cov_callback")
    # subscribe to cov publishes
    agent.vip.pubsub.subscribe(
        peer='pubsub',
        # determine the fake device path
        prefix="devices/fakedriver/all",
        callback=agent.cov_callback).get()

    def stop_agent():
        print("In teardown method of query_agent")
        agent.core.stop()

    request.addfinalizer(stop_agent)
    return agent


@pytest.mark.driver
def test_cov_update_published(volttron_instance, test_agent):
    """Tests the functionality of BACnet change of value forwarding in the
    Master Driver and driver.py"""
    # Reset master driver config store
    cmd = ['volttron-ctl', 'config', 'delete', PLATFORM_DRIVER, '--all']
    process = Popen(cmd, env=volttron_instance.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = process.wait()
    assert result == 0

    # Add fake device configuration
    cmd = ['volttron-ctl', 'config', 'store', PLATFORM_DRIVER,
           'fake.csv', 'examples/configurations/drivers/fake.csv', '--csv']
    process = Popen(cmd, env=volttron_instance.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = process.wait()
    assert result == 0

    cmd = ['volttron-ctl', 'config', 'store', PLATFORM_DRIVER,
           "devices/fakedriver", 'examples/configurations/drivers/fake.config', '--json']
    process = Popen(cmd, env=volttron_instance.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = process.wait()
    assert result == 0

    # install master driver, start the master driver, which starts the device
    master_uuid = volttron_instance.install_agent(
        agent_dir=get_services_core("MasterDriverAgent"),
        config_file={},
        start=True)
    print("agent id: ", master_uuid)

    # tell the master driver to forward the value
    point_name = "PowerState"
    device_path = "fakedriver"
    result_dict = {"fake1": "test", "fake2": "test", "fake3": "test"}
    test_agent.vip.rpc.call(PLATFORM_DRIVER, 'forward_bacnet_cov_value', device_path, point_name, result_dict)
    # wait for the publishes to make it to the bus
    gevent.sleep(2)

    # Mock checks
    # Should have one "PowerState" publish for each item in the result dict
    # Total all publishes likely will include regular scrapes
    assert test_agent.cov_callback.call_count >= 3
    test_count = 0
    for call_arg in test_agent.cov_callback.call_args_list:
        if call_arg[0][5][0].get("PowerState", False):
            test_count += 1
    assert test_count == 3
