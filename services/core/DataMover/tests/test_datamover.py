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
import random
from datetime import datetime
import gevent
import pytest
from pytest import approx

from volttron.platform import get_services_core
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod
from volttron.platform.messaging import topics
from volttron.platform.vip.agent import Agent
from volttron.platform.keystore import KnownHostsStore

datamover_uuid = None
datamover_config = {
    "destination-vip": "",
    "topic_replace_list": [
        {"from": "PNNL/BUILDING_1", "to": "PNNL/BUILDING1_ANON"}
    ]
}
sqlite_config = {
    "connection": {
        "type": "sqlite",
        "params": {
            "database": 'test.sqlite'
        }
    }
}

volttron_instance1 = None
volttron_instance2 = None


@pytest.fixture(scope="module")
def volttron_instances(request, get_volttron_instances):
    global volttron_instance1, volttron_instance2
    volttron_instance1, volttron_instance2 = get_volttron_instances(2)


# Fixture for setup and teardown of publish agent
@pytest.fixture(scope="module")
def publish_agent(request, volttron_instances, forwarder):
    global volttron_instance1, volttron_instance2
    # 1: Start a fake agent to publish to message bus
    agent = volttron_instance1.build_agent(identity='test-agent')

    # 2: add a tear down method to stop sqlhistorian agent and the fake
    # agent that published to message bus
    def stop_agent():
        print("In teardown method of publish_agent")
        if isinstance(agent, Agent):
            agent.core.stop()

    request.addfinalizer(stop_agent)
    return agent


@pytest.fixture(scope="module")
def query_agent(request, volttron_instances, sqlhistorian):
    # 1: Start a fake agent to query the sqlhistorian in volttron_instance2
    agent = volttron_instance2.build_agent()

    # 2: add a tear down method to stop sqlhistorian agent and the fake agent that published to message bus
    def stop_agent():
        print("In teardown method of module")
        agent.core.stop()

    request.addfinalizer(stop_agent)
    return agent


@pytest.fixture(scope="module")
def sqlhistorian(request, volttron_instances):
    global volttron_instance1, volttron_instance2
    global sqlite_config
    # 1: Install historian agent
    # Install and start sqlhistorian agent in instance2
    agent_uuid = volttron_instance2.install_agent(
        agent_dir=get_services_core("SQLHistorian"),
        config_file=sqlite_config,
        start=True,
        vip_identity='platform.historian')
    print("sqlite historian agent id: ", agent_uuid)


@pytest.fixture(scope="module")
def forwarder(request, volttron_instances):
    global volttron_instance1, volttron_instance2

    global datamover_uuid, datamover_config
    # 1. Update destination address in forwarder configuration

    volttron_instance1.allow_all_connections()
    volttron_instance2.allow_all_connections()

    datamover_config["destination-vip"] = volttron_instance2.vip_address

    known_hosts_file = os.path.join(volttron_instance1.volttron_home, 'known_hosts')
    known_hosts = KnownHostsStore(known_hosts_file)
    known_hosts.add(volttron_instance2.vip_address, volttron_instance2.serverkey)

    # setup destination address to include keys
    datamover_config["destination-serverkey"] = volttron_instance2.serverkey

    # 1: Install historian agent
    # Install and start sqlhistorian agent in instance2
    datamover_uuid = volttron_instance1.install_agent(
        agent_dir=get_services_core("DataMover"),
        config_file=datamover_config,
        start=True)
    print("forwarder agent id: ", datamover_uuid)


def publish(publish_agent, topic, header, message):
    if isinstance(publish_agent, Agent):
        publish_agent.vip.pubsub.publish('pubsub',
                                         topic,
                                         headers=header,
                                         message=message).get(timeout=10)
    else:
        publish_agent.publish_json(topic, header, message)


