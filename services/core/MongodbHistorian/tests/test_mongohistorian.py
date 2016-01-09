# Example file using the weather agent.
#
# Requirements
#    - A VOLTTRON instance must be started
#    - A weatheragnet must be running prior to running this code.
#
# Author: Craig Allwardt
import pytest
import sqlite3
import gevent
import random
from volttron.platform.messaging import headers as headers_mod
from datetime import datetime
try:
    import pymongo
    HAS_PYMONGO = True
except:
    HAS_PYMONGO = False
# Module level variables
ALL_TOPIC = "devices/Building/LAB/Device/all"

mongo_platform = {
    "agentid": "mongodb-historian",
    "identity": "platform.historian",
    "connection": {
        "type": "mongodb",
        "params": {
            "host": "localhost",
            "port": 27017,
            "database": "mongo_test",
            "user": "test",
            "passwd": "test"
        }
    }
}

query_points = {
    "oat_point": "Building/LAB/Device/OutsideAirTemperature",
    "mixed_point": "Building/LAB/Device/MixedAirTemperature",
    "damper_point": "Building/LAB/Device/DamperSignal"
}

db_connection = None
publish_agent = None
agent_uuid = None

# Fixtures for setup and teardown
@pytest.fixture(scope="module",
    params=[
        pytest.mark.skipif(not HAS_PYMONGO,
            reason='No pymongo client available.')(mongo_platform)
    ])
def mongohistorian(request, volttron_instance1):
    global db_connection, publish_agent, agent_uuid
    print("** Setting up test_mongohistorian module **")
    # Make database connection
    print("request param", request.param)

    # 1: Install historian agent
    #try:
    # Install and start mongohistorian agent
    agent_uuid = volttron_instance1.install_agent(
                agent_dir="services/core/MongodbHistorian",
                config_file=request.param,
                start=True)
    gevent.sleep(1)
    print("agent id: ", agent_uuid)
    # except Exception as exception:
    #     print("Exception installing/starting mongohistorian agent of type " + request.param['connection']['type'] , exception)
    #     pytest.skip(msg='Exception setting up test module: '+ exception.message)

    # 2: Open db connection that can be used for row deletes after each test method
    connect_mongo(request)

    # 3: Start a fake agent to publish to message bus
    try:
        publish_agent = volttron_instance1.build_agent()
        gevent.sleep(1)
    except Exception as exception:
        print("Exception creating publish agent for test ")
        pytest.skip(msg='Exception creating publish agent for test: '+ exception.message)

    # 4: add a tear down method to stop mongohistorian agent and the fake agent that published to message bus
    def stop_agent():
        print("In teardown method of module")
        if db_connection:
            db_connection.close()
            print("closed connection to db")

        volttron_instance1.stop_agent(agent_uuid)
        #volttron_instance1.remove_agent(agent_uuid)

        publish_agent.core.stop()

    request.addfinalizer(stop_agent)
    return request.param

def connect_mongo(request):
    print('connecting to mongo database')
    params = request.param['connection']['params']
    mongo_uri = "mongodb://{user}:{passwd}@{host}:{port}/{database}".format(
        **params)
    return pymongo.MongoClient(mongo_uri)

def database_name(request):
    return request.params['connection']['params']['database']

@pytest.fixture()
def clean(request, mongohistorian):
    def delete_rows():
        global db_connection
        db = db_connection[mongo_platform['connection']['params']['database']]
        # db.data.remove()
        # db.topics.remove()
        print("deleted test records")

    request.addfinalizer(delete_rows)

@pytest.mark.historian
@pytest.mark.mongodb
def test_can_connect(mongohistorian, clean):
    ''' Tests whether we can connect to the mongo database at all.

    Test that we can read/write data on the database while we are at it.
    '''
    global db_connection
    db = db_connection[mongo_platform['connection']['params']['database']]
    result = db.test.insert_one({'x': 1})
    assert result > 0
    result = db.test.insert_one({'here': 'Data to search on'})
    assert result > 0

    result = db.test.find_one({'x': 1})
    assert result['x'] == 1
    result = db.test.find_one({'here': 'Data to search on'})
    assert result['here'] == 'Data to search on'
    assert db.test.remove()



