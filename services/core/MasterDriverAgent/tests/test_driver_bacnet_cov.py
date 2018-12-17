# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
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

import pytest
import gevent
import gevent.subprocess as subprocess
from mock import MagicMock
from gevent.subprocess import Popen
from volttron.platform import get_services_core
from volttron.platform.agent.known_identities import PLATFORM_DRIVER

@pytest.fixture(scope="module")
def query_agent(request, volttron_instance):
    agent = volttron_instance.build_agent()
    agent.cov_callback = MagicMock(name="cov_callback")
    # subscribe to fake driver's point publish
    # TODO get poll topic for the device
    poll_topic = "alerts"
    agent.vip.pubsub.subscribe(
        peer='pubsub',
        prefix=poll_topic,
        callback=agent.cov_callback).get()

    gevent.sleep(3)

    def stop_agent():
        print("In teardown method of query_agent")
        agent.core.stop()

    request.addfinalizer(stop_agent)
    return agent

@pytest.mark.dev
def test_cov_update_published(volttron_instance, query_agent):
    # Reset master driver config store
    cmd = ['volttron-ctl', 'config', 'delete', PLATFORM_DRIVER, '--all']
    process = Popen(cmd, env=volttron_instance.env,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = process.wait()
    assert result == 0

    # Add registry configuration for the fake driver to the config store
    cmd = ['volttron-ctl', 'config', 'store', PLATFORM_DRIVER,
           'fake.csv', 'examples/configurations/drivers/fake.csv',
           '--csv']
    process = Popen(cmd, env=volttron_instance.env,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = process.wait()
    assert result == 0

    # Add driver configuration to the config store
    cmd = ['volttron-ctl', 'config', 'store', PLATFORM_DRIVER,
           "devices/fakedriver", 'examples/configurations/drivers/fake.config',
           '--json']
    process = Popen(cmd, env=volttron_instance.env,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = process.wait()
    assert result == 0

    # Start the master driver agent which would in turn start the fake driver
    # using the configs created above
    master_uuid = volttron_instance.install_agent(
        agent_dir=get_services_core("MasterDriverAgent"),
        config_file={},
        start=True)
    print("agent id: ", master_uuid)
    gevent.sleep(2)  # wait for the agent to start and start the devices

    # tell the master driver to forward the value
    point_name = "PowerState"
    point_values = {"fake1": 0, "fake2": 1, "fake3": False}
    query_agent.vip.rpc.call(PLATFORM_DRIVER, 'forward_cov_value', point_name,
                             point_values)
    # wait for the publishes to make it to the bus
    gevent.sleep(2)
    # check mock
    print query_agent.cov_callback.call_count
    print query_agent.cov_callback.call_args
