# pytest test cases for SQLHistorian
# For mysql test's to succeed
# 1. MySql server should be running
# 2. test database and test user should exist
# 3. Test user should have all privileges on test database
# 4. Refer to the dictionary object mysql_platform for the server configuration
import random
import sqlite3
from datetime import datetime, timedelta

import gevent
import pytest
import re
from volttron.platform.messaging import headers as headers_mod
from volttron.platform.messaging import topics
from volttron.platform.agent import utils

try:
    import mysql.connector as mysql
    from mysql.connector import errorcode

    HAS_MYSQL_CONNECTOR = True
except:
    HAS_MYSQL_CONNECTOR = False
# Module level variables
ALL_TOPIC = "devices/Building/LAB/Device/all"
query_points = {
    "oat_point": "Building/LAB/Device/OutsideAirTemperature",
    "mixed_point": "Building/LAB/Device/MixedAirTemperature",
    "damper_point": "Building/LAB/Device/DamperSignal"
}
# default table_defs
sqlite_platform1 = {
    "agentid": "sqlhistorian-sqlite",
    "identity": "platform.historian",
    "connection": {
        "type": "sqlite",
        "params": {
            "database": 'test.sqlite'
        }
    }
}
# table_defs without prefix
sqlite_platform2 = {
    "agentid": "sqlhistorian-sqlite",
    "identity": "platform.historian",
    "connection": {
        "type": "sqlite",
        "params": {
            "database": 'test.sqlite'
        }
    },
    "tables_def": {
        "table_prefix": "",
        "data_table": "data_table",
        "topics_table": "topics_table",
        "meta_table": "meta_table",
    }
}
# table_defs with prefix
sqlite_platform3 = {
    "agentid": "sqlhistorian-sqlite",
    "identity": "platform.historian",
    "connection": {
        "type": "sqlite",
        "params": {
            "database": 'test.sqlite'
        }
    },
    "tables_def": {
        "table_prefix": "prefix",
        "data_table": "data_table",
        "topics_table": "topics_table",
        "meta_table": "meta_table",
    }
}

# Create a database "historian", create user "historian" with passwd
# "historian" and grant historian user access to "historian" database

# config without table_defs
mysql_platform1 = {
    "agentid": "sqlhistorian-mysql",
    "identity": "platform.historian",
    "connection": {
        "type": "mysql",
        "params": {
            "host": "localhost",
            "port": 3306,
            "database": "test_historian",
            "user": "historian",
            "passwd": "historian"
        }
    }
}
# table_defs without prefix
mysql_platform2 = {
    "agentid": "sqlhistorian-mysql",
    "identity": "platform.historian",
    "connection": {
        "type": "mysql",
        "params": {
            "host": "localhost",
            "port": 3306,
            "database": "test_historian",
            "user": "historian",
            "passwd": "historian"
        }
    },
    "tables_def": {
        "table_prefix": "",
        "data_table": "data_table",
        "topics_table": "topics_table",
        "meta_table": "meta_table",
    }
}
# table_defs with prefix
mysql_platform3 = {
    "agentid": "sqlhistorian-mysql",
    "identity": "platform.historian",
    "connection": {
        "type": "mysql",
        "params": {
            "host": "localhost",
            "port": 3306,
            "database": "test_historian",
            "user": "historian",
            "passwd": "historian"
        }
    },
    "tables_def": {
        "table_prefix": "prefix",
        "data_table": "data_table",
        "topics_table": "topics_table",
        "meta_table": "meta_table",
    }
}

offset = timedelta(seconds=3)
db_connection = None
MICROSECOND_SUPPORT = True

# Don't like declaring this global but I am not able to find a way
# to introspect this using pytest request object in the clean fixture
data_table = 'data'
topics_table = 'topics'
meta_table = 'meta'


# Fixtures for setup and teardown
@pytest.fixture(scope="module",
                params=[
                    pytest.mark.skipif(
                        not HAS_MYSQL_CONNECTOR,
                        reason='No mysql client available.')(mysql_platform1),
                    pytest.mark.skipif(
                        not HAS_MYSQL_CONNECTOR,
                        reason='No mysql client available.')(mysql_platform2),
                    pytest.mark.skipif(
                        not HAS_MYSQL_CONNECTOR,
                        reason='No mysql client available.')(mysql_platform3),
                    sqlite_platform1,
                    sqlite_platform2,
                    sqlite_platform3
                ])
