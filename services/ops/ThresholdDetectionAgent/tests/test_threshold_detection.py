# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

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

"""
Pytest test cases for ThresholdDetectionAgent
"""

import pytest
import gevent

from volttron.platform import get_ops
from volttron.platform.agent.known_identities import CONFIGURATION_STORE
from volttron.platform.vip.agent import Agent, PubSub
from volttrontesting.utils.utils import poll_gevent_sleep

from volttrontesting.utils import is_running_in_container
from volttron.platform import jsonapi


if is_running_in_container():
    pytest.skip("Test module is flaky in containers", allow_module_level=True)

_default_config = {
    "test_max": {
        "threshold_max": 10
    }
}

_test_config = {
    "test_max": {
        "threshold_max": 10,
    },
    "test_min": {
        "threshold_min": 10,
    },
    "devices/all": {
        "point": {
            "threshold_max": 10,
            "threshold_min": 0,
        }
    }
}


class AlertWatcher(Agent):
    """Keep track of seen alerts"""
    def __init__(self, *args, **kwargs):
        super(AlertWatcher, self).__init__(*args, **kwargs)
        self.seen_alert_keys = set()
        print("Creating AlertWatcher with object_id: {}".format(id(self)))

    @PubSub.subscribe('pubsub', 'alerts')
    def add_alert_key(self, peer, sender, bus, topic, headers, messages):
        print("Tester Agent Got Publish")
        print("object_id: {}".format(id(self)))
        print("SENDER: {}".format(sender))
        print("TOPIC: {}".format(topic))
        print("HEADERS: {}".format(headers))
        print("MESSAGE: {}".format(messages))
        alert_key = headers.get('alert_key')
        if alert_key:
            self.seen_alert_keys.add(alert_key)
        print("ALERT KEYS ARE NOW: {}".format(self.seen_alert_keys))
        print("Finish add_alert_key\n")

    def remove_key(self, key):
        self.seen_alert_keys.remove(key)

    def clear_keys(self):
        self.seen_alert_keys.clear()

    def reset_store(self):
        self.vip.rpc.call(CONFIGURATION_STORE,
                          'manage_store',
                          'platform.thresholddetection',
                          'config',
                          jsonapi.dumps(_test_config),
                          'json').get()


@pytest.fixture(scope="module")
def threshold_tester_agent(volttron_instance):
    """
    Fixture used for setting up ThresholdDetectionAgent and
    tester agents
    """

    print("ADDRESS IS: ", volttron_instance.vip_address)
    threshold_detection_uuid = volttron_instance.install_agent(
        agent_dir=get_ops("ThresholdDetectionAgent"),
        config_file=_default_config,
        start=True)

    agent = volttron_instance.build_agent(agent_class=AlertWatcher,
                                          identity="alert_watcher",
                                          enable_store=True)
    capabilities = {'edit_config_store': {'identity': "platform.thresholddetection"}}
    volttron_instance.add_capabilities(agent.core.publickey, capabilities)

    agent.reset_store()
    # agent.vip.rpc.call(CONFIGURATION_STORE,
    #                    'manage_store',
    #                    'platform.thresholddetection',
    #                    'config',
    #                    jsonapi.dumps(_test_config),
    #                    'json').get()

    yield agent

    agent.vip.rpc.call(CONFIGURATION_STORE,
                       'manage_delete_store',
                       'platform.thresholddetection').get()
    volttron_instance.remove_agent(threshold_detection_uuid)


def publish(agent, config, operation, to_max=True):
    for topic, value in config.items():

        if to_max is True and value.get('threshold_max') is not None:
            threshold = value['threshold_max']
        elif to_max is False and value.get('threshold_min') is not None:
            threshold = value['threshold_min']
        else:
            continue
        print("Publishing on topic: {} value: {}".format(topic, operation(threshold)))
        agent.vip.pubsub.publish('pubsub', topic, None, operation(threshold)).get()


def test_above_max(threshold_tester_agent):
    """Should get alert because values exceed max"""
    publish(threshold_tester_agent, _test_config, lambda x: x+1)
    check = lambda: threshold_tester_agent.seen_alert_keys == set(['test_max'])
    try:
        assert poll_gevent_sleep(5, check)
    finally:
        threshold_tester_agent.clear_keys()


