import random
from datetime import datetime, timedelta

import gevent
import pytest
from volttron.platform.agent import PublishMixin
from volttron.platform.messaging import headers as headers_mod
from volttron.platform.messaging import topics
from volttron.platform.vip.agent import Agent
from gevent.subprocess import Popen
import gevent.subprocess as subprocess
from mock import MagicMock

# import types

forwarder_uuid = None
forwarder_config = {

    "agentid": "forwarder",
    "destination-vip": "",
    "custom_topic_list": [],
    "services_topic_list": [
        "devices", "record", "analysis", "actuators", "datalogger"
    ],
    "topic_replace_list": [
        {"from": "PNNL/BUILDING_1", "to": "PNNL/BUILDING1_ANON"}
    ]
}
sqlite_config = {
    "agentid": "sqlhistorian-sqlite",
    "identity": "platform.historian",
    "connection": {
        "type": "sqlite",
        "params": {
            "database": 'test.sqlite'
        }
    }
}


# Fixture for setup and teardown of publish agent
@pytest.fixture(scope="module",
                params=['volttron_2', 'volttron_3'])
def publish_agent(request, volttron_instance1, forwarder):
    # 1: Start a fake agent to publish to message bus
    if request.param == 'volttron_2':
        agent = PublishMixin(
            volttron_instance1.opts['publish_address'])
    else:
        agent = volttron_instance1.build_agent()

    # 2: add a tear down method to stop sqlhistorian agent and the fake
    # agent that published to message bus
    def stop_agent():
        print("In teardown method of module")
        if isinstance(agent, Agent):
            agent.core.stop()

    request.addfinalizer(stop_agent)
    return agent


@pytest.fixture(scope="module")
def query_agent(request, volttron_instance2, sqlhistorian):
    # 1: Start a fake agent to query the sqlhistorian in volttron_instance2
    agent = volttron_instance2.build_agent()

    # 2: add a tear down method to stop sqlhistorian agent and the fake
    # agent that published to message bus
    def stop_agent():
        print("In teardown method of module")
        agent.core.stop()

    request.addfinalizer(stop_agent)
    return agent


@pytest.fixture(scope="module")
def sqlhistorian(request, volttron_instance2):
    global sqlite_config
    # 1: Install historian agent
    # Install and start sqlhistorian agent in instance2
    agent_uuid = volttron_instance2.install_agent(
        agent_dir="services/core/SQLHistorian",
        config_file=sqlite_config,
        start=True)
    print("sqlite historian agent id: ", agent_uuid)



@pytest.fixture(scope="module")
def forwarder(request, volttron_instance1, volttron_instance2):
    global forwarder_uuid
    # 1. Update destination address in forwarder configuration
    forwarder_config["destination-vip"] = volttron_instance2.vip_address
    # 1: Install historian agent
    # Install and start sqlhistorian agent in instance2
    forwarder_uuid = volttron_instance1.install_agent(
        agent_dir="services/core/ForwardHistorian",
        config_file=forwarder_config,
        start=True)
    print("forwarder agent id: ", forwarder_uuid)


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

    @param publish_agent: Fake agent used to publish messages to bus in
    volttron_instance1. Calling this fixture makes sure all the dependant
    fixtures are called to setup and start volttron_instance1 and forwareder
    agent and returns the  instance of fake agent to publish
    @param query_agent: Fake agent used to query sqlhistorian in
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
    time1 = datetime.utcnow().isoformat(' ')
    headers = {
        headers_mod.DATE: time1
    }
    publish(publish_agent, 'devices/PNNL/BUILDING_1/Device/all', headers, all_message)
    gevent.sleep(1)

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
    (time1_date, time1_time) = time1.split(" ")
    assert (result['values'][0][0] == time1_date + 'T' + time1_time + '+00:00')
    assert (result['values'][0][1] == oat_reading)
    assert set(result['metadata'].items()) == set(float_meta.items())


