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
# import mysql.connector

# Module level variables
ALL_TOPIC = "devices/Building/LAB/Device/all"
sqlite_platform = {
    "agentid": "sqlhistorian-sqlite",
    "identity": "platform.historian",
    "connection": {
        "type": "sqlite",
        "params": {
            "database": 'test.sqlite'
        }
    }
}
query_points = {
    "oat_point": "Building/LAB/Device/OutsideAirTemperature",
    "mixed_point": "Building/LAB/Device/MixedAirTemperature",
    "damper_point": "Building/LAB/Device/DamperSignal"
}

# Create a database "historian", create user "historian" with passwd "historian" and
# grant historian user access to "historian" database
mysql_platform = {
    "agentid": "sqlhistorian-mysql",
    "identity": "platform.historian",
    "connection": {
        "type": "mysql",
        "params": {
            "host": "localhost",
            "port": 3306,
            "database": "historian",
            "user": "historian",
            "passwd": "historian"
        }
    }
}

db_connection = None
publish_agent = None


# Fixtures for setup and teardown
@pytest.fixture(scope="module", params=[sqlite_platform])
def sqlhistorian(request, volttron_instance1):
    global db_connection, publish_agent
    print("** Setting up test_sqlhistorian module **")
    # Make database connection
    print("request param", request.param)

    # Install and start sqlhistorian agent
    agent_uuid = volttron_instance1.install_agent(
            agent_dir="services/core/SQLHistorian",
            config_file=request.param,
            start=True)
    gevent.sleep(1)
    if request.param['connection']['type'] == "sqlite":
        from os import path
        db_name = request.param['connection']['params']['database']
        database_path = path.join(volttron_instance1.volttron_home,
                                  'agents', agent_uuid,
                                  'sqlhistorianagent-3.0.1/sqlhistorianagent-3.0.1.agent-data/data',
                                  db_name)
        print(database_path)
        assert path.exists(database_path)

        try:
            print "connecting to sqlite path " + database_path
            db_connection = sqlite3.connect(database_path)
            print "successfully connected to sqlite"
        except sqlite3.Error, e:
            pytest.skip(msg="Unable to connect to sqlite databse: " +
                            database_path +
                            " Exception:" + e.args[0])
    elif request.param['connection']['type'] == "mysql":
        print "connect to mysql"
        # db_connection = sqlite3.connect('example.db')
    else:
        pytest.skip(msg="Invalid database type specified " + request.param['connection']['type'])

    # Start a fake agent to publish to message bus
    publish_agent = volttron_instance1.build_agent()
    gevent.sleep(1)

    # add a tear down method to stop sqlhistorian agent and the fake agent that published to message bus
    def stop_agent():
        print("In teardown method of module")
        if db_connection:
            db_connection.close()
        volttron_instance1.stop_agent(agent_uuid)
        publish_agent.core.stop()

    request.addfinalizer(stop_agent)


@pytest.fixture(params=[sqlite_platform])
def clean(request):
    pass

    def delete_row_sqlite():
        global db_connection
        print("Sqlite delete test records")
        cursor = db_connection.cursor()
        cursor.execute("DELETE FROM data")
        cursor.execute("DELETE FROM topics;")
        db_connection.commit()

    if request.param['connection']['type'] == "sqlite":
        print("Adding sqlite finalizer")
        request.addfinalizer(delete_row_sqlite)
    else:
        print ("Adding mysql finalizer")


