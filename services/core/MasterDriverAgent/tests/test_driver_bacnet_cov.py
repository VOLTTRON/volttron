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
import os
import json
import gevent
import gevent.subprocess as subprocess
from gevent.subprocess import Popen
from mock import MagicMock
from volttron.platform import get_services_core
from volttron.platform.agent.known_identities import PLATFORM_DRIVER, \
    CONFIGURATION_STORE
from volttron.platform.messaging.topics import DRIVER_TOPIC_ALL

FAKE_DEVICE_CONFIG = {
    "driver_config": {},
    "registry_config": [],
    "interval": 5,
    "timezone": "US/Pacific",
    "heart_beat_point": "Heartbeat",
    "driver_type": "fakedriver",
    "publish_breadth_first_all": False,
    "publish_depth_first": False,
    "publish_breadth_first": False
}

@pytest.fixture(scope="module")
def test_agent(request, volttron_instance):
    # 1: Start a fake agent for sending rpc calls and listening to the bus
    agent = volttron_instance.build_agent()
    agent.poll_callback = MagicMock(name="poll_callback")
    # subscribe to weather poll results
    agent.vip.pubsub.subscribe(
        peer='pubsub',
        # determine the fake device path
        prefix="",
        callback=agent.poll_callback).get()

    # 2: add a tear down method to stop the fake
    # agent that published to message bus
    def stop_agent():
        print("In teardown method of query_agent")
        agent.core.stop()

    request.addfinalizer(stop_agent)
    return agent

@pytest.mark.dev
def test_cov_forwarding(test_agent, volttron_instance):
    # Reset master driver config store
    cmd = ['volttron-ctl', 'config', 'delete', PLATFORM_DRIVER, '--all']
    process = Popen(cmd, env=volttron_instance.env, cwd=os.getcwd(),
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = process.wait()
    print(result)
    assert result == 0
    test_agent.vip.rpc.call(CONFIGURATION_STORE, "manage_store",
                            PLATFORM_DRIVER, "fake",
                            json.dumps(FAKE_DEVICE_CONFIG),
                            config_type='json',
                            )
    # install master driver
    master_uuid = volttron_instance.install_agent(
        agent_dir=get_services_core("MasterDriverAgent"),
        config_file={},
        start=True)
    # send forward cov rpc call to master driver

    # make magic mock asserts