def publish_fake_data(agent):
    '''
    Publishes an all message to the passed instances of volttron's message bus.

    The format mimics the format used by VOLTTRON drivers. Uses the passed
    agent's vip pubsub to publish an all message.

    returns a dictionary of random readings
        {
            "datetime": isoformatted string,
            "oat_reading": number,
            "mixed_reading": number,
            "damper_reading": number
        }
    '''
    global ALL_TOPIC

    # Make some random readings
    oat_reading = random.uniform(30, 100)
    mixed_reading = oat_reading + random.uniform(-5, 5)
    damper_reading = random.uniform(0, 100)

    # Create a message for all points.
    all_message = [{'OutsideAirTemperature': oat_reading, 'MixedAirTemperature': mixed_reading,
                    'DamperSignal': damper_reading},
                   {'OutsideAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                    'MixedAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                    'DamperSignal': {'units': '%', 'tz': 'UTC', 'type': 'float'}
                    }]

    # Create timestamp
    now = datetime.utcnow().isoformat(' ')

    # now = '2015-12-02T00:00:00'
    headers = {
        headers_mod.DATE: now
    }

    # Publish messages
    publish_agent.vip.pubsub.publish(
            'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)

    return {
        "datetime": now,
        "oat_reading": oat_reading,
        "mixed_reading": mixed_reading,
        "damper_reading": damper_reading
    }



@pytest.mark.historian
@pytest.mark.mongodb
def test_basic_function(volttron_instance1, mongohistorian, clean):
    """
    Test basic functionality of sql historian. Inserts three points as part of all topic and checks
    if all three got into the database
    :param volttron_instance1: The instance against which the test is run
    :param mongohistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    global query_points,  db_connection
    # print('HOME', volttron_instance1.volttron_home)
    print("\n** test_basic_function **")

    publish_agent = volttron_instance1.build_agent()

    # Publish data to message bus that should be recorded in the mongo database.
    expected = publish_fake_data(publish_agent)

    # make sure that we allow some time for publish to happen.
    gevent.sleep(3)
    # Query the historian
    result = publish_agent.vip.rpc.call('platform.historian',
                                        'query',
                                        topic=query_points['oat_point'],
                                        count=20,
                                        order="LAST_TO_FIRST").get(timeout=100)
    print('Query Result', result)


    #FOR DEBUG - START
    # cursor = db_connection.cursor()
    # cursor.execute(
    #         "SELECT ts FROM data")
    # rows = cursor.fetchall()
    # print("select query result1: " , rows)
    # params = request.param['connection']['params']
    # mongo_uri = "mongodb://{host}:{port}/{database}".format(
    #     **params)
    # new_connection = pymongo.MongoClient(mongo_uri)
    # #
    # ## Query the historian
    # result = publish_agent.vip.rpc.call('platform.historian',
    #                                     'query',
    #                                     topic=query_points['oat_point'],
    #                                     count=20,
    #                                     order="LAST_TO_FIRST").get(timeout=100)
    # print('Query Result', result)
    #
    #
    # cursor = db_connection.cursor()
    # cursor.execute(
    #         "SELECT ts FROM data")
    # rows = cursor.fetchall()
    # print("select query result1: " , rows)
    # params = request.param['connection']['params']
    # mongo_uri = "mongodb://{host}:{port}/{database}".format(
    #     **params)
    # new_connection = pymongo.MongoClient(mongo_uri)
    #
    # if mongohistorian['connection']['type'] == 'mysql':
    #     new_connection = mysql.connect(**mongohistorian['connection']['params'])
    #     newcur = new_connection.cursor()
    #     newcur.execute("SELECT ts from data")
    #     new_rows = newcur.fetchall()
    #     print("select query result2: " , new_rows)
    #     new_connection.close()
    # else:
    #     from os import path
    #     db_name = mongohistorian['connection']['params']['database']
    #     database_path = path.join(volttron_instance1.volttron_home,
    #                           'agents', agent_uuid,
    #                           'mongohistorianagent-3.0.1/mongohistorianagent-3.0.1.agent-data/data',
    #                           db_name)
    #     new_connection = sqlite3.connect(database_path)
    #     newcur = new_connection.cursor()
    #     newcur.execute("SELECT ts from data")
    #     new_rows = newcur.fetchall()
    #     print("select query result2: " , new_rows)
    #     new_connection.close()
    # # FOR DEBUG END
    # assert (len(result['values']) == 1)
    # (now_date, now_time) = now.split(" ")
    # assert (result['values'][0][0] == now_date + 'T' + now_time)
    # assert (result['values'][0][1] == oat_reading)
    #
    # # Query the historian
    # result = publish_agent.vip.rpc.call('platform.historian',
    #                                     'query',
    #                                     topic=query_points['mixed_point'],
    #                                     count=20,
    #                                     order="LAST_TO_FIRST").get(timeout=10)
    # print('Query Result', result)
    # assert (len(result['values']) == 1)
    # (now_date, now_time) = now.split(" ")
    # assert (result['values'][0][0] == now_date + 'T' + now_time)
    # assert (result['values'][0][1] == mixed_reading)
    #
    # # Query the historian
    # result = publish_agent.vip.rpc.call('platform.historian',
    #                                     'query',
    #                                     topic=query_points['damper_point'],
    #                                     count=20,
    #                                     order="LAST_TO_FIRST").get(timeout=10)
    # print('Query Result', result)
    # assert (len(result['values']) == 1)
    # (now_date, now_time) = now.split(" ")
    # assert (result['values'][0][0] == now_date + 'T' + now_time)
    # assert (result['values'][0][1] == damper_reading)


@pytest.mark.historian
def test_exact_timestamp(volttron_instance1, mongohistorian, clean):
    """
    Test query based on same start and end time with literal 'Z' at the end of utc time.
    Expected result: record with timestamp == start time
    :param volttron_instance1: The instance against which the test is run
    :param mongohistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    global publish_agent, query_points, ALL_TOPIC
    # print('HOME', volttron_instance1.volttron_home)
    print("\n** test_exact_timestamp **")
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random.uniform(30, 100)
    mixed_reading = oat_reading + random.uniform(-5, 5)
    damper_reading = random.uniform(0, 100)

    # Create a message for all points.
    all_message = [{'OutsideAirTemperature': oat_reading, 'MixedAirTemperature': mixed_reading,
                    'DamperSignal': damper_reading},
                   {'OutsideAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                    'MixedAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                    'DamperSignal': {'units': '%', 'tz': 'UTC', 'type': 'float'}
                    }]

    # Create timestamp
    now = datetime.utcnow().isoformat(' ') + 'Z'
    print("now is ", now)
    # now = '2015-12-02T00:00:00'
    headers = {
        headers_mod.DATE: now
    }

    # Publish messages
    publish_agent.vip.pubsub.publish(
            'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)

    gevent.sleep(5)

    # pytest.set_trace()
    # Query the historian
    result = publish_agent.vip.rpc.call('platform.historian',
                                        'query',
                                        topic=query_points['mixed_point'],
                                        start=now,
                                        end=now,
                                        count=20,
                                        order="LAST_TO_FIRST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 1)
    (now_date, now_time) = now.split(" ")
    if now_time[-1:] == 'Z':
        now_time = now_time[:-1]
    assert (result['values'][0][0] == now_date + 'T' + now_time)
    assert (result['values'][0][1] == mixed_reading)


@pytest.mark.historian
def test_query_start_time(volttron_instance1, mongohistorian, clean):
    """
    Test query based on start_time alone. Expected result record with timestamp>= start_time
    :param volttron_instance1: The instance against which the test is run
    :param mongohistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    global publish_agent, query_points, ALL_TOPIC
    # print('HOME', volttron_instance1.volttron_home)
    print("\n** test_query_start_time **")
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random.uniform(30, 100)
    mixed_reading = oat_reading + random.uniform(-5, 5)
    damper_reading = random.uniform(0, 100)

    # Create a message for all points.
    all_message = [{'OutsideAirTemperature': oat_reading, 'MixedAirTemperature': mixed_reading,
                    'DamperSignal': damper_reading},
                   {'OutsideAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                    'MixedAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                    'DamperSignal': {'units': '%', 'tz': 'UTC', 'type': 'float'}
                    }]

    # Publish messages twice
    time1 = datetime.utcnow().isoformat(' ')
    headers = {
        headers_mod.DATE: time1
    }
    publish_agent.vip.pubsub.publish(
            'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)
    gevent.sleep(1)
    time2 = datetime.utcnow().isoformat(' ')
    headers = {
        headers_mod.DATE: time2
    }
    publish_agent.vip.pubsub.publish(
            'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)

    gevent.sleep(5)
    # pytest.set_trace()
    # pytest.set_trace()
    # Query the historian
    result = publish_agent.vip.rpc.call('platform.historian',
                                        'query',
                                        topic=query_points['oat_point'],
                                        start=time1,
                                        count=20,
                                        order="LAST_TO_FIRST").get(timeout=10)
    print ("time1:", time1)
    print ("time2:", time2)
    print('Query Result', result)
    assert (len(result['values']) == 2)
    (time2_date, time2_time) = time2.split(" ")
    if time2_time[-1:] == 'Z':
        time2_time = time2_time[:-1]
    # Verify order LAST_TO_FIRST.
    assert (result['values'][0][0] == time2_date + 'T' + time2_time)
    assert (result['values'][0][1] == oat_reading)


@pytest.mark.historian
def test_query_start_time_with_z(volttron_instance1, mongohistorian, clean):
    """
    Test query based on start_time alone. Expected result record with timestamp>= start_time
    :param volttron_instance1: The instance against which the test is run
    :param mongohistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    global publish_agent, query_points, ALL_TOPIC
    # print('HOME', volttron_instance1.volttron_home)
    print("\n** test_query_start_time_with_z **")
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random.uniform(30, 100)
    mixed_reading = oat_reading + random.uniform(-5, 5)
    damper_reading = random.uniform(0, 100)

    # Create a message for all points.
    all_message = [{'OutsideAirTemperature': oat_reading, 'MixedAirTemperature': mixed_reading,
                    'DamperSignal': damper_reading},
                   {'OutsideAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                    'MixedAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                    'DamperSignal': {'units': '%', 'tz': 'UTC', 'type': 'float'}
                    }]

    # Publish messages twice
    time1 = datetime.utcnow().isoformat(' ') + 'Z'
    headers = {
        headers_mod.DATE: time1
    }
    publish_agent.vip.pubsub.publish(
            'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)
    gevent.sleep(1)
    time2 = datetime.utcnow().isoformat(' ') + 'Z'
    headers = {
        headers_mod.DATE: time2
    }
    publish_agent.vip.pubsub.publish(
            'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)

    gevent.sleep(5)

    # Query the historian
    result = publish_agent.vip.rpc.call('platform.historian',
                                        'query',
                                        topic=query_points['oat_point'],
                                        start=time1,
                                        count=20,
                                        order="LAST_TO_FIRST").get(timeout=10)
    print ("time1:", time1)
    print ("time2:", time2)
    print('Query Result', result)
    assert (len(result['values']) == 2)
    (time2_date, time2_time) = time2.split(" ")
    if time2_time[-1:] == 'Z':
        time2_time = time2_time[:-1]
    # Verify order LAST_TO_FIRST.
    assert (result['values'][0][0] == time2_date + 'T' + time2_time)
    assert (result['values'][0][1] == oat_reading)


@pytest.mark.historian
def test_query_end_time(volttron_instance1, mongohistorian, clean):
    """
    Test query based on end time alone. Expected result record with timestamp<= end time
    :param volttron_instance1: The instance against which the test is run
    :param mongohistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    global publish_agent, query_points, ALL_TOPIC, db_connection,agent_uuid
    # print('HOME', volttron_instance1.volttron_home)
    print("\n** test_query_end_time **")

    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random.uniform(30, 100)
    mixed_reading = oat_reading + random.uniform(-5, 5)
    damper_reading = random.uniform(0, 100)

    # Create a message for all points.
    all_message = [{'OutsideAirTemperature': oat_reading, 'MixedAirTemperature': mixed_reading,
                    'DamperSignal': damper_reading},
                   {'OutsideAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                    'MixedAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                    'DamperSignal': {'units': '%', 'tz': 'UTC', 'type': 'float'}
                    }]

    # Publish messages twice
    time1 = datetime.utcnow().isoformat(' ')
    headers = {
        headers_mod.DATE: time1
    }
    publish_agent.vip.pubsub.publish(
            'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)
    gevent.sleep(1)
    time2 = datetime.utcnow().isoformat(' ')
    headers = {
        headers_mod.DATE: time2
    }
    publish_agent.vip.pubsub.publish(
            'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)

    gevent.sleep(5)

    # pytest.set_trace()
    # Query the historian
    result = publish_agent.vip.rpc.call('platform.historian',
                                        'query',
                                        topic=query_points['mixed_point'],
                                        end=time2,
                                        count=20,
                                        order="FIRST_TO_LAST").get(timeout=100)
    print ("time1:", time1)
    print ("time2:", time2)
    print('Query Result', result)

    # FOR DEBUG - START
    cursor = db_connection.cursor()
    cursor.execute(
            "SELECT ts FROM data")
    rows = cursor.fetchall()
    print("select query result1: " , rows)

    if mongohistorian['connection']['type'] == 'mysql':
        new_connection = mysql.connect(**mongohistorian['connection']['params'])
        newcur = new_connection.cursor()
        newcur.execute("SELECT ts from data")
        new_rows = newcur.fetchall()
        print("select query result2: " , new_rows)
        new_connection.close()
    else:
        from os import path
        db_name = mongohistorian['connection']['params']['database']
        database_path = path.join(volttron_instance1.volttron_home,
                              'agents', agent_uuid,
                              'mongohistorianagent-3.0.1/mongohistorianagent-3.0.1.agent-data/data',
                              db_name)
        new_connection = sqlite3.connect(database_path)
        newcur = new_connection.cursor()
        newcur.execute("SELECT ts from data")
        new_rows = newcur.fetchall()
        print("select query result2: " , new_rows)
        new_connection.close()
    # FOR DEBUG - END
    # pytest.set_trace()
    assert (len(result['values']) == 2)
    (time1_date, time1_time) = time1.split(" ")
    # verify ordering("FIRST_TO_LAST" is specified so expecting time1 in index 0
    assert (result['values'][0][0] == time1_date + 'T' + time1_time)
    assert (result['values'][0][1] == mixed_reading)


@pytest.mark.historian
def test_query_end_time_with_z(volttron_instance1, mongohistorian, clean):
    """
    Test query based on end time alone. Expected result record with timestamp<= end time
    :param volttron_instance1: The instance against which the test is run
    :param mongohistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    global publish_agent, query_points, ALL_TOPIC
    # print('HOME', volttron_instance1.volttron_home)
    print("\n** test_query_end_time_with_z **")
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random.uniform(30, 100)
    mixed_reading = oat_reading + random.uniform(-5, 5)
    damper_reading = random.uniform(0, 100)

    # Create a message for all points.
    all_message = [{'OutsideAirTemperature': oat_reading, 'MixedAirTemperature': mixed_reading,
                    'DamperSignal': damper_reading},
                   {'OutsideAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                    'MixedAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                    'DamperSignal': {'units': '%', 'tz': 'UTC', 'type': 'float'}
                    }]

    # Publish messages twice
    time1 = datetime.utcnow().isoformat(' ') + 'Z'
    headers = {
        headers_mod.DATE: time1
    }
    publish_agent.vip.pubsub.publish(
            'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)
    gevent.sleep(1)
    time2 = datetime.utcnow().isoformat(' ') + 'Z'
    headers = {
        headers_mod.DATE: time2
    }
    publish_agent.vip.pubsub.publish(
            'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)

    gevent.sleep(5)

    # pytest.set_trace()
    # Query the historian
    result = publish_agent.vip.rpc.call('platform.historian',
                                        'query',
                                        topic=query_points['mixed_point'],
                                        end=time2,
                                        count=20,
                                        order="FIRST_TO_LAST").get(timeout=10)
    print ("time1:", time1)
    print ("time2:", time2)
    print('Query Result', result)
    # pytest.set_trace()
    assert (len(result['values']) == 2)
    (time1_date, time1_time) = time1.split(" ")
    if time1_time[-1:] == 'Z':
        time1_time = time1_time[:-1]
    # verify ordering("FIRST_TO_LAST" is specified so expecting time1 in index 0
    assert (result['values'][0][0] == time1_date + 'T' + time1_time)
    assert (result['values'][0][1] == mixed_reading)


@pytest.mark.historian
def test_zero_timestamp(volttron_instance1, mongohistorian, clean):
    """
    Test query based with timestamp where time is 00:00:00. Test with and without Z at the end.
    Expected result: record with timestamp == 00:00:00.000001
    :param volttron_instance1: The instance against which the test is run
    :param mongohistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    global publish_agent, query_points, ALL_TOPIC
    # print('HOME', volttron_instance1.volttron_home)
    print("\n** test_zero_timestamp **")
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random.uniform(30, 100)
    mixed_reading = oat_reading + random.uniform(-5, 5)
    damper_reading = random.uniform(0, 100)

    # Create a message for all points.
    all_message = [{'OutsideAirTemperature': oat_reading, 'MixedAirTemperature': mixed_reading,
                    'DamperSignal': damper_reading},
                   {'OutsideAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                    'MixedAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                    'DamperSignal': {'units': '%', 'tz': 'UTC', 'type': 'float'}
                    }]

    # Create timestamp
    now = '2015-12-17 00:00:00.000000Z'
    headers = {
        headers_mod.DATE: now
    }

    # Publish messages
    publish_agent.vip.pubsub.publish(
            'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)

    gevent.sleep(5)

    # Query the historian
    result = publish_agent.vip.rpc.call('platform.historian',
                                        'query',
                                        topic=query_points['mixed_point'],
                                        start=now,
                                        count=20,
                                        order="LAST_TO_FIRST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 1)
    (now_date, now_time) = now.split(" ")
    now_time = now_time[:-2] + '1'
    assert (result['values'][0][0] == now_date + 'T' + now_time)
    assert (result['values'][0][1] == mixed_reading)

    # Create timestamp
    now = '2015-12-17 00:00:00.000000'
    headers = {
        headers_mod.DATE: now
    }

    # Publish messages
    publish_agent.vip.pubsub.publish(
            'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)

    gevent.sleep(5)

    # Query the historian
    result = publish_agent.vip.rpc.call('platform.historian',
                                        'query',
                                        topic=query_points['mixed_point'],
                                        start=now,
                                        count=20,
                                        order="LAST_TO_FIRST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 1)
    (now_date, now_time) = now.split(" ")
    now_time = now_time[:-1] + '1'
    assert (result['values'][0][0] == now_date + 'T' + now_time)
    assert (result['values'][0][1] == mixed_reading)


@pytest.mark.historian
@pytest.mark.xfail
def test_topic_name_case_change(volttron_instance1, mongohistorian, clean):
    """
    When case of a topic name changes check if the doesn't cause a duplicate topic in db
    Expected result: The topic name should get updated and topic id should remain same. i.e should be able
    Test issue #234
    to query the same result before and after topic name case change
    :param volttron_instance1: The instance against which the test is run
    :param mongohistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    global publish_agent, query_points, ALL_TOPIC, db_connection
    # print('HOME', volttron_instance1.volttron_home)
    print("\n** test_topic_name_case_change **")
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random.uniform(30, 100)
    mixed_reading = oat_reading + random.uniform(-5, 5)

    # Create a message for all points.
    all_message = [{'OutsideAirTemperature': oat_reading, 'MixedAirTemperature': mixed_reading},
                   {'OutsideAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                    'MixedAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'}
                    }]

    # Create timestamp
    time1 = '2015-12-17 00:00:00.000000Z'
    headers = {
        headers_mod.DATE: time1
    }

    # Publish messages
    publish_agent.vip.pubsub.publish(
            'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)

    gevent.sleep(5)

    # Create a message for all points.
    all_message = [{'Outsideairtemperature': oat_reading, 'MixedAirTemperature': mixed_reading},
                   {'Outsideairtemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                    'MixedAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'}
                    }]

    # Create timestamp
    time2 = '2015-12-17 01:10:00.000000Z'
    headers = {
        headers_mod.DATE: time2
    }

    # Publish messages
    publish_agent.vip.pubsub.publish(
            'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)
    # Query the historian
    result = publish_agent.vip.rpc.call('platform.historian',
                                        'query',
                                        topic=query_points['oat_point'],
                                        start=time1,
                                        count=20,
                                        order="FIRST_TO_LAST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 2)
    (time1_date, time1_time) = time1.split(" ")
    time1_time = time1_time[:-2] + '1'
    assert (result['values'][0][0] == time1_date + 'T' + time1_time)
    assert (result['values'][0][1] == oat_reading)

    cursor = db_connection.cursor()
    cursor.execute(
            "SELECT topic_name FROM topics WHERE topic_name='Building/LAB/Device/OutsideAirTemperature' COLLATE NOCASE")
    rows = cursor.fetchall()
    print(rows)
    assert rows[0][0] == "Building/LAB/Device/Outsideairtemperature"
    assert len(rows) == 1


@pytest.mark.historian
def test_invalid_query(volttron_instance1, mongohistorian, clean):
    """
    Test query with invalid input
    :param volttron_instance1: The instance against which the test is run
    :param mongohistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    global publish_agent, query_points, ALL_TOPIC
    # print('HOME', volttron_instance1.volttron_home)
    print("\n** test_invalid_query **")
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random.uniform(30, 100)
    mixed_reading = oat_reading + random.uniform(-5, 5)
    damper_reading = random.uniform(0, 100)

    # Create a message for all points.
    all_message = [{'OutsideAirTemperature': oat_reading, 'MixedAirTemperature': mixed_reading,
                    'DamperSignal': damper_reading},
                   {'OutsideAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                    'MixedAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                    'DamperSignal': {'units': '%', 'tz': 'UTC', 'type': 'float'}
                    }]

    # Create timestamp
    now = datetime.utcnow().isoformat(' ') + 'Z'
    headers = {
        headers_mod.DATE: now
    }

    # Publish messages
    publish_agent.vip.pubsub.publish(
            'pubsub', ALL_TOPIC, headers, all_message).get(timeout=5)

    # Query without topic id
    with pytest.raises(Exception) as excinfo:
        publish_agent.vip.rpc.call('platform.historian',
                                   'query',
                                   # topic=query_points['mixed_point'],
                                   start=now,
                                   count=20,
                                   order="LAST_TO_FIRST").get(timeout=10)
        assert '"Topic" required' in str(excinfo.value)

    with pytest.raises(Exception) as excinfo:
        publish_agent.vip.rpc.call('platform.historian1',
                                   'query',
                                   topic=query_points['mixed_point'],
                                   start=now,
                                   count=20,
                                   order="LAST_TO_FIRST").get(timeout=10)
        assert "No route to host: platform.historian1" in str(excinfo.value)