def sqlhistorian(request, volttron_instance1):
    global db_connection, publish_agent, agent_uuid, data_table, \
        topics_table, meta_table
    print("** Setting up test_sqlhistorian module **")
    # Make database connection
    print("request param", request.param)
    if request.param['connection']['type'] == 'sqlite':
        request.param['connection']['params']['database'] = \
            volttron_instance1.volttron_home + "/historian.sqlite"

    # 1: Install historian agent
    # Install and start sqlhistorian agent
    agent_uuid = volttron_instance1.install_agent(
        agent_dir="services/core/SQLHistorian",
        config_file=request.param,
        start=True)
    print("agent id: ", agent_uuid)

    # figure out table names from config
    # Set this hear so that cleanup fixture can use it
    if request.param.get('tables_def', None) is None:
        data_table = 'data'
        topics_table = 'topics'
        meta_table = 'meta'
    elif request.param['tables_def']['table_prefix']:
        data_table = request.param['tables_def']['table_prefix'] + "_" + \
            request.param['tables_def']['data_table']
        topics_table = request.param['tables_def']['table_prefix'] + "_" + \
            request.param['tables_def']['topics_table']
        meta_table = request.param['tables_def']['table_prefix'] + "_" + \
            request.param['tables_def']['meta_table']
    else:
        data_table = request.param['tables_def']['data_table']
        topics_table = request.param['tables_def']['topics_table']
        meta_table = request.param['tables_def']['meta_table']

    # 2: Open db connection that can be used for row deletes after
    # each test method. Create tables in case of mysql
    if request.param['connection']['type'] == "sqlite":
        connect_sqlite(request)
    elif request.param['connection']['type'] == "mysql":
        connect_mysql(request)
    else:
        print("Invalid database type specified " + request.param['connection'][
            'type'])
        pytest.fail(msg="Invalid database type specified " +
                        request.param['connection']['type'])

    # 3: Start a fake agent to publish to message bus
    publish_agent = volttron_instance1.build_agent()

    # 4: add a tear down method to stop sqlhistorian agent and the fake
    # agent that published to message bus
    def stop_agent():
        print("In teardown method of module")
        if db_connection:
            db_connection.close()
            print("closed connection to db")

        volttron_instance1.stop_agent(agent_uuid)
        publish_agent.core.stop()

    request.addfinalizer(stop_agent)
    return request.param


def connect_mysql(request):
    global db_connection, MICROSECOND_SUPPORT, data_table,\
        topics_table, meta_table
    print "connect to mysql"
    db_connection = mysql.connect(**request.param['connection']['params'])
    cursor = db_connection.cursor()
    cursor.execute("SELECT version()")
    version = cursor.fetchone()
    p = re.compile('(\d+)\D+(\d+)\D+(\d+)\D*')
    version_nums = p.match(version[0]).groups()

    print (version)
    if int(version_nums[0]) < 5:
        MICROSECOND_SUPPORT = False
    elif int(version_nums[1]) < 6:
        MICROSECOND_SUPPORT = False
    elif int(version_nums[2]) < 4:
        MICROSECOND_SUPPORT = False
    else:
        MICROSECOND_SUPPORT = True

    cursor = db_connection.cursor()
    print("MICROSECOND_SUPPORT ", MICROSECOND_SUPPORT)

    if MICROSECOND_SUPPORT:
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS ' + data_table +
            ' (ts timestamp(6) NOT NULL,\
             topic_id INTEGER NOT NULL, \
             value_string TEXT NOT NULL, \
             UNIQUE(ts, topic_id))')
    else:
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS ' + data_table +
            ' (ts timestamp NOT NULL,\
             topic_id INTEGER NOT NULL, \
             value_string TEXT NOT NULL, \
             UNIQUE(ts, topic_id))')
    cursor.execute(
        'CREATE TABLE IF NOT EXISTS ' + topics_table +
        ' (topic_id INTEGER NOT NULL AUTO_INCREMENT, \
         topic_name varchar(512) NOT NULL, \
         PRIMARY KEY (topic_id),\
         UNIQUE(topic_name))')

    cursor.execute(
        'CREATE TABLE IF NOT EXISTS ' + meta_table +
        '(topic_id INTEGER NOT NULL, \
          metadata TEXT NOT NULL, \
          PRIMARY KEY(topic_id));')
    db_connection.commit()
    print("created mysql tables")
    # clean up any rows from older runs
    cursor = db_connection.cursor()
    cursor.execute("DELETE FROM data")
    db_connection.commit()