@pytest.mark.historian
@pytest.mark.forwarder
def test_devices_topic(publish_agent, query_agent):
    """
    Test if devices topic message is getting forwarded to historian running on
    another instance. Test if topic name substitutions happened.
    Publish to 'devices/PNNL/BUILDING_1/Device/all' in volttron_instance1 and query
    for topic 'devices/PNNL/BUILDING1_ANON/Device/all' in volttron_instance2

    :param publish_agent: Fake agent used to publish messages to bus in
    volttron_instance1. Calling this fixture makes sure all the dependant
    fixtures are called to setup and start volttron_instance1 and forwareder
    agent and returns the  instance of fake agent to publish

    :param query_agent: Fake agent used to query sqlhistorian in
    volttron_instance2. Calling this fixture makes sure all the dependant
    fixtures are called to setup and start volttron_instance2 and sqlhistorian
    agent and returns the instance of a fake agent to query the historian
    """
    print("\n** test_devices_topic **")
    oat_reading = random.uniform(30, 100)
    float_meta = {'units': 'F', 'tz': 'UTC', 'type': 'float'}
    # Create a message for all points.
    all_message = [{'OutsideAirTemperature': oat_reading},
                   {'OutsideAirTemperature': float_meta}]

    # Publish messages twice
    time1 = utils.format_timestamp(datetime.utcnow())
    headers = {
        headers_mod.DATE: time1,
        headers_mod.TIMESTAMP: time1
    }
    publish(publish_agent, 'devices/PNNL/BUILDING_1/Device/all', headers, all_message)
    gevent.sleep(3)

    # Verify topic name replacement by querying the replaced topic name
    # PNNL/BUILDING_1 should be replaced with PNNL/BUILDING1_ANON
    result = query_agent.vip.rpc.call(
        'platform.historian',
        'query',
        topic='PNNL/BUILDING1_ANON/Device/OutsideAirTemperature',
        start=time1,
        count=20,
        order="LAST_TO_FIRST").get(timeout=10)

    assert (len(result['values']) == 1)
    (time1_date, time1_time) = time1.split("T")
    assert (result['values'][0][0] == time1_date + 'T' + time1_time + '+00:00')
    assert (result['values'][0][1] == approx(oat_reading))
    assert set(result['metadata'].items()) == set(float_meta.items())


