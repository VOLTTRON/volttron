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

import os
import json
import gevent
import pytest
import paho.mqtt.client as mqtt_client
from paho.mqtt.client import MQTTv311, MQTTv31

from volttron.platform import get_services_core
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod
from volttron.platform.messaging.health import STATUS_GOOD

default_config_path = os.path.join(get_services_core("MQTTHistorian"), "config")
with open(default_config_path, "r") as config_file:
    DEFAULT_CONFIG = json.load(config_file)
assert isinstance(DEFAULT_CONFIG, dict)
mqtt_connection = DEFAULT_CONFIG.get('connection')
assert mqtt_connection and isinstance(mqtt_connection, dict)
MQTT_PORT = int(mqtt_connection.get('mqtt_port')) if 'mqtt_port' in mqtt_connection else 1883
MQTT_PROTOCOL = mqtt_connection.get('mqtt_protocol') if 'mqtt_protocol' in mqtt_connection else "MQTTv311"
if MQTT_PROTOCOL == "MQTTv311":
    MQTT_PROTOCOL = MQTTv311
elif MQTT_PROTOCOL == "MQTTv31":
    MQTT_PROTOCOL = MQTTv31
else:
    raise ValueError('MQTT protocol expects MQTTv311 or MQTTv31')

TEST_PUBLISH = [{'SampleLong1': 50, 'SampleBool1': True, 'SampleFloat1': 10.0, }, {'SampleFloat1': {'units': 'PPM', " \
              "'type': 'integer', 'tz': 'US/Pacific'}, 'SampleLong1': {'units': 'Enumeration', 'type': 'integer', " \
              "'tz': 'US/Pacific'}, 'SampleBool1': {'units': 'On / Off', 'type': 'integer', 'tz': 'US/Pacific'}}]
TEST_TOPIC = 'devices/campus/building/fake/all'


@pytest.fixture(scope="module")
def helper_agent(request, volttron_instance):
    # 1: Start a fake agent to query the historian agent in volttron_instance
    agent = volttron_instance.build_agent()

    # 2: add a tear down method to stop the fake agent that published to message bus
    def stop_agent():
        print("In teardown method of helper_agent")
        agent.core.stop()

    request.addfinalizer(stop_agent)
    return agent


@pytest.fixture(scope='module')
def mqtt_broker_client(request):
    client = mqtt_client.Client()

    def on_connect(client, userdata, flags, rc):
        print('Starting Paho-MQTT client')
        client.subscribe('#')

    client.on_connect = on_connect

    client.connect_async('localhost', port=MQTT_PORT)
    client.loop_start()

    def stop_client():
        client.loop_stop()
        client.disconnect()

    request.addfinalizer(stop_client)
    return client


@pytest.mark.historian
def test_can_publish_individual_points(volttron_instance, helper_agent, mqtt_broker_client):
    """
    Test the agent will by default subscribe to devices topics and publish "all" publish data as individual points
    """
    # publish a device "all" publish with a few points, by default we should see each point from the all publish as
    # a single publish on the MQTT broker
    uuid = volttron_instance.install_agent(
        agent_dir=get_services_core("MQTTHistorian"),
        config_file=DEFAULT_CONFIG,
        start=True,
        vip_identity="mqtt_historian")

    assert helper_agent.vip.rpc.call("mqtt_historian", "health.get_status").get(timeout=10).get('status') == STATUS_GOOD

    callback_messages = {}

    def on_message(client, userdata, message):
        if message.topic not in callback_messages:
            callback_messages[message.topic] = []
        callback_messages[message.topic].append(message.payload.decode('utf-8'))

    mqtt_broker_client.on_message = on_message
    gevent.sleep(1)

    utcnow = utils.get_aware_utc_now()
    utcnow_string = utils.format_timestamp(utcnow)
    headers = {
        headers_mod.DATE: utcnow_string,
        headers_mod.TIMESTAMP: utcnow_string,
        headers_mod.SYNC_TIMESTAMP: utcnow_string
    }

    print('Sending device data to VOLTTRON messagebus')
    helper_agent.vip.pubsub.publish('pubsub',
                                    TEST_TOPIC,
                                    headers=headers,
                                    message=TEST_PUBLISH).get(timeout=10.0)

    gevent.sleep(3)

    assert len(callback_messages) == len(TEST_PUBLISH[0])
    for topic, value in callback_messages.items():
        point = topic.split("/")[-1]
        assert point in TEST_PUBLISH[0]
        for datapoint in value:
            # account for True in Python dict being capitalized but lower in JSON
            if datapoint.lower() == 'true':
                assert datapoint.lower() == str(TEST_PUBLISH[0][point]).lower()
            else:
                assert datapoint == str(TEST_PUBLISH[0][point])

    volttron_instance.stop_agent(uuid)


@pytest.mark.historian
def test_can_publish_all_topic(volttron_instance, helper_agent, mqtt_broker_client):
    """
    Test that using custom topics we can output the entirety of a device "all" publish to a single topic on the broker
    """
    # publish a device "all" publish with a few points, using a different config we should be able to get the entire
    # "all" publish as a single topic on the broker
    # prevent capturing device data normally, capture device topics using the record data capture method
    config_additions = {"capture_device_data": False,
                        "custom_topics": {
                            "capture_record_data": ["devices"]}}
    config = DEFAULT_CONFIG.copy()
    config.update(config_additions)

    uuid = volttron_instance.install_agent(
        agent_dir=get_services_core("MQTTHistorian"),
        config_file=config,
        start=True,
        vip_identity="mqtt_all_publish")

    assert helper_agent.vip.rpc.call("mqtt_all_publish", "health.get_status").get(timeout=10).get('status') == STATUS_GOOD

    callback_messages = {}

    def on_message(client, userdata, message):
        if message.topic not in callback_messages:
            callback_messages[message.topic] = []
        callback_messages[message.topic].append(message.payload.decode('utf-8'))

    mqtt_broker_client.on_message = on_message

    gevent.sleep(1)

    utcnow = utils.get_aware_utc_now()
    utcnow_string = utils.format_timestamp(utcnow)
    headers = {
        headers_mod.DATE: utcnow_string,
        headers_mod.TIMESTAMP: utcnow_string,
        headers_mod.SYNC_TIMESTAMP: utcnow_string
    }

    print('Sending device data to VOLTTRON messagebus')
    helper_agent.vip.pubsub.publish('pubsub',
                                    TEST_TOPIC,
                                    headers=headers,
                                    message=TEST_PUBLISH).get(timeout=10.0)

    gevent.sleep(3)

    assert len(callback_messages) == 1
    for topic, value in callback_messages.items():
        assert topic == TEST_TOPIC
        assert json.loads(value[0]) == TEST_PUBLISH

    volttron_instance.stop_agent(uuid)