def test_above_min(threshold_tester_agent):
    """Should not get any alerts because values are above min"""
    publish(threshold_tester_agent, _test_config, lambda x: x+1, to_max=False)
    gevent.sleep(1)
    assert len(threshold_tester_agent.seen_alert_keys) == 0


def test_below_max(threshold_tester_agent):
    """Should not get any alerts because values are below max"""
    publish(threshold_tester_agent, _test_config, lambda x: x-1)
    gevent.sleep(1)
    assert len(threshold_tester_agent.seen_alert_keys) == 0


def test_below_min(threshold_tester_agent):
    """Should get alert because values below min"""
    publish(threshold_tester_agent, _test_config, lambda x: x-1, to_max=False)

    try:
        check = lambda: threshold_tester_agent.seen_alert_keys == set(['test_min'])
        assert poll_gevent_sleep(5, check)
    finally:
        threshold_tester_agent.clear_keys()


def test_update_config(threshold_tester_agent):
    updated_config = {
        "updated_topic": {
            "threshold_max": 10,
            "threshold_min": 0,
        }
    }
    print("*******************test_update_config")
    print("Before Modifying Config Store {}".format(threshold_tester_agent.vip.pubsub.list(threshold_tester_agent.core.identity).get()))
    # threshold_tester_agent.vip.pubsub.publish('pubsub', topic="alerts/woot", headers={"foo": "bar"})
    # threshold_tester_agent.vip .config.set('config', updated_config, True)
    threshold_tester_agent.vip.rpc.call(CONFIGURATION_STORE,
                                        'manage_store',
                                        'platform.thresholddetection',
                                        'config',
                                        jsonapi.dumps(updated_config),
                                        'json').get()
    gevent.sleep(0.1)
    # gevent.sleep(1)
    # Sleep for chance to update from config callback.
    # config = threshold_tester_agent.vip.config.get()
    # assert threshold_tester_agent.vip.config.get() == updated_config
    print("Before Publish {}".format(
        threshold_tester_agent.vip.pubsub.list(threshold_tester_agent.core.identity).get()))
    print("Alert keys before: {}".format(threshold_tester_agent.seen_alert_keys))
    publish(threshold_tester_agent, updated_config, lambda x: x+1)
    print("Alert keys after publish: {}".format(threshold_tester_agent.seen_alert_keys))
    print("After Publish Store {}".format(
        threshold_tester_agent.vip.pubsub.list(threshold_tester_agent.core.identity).get()))

    print("Checking object id object_id: {}".format(id(threshold_tester_agent)))
    check = lambda: threshold_tester_agent.seen_alert_keys == set(['updated_topic'])

    try:
        assert poll_gevent_sleep(5, check)
    finally:
        print("Done with testing Now!")
        threshold_tester_agent.clear_keys()
        threshold_tester_agent.reset_store()


def test_device_publish(threshold_tester_agent):
    gevent.sleep(2)
    threshold_tester_agent.vip.pubsub.publish('pubsub', 'devices/all',
                                              headers={}, message=[{'point': 11}]).get()
    gevent.sleep(0.2)
    check = lambda: threshold_tester_agent.seen_alert_keys == set(['devices/all'])
    try:
        assert poll_gevent_sleep(5, check)
    finally:
        threshold_tester_agent.clear_keys()


def test_remove_from_config_store(threshold_tester_agent):
    threshold_tester_agent.vip.rpc.call(CONFIGURATION_STORE,
                                        'manage_delete_config',
                                        'platform.thresholddetection',
                                        'config').get()
    publish(threshold_tester_agent, _test_config, lambda x: x+1)
    publish(threshold_tester_agent, _test_config, lambda x: x-1, to_max=False)
    publish(threshold_tester_agent, _default_config, lambda x: x+1)
    check = lambda: threshold_tester_agent.seen_alert_keys == set(['test_max'])
    try:
        assert poll_gevent_sleep(5, check)
    finally:
        threshold_tester_agent.clear_keys()