@pytest.mark.historian
@pytest.mark.forwarder
def test_record_topic(publish_agent, query_agent):
    """
    Test if record topic message is getting forwarded to historian running on
    another instance.

    :param publish_agent: Fake agent used to publish messages to bus in
    volttron_instance1. Calling this fixture makes sure all the dependant
    fixtures are called to setup and start volttron_instance1 and forwareder
    agent and returns the  instance of fake agent to publish

    :param query_agent: Fake agent used to query sqlhistorian in
    volttron_instance2. Calling this fixture makes sure all the dependant
    fixtures are called to setup and start volttron_instance2 and sqlhistorian
    agent and returns the instance of a fake agent to query the historian
    """
    # Create timestamp
    print("\n** test_record_topic **")
    now = utils.format_timestamp(datetime.utcnow())
    print("now is ", now)
    headers = {
        headers_mod.DATE: now,
        headers_mod.TIMESTAMP: now
    }
    # Publish messages
    publish(publish_agent, topics.RECORD, headers, 1)

    # sleep so that records gets inserted with unique timestamp
    gevent.sleep(0.5)
    time2 = utils.format_timestamp(datetime.utcnow())
    headers = {
        headers_mod.DATE: time2,
        headers_mod.TIMESTAMP: time2
    }
    publish(publish_agent, topics.RECORD, headers, 'value0')
    # sleep so that records gets inserted with unique timestamp
    gevent.sleep(0.5)
    time3 = utils.format_timestamp(datetime.utcnow())
    headers = {
        headers_mod.DATE: time3,
        headers_mod.TIMESTAMP: time3
    }
    publish(publish_agent, topics.RECORD, headers, {'key': 'value'})
    gevent.sleep(0.5)
    result = query_agent.vip.rpc.call('platform.historian',
                                      'query',
                                      topic=topics.RECORD,
                                      start=now,
                                      order="FIRST_TO_LAST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 3)
    assert (result['values'][0][1] == 1)
    assert (result['values'][1][1] == 'value0')
    assert (result['values'][2][1] == {'key': 'value'})
    assert result['values'][2][0] == time3 + '+00:00'


@pytest.mark.historian
@pytest.mark.forwarder
def test_record_topic_no_header(publish_agent, query_agent):
    """
    Test if record topic message is getting forwarded to historian running on
    another instance.

    :param publish_agent: Fake agent used to publish messages to bus in
    volttron_instance1. Calling this fixture makes sure all the dependant
    fixtures are called to setup and start volttron_instance1 and forwareder
    agent and returns the  instance of fake agent to publish

    :param query_agent: Fake agent used to query sqlhistorian in
    volttron_instance2. Calling this fixture makes sure all the dependant
    fixtures are called to setup and start volttron_instance2 and sqlhistorian
    agent and returns the instance of a fake agent to query the historian
    """
    # Create timestamp
    print("\n** test_record_topic **")
    gevent.sleep(1)  # so that there is no side effect from last test case

    now = datetime.utcnow().isoformat() + 'Z'
    print("now is ", now)
    # Publish messages
    publish(publish_agent, topics.RECORD, None, 1)
    # sleep so that records gets inserted with unique timestamp
    gevent.sleep(0.5)
    publish(publish_agent, topics.RECORD, None, 'value0')
    # sleep so that records gets inserted with unique timestamp
    gevent.sleep(0.5)
    publish(publish_agent, topics.RECORD, None, {'key': 'value'})
    gevent.sleep(1)
    result = query_agent.vip.rpc.call('platform.historian',
                                      'query',
                                      topic=topics.RECORD,
                                      start=now,
                                      order="FIRST_TO_LAST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 3)
    assert (result['values'][0][1] == 1)
    assert (result['values'][1][1] == 'value0')
    assert (result['values'][2][1] == {'key': 'value'})


@pytest.mark.historian
@pytest.mark.forwarder
def test_analysis_topic(publish_agent, query_agent):
    """
    Test if devices topic message is getting forwarded to historian running on
    another instance. Test if topic name substitutions happened.
    Publish to topic
    'analysis/PNNL/BUILDING_1/Device/MixedAirTemperature' in volttron_instance1 and
    query for topic
    'PNNL/BUILDING1_ANON/Device/MixedAirTemperature' in volttron_instance2

    :param publish_agent: Fake agent used to publish messages to bus in
    volttron_instance1. Calling this fixture makes sure all the dependant
    fixtures are called to setup and start volttron_instance1 and forwareder
    agent and returns the  instance of fake agent to publish

    :param query_agent: Fake agent used to query sqlhistorian in
    volttron_instance2. Calling this fixture makes sure all the dependant
    fixtures are called to setup and start volttron_instance2 and sqlhistorian
    agent and returns the instance of a fake agent to query the historian
    """
    print("\n** test_analysis_topic **")
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random.uniform(30, 100)
    mixed_reading = oat_reading + random.uniform(-5, 5)
    damper_reading = random.uniform(0, 100)

    # Create a message for all points.
    all_message = [{'OutsideAirTemperature': oat_reading,
                    'MixedAirTemperature': mixed_reading,
                    'DamperSignal': damper_reading},
                   {'OutsideAirTemperature': {'units': 'F', 'tz': 'UTC',
                                              'type': 'float'},
                    'MixedAirTemperature': {'units': 'F', 'tz': 'UTC',
                                            'type': 'float'},
                    'DamperSignal': {'units': '%', 'tz': 'UTC',
                                     'type': 'float'}
                    }]

    # Create timestamp
    now = utils.format_timestamp(datetime.utcnow())
    print("now is ", now)
    headers = {
        headers_mod.DATE: now,
        headers_mod.TIMESTAMP: now
    }
    # Publish messages
    publish(publish_agent, 'analysis/PNNL/BUILDING_1/Device', headers, all_message)
    gevent.sleep(0.5)

    # pytest.set_trace()
    # Query the historian
    result = query_agent.vip.rpc.call(
        'platform.historian',
        'query',
        topic='PNNL/BUILDING1_ANON/Device/MixedAirTemperature',
        start=now,
        order="LAST_TO_FIRST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 1)
    (now_date, now_time) = now.split("T")
    if now_time[-1:] == 'Z':
        now_time = now_time[:-1]
    assert (result['values'][0][0] == now_date + 'T' + now_time + '+00:00')
    assert (result['values'][0][1] == approx(mixed_reading))


@pytest.mark.historian
@pytest.mark.forwarder
def test_analysis_topic_no_header(publish_agent, query_agent):
    """
    Test if devices topic message is getting forwarded to historian running on
    another instance. Test if topic name substitutions happened.
    Publish to topic
    'analysis/PNNL/BUILDING_1/Device/MixedAirTemperature' in volttron_instance1 and
    query for topic
    'PNNL/BUILDING1_ANON/Device/MixedAirTemperature' in volttron_instance2

    :param publish_agent: Fake agent used to publish messages to bus in
    volttron_instance1. Calling this fixture makes sure all the dependant
    fixtures are called to setup and start volttron_instance1 and forwareder
    agent and returns the  instance of fake agent to publish

    :param query_agent: Fake agent used to query sqlhistorian in
    volttron_instance2. Calling this fixture makes sure all the dependant
    fixtures are called to setup and start volttron_instance2 and sqlhistorian
    agent and returns the instance of a fake agent to query the historian
    """
    print("\n** test_analysis_topic **")
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random.uniform(30, 100)
    mixed_reading = oat_reading + random.uniform(-5, 5)
    damper_reading = random.uniform(0, 100)

    # Create a message for all points.
    all_message = [{'OutsideAirTemperature': oat_reading,
                    'MixedAirTemperature': mixed_reading,
                    'DamperSignal': damper_reading},
                   {'OutsideAirTemperature': {'units': 'F', 'tz': 'UTC',
                                              'type': 'float'},
                    'MixedAirTemperature': {'units': 'F', 'tz': 'UTC',
                                            'type': 'float'},
                    'DamperSignal': {'units': '%', 'tz': 'UTC',
                                     'type': 'float'}
                    }]

    # Create timestamp
    now = datetime.utcnow().isoformat() + 'Z'
    print("now is ", now)

    # Publish messages
    publish(publish_agent, 'analysis/PNNL/BUILDING_1/Device', None, all_message)
    gevent.sleep(0.5)

    # pytest.set_trace()
    # Query the historian
    result = query_agent.vip.rpc.call(
        'platform.historian',
        'query',
        topic='PNNL/BUILDING1_ANON/Device/MixedAirTemperature',
        start=now,
        order="LAST_TO_FIRST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 1)
    assert (result['values'][0][1] == approx(mixed_reading))


@pytest.mark.historian
@pytest.mark.forwarder
def test_log_topic(publish_agent, query_agent):
    """
    Test if log topic message is getting forwarded to historian running on
    another instance. Test if topic name substitutions happened.
    Publish to topic
    'datalogger/PNNL/BUILDING_1/Device' in volttron_instance1 and
    query for topic
    'datalogger/PNNL/BUILDING1_ANON/Device/MixedAirTemperature' in
    volttron_instance2
    Expected result:
     Record should get entered into database with current time at time of
     insertion and should ignore timestamp in header. Topic name
     substitution should have happened


    :param publish_agent: Fake agent used to publish messages to bus in
    volttron_instance1. Calling this fixture makes sure all the dependant
    fixtures are called to setup and start volttron_instance1 and forwareder
    agent and returns the  instance of fake agent to publish

    :param query_agent: Fake agent used to query sqlhistorian in
    volttron_instance2. Calling this fixture makes sure all the dependant
    fixtures are called to setup and start volttron_instance2 and sqlhistorian
    agent and returns the instance of a fake agent to query the historian
    """
    print("\n** test_log_topic **")
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random.uniform(30, 100)
    mixed_reading = oat_reading + random.uniform(-5, 5)

    # Create a message for all points.
    message = {'MixedAirTemperature': {'Readings': mixed_reading,
                                       'Units': 'F',
                                       'tz': 'UTC',
                                       'type': 'float'}}
    # Create timestamp
    current_time = utils.format_timestamp(datetime.utcnow())
    print("current_time is ", current_time)
    future_time = '2017-12-02T00:00:00'
    headers = {
        headers_mod.DATE: future_time,
        headers_mod.TIMESTAMP: future_time
    }
    print("time in header is ", future_time)

    # Publish messages
    publish(publish_agent, "datalogger/PNNL/BUILDING_1/Device", headers, message)
    gevent.sleep(1)

    # Query the historian
    result = query_agent.vip.rpc.call(
        'platform.historian',
        'query',
        start=current_time,
        topic="datalogger/PNNL/BUILDING1_ANON/Device/MixedAirTemperature",
        order="LAST_TO_FIRST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 1)
    assert (result['values'][0][1] == approx(mixed_reading))


@pytest.mark.historian
@pytest.mark.forwarder
def test_log_topic_no_header(publish_agent, query_agent):
    """
    Test if log topic message is getting forwarded to historian running on
    another instance. Test if topic name substitutions happened.
    Publish to topic
    'datalogger/PNNL/BUILDING_1/Device' in volttron_instance1 and
    query for topic
    'datalogger/PNNL/BUILDING1_ANON/Device/MixedAirTemperature' in
    volttron_instance2

    :param publish_agent: Fake agent used to publish messages to bus in
    volttron_instance1. Calling this fixture makes sure all the dependant
    fixtures are called to setup and start volttron_instance1 and forwareder
    agent and returns the  instance of fake agent to publish

    :param query_agent: Fake agent used to query sqlhistorian in
    volttron_instance2. Calling this fixture makes sure all the dependant
    fixtures are called to setup and start volttron_instance2 and sqlhistorian
    agent and returns the instance of a fake agent to query the historian
    """
    print("\n** test_log_topic **")
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random.uniform(30, 100)
    mixed_reading = oat_reading + random.uniform(-5, 5)
    current_time = datetime.utcnow().isoformat()
    # Create a message for all points.
    message = {'MixedAirTemperature': {'Readings': mixed_reading,
                                       'Units': 'F',
                                       'tz': 'UTC',
                                       'type': 'float'}}
    gevent.sleep(1)  # sleep so that there is no side effect from earlier test
    # Publish messages
    publish(publish_agent, "datalogger/PNNL/BUILDING_1/Device", None, message)
    gevent.sleep(0.5)

    # Query the historian
    result = query_agent.vip.rpc.call(
        'platform.historian',
        'query',
        topic="datalogger/PNNL/BUILDING1_ANON/Device/MixedAirTemperature",
        start=current_time,
        order="LAST_TO_FIRST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 1)
    assert (result['values'][0][1] == approx(mixed_reading))


@pytest.mark.historian
@pytest.mark.forwarder
def test_old_config(volttron_instances, forwarder):
    """
    Test adding 'agentid' and 'identity' to config. identity should be 
    supported with "deprecated warning" and "agentid" should get ignored with a
    warning message
    """
    print("\n** test_old_config **")

    global datamover_config

    datamover_config['agentid'] = "test_forwarder_agent_id"
    datamover_config['identity'] = "second forwarder"

    # 1: Install historian agent
    # Install and start sqlhistorian agent in instance2
    uuid = volttron_instance1.install_agent(
        agent_dir=get_services_core("DataMover"),
        config_file=datamover_config,
        start=True)

    print("data_mover agent id: ", uuid)