@pytest.mark.historian
@pytest.mark.forwarder
def test_record_topic(publish_agent, query_agent):
    """
    Test if record topic message is getting forwarded to historian running on
    another instance.

    @param publish_agent: Fake agent used to publish messages to bus in
    volttron_instance1. Calling this fixture makes sure all the dependant
    fixtures are called to setup and start volttron_instance1 and forwareder
    agent and returns the  instance of fake agent to publish
    @param query_agent: Fake agent used to query sqlhistorian in
    volttron_instance2. Calling this fixture makes sure all the dependant
    fixtures are called to setup and start volttron_instance2 and sqlhistorian
    agent and returns the instance of a fake agent to query the historian
    """
    # Create timestamp
    print("\n** test_record_topic **")
    now = datetime.utcnow().isoformat() + 'Z'
    print("now is ", now)
    headers = {
        headers_mod.DATE: now
    }
    # Publish messages
    publish(publish_agent, topics.RECORD, headers, 1)

    # sleep so that records gets inserted with unique timestamp
    gevent.sleep(0.5)
    time2 = datetime.utcnow()
    time2 = time2.isoformat()
    headers = {
        headers_mod.DATE: time2
    }
    publish(publish_agent, topics.RECORD, headers, 'value0')
    # sleep so that records gets inserted with unique timestamp
    gevent.sleep(0.5)
    time3 = datetime.utcnow()
    time3 = time3.isoformat()
    headers = {
        headers_mod.DATE: time3
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

    @param publish_agent: Fake agent used to publish messages to bus in
    volttron_instance1. Calling this fixture makes sure all the dependant
    fixtures are called to setup and start volttron_instance1 and forwareder
    agent and returns the  instance of fake agent to publish
    @param query_agent: Fake agent used to query sqlhistorian in
    volttron_instance2. Calling this fixture makes sure all the dependant
    fixtures are called to setup and start volttron_instance2 and sqlhistorian
    agent and returns the instance of a fake agent to query the historian
    """
    # Create timestamp
    print("\n** test_record_topic **")
    gevent.sleep(1)  # so that there is no side effect from last test case

    now = datetime.utcnow().isoformat() + 'Z'
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

    @param publish_agent: Fake agent used to publish messages to bus in
    volttron_instance1. Calling this fixture makes sure all the dependant
    fixtures are called to setup and start volttron_instance1 and forwareder
    agent and returns the  instance of fake agent to publish
    @param query_agent: Fake agent used to query sqlhistorian in
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
    headers = {
        headers_mod.DATE: now
    }
    # Publish messages
    publish(publish_agent, 'analysis/PNNL/BUILDING_1/Device/MixedAirTemperature',
            headers, all_message)
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
    assert (result['values'][0][1] == mixed_reading)


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

    @param publish_agent: Fake agent used to publish messages to bus in
    volttron_instance1. Calling this fixture makes sure all the dependant
    fixtures are called to setup and start volttron_instance1 and forwareder
    agent and returns the  instance of fake agent to publish
    @param query_agent: Fake agent used to query sqlhistorian in
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
    publish(publish_agent, 'analysis/PNNL/BUILDING_1/Device/MixedAirTemperature',
            None, all_message)
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
    assert (result['values'][0][1] == mixed_reading)


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


    @param publish_agent: Fake agent used to publish messages to bus in
    volttron_instance1. Calling this fixture makes sure all the dependant
    fixtures are called to setup and start volttron_instance1 and forwareder
    agent and returns the  instance of fake agent to publish
    @param query_agent: Fake agent used to query sqlhistorian in
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
    # pytest.set_trace()
    # Create timestamp
    current_time = datetime.utcnow().isoformat() + 'Z'
    print("current_time is ", current_time)
    future_time = '2017-12-02T00:00:00'
    headers = {
        headers_mod.DATE: future_time
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
    assert (result['values'][0][1] == mixed_reading)


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

    @param publish_agent: Fake agent used to publish messages to bus in
    volttron_instance1. Calling this fixture makes sure all the dependant
    fixtures are called to setup and start volttron_instance1 and forwareder
    agent and returns the  instance of fake agent to publish
    @param query_agent: Fake agent used to query sqlhistorian in
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
    assert (result['values'][0][1] == mixed_reading)


@pytest.mark.historian
@pytest.mark.forwarder
def test_actuator_topic(publish_agent, query_agent, volttron_instance1,
                        volttron_instance2):
    print("\n** test_actuator_topic **")

    # Create master driver config and 4 fake devices each with 6 points
    process = Popen(['python', 'config_builder.py', '--count=1',
                     '--publish-only-depth-all',
                     'fake', 'fake_unit_testing.csv', 'null'],
                    env=volttron_instance1.env,
                    cwd='scripts/scalability-testing',
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = process.wait()
    print result
    assert result == 0

    # Start the master driver agent which would intern start the fake driver
    # using the configs created above
    master_uuid = volttron_instance1.install_agent(
        agent_dir="services/core/MasterDriverAgent",
        config_file="scripts/scalability-testing/configs/master-driver.agent",
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

    listener_uuid = volttron_instance2.install_agent(
        agent_dir="examples/ListenerAgent",
        config_file="examples/ListenerAgent/config",
        start=True)
    print("agent id: ", listener_uuid)

    # Make query agent running in instance two subscribe to
    # actuator_schedule_result topic
    # query_agent.callback = types.MethodType(callback, query_agent)
    query_agent.callback = MagicMock(name="callback")
    # subscribe to schedule response topic
    query_agent.vip.pubsub.subscribe(
        peer='pubsub',
        prefix=topics.ACTUATOR_SCHEDULE_RESULT,
        callback=query_agent.callback).get()

    # Now publish in volttron_instance1

    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=2))
    header = {
        'type': 'NEW_SCHEDULE',
        'requesterID': 'test-agent',  # The name of the requesting agent.
        'taskID': 'task_schedule_response',
        'priority': 'LOW'  # ('HIGH, 'LOW', 'LOW_PREEMPT').
    }
    msg = [
        ['fakedriver0', start, end]
    ]
    # reset mock to ignore any previous callback
    publish(publish_agent, topics.ACTUATOR_SCHEDULE_REQUEST, header, msg)
    gevent.sleep(1)  # wait for topic to be forwarded and callback to happen

    # assert query_agent.callback.call_count == 1
    print ('call args ', query_agent.callback.call_args_list)
    # assert query_agent.callback.call_args[0][1] == 'platform.actuator'
    assert query_agent.callback.call_args[0][3] == \
           topics.ACTUATOR_SCHEDULE_RESULT
    result_header = query_agent.callback.call_args[0][4]
    result_message = query_agent.callback.call_args[0][5]
    assert result_header['type'] == 'NEW_SCHEDULE'
    assert result_header['taskID'] == 'task_schedule_response'
    assert result_header['requesterID'] == 'test-agent'
    assert result_message['result'] == 'SUCCESS'


@pytest.mark.historian
@pytest.mark.forwarder
def test_topic_not_forwarded(publish_agent, query_agent, volttron_instance1,
                             volttron_instance2):
    """
    Test if devices topic message is getting forwarded to historian running on
    another instance. Test if topic name substitutions happened.
    Publish to topic
    'datalogger/PNNL/BUILDING_1/Device' in volttron_instance1 and
    query for topic
    'datalogger/PNNL/BUILDING1_ANON/Device/MixedAirTemperature' in
    volttron_instance2

    @param publish_agent: Fake agent used to publish messages to bus in
    volttron_instance1. Calling this fixture makes sure all the dependant
    fixtures are called to setup and start volttron_instance1 and forwareder
    agent and returns the  instance of fake agent to publish
    @param query_agent: Fake agent used to query sqlhistorian in
    volttron_instance2. Calling this fixture makes sure all the dependant
    fixtures are called to setup and start volttron_instance2 and sqlhistorian
    agent and returns the instance of a fake agent to query the historian
    @param volttron_instance1: volttron platform instance in which forward
    historian is running. It forwards to instance2
    @param volttron_instance2: volttron platform instance in which
    sqlhistorian is running.
    """
    print("\n** test_topic_not_forwarded **")
    global forwarder_uuid
    volttron_instance1.stop_agent(forwarder_uuid)

    try:

        print("\n** test_log_topic **")
        new_config = {"agentid": "forwarder",
                      "destination-vip": volttron_instance2.vip_address,
                      "custom_topic_list": [],
                      "services_topic_list":
                          ["devices", "record", "analysis"],
                      "topic_replace_list":
                          [{"from": "PNNL/BUILDING_1", "to": "PNNL/BUILDING1_ANON"}]}

        forwarder_uuid = volttron_instance1.install_agent(
            agent_dir="services/core/ForwardHistorian",
            config_file=new_config,
            start=True)
        gevent.sleep(1)
        # Publish fake data.
        # The format mimics the format used by VOLTTRON drivers.
        # Make some random readings
        oat_reading = random.uniform(30, 100)
        mixed_reading = oat_reading + random.uniform(-5, 5)

        # Create a message for all points.
        message = {
            'MixedAirTemperature': {'Readings': mixed_reading, 'Units': 'F',
                                    'tz': 'UTC', 'type': 'float'}}

        # pytest.set_trace()
        # Create timestamp
        now = datetime.utcnow().isoformat() + 'Z'
        print("now is ", now)
        # now = '2015-12-02T00:00:00'

        # Publish messages
        publish(publish_agent, "datalogger/PNNL/BUILDING_1/Device", None, message)
        gevent.sleep(1)

        # Query the historian
        result = query_agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic="datalogger/PNNL/BUILDING1_ANON/Device/MixedAirTemperature",
            start=now,
            count=20,
            order="LAST_TO_FIRST").get(timeout=10)
        print('Query Result', result)
        assert (result == {})

    finally:
        volttron_instance1.stop_agent(forwarder_uuid)
        forwarder_config["destination-vip"] = volttron_instance2.vip_address
        # 1: Install historian agent
        # Install and start sqlhistorian agent in instance2
        forwarder_uuid = volttron_instance1.install_agent(
            agent_dir="services/core/ForwardHistorian",
            config_file=forwarder_config,
            start=True)

        # def callback(self, peer, sender, bus, topic, headers, message):
        #     print("*************In callback")
        #     print ("topic:", topic, 'header:', headers, 'message:', message)