@pytest.mark.historian
def test_basic_function(volttron_instance1, sqlhistorian, clean):
    """
    Test basic functionality of sql historian. Inserts three points as part of all topic and checks
    if all three got into the database
    :param volttron_instance1: The instance against which the test is run
    :param sqlhistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    global publish_agent, query_points, ALL_TOPIC
    # print('HOME', volttron_instance1.volttron_home)
    print("** test_basic_function **")
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
    now = datetime.utcnow().isoformat(' ')

    # now = '2015-12-02T00:00:00'
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
                                        topic=query_points['oat_point'],
                                        count=20,
                                        order="LAST_TO_FIRST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 1)
    (now_date, now_time) = now.split(" ")
    assert (result['values'][0][0] == now_date + 'T' + now_time)
    assert (result['values'][0][1] == oat_reading)

    # Query the historian
    result = publish_agent.vip.rpc.call('platform.historian',
                                        'query',
                                        topic=query_points['mixed_point'],
                                        count=20,
                                        order="LAST_TO_FIRST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 1)
    (now_date, now_time) = now.split(" ")
    assert (result['values'][0][0] == now_date + 'T' + now_time)
    assert (result['values'][0][1] == mixed_reading)

    # Query the historian
    result = publish_agent.vip.rpc.call('platform.historian',
                                        'query',
                                        topic=query_points['damper_point'],
                                        count=20,
                                        order="LAST_TO_FIRST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 1)
    (now_date, now_time) = now.split(" ")
    assert (result['values'][0][0] == now_date + 'T' + now_time)
    assert (result['values'][0][1] == damper_reading)


# TODO Might need change base on fix to issue #261
@pytest.mark.historian
def test_query_start_time(volttron_instance1, sqlhistorian, clean):
    """
    Test query based on start_time alone. Expected result record with timestamp>= start_time
    :param volttron_instance1: The instance against which the test is run
    :param sqlhistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    global publish_agent, query_points, ALL_TOPIC
    # print('HOME', volttron_instance1.volttron_home)
    print("** test_query_start_time **")
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
        headers_mod.DATE: time1
    }
    publish_agent.vip.pubsub.publish(
            'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)

    gevent.sleep(5)

    # pytest.set_trace()
    # Query the historian
    result = publish_agent.vip.rpc.call('platform.historian',
                                        'query',
                                        topic=query_points['oat_point'],
                                        start=time1,
                                        count=20,
                                        order="LAST_TO_FIRST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 2)
    (time2_date, time2_time) = time2.split(" ")
    # Verify order LAST_TO_FIRST.
    assert (result['values'][0][0] == time2_date + 'T' + time2_time)
    assert (result['values'][0][1] == oat_reading)


# TODO Might need change base on fix to issue #261
@pytest.mark.historian
def test_query_end_time(volttron_instance1, sqlhistorian, clean):
    """
    Test query based on end time alone. Expected result record with timestamp<= end time
    :param volttron_instance1: The instance against which the test is run
    :param sqlhistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    global publish_agent, query_points, ALL_TOPIC
    # print('HOME', volttron_instance1.volttron_home)
    print("** test_query_end_time **")
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
                                        order="FIRST_TO_LAST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 2)
    (time1_date, time1_time) = time1.split(" ")
    # verify ordering("FIRST_TO_LAST" is specified so expecting time1 in index 0
    assert (result['values'][0][0] == time1_date + 'T' + time1_time)
    assert (result['values'][0][1] == mixed_reading)


# TODO Might need change base on fix to issue #261
@pytest.mark.historian
def test_exact_timestamp(volttron_instance1, sqlhistorian, clean):
    """
    Test query based on same start and end time with literal 'Z' at the end of utc time.
    Expected result: record with timestamp == start time
    :param volttron_instance1: The instance against which the test is run
    :param sqlhistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    global publish_agent, query_points, ALL_TOPIC
    # print('HOME', volttron_instance1.volttron_home)
    print("** test_exact_timestamp **")
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

    pytest.set_trace()
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
    assert (result['values'][0][0] == now_date + 'T' + now_time)
    assert (result['values'][0][1] == mixed_reading)


# TODO Might need change base on fix to issue #261
@pytest.mark.historian
def test_zero_timestamp(volttron_instance1, sqlhistorian, clean):
    """
    Test query based with timestamp where time is 00:00:00. Test with and without Z at the end.
    Expected result: record with timestamp == 00:00:00.000001
    :param volttron_instance1: The instance against which the test is run
    :param sqlhistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    global publish_agent, query_points, ALL_TOPIC
    # print('HOME', volttron_instance1.volttron_home)
    print("** test_zero_timestamp **")
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
def test_topic_name_case_change(volttron_instance1, sqlhistorian, clean):
    """
    When case of a topic name changes check if the doesn't cause a duplicate topic in db
    Expected result: The topic name should get updated and topic id should remain same. i.e should be able
    Test issue #234
    to query the same result before and after topic name case change
    :param volttron_instance1: The instance against which the test is run
    :param sqlhistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    global publish_agent, query_points, ALL_TOPIC, db_connection
    # print('HOME', volttron_instance1.volttron_home)
    print("** test_topic_name_case_change **")
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
    pytest.set_trace()
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
def test_invalid_query(volttron_instance1, sqlhistorian, clean):
    """
    Test query with invalid input
    :param volttron_instance1: The instance against which the test is run
    :param sqlhistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    global publish_agent, query_points, ALL_TOPIC
    # print('HOME', volttron_instance1.volttron_home)
    print("** test_invalid_query **")
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
            'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)

    gevent.sleep(5)

    # Query without topic id
    with pytest.raises(Exception) as excinfo:
        publish_agent.vip.rpc.call('platform.historian',
                                   'query',
                                   # topic=query_points['mixed_point'],
                                   start=now,
                                   count=20,
                                   order="LAST_TO_FIRST").get(timeout=20)
    assert '"Topic" required' in str(excinfo.value)

    with pytest.raises(Exception) as excinfo:
        publish_agent.vip.rpc.call('platform.historian1',
                                   'query',
                                   topic=query_points['mixed_point'],
                                   start=now,
                                   count=20,
                                   order="LAST_TO_FIRST").get(timeout=10)
    assert "No route to host: platform.historian1" in str(excinfo.value)
