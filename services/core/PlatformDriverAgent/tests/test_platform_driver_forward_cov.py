# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
# }}}
import logging
import os
import pytest
import gevent
import gevent.subprocess as subprocess
from gevent.subprocess import check_call
from mock import MagicMock
from volttron.platform.agent import utils
from volttron.platform import get_services_core, get_volttron_root
from volttron.platform.agent.known_identities import PLATFORM_DRIVER

utils.setup_logging()
_log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def test_agent(volttron_instance):
    """Dynamic agent for sending rpc calls and listening to the bus"""
    agent = volttron_instance.build_agent()
    agent.cov_callback = MagicMock(name="cov_callback")
    # subscribe to cov publishes
    agent.vip.pubsub.subscribe(
        peer='pubsub',
        # determine the fake device path
        prefix="devices/fakedriver/all",
        callback=agent.cov_callback).get()

    yield agent

    _log.info("In teardown method of query_agent")
    agent.core.stop()


@pytest.mark.driver
def test_forward_bacnet_cov_value(volttron_instance, test_agent):
    """Tests the functionality of BACnet change of value forwarding in the
    Platform Driver and driver.py"""
    # Reset platform driver config store
    cmd = ['volttron-ctl', 'config', 'delete', PLATFORM_DRIVER, '--all']
    retcode = check_call(cmd, env=volttron_instance.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert retcode == 0

    # Add fake device configuration
    fake_csv_infile = os.path.join(get_volttron_root(), 'examples/configurations/drivers/fake.csv')
    cmd = ['volttron-ctl', 'config', 'store', PLATFORM_DRIVER,
           'fake.csv', fake_csv_infile, '--csv']
    retcode = check_call(cmd, env=volttron_instance.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert retcode == 0

    fakedriver_infile = os.path.join(get_volttron_root(), 'examples/configurations/drivers/fake.config')
    cmd = ['volttron-ctl', 'config', 'store', PLATFORM_DRIVER,
           "devices/fakedriver", fakedriver_infile, '--json']
    retcode = check_call(cmd, env=volttron_instance.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert retcode == 0

    # install platform driver, start the platform driver, which starts the device
    platform_uuid = volttron_instance.install_agent(
        agent_dir=get_services_core("PlatformDriverAgent"),
        config_file={},
        start=True)
    print("agent id: ", platform_uuid)

    # tell the platform driver to forward the value
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
