# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
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

import os
import gevent
import json
import pytest
from mock import MagicMock

from volttron.platform.messaging.health import STATUS_GOOD
from volttron.platform import get_ops, get_home
from volttron.platform.vip.agent import Agent

test_path = os.path.join(get_home(), "test.txt")

test_config = {
    "files": [
        {
            "file": test_path,
            "topic": "platform/test_topic"
        }
    ]
}


@pytest.fixture(scope="module")
def publish_agent(request, volttron_instance):
    # 1: Start a fake agent to publish to message bus
    agent = volttron_instance.build_agent(identity='test-agent')

    with open(test_path, "w") as textfile:
        textfile.write("test_data")

    agent.callback = MagicMock(name="callback")
    agent.callback.reset_mock()

    agent.vip.pubsub.subscribe(peer='pubsub', prefix="platform/test_topic", callback=agent.callback).get()

    def stop_agent():
        print("In teardown method of publish_agent")
        if isinstance(agent, Agent):
            agent.core.stop()
        os.remove(test_path)

    request.addfinalizer(stop_agent)
    return agent


def test_default_config(volttron_instance, publish_agent):
    """
    Test the default configuration file included with the agent
    """
    config_path = os.path.join(get_ops("FileWatchPublisher"), "filewatchpublisher.config")
    with open(config_path, "r") as config_file:
        config_json = json.load(config_file)
    assert isinstance(config_json, dict)
    watcher_uuid = volttron_instance.install_agent(
        agent_dir=get_ops("FileWatchPublisher"),
        config_file=config_json,
        start=True,
        vip_identity="health_test")
    assert publish_agent.vip.rpc.call("health_test", "health.get_status").get(timeout=10).get('status') == STATUS_GOOD
    volttron_instance.remove_agent(watcher_uuid)


# def test_file_watcher(volttron_instance, publish_agent):
#     watcher_uuid = volttron_instance.install_agent(
#         agent_dir=get_ops("FileWatchPublisher"),
#         config_file=test_config,
#         start=True,
#         vip_identity="health_test")
#
#     with open(test_path, "w+") as textfile:
#         textfile.write("more test_data")
#
#     gevent.sleep(1)
#
#     assert publish_agent.callback.call_count == 1
#     print(publish_agent.callback.call_args)
#     volttron_instance.remove_agent(watcher_uuid)