def connect_sqlite(request):
    global db_connection, MICROSECOND_SUPPORT, data_table

    database_path = request.param['connection']['params']['database']
    print "connecting to sqlite path " + database_path
    db_connection = sqlite3.connect(database_path)
    print "successfully connected to sqlite"
    MICROSECOND_SUPPORT = True


@pytest.fixture()
def clean(request):
    def delete_rows():
        global db_connection, data_table
        cursor = db_connection.cursor()
        cursor.execute("DELETE FROM " + data_table)
        db_connection.commit()
        print("deleted test records from " + data_table)

    request.addfinalizer(delete_rows)


def assert_timestamp(result, expected_date, expected_time):
    global MICROSECOND_SUPPORT
    print("MICROSECOND SUPPORT ", MICROSECOND_SUPPORT)
    print("TIMESTAMP with microseconds ", expected_time)
    print("TIMESTAMP without microseconds ", expected_time[:-7])
    if MICROSECOND_SUPPORT:
        assert (result == expected_date + 'T' + expected_time + '+00:00')
    else:
        # mysql version < 5.6.4
        assert (result == expected_date + 'T' + expected_time[:-7] + '.000000')


@pytest.mark.historian
def test_basic_function(volttron_instance1, sqlhistorian, clean):
    """
    Test basic functionality of sql historian. Inserts three points as part
    of all topic and checks if all three got into the database
    :param volttron_instance1: The instance against which the test is run
    :param sqlhistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    global publish_agent, query_points, ALL_TOPIC, db_connection
    # print('HOME', volttron_instance1.volttron_home)
    print("\n** test_basic_function **")

    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random.uniform(30, 100)
    mixed_reading = oat_reading + random.uniform(-5, 5)
    damper_reading = random.uniform(0, 100)

    float_meta = {'units': 'F', 'tz': 'UTC', 'type': 'float'}
    percent_meta = {'units': '%', 'tz': 'UTC', 'type': 'float'}

    # Create a message for all points.
    all_message = [{'OutsideAirTemperature': oat_reading,
                    'MixedAirTemperature': mixed_reading,
                    'DamperSignal': damper_reading},
                   {'OutsideAirTemperature': float_meta,
                    'MixedAirTemperature': float_meta,
                    'DamperSignal': percent_meta
                    }]

    # Create timestamp
    now = datetime.utcnow().isoformat(' ')

    # now = '2015-12-02T00:00:00'
    headers = {
        headers_mod.DATE: now
    }
    print("Published time in header: " + now)
    # Publish messages
    publish_agent.vip.pubsub.publish(
        'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)

    gevent.sleep(1)

    # Query the historian
    result = publish_agent.vip.rpc.call('platform.historian',
                                        'query',
                                        topic=query_points['oat_point'],
                                        count=20,
                                        order="LAST_TO_FIRST").get(timeout=100)
    print('Query Result', result)
    assert (len(result['values']) == 1)
    (now_date, now_time) = now.split(" ")
    assert_timestamp(result['values'][0][0], now_date, now_time)
    assert (result['values'][0][1] == oat_reading)
    assert set(result['metadata'].items()) == set(float_meta.items())

    # Query the historian
    result = publish_agent.vip.rpc.call('platform.historian',
                                        'query',
                                        topic=query_points['mixed_point'],
                                        count=20,
                                        order="LAST_TO_FIRST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 1)
    (now_date, now_time) = now.split(" ")
    assert_timestamp(result['values'][0][0], now_date, now_time)
    assert (result['values'][0][1] == mixed_reading)
    assert set(result['metadata'].items()) == set(float_meta.items())

    # Query the historian
    result = publish_agent.vip.rpc.call('platform.historian',
                                        'query',
                                        topic=query_points['damper_point'],
                                        count=20,
                                        order="LAST_TO_FIRST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 1)
    (now_date, now_time) = now.split(" ")
    assert_timestamp(result['values'][0][0], now_date, now_time)
    assert (result['values'][0][1] == damper_reading)
    assert set(result['metadata'].items()) == set(percent_meta.items())


@pytest.mark.historian
def test_exact_timestamp(volttron_instance1, sqlhistorian, clean):
    """
    Test query based on same start and end time with literal 'Z' at the end
    of utc time.
    Expected result: record with timestamp == start time
    :param volttron_instance1: The instance against which the test is run
    :param sqlhistorian: instance of the sql historian tested
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
    # now = '2015-12-02T00:00:00'
    headers = {
        headers_mod.DATE: now
    }

    # Publish messages
    publish_agent.vip.pubsub.publish(
        'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)

    gevent.sleep(0.5)

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
    (now_date, now_time) = now.split("T")
    if now_time[-1:] == 'Z':
        now_time = now_time[:-1]
    assert_timestamp(result['values'][0][0], now_date, now_time)
    assert (result['values'][0][1] == mixed_reading)


@pytest.mark.historian
def test_exact_timestamp_with_z(volttron_instance1, sqlhistorian, clean):
    """
    Test query based on same start and end time with literal 'Z' at the end
    of utc time.
    Expected result: record with timestamp == start time
    :param volttron_instance1: The instance against which the test is run
    :param sqlhistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    global publish_agent, query_points, ALL_TOPIC
    # print('HOME', volttron_instance1.volttron_home)
    print("\n** test_exact_timestamp_with_z **")
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
    # now = '2015-12-02T00:00:00'
    headers = {
        headers_mod.DATE: now
    }

    # Publish messages
    publish_agent.vip.pubsub.publish(
        'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)

    gevent.sleep(0.5)

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
    (now_date, now_time) = now.split("T")
    if now_time[-1:] == 'Z':
        now_time = now_time[:-1]
    assert_timestamp(result['values'][0][0], now_date, now_time)
    assert (result['values'][0][1] == mixed_reading)


@pytest.mark.historian
def test_query_start_time(volttron_instance1, sqlhistorian, clean):
    """
    Test query based on start_time alone. Expected result record with
    timestamp>= start_time
    :param volttron_instance1: The instance against which the test is run
    :param sqlhistorian: instance of the sql historian tested
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

    # Publish messages twice
    time1 = datetime.utcnow().isoformat(' ')
    headers = {
        headers_mod.DATE: time1
    }
    publish_agent.vip.pubsub.publish(
        'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)
    gevent.sleep(0.5)
    time2 = datetime.utcnow() + offset
    time2 = time2.isoformat(' ')
    headers = {
        headers_mod.DATE: time2
    }
    publish_agent.vip.pubsub.publish(
        'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)

    gevent.sleep(0.5)
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
    assert_timestamp(result['values'][0][0], time2_date, time2_time)
    assert (result['values'][0][1] == oat_reading)


@pytest.mark.historian
def test_query_start_time_with_z(volttron_instance1, sqlhistorian, clean):
    """
    Test query based on start_time alone. Expected result record with
    timestamp>= start_time
    :param volttron_instance1: The instance against which the test is run
    :param sqlhistorian: instance of the sql historian tested
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

    # Publish messages twice
    time1 = datetime.utcnow().isoformat(' ') + 'Z'
    headers = {
        headers_mod.DATE: time1
    }
    publish_agent.vip.pubsub.publish(
        'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)
    gevent.sleep(0.5)

    time2 = utils.format_timestamp(datetime.utcnow() + offset)
    print ('time2', time2)
    headers = {
        headers_mod.DATE: time2
    }
    publish_agent.vip.pubsub.publish(
        'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)

    gevent.sleep(0.5)

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
    # Verify order LAST_TO_FIRST.
    (time2_date, time2_time) = time2.split("T")
    assert_timestamp(result['values'][0][0], time2_date, time2_time)
    assert (result['values'][0][1] == oat_reading)


@pytest.mark.historian
def test_query_end_time(volttron_instance1, sqlhistorian, clean):
    """
    Test query based on end time alone. Expected result record with
    timestamp<= end time
    :param volttron_instance1: The instance against which the test is run
    :param sqlhistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    global publish_agent, query_points, ALL_TOPIC, db_connection, agent_uuid
    # print('HOME', volttron_instance1.volttron_home)
    print("\n** test_query_end_time **")

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

    # Publish messages twice
    time1 = datetime.utcnow().isoformat(' ')
    headers = {
        headers_mod.DATE: time1
    }
    publish_agent.vip.pubsub.publish(
        'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)
    gevent.sleep(0.5)
    time2 = datetime.utcnow() + offset
    time2 = time2.isoformat(' ')
    headers = {
        headers_mod.DATE: time2
    }
    publish_agent.vip.pubsub.publish(
        'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)

    gevent.sleep(0.5)

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

    assert (len(result['values']) == 2)
    (time1_date, time1_time) = time1.split(" ")
    # verify ordering("FIRST_TO_LAST" is specified so expecting time1 in
    # index 0
    assert_timestamp(result['values'][0][0], time1_date, time1_time)
    assert (result['values'][0][1] == mixed_reading)


@pytest.mark.historian
def test_query_end_time_with_z(volttron_instance1, sqlhistorian, clean):
    """
    Test query based on end time alone. Expected result record with
    timestamp<= end time
    :param volttron_instance1: The instance against which the test is run
    :param sqlhistorian: instance of the sql historian tested
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

    # Publish messages twice
    time1 = datetime.utcnow().isoformat(' ') + 'Z'
    headers = {
        headers_mod.DATE: time1
    }
    publish_agent.vip.pubsub.publish(
        'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)
    gevent.sleep(0.5)
    time2 = datetime.utcnow() + offset
    time2 = time2.isoformat(' ') + 'Z'
    headers = {
        headers_mod.DATE: time2
    }
    publish_agent.vip.pubsub.publish(
        'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)

    gevent.sleep(0.5)

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
    # verify ordering("FIRST_TO_LAST" is specified so expecting time1 in
    # index 0
    assert_timestamp(result['values'][0][0], time1_date, time1_time)
    assert (result['values'][0][1] == mixed_reading)


@pytest.mark.historian
def test_zero_timestamp(volttron_instance1, sqlhistorian, clean):
    """
    Test query based with timestamp where time is 00:00:00. Test with and
    without Z at the end.
    Expected result: record with timestamp == 00:00:00.000001
    :param volttron_instance1: The instance against which the test is run
    :param sqlhistorian: instance of the sql historian tested
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
    now = '2015-12-17 00:00:00.000000Z'
    headers = {
        headers_mod.DATE: now
    }

    # Publish messages
    publish_agent.vip.pubsub.publish(
        'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)

    gevent.sleep(0.5)

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
    now_time = now_time[:-1]
    assert_timestamp(result['values'][0][0], now_date, now_time)
    assert (result['values'][0][1] == mixed_reading)

    # Create timestamp
    now = '2015-12-17 00:00:00.000000'
    headers = {
        headers_mod.DATE: now
    }

    # Publish messages
    publish_agent.vip.pubsub.publish(
        'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)

    gevent.sleep(0.5)

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
    assert_timestamp(result['values'][0][0], now_date, now_time)
    assert (result['values'][0][1] == mixed_reading)


@pytest.mark.historian
def test_topic_name_case_change(volttron_instance1, sqlhistorian, clean):
    """
    When case of a topic name changes check if they are saved as two topics
    Expected result: query result should be cases sensitive
    :param volttron_instance1: The instance against which the test is run
    :param sqlhistorian: instance of the sql historian tested
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
    all_message = [{'OutsideAirTemperature': oat_reading,
                    'MixedAirTemperature': mixed_reading},
                   {'OutsideAirTemperature': {'units': 'F', 'tz': 'UTC',
                                              'type': 'float'},
                    'MixedAirTemperature': {'units': 'F', 'tz': 'UTC',
                                            'type': 'float'}
                    }]

    # Create timestamp
    time1 = '2015-12-17 00:00:00.000000Z'
    headers = {
        headers_mod.DATE: time1
    }

    # Publish messages
    publish_agent.vip.pubsub.publish(
        'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)

    gevent.sleep(0.5)

    # Create a message for all points.
    all_message = [{'Outsideairtemperature': oat_reading,
                    'MixedAirTemperature': mixed_reading},
                   {'Outsideairtemperature': {'units': 'F', 'tz': 'UTC',
                                              'type': 'float'},
                    'MixedAirTemperature': {'units': 'F', 'tz': 'UTC',
                                            'type': 'float'}
                    }]

    # Create timestamp
    time2 = '2015-12-17 01:10:00.000000Z'
    headers = {
        headers_mod.DATE: time2
    }

    # Publish messages
    publish_agent.vip.pubsub.publish(
        'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)

    gevent.sleep(0.5)

    # Query the historian
    print("query time ", time1)
    result = publish_agent.vip.rpc.call(
        'platform.historian',
        'query',
        topic="Building/LAB/Device/OutsideAirTemperature",
        start=time1,
        count=20,
        order="FIRST_TO_LAST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 2)
    (time1_date, time1_time) = time1.split(" ")
    time1_time = time1_time[:-1]
    assert_timestamp(result['values'][0][0], time1_date, time1_time)
    assert (result['values'][0][1] == oat_reading)


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
    print("\n** test_invalid_query **")
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


@pytest.mark.historian
def test_analysis_topic(volttron_instance1, sqlhistorian, clean):
    """
    Test query based on same start and end time with literal 'Z' at the end
    of utc time.
    Expected result: record with timestamp == start time
    :param volttron_instance1: The instance against which the test is run
    :param sqlhistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    global publish_agent, query_points
    # print('HOME', volttron_instance1.volttron_home)
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
    # now = '2015-12-02T00:00:00'
    headers = {
        headers_mod.DATE: now
    }
    # Publish messages
    publish_agent.vip.pubsub.publish(
        'pubsub', "analysis/Building/LAB/Device/MixedAirTemperature", headers,
        all_message).get(timeout=10)

    gevent.sleep(0.5)

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
    (now_date, now_time) = now.split("T")
    if now_time[-1:] == 'Z':
        now_time = now_time[:-1]
    assert_timestamp(result['values'][0][0], now_date, now_time)
    assert (result['values'][0][1] == mixed_reading)


@pytest.mark.historian
def test_record_topic_query(volttron_instance1, sqlhistorian, clean):
    """
    Test query based on same start with literal 'Z' at the end of utc time.
    Cannot query based on exact time as timestamp recorded is time of insert
    publish and query record topic
    :param volttron_instance1: The instance against which the test is run
    :param sqlhistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    global publish_agent
    # print('HOME', volttron_instance1.volttron_home)
    print("\n** test_exact_timestamp **")
    # Publish int data

    # Create timestamp
    now = datetime.utcnow().isoformat() + 'Z'
    print("now is ", now)

    # Publish messages
    publish_agent.vip.pubsub.publish(
        'pubsub', topics.RECORD, None, 1).get(timeout=10)
    # sleep 1 second so that records gets inserted with unique timestamp
    # even in case of older mysql
    gevent.sleep(1)
    publish_agent.vip.pubsub.publish(
        'pubsub', topics.RECORD, None, 'value0').get(timeout=10)
    # sleep 1 second so that records gets inserted with unique timestamp
    # even in case of older mysql
    gevent.sleep(1)
    publish_agent.vip.pubsub.publish(
        'pubsub', topics.RECORD, None, {'key': 'value'}).get(timeout=10)

    gevent.sleep(0.5)

    # pytest.set_trace()
    # Query the historian
    result = publish_agent.vip.rpc.call('platform.historian',
                                        'query',
                                        topic=topics.RECORD,
                                        start=now,
                                        count=20,
                                        order="FIRST_TO_LAST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 3)
    assert (result['values'][0][1] == 1)
    assert (result['values'][1][1] == 'value0')
    assert (result['values'][2][1] == {'key': 'value'})


@pytest.mark.historian
def test_log_topic(volttron_instance1, sqlhistorian, clean):
    """
    Test query based on same start and end time with literal 'Z' at the end
    of utc time.
    Expected result: record with timestamp == start time
    :param volttron_instance1: The instance against which the test is run
    :param sqlhistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    global publish_agent, query_points
    # print('HOME', volttron_instance1.volttron_home)
    print("\n** test_log_topic **")
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random.uniform(30, 100)
    mixed_reading = oat_reading + random.uniform(-5, 5)

    # Create a message for all points.
    message = {'MixedAirTemperature': {'Readings': mixed_reading, 'Units': 'F',
                                       'tz': 'UTC', 'type': 'float'}}

    # pytest.set_trace()
    # Create timestamp
    now = datetime.utcnow().isoformat() + 'Z'
    print("now is ", now)
    # now = '2015-12-02T00:00:00'

    # Publish messages
    publish_agent.vip.pubsub.publish(
        'pubsub', "datalogger/Building/LAB/Device", None, message).get(
        timeout=10)

    gevent.sleep(1)

    # Query the historian
    result = publish_agent.vip.rpc.call(
        'platform.historian',
        'query',
        topic="datalogger/Building/LAB/Device/MixedAirTemperature",
        start=now,
        count=20,
        order="LAST_TO_FIRST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 1)
    assert (result['values'][0][1] == mixed_reading)
