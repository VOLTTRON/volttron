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

"""
Pytest test cases for testing actuator agent using rpc calls.
"""
from datetime import datetime, timedelta


import gevent
import gevent.subprocess as subprocess
import pytest
from gevent.subprocess import Popen
from mock import MagicMock

from volttron.platform import get_services_core, get_examples, jsonapi
from volttron.platform.jsonrpc import RemoteError
from volttron.platform.messaging import topics
from volttron.platform.agent.known_identities import PLATFORM_DRIVER, CONFIGURATION_STORE

REQUEST_CANCEL_SCHEDULE = 'request_cancel_schedule'
REQUEST_NEW_SCHEDULE = 'request_new_schedule'
PLATFORM_ACTUATOR = 'platform.actuator'
TEST_AGENT = 'test-agent'
PRIORITY_LOW = 'LOW'
SUCCESS = 'SUCCESS'
FAILURE = 'FAILURE'


@pytest.fixture(scope="module")
def publish_agent(request, volttron_instance):
    """
    Fixture used for setting up the environment.
    1. Creates fake driver configs
    2. Starts the master driver agent with the created fake driver agents
    3. Starts the actuator agent
    4. Creates an instance Agent class for publishing and returns it

    :param request: pytest request object
    :param volttron_instance: instance of volttron in which test cases are run
    :return: an instance of fake agent used for publishing
    """

    # Reset master driver config store
    cmd = ['volttron-ctl', 'config', 'delete', PLATFORM_DRIVER, '--all']

    process = Popen(cmd, env=volttron_instance.env,
                    cwd='scripts/scalability-testing',
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    (output, error) = process.communicate()
    assert process.returncode == 0

    # Add master driver configuration files to config store.
    cmd = ['volttron-ctl', 'config', 'store',PLATFORM_DRIVER,
           'fake.csv', 'fake_unit_testing.csv', '--csv']
    process = Popen(cmd, env=volttron_instance.env,
                    cwd='scripts/scalability-testing',
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    result = process.wait()
    assert result == 0

    config_name = "devices/fakedriver"
    cmd = ['volttron-ctl', 'config', 'store', PLATFORM_DRIVER,
           config_name, 'fake_unit_testing.config', '--json']
    process = Popen(cmd, env=volttron_instance.env,
                    cwd='scripts/scalability-testing',
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    result = process.wait()
    assert result == 0

    # Start the master driver agent which would intern start the fake driver
    #  using the configs created above
    master_uuid = volttron_instance.install_agent(
        agent_dir=get_services_core("MasterDriverAgent"),
        config_file={},
        start=True)
    print("agent id: ", master_uuid)
    gevent.sleep(2)  # wait for the agent to start and start the devices

    # Start the actuator agent through which publish agent should communicate
    # to fake device. Start the master driver agent which would intern start
    # the fake driver using the configs created above
    actuator_uuid = volttron_instance.install_agent(
        agent_dir=get_services_core("ActuatorAgent"),
        config_file=get_services_core("ActuatorAgent/tests/actuator.config"),
        start=True)
    print("agent id: ", actuator_uuid)
    gevent.sleep(2)

    example_uuid = volttron_instance.install_agent(
        agent_dir=get_examples("ConfigActuation"),
        config_file={},
        vip_identity="config_actuation")
    gevent.sleep(2)

    # 3: Start a fake agent to publish to message bus
    publish_agent = volttron_instance.build_agent(identity=TEST_AGENT)
    capabilities = {'edit_config_store': {'identity': "config_actuation"}}
    volttron_instance.add_capabilities(publish_agent.core.publickey, capabilities)

    # 4: add a tear down method to stop sqlhistorian agent and the fake agent
    #  \that published to message bus
    def stop_agent():
        print("In teardown method of module")
        volttron_instance.stop_agent(actuator_uuid)
        volttron_instance.stop_agent(master_uuid)
        volttron_instance.stop_agent(example_uuid)
        volttron_instance.remove_agent(actuator_uuid)
        volttron_instance.remove_agent(master_uuid)
        volttron_instance.remove_agent(example_uuid)
        publish_agent.core.stop()

    request.addfinalizer(stop_agent)
    return publish_agent


def test_thing(publish_agent):
    value = publish_agent.vip.rpc.call(PLATFORM_ACTUATOR,
                                       "get_point",
                                       "fakedriver/SampleWritableFloat1").get()
    assert value == 10.0

    publish_agent.vip.rpc.call(CONFIGURATION_STORE,
                               "manage_store",
                               "config_actuation",
                               "fakedriver",
                               jsonapi.dumps({"SampleWritableFloat1": 42.0}),
                               "json").get()

    value = publish_agent.vip.rpc.call(PLATFORM_ACTUATOR,
                                       "get_point",
                                       "fakedriver/SampleWritableFloat1").get()
    assert value == 42.0
