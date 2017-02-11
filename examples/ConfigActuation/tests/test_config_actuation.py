# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

"""
Pytest test cases for testing actuator agent using rpc calls.
"""
from datetime import datetime, timedelta

import json
import gevent
import gevent.subprocess as subprocess
import pytest
from gevent.subprocess import Popen
from mock import MagicMock
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
def publish_agent(request, volttron_instance1):
    """
    Fixture used for setting up the environment.
    1. Creates fake driver configs
    2. Starts the master driver agent with the created fake driver agents
    3. Starts the actuator agent
    4. Creates an instance Agent class for publishing and returns it

    :param request: pytest request object
    :param volttron_instance1: instance of volttron in which test cases are run
    :return: an instance of fake agent used for publishing
    """

    # Reset master driver config store
    cmd = ['volttron-ctl', 'config', 'delete', PLATFORM_DRIVER, '--all']

    process = Popen(cmd, env=volttron_instance1.env,
                    cwd='scripts/scalability-testing',
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = process.wait()
    print(result)
    assert result == 0

    # Add master driver configuration files to config store.
    cmd = ['volttron-ctl', 'config', 'store',PLATFORM_DRIVER,
           'fake.csv', 'fake_unit_testing.csv', '--csv']
    process = Popen(cmd, env=volttron_instance1.env,
                    cwd='scripts/scalability-testing',
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = process.wait()
    print(result)
    assert result == 0

    config_name = "devices/fakedriver"
    cmd = ['volttron-ctl', 'config', 'store', PLATFORM_DRIVER,
           config_name, 'fake_unit_testing.config', '--json']
    process = Popen(cmd, env=volttron_instance1.env,
                    cwd='scripts/scalability-testing',
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = process.wait()
    print(result)
    assert result == 0

    # Start the master driver agent which would intern start the fake driver
    #  using the configs created above
    master_uuid = volttron_instance1.install_agent(
        agent_dir="services/core/MasterDriverAgent",
        config_file={},
        start=True)
    print("agent id: ", master_uuid)
    gevent.sleep(2)  # wait for the agent to start and start the devices

    # Start the actuator agent through which publish agent should communicate
    # to fake device. Start the master driver agent which would intern start
    # the fake driver using the configs created above
    actuator_uuid = volttron_instance1.install_agent(
        agent_dir="services/core/ActuatorAgent",
        config_file="services/core/ActuatorAgent/tests/actuator.config",
        start=True)
    print("agent id: ", actuator_uuid)
    gevent.sleep(2)


    example_uuid = volttron_instance1.install_agent(
        agent_dir="examples/ConfigActuation",
        config_file={},
        vip_identity="config_actuation")
    gevent.sleep(2)

    # 3: Start a fake agent to publish to message bus
    publish_agent = volttron_instance1.build_agent(identity=TEST_AGENT)

    # 4: add a tear down method to stop sqlhistorian agent and the fake agent
    #  \that published to message bus
    def stop_agent():
        print("In teardown method of module")
        volttron_instance1.stop_agent(actuator_uuid)
        volttron_instance1.stop_agent(master_uuid)
        volttron_instance1.stop_agent(example_uuid)
        volttron_instance1.remove_agent(actuator_uuid)
        volttron_instance1.remove_agent(master_uuid)
        volttron_instance1.remove_agent(example_uuid)
        publish_agent.core.stop()

    request.addfinalizer(stop_agent)
    return publish_agent


@pytest.mark.skipif("True", "4.1 need to fix")
def test_thing(publish_agent):
    value = publish_agent.vip.rpc.call(PLATFORM_ACTUATOR,
                                       "get_point",
                                       "fakedriver/SampleWritableFloat1").get()
    assert value == 10.0

    publish_agent.vip.rpc.call(CONFIGURATION_STORE,
                               "manage_store",
                               "config_actuation",
                               "fakedriver",
                               json.dumps({"SampleWritableFloat1": 42.0}),
                               "json").get()

    value = publish_agent.vip.rpc.call(PLATFORM_ACTUATOR,
                                       "get_point",
                                       "fakedriver/SampleWritableFloat1").get()
    assert value == 42.0
