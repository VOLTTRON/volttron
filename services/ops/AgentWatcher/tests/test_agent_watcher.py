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

import os
import json
import pytest
import gevent

from volttron.platform import get_ops, get_examples, jsonapi
from volttron.platform.messaging.health import STATUS_GOOD

WATCHER_CONFIG = {
    "watchlist": ["listener"],
    "check-period": 1
}

alert_messages = {}
listener_uuid = None


@pytest.fixture(scope='module')
def platform(request, volttron_instance):
    global listener_uuid

    listener_uuid = volttron_instance.install_agent(
        agent_dir=get_examples("ListenerAgent"),
        vip_identity="listener",
        start=True)
    gevent.sleep(2)

    watcher_uuid = volttron_instance.install_agent(
        agent_dir=get_ops("AgentWatcher"),
        config_file=WATCHER_CONFIG)
    gevent.sleep(2)

    agent = volttron_instance.build_agent()

    def onmessage(peer, sender, bus, topic, headers, message):
        global alert_messages

        alert = jsonapi.loads(message)["context"]

        try:
            alert_messages[alert] += 1
        except KeyError:
            alert_messages[alert] = 1

    agent.vip.pubsub.subscribe(peer='pubsub',
                               prefix='alerts',
                               callback=onmessage)

    def stop():
        volttron_instance.stop_agent(listener_uuid)
        volttron_instance.stop_agent(watcher_uuid)

        volttron_instance.remove_agent(listener_uuid)
        volttron_instance.remove_agent(watcher_uuid)

        agent.core.stop()
        alert_messages.clear()

    request.addfinalizer(stop)
    return volttron_instance


def test_agent_watcher(platform):
    global alert_messages
    global listener_uuid

    gevent.sleep(2)
    assert not alert_messages

    platform.stop_agent(listener_uuid)
    gevent.sleep(2)
    assert alert_messages
    assert "Agent(s) expected but but not running ['listener']" in alert_messages

    platform.start_agent(listener_uuid)
    alert_messages.clear()
    gevent.sleep(2)

    assert not alert_messages


def test_default_config(platform):
    """
    Test the default configuration file included with the agent
    """
    publish_agent = platform.build_agent(identity="test_agent")
    gevent.sleep(1)

    config_path = os.path.join(get_ops("AgentWatcher"), "config")
    with open(config_path, "r") as config_file:
        config_json = json.load(config_file)
    assert isinstance(config_json, dict)

    assert 'watchlist' in config_json and 'check-period' in config_json
    assert isinstance(config_json.get('watchlist'), list) and (
            isinstance(config_json.get('check-period'), int) or isinstance(config_json.get('check-period'), float))
    if len(config_json.get('watchlist')) > 0:
        for watch in config_json.get('watchlist'):
            assert isinstance(watch, str)

    platform.install_agent(
        agent_dir=get_ops("AgentWatcher"),
        config_file=config_json,
        start=True,
        vip_identity="health_test")

    gevent.sleep(2)

    if len(config_json.get('watchlist')) > 0:
        assert f"Agent(s) expected but but not running {config_json.get('watchlist')}" in alert_messages
    else:
        assert not alert_messages

    assert publish_agent.vip.rpc.call("health_test", "health.get_status").get(timeout=10).get('status') == STATUS_GOOD

    publish_agent.core.stop()

    gevent.sleep(2)
    assert alert_messages
