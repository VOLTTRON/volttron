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
"""
pytest test cases for SQLHistorian and MongodbHistorian
For mysql tests and MongodbHistorian test
 1. MySql server/Mongod process should be running
 2. test database and test user should exist
 3. Test user should have all privileges on test database
 4. Refer to the parameters passed to the historian fixture for the server
 configuration

This test case is a generic test case that all historians should satisfy. To
test a specific historian implementation through this test suite do the
following
 1. Create setup_<connection_type> method (for example: setup_mysql,
 setup_sqlite). setup method should return a database connection object and
 the precision of the microsecond supported by this database for timestamp
 datatype.
 2. Create a cleanup_<connection_type> method. cleanup method will be called
 after every test case and can be used for deleting test records in the
 database
 3. Create a historian configuration dictionary with one additional key
 "source_historian". The value of this should be path to the historian
 source package. For example "source_historian": "services/core/SQLHistorian"
 4. Add the configuration as a parameter to the historian fixture
 5. Optional step: If you want more than one configuration to be tested for
 the same historian implementation but don't want anything but the basic test
 case for these additional configuration, add a "agent-id" key to your
 configuration and mark the primary configuration's agent-id with value
 ending with -1 and rest as something that doesn't end with -1. For the
 primary configuration all the test cases will be run. For the additional
 configuration only the test_basic_function test would be run.


"""
import copy
from datetime import datetime, timedelta
import os
import random
import sqlite3
import sys

from tzlocal import get_localzone
import gevent
import pytest
import re
import pytz

from volttron.platform import get_volttron_root, get_services_core
from volttron.platform.agent import PublishMixin
from volttron.platform.agent import utils
from volttron.platform.jsonrpc import RemoteError
from volttron.platform.messaging import headers as headers_mod
from volttron.platform.messaging import topics
from volttron.platform.vip.agent import Agent

try:
    from crate import client
    from crate.client.exceptions import ProgrammingError
    # Adding crate historian to the path so we have access to it's packages
    # for removing/creating schema for testing with.
    root = get_volttron_root()
    crate_path = get_services_core("CrateHistorian")

    sys.path.insert(0, crate_path)
    import crate_historian
    from volttron.platform.dbutils import crateutils as crate_utils
    # Once we fix the tests this will be able to be tested here.
    HAS_CRATE_CONNECTOR = True
except:
    HAS_CRATE_CONNECTOR = False

try:
    import mysql.connector as mysql
    from mysql.connector import errorcode

    HAS_MYSQL_CONNECTOR = True
except:
    HAS_MYSQL_CONNECTOR = False

try:
    import pymongo

    HAS_PYMONGO = True
except:
    HAS_PYMONGO = False

mysql_skipif = pytest.mark.skipif(not HAS_MYSQL_CONNECTOR,
                                  reason='No mysql connector available')
pymongo_skipif = pytest.mark.skipif(not HAS_PYMONGO,
                                    reason='No pymongo client available.')
crate_skipif = pytest.mark.skipif(not HAS_CRATE_CONNECTOR,
                                  reason='No crate client available.')
# Module level variables
DEVICES_ALL_TOPIC = "devices/Building/LAB/Device/all"
MICROSECOND_PRECISION = 0
table_names = dict()
connection_type = ""
query_points = {
    "oat_point": "Building/LAB/Device/OutsideAirTemperature",
    "mixed_point": "Building/LAB/Device/MixedAirTemperature",
    "damper_point": "Building/LAB/Device/DamperSignal"
}
# NOTE - In the below configuration, source_historian' is added
# only for test case setup purposes. It is removed from config before
# using the configuration for installing the agent.

# default table_defs
sqlite_platform = {
    "source_historian": get_services_core("SQLHistorian"),
    "connection": {
        "type": "sqlite",
        "params": {
            "database": 'test.sqlite'
        }
    }
}

crate_platform = {
    "source_historian": get_services_core("CrateHistorian"),
    "schema": "testing_historian",
    "connection": {
        "type": "crate",
        "params": {
            "host": "http://localhost:4200",
            "debug": False
        }
    }
}

# Create a database "historian", create user "historian" with passwd
# "historian" and grant historian user access to "historian" database

# config without table_defs
mysql_platform = {
    "source_historian": get_services_core("SQLHistorian"),
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

mongo_platform = {
    "source_historian": get_services_core("MongodbHistorian"),
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

offset = timedelta(seconds=3)
db_connection = None
identity = None

# Don't like declaring this global but I am not able to find a way
# to introspect this using pytest request object in the clean_db_rows fixture
data_table = 'data'
topics_table = 'topics'
meta_table = 'meta'


def setup_crate(connection_params, table_names):
    print("setup crate")
    conn = client.connect(connection_params['host'],
                          error_trace=True)
    schema = "testing_historian"
    cursor = conn.cursor()
    crate_utils.create_schema(conn, schema)
    MICROSECOND_PRECISION = 3
    return conn, MICROSECOND_PRECISION


def setup_mysql(connection_params, table_names):
    print ("setup mysql")
    db_connection = mysql.connect(**connection_params)
    # clean_db_rows up any rows from older runs if exists
    try:
        cursor = db_connection.cursor()
        cursor.execute("DELETE FROM " + table_names['data_table'])
        cursor.execute("DELETE FROM " + table_names['topics_table'])
        cursor.execute("DELETE FROM " + table_names['meta_table'])
        cursor.execute("DELETE FROM " + "volttron_table_definitions")
        db_connection.commit()
    except Exception as e:
        print ("Error cleaning existing table from last runs {}".format(e))

    cursor = db_connection.cursor()
    cursor.execute("SELECT version()")
    version = cursor.fetchone()
    p = re.compile('(\d+)\D+(\d+)\D+(\d+)\D*')
    version_nums = p.match(version[0]).groups()

    print (version)
    if int(version_nums[0]) < 5:
        MICROSECOND_PRECISION = 0
    elif int(version_nums[1]) < 6:
        MICROSECOND_PRECISION = 0
    elif int(version_nums[2]) < 4:
        MICROSECOND_PRECISION = 0
    else:
        MICROSECOND_PRECISION = 6

    return db_connection, MICROSECOND_PRECISION


def setup_sqlite(connection_params, table_names):
    print ("setup sqlite")
    database_path = connection_params['database']
    print ("connecting to sqlite path " + database_path)
    db_connection = sqlite3.connect(database_path)
    print ("successfully connected to sqlite")
    db_connection.commit()
    return db_connection, 6


def setup_mongodb(connection_params, table_names):
    print ("setup mongodb")
    mongo_conn_str = 'mongodb://{user}:{passwd}@{host}:{port}/{database}'
    params = connection_params
    mongo_conn_str = mongo_conn_str.format(**params)
    mongo_client = pymongo.MongoClient(mongo_conn_str)
    db = mongo_client[connection_params['database']]
    db[table_names['data_table']].remove()
    db[table_names['topics_table']].remove()
    db[table_names['meta_table']].remove()
    db["volttron_table_definitions"].remove()
    return db, 3


def cleanup_sql(db_connection, truncate_tables):
    cursor = db_connection.cursor()
    for table in truncate_tables:
        cursor.execute("DELETE FROM " + table)
    db_connection.commit()
    cursor.close()


def cleanup_sqlite(db_connection, truncate_tables):
    cleanup_sql(db_connection, truncate_tables)


def cleanup_mysql(db_connection, truncate_tables):
    cleanup_sql(db_connection, truncate_tables)


def cleanup_mongodb(db_connection, truncate_tables):
    for collection in truncate_tables:
        db_connection[collection].remove()


def cleanup_crate(db_connection, truncate_tables):
    crate_utils.drop_schema(db_connection, truncate_tables,
                            schema=crate_platform['schema'])


def random_uniform(a, b):
    """
    Creates a random uniform value for using within our tests.  This function
    will chop a float off at a specific uniform number of decimals.

    :param a: lower bound of range for return value
    :param b: upper bound of range for return value
    :return: A psuedo random uniform float.
    :type a: int
    :type b: int
    :rtype: float
    """
    format_spec = "{0:.13f}"
    return float(format_spec.format(random.uniform(a, b)))


def get_table_names(config):
    default_table_def = {"table_prefix": "",
                         "data_table": "data",
                         "topics_table": "topics",
                         "meta_table": "meta"}
    tables_def = config.get('tables_def', None)
    if not tables_def:
        tables_def = default_table_def
    table_names = dict(tables_def)
    table_names["agg_topics_table"] = \
        "aggregate_" + tables_def["topics_table"]
    table_names["agg_meta_table"] = \
        "aggregate_" + tables_def["meta_table"]

    table_prefix = tables_def.get('table_prefix', None)
    table_prefix = table_prefix + "_" if table_prefix else ""
    if table_prefix:
        for key, value in table_names.items():
            table_names[key] = table_prefix + table_names[key]

    return table_names


@pytest.fixture(scope="module")
def publish_agent(request, volttron_instance):
    # 1: Start a fake agent to publish to message bus
    print("**In setup of publish_agent volttron is_running {}".format(
        volttron_instance.is_running))

    agent = volttron_instance.build_agent()

    # 2: add a tear down method to stop the fake
    # agent that published to message bus
    def stop_agent():
        print("In teardown method of publish_agent")
        if isinstance(agent, Agent):
            agent.core.stop()

    request.addfinalizer(stop_agent)
    return agent


@pytest.fixture(scope="module")
def query_agent(request, volttron_instance):
    # 1: Start a fake agent to query the historian agent in volttron_instance2
    agent = volttron_instance.build_agent()

    # 2: add a tear down method to stop the fake
    # agent that published to message bus
    def stop_agent():
        print("In teardown method of query_agent")
        agent.core.stop()

    request.addfinalizer(stop_agent)
    return agent


# Fixtures for setup and teardown of historian agent
@pytest.fixture(scope="module",
                params=[
                    crate_skipif(crate_platform),
                    mysql_skipif(mysql_platform),
                    sqlite_platform,
                    pymongo_skipif(mongo_platform)
                ])
def historian(request, volttron_instance, query_agent):
    global db_connection, MICROSECOND_PRECISION, table_names, \
        connection_type, identity

    print("** Setting up test_historian module **")
    # Make database connection
    print("request param", request.param)
    connection_type = request.param['connection']['type']
    if connection_type == 'sqlite':
        request.param['connection']['params']['database'] = \
            volttron_instance.volttron_home + "/historian.sqlite"

    table_names = get_table_names(request.param)

    # 2: Open db connection that can be used for row deletes after
    # each test method. Create tables
    function_name = "setup_" + connection_type
    try:
        setup_function = globals()[function_name]
        print(table_names)
        db_connection, MICROSECOND_PRECISION = \
            setup_function(request.param['connection']['params'], table_names)
    except NameError:
        pytest.fail(
            msg="No setup method({}) found for connection type {} ".format(
                function_name, connection_type))

    print ("request.param -- {}".format(request.param))
    # 2. Install agent - historian
    source = request.param.pop('source_historian')
    historian_uuid = volttron_instance.install_agent(
        vip_identity='platform.historian',
        agent_dir=source,
        config_file=request.param,
        start=True)
    print("agent id: ", historian_uuid)
    identity = 'platform.historian'

    # 3: add a tear down method to stop historian agent
    def stop_agent():
        print("In teardown method of sqlagent")
        if volttron_instance.is_running():
            volttron_instance.stop_agent(historian_uuid)
        volttron_instance.remove_agent(historian_uuid)

    request.addfinalizer(stop_agent)
    # put source info back as test cases might use it to installer more
    # instances of historian
    request.param['source_historian'] = source
    return request.param


@pytest.fixture()
def clean_db_rows(request):
    import inspect
    global db_connection, connection_type, table_names
    print("*** IN clean_db_rows FIXTURE ***")
    cleanup_function = globals()["cleanup_" + connection_type]
    #inspect.getargspec(cleanup_function)[0]
    # if "schema" in inspect.getargspec(cleanup_function)[0]:
    #     cleanup_function(db_connection, [table_names['data_table']],
    #                      schema=connection_type[])
    cleanup_function(db_connection, [table_names['data_table']])


def publish(publish_agent, topic, header, message):
    if isinstance(publish_agent, Agent):
        publish_agent.vip.pubsub.publish('pubsub',
                                         topic,
                                         headers=header,
                                         message=message).get(timeout=10)
    else:
        publish_agent.publish_json(topic, header, message)


def assert_timestamp(result, expected_date, expected_time):
    global MICROSECOND_PRECISION
    print("TIMESTAMP expected ", expected_time)

    if expected_time[-6:] == "+00:00":
        expected_time = expected_time[:-6]

    if MICROSECOND_PRECISION > 0 and MICROSECOND_PRECISION <6:
        truncate = (6 - MICROSECOND_PRECISION) * -1
        assert (result == expected_date + 'T'
                         + expected_time[:truncate] + '0'*
                            MICROSECOND_PRECISION + '+00:00')

    elif MICROSECOND_PRECISION == 6:
        assert result == expected_date + 'T' + expected_time + '+00:00'
    else:
        # mysql version < 5.6.4
        assert (result == expected_date + 'T' + expected_time[:-7] +
                '.000000+00:00')

@pytest.mark.historian
def test_basic_function(request, historian, publish_agent, query_agent,
                        clean_db_rows):
    """
    Test basic functionality of historian. Inserts three points as part
    of all topic and checks if all three got into the database
    Expected result:
    Should be able to query data based on topic name. Result should contain
    both data and metadata
    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param historian: instance of the historian tested
    :param clean_db_rows: fixture to clear data table
    """
    global query_points, DEVICES_ALL_TOPIC, db_connection

    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_basic_function for {}**".format(
        request.keywords.node.name))

    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings.  Randome readings are going to be
    # within the tolerance here.
    format_spec = "{0:.13f}"
    oat_reading = random_uniform(30, 100)
    mixed_reading = oat_reading + random_uniform(-5, 5)
    damper_reading = random_uniform(0, 100)

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
    publish(publish_agent, DEVICES_ALL_TOPIC, headers, all_message)

    gevent.sleep(1)

    # Query the historian
    result = query_agent.vip.rpc.call(identity,
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
    result = query_agent.vip.rpc.call(identity,
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
    result = query_agent.vip.rpc.call(identity,
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
def test_basic_function_optional_config(request, historian, publish_agent,
                                        query_agent, clean_db_rows, 
                                        volttron_instance):

    """
    Test optional table_def config for historians
    Expected result:
    data published to message bus should not be recorded in the historian
    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param historian: instance of the historian tested
    :param clean_db_rows: fixture to clear data table 
    :param volttron_instance: instance of PlatformWrapper. Volttron
    instance in which agents are tested
    """
    global query_points, DEVICES_ALL_TOPIC, db_connection, topics_table, \
        connection_type
    if historian['connection']['type'] == 'crate':
        pytest.skip("Skipping testing for optional 'tables_defs' config for "
                    "crate historian")

    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_basic_function_optional_config for {}**".format(
        request.keywords.node.name))
    agent_uuid = None
    try:
        new_historian = copy.copy(historian)
        new_historian["tables_def"] = {"table_prefix": "",
            "data_table": "data_table", "topics_table": "topics_table",
            "meta_table": "meta_table"}

        # 1: Install historian agent
        # Install and start historian agent
        source = new_historian.pop('source_historian')
        agent_uuid = volttron_instance.install_agent(agent_dir=source,
            config_file=new_historian, start=True,
            vip_identity='hist2')
        print("agent id: ", agent_uuid)

        # Create timestamp
        query_start = datetime.utcnow().isoformat() + 'Z'
        print("query_start is ", query_start)

        # Publish messages
        publish(publish_agent, topics.RECORD(subtopic="test"), None, 1)
        # sleep 1 second so that records gets inserted with unique timestamp
        # even in case of older mysql
        gevent.sleep(1)

        # Query the historian
        result = query_agent.vip.rpc.call('hist2', 'query',
            topic=topics.RECORD(subtopic="test"), start=query_start,
            count=20, order="FIRST_TO_LAST").get(timeout=10)
        print('Query Result', result)
        assert (len(result['values']) == 1)
        assert (result['values'][0][1] == 1)

        volttron_instance.remove_agent(agent_uuid)

        # reinstall agent this time with readonly=True

        new_historian["tables_def"] = {"table_prefix": "prefix",
                                       "data_table": "data_table",
                                       "topics_table": "topics_table",
                                       "meta_table": "meta_table"}
        agent_uuid = volttron_instance.install_agent(agent_dir=source,
            config_file=new_historian, start=True,
            vip_identity='hist2')
        print("agent id: ", agent_uuid)

        # Publish messages
        publish(publish_agent, topics.RECORD(subtopic="test"), None, 2)
        gevent.sleep(1)

        # Query the historian
        result = query_agent.vip.rpc.call('hist2', 'query',
            topic=topics.RECORD(subtopic="test"), start=query_start,
            count=20, order="FIRST_TO_LAST").get(timeout=10)
        print('Query Result', result)
        assert (len(result['values']) == 1)
        assert (result['values'][0][1] == 2)

    finally:
        if agent_uuid:
            cleanup_function = globals()["cleanup_" + connection_type]
            cleanup_function(db_connection,
                             ['data_table', 'topics_table',
                              'meta_table', 'prefix_data_table',
                              'prefix_topics_table', 'prefix_meta_table'])
            volttron_instance.stop_agent(agent_uuid)
            volttron_instance.remove_agent(agent_uuid)



@pytest.mark.historian
def test_exact_timestamp(request, historian, publish_agent, query_agent,
                         clean_db_rows):
    """
    Test query based on same start and end time with literal 'Z' at the end
    of utc time.
    Expected result: record with timestamp == start time

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param historian: instance of the historian tested
    :param clean_db_rows: fixture to clear data table 
    """

    global query_points, DEVICES_ALL_TOPIC

    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_exact_timestamp for for {}**".format(
        request.keywords.node.name))
    # Publish fake data.
    now, reading, meta = publish_devices_fake_data(publish_agent)
    gevent.sleep(0.5)

    # Query the historian
    result = query_agent.vip.rpc.call(identity,
                                      'query',
                                      topic=query_points['mixed_point'],
                                      start=now,
                                      end=now,
                                      count=20,
                                      order="LAST_TO_FIRST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 1)
    (now_date, now_time) = now.split("T")
    now_time = now_time.split("+")[0]
    if now_time[-1:] == 'Z':
        now_time = now_time[:-1]
    assert_timestamp(result['values'][0][0], now_date, now_time)
    assert (result['values'][0][1] == reading)


@pytest.mark.historian
def test_exact_timestamp_with_z(request, historian, publish_agent,
                                query_agent,
                                clean_db_rows):
    """
    Test query based on same start and end time with literal 'Z' at the end
    of utc time.
    Expected result: record with timestamp == start time

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param historian: instance of the historian tested
    :param clean_db_rows: fixture to clear data table 
    """

    global query_points, DEVICES_ALL_TOPIC
    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_exact_timestamp_with_z for {}**".format(
        request.keywords.node.name))
    # Publish fake data.
    time1 = datetime.utcnow().isoformat() + 'Z'
    time1, reading, meta = publish_devices_fake_data(publish_agent, time1)
    gevent.sleep(0.5)

    # Query the historian
    result = query_agent.vip.rpc.call(identity,
                                      'query',
                                      topic=query_points['mixed_point'],
                                      start=time1,
                                      end=time1,
                                      count=20,
                                      order="LAST_TO_FIRST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 1)
    (now_date, now_time) = time1.split("T")
    now_time = now_time.split("+")[0]
    if now_time[-1:] == 'Z':
        now_time = now_time[:-1]
    assert_timestamp(result['values'][0][0], now_date, now_time)
    assert (result['values'][0][1] == reading)


@pytest.mark.historian
def test_query_start_time(request, historian, publish_agent, query_agent,
                          clean_db_rows):
    """
    Test query based on start_time alone. Expected result record with
    timestamp>= start_time

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param historian: instance of the historian tested
    :param clean_db_rows: fixture to clear data table 
    """

    global query_points, DEVICES_ALL_TOPIC
    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_query_start_time for {}**".format(
        request.keywords.node.name))
    # Publish fake data.
    time1, reading, meta = publish_devices_fake_data(publish_agent)
    gevent.sleep(0.5)
    time2, reading, meta = publish_devices_fake_data(publish_agent)

    gevent.sleep(0.5)

    # Query the historian
    result = query_agent.vip.rpc.call(identity,
                                      'query',
                                      topic=query_points['oat_point'],
                                      start=time1,
                                      count=20,
                                      order="LAST_TO_FIRST").get(timeout=10)
    print ("time1:", time1)
    print ("time2:", time2)
    print('Query Result', result)
    assert len(result['values']) == 2
    (time2_date, time2_time) = time2.split("T")
    time2_time = time2_time.split("+")[0]
    if time2_time[-1:] == 'Z':
        time2_time = time2_time[:-1]
    # Verify order LAST_TO_FIRST.
    assert_timestamp(result['values'][0][0], time2_date, time2_time)
    assert (result['values'][0][1] == reading)


@pytest.mark.historian
def test_query_start_time_with_z(request, historian, publish_agent,
                                 query_agent,
                                 clean_db_rows):
    """
    Test query based on start_time alone. Expected result record with
    timestamp>= start_time

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param historian: instance of the historian tested
    :param clean_db_rows: fixture to clear data table 
    """

    global query_points, DEVICES_ALL_TOPIC
    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_query_start_time_with_z for {}**".format(
        request.keywords.node.name))
    # Publish fake data.
    time1 = datetime.utcnow().isoformat(' ') + 'Z'
    time1, reading, meta = publish_devices_fake_data(publish_agent, time1)
    gevent.sleep(0.5)

    time2 = utils.format_timestamp(datetime.utcnow() + offset)
    time2, reading, meta = publish_devices_fake_data(publish_agent, time2)
    gevent.sleep(0.5)

    # Query the historian
    result = query_agent.vip.rpc.call(identity,
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
    time2_time = time2_time.split("+")[0]
    assert_timestamp(result['values'][0][0], time2_date, time2_time)
    assert (result['values'][0][1] == reading)


@pytest.mark.historian
def test_query_end_time(request, historian, publish_agent, query_agent,
                        clean_db_rows):
    """
    Test query based on end time alone. Expected result record with
    timestamp<= end time

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param historian: instance of the historian tested
    :param clean_db_rows: fixture to clear data table 
    """

    global query_points, DEVICES_ALL_TOPIC, db_connection
    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_query_end_time for {}**".format(
        request.keywords.node.name))

    # Publish fake data.
    time1 = datetime.utcnow().isoformat(' ')
    time1, reading1, meta1 = publish_devices_fake_data(publish_agent, time1)
    gevent.sleep(0.5)

    time2 = datetime.utcnow() + offset
    # because end_time is not inclusive
    query_end_time = time2 + timedelta(seconds=1)
    time2 = time2.isoformat(' ')
    time2, reading2, meta2 = publish_devices_fake_data(publish_agent, time2)

    gevent.sleep(0.5)

    # pytest.set_trace()
    # Query the historian
    result = query_agent.vip.rpc.call(identity,
                                      'query',
                                      topic=query_points['mixed_point'],
                                      end=query_end_time.isoformat(' '),
                                      count=20,
                                      order="FIRST_TO_LAST").get(timeout=100)
    print ("time1:", time1)
    print ("time2:", time2)
    print('Query Result', result)

    assert (len(result['values']) == 2)
    (time1_date, time1_time) = time1.split(" ")
    time1_time = time1_time.split("+")[0]
    # verify ordering("FIRST_TO_LAST" is specified so expecting time1 in
    # index 0
    assert_timestamp(result['values'][0][0], time1_date, time1_time)
    assert (result['values'][0][1] == reading1)


@pytest.mark.historian
def test_query_end_time_with_z(request, historian, publish_agent,
                               query_agent, clean_db_rows):
    """
    Test query based on end time alone. Expected result record with
    timestamp<= end time

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param historian: instance of the historian tested
    :param clean_db_rows: fixture to clear data table 
    """

    global query_points, DEVICES_ALL_TOPIC
    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_query_end_time_with_z for {}**".format(
        request.keywords.node.name))

    # Publish fake data twice
    time1 = datetime.utcnow().isoformat(' ') + 'Z'
    time1, reading1, meta1 = publish_devices_fake_data(publish_agent, time1)
    gevent.sleep(0.5)

    time2 = datetime.utcnow() + offset
    # because end_time is not inclusive
    query_end_time = time2 + timedelta(seconds=1)
    time2 = time2.isoformat(' ') + 'Z'
    time2, reading2, meta2 = publish_devices_fake_data(publish_agent, time2)
    gevent.sleep(0.5)

    # pytest.set_trace()
    # Query the historian
    result = query_agent.vip.rpc.call(identity,
                                      'query',
                                      topic=query_points['mixed_point'],
                                      end=query_end_time.isoformat(),
                                      count=20,
                                      order="FIRST_TO_LAST").get(timeout=10)
    print ("time1:", time1)
    print ("time2:", time2)
    print('Query Result', result)
    # pytest.set_trace()
    assert (len(result['values']) == 2)
    (time1_date, time1_time) = time1.split(" ")
    time1_time = time1_time.split("+")[0]
    if time1_time[-1:] == 'Z':
        time1_time = time1_time[:-1]
    # verify ordering("FIRST_TO_LAST" is specified so expecting time1 in
    # index 0
    assert_timestamp(result['values'][0][0], time1_date, time1_time)
    assert (result['values'][0][1] == reading1)

@pytest.mark.historian
def test_zero_timestamp(request, historian, publish_agent, query_agent,
                        clean_db_rows):
    """
    Test query based with timestamp where time is 00:00:00. Test with and
    without Z at the end.
    Expected result: record with timestamp == 00:00:00.000001

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param historian: instance of the historian tested
    :param clean_db_rows: fixture to clear data table 
    """

    global query_points, DEVICES_ALL_TOPIC
    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_zero_timestamp for {}**".format(
        request.keywords.node.name))
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    now = '2015-12-17 00:00:00.000000Z'
    now, reading, meta = publish_devices_fake_data(publish_agent, now)
    gevent.sleep(0.5)

    # Query the historian
    result = query_agent.vip.rpc.call(identity,
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
    assert (result['values'][0][1] == reading)

    # Create timestamp
    now = '2015-12-17 00:00:00.000000'
    now, reading, meta = publish_devices_fake_data(publish_agent, now)
    gevent.sleep(0.5)

    # Query the historian
    result = query_agent.vip.rpc.call(identity,
                                      'query',
                                      topic=query_points['mixed_point'],
                                      start=now,
                                      count=20,
                                      order="LAST_TO_FIRST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 1)
    (now_date, now_time) = now.split(" ")
    assert_timestamp(result['values'][0][0], now_date, now_time)
    assert (result['values'][0][1] == reading)


@pytest.mark.historian
def test_topic_name_case_change(request, historian, publish_agent,
                                query_agent, clean_db_rows):
    """
    When case of a topic name changes check if they are saved as two topics
    Expected result: query result should be cases sensitive

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param historian: instance of the historian tested
    :param clean_db_rows: fixture to clear data table 
    """

    global query_points, DEVICES_ALL_TOPIC, db_connection, table_names
    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_topic_name_case_change for {}**".format(
        request.keywords.node.name))
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random_uniform(30, 100)
    mixed_reading = oat_reading + random_uniform(-5, 5)

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
    publish(publish_agent, DEVICES_ALL_TOPIC, headers, all_message)
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
    publish(publish_agent, DEVICES_ALL_TOPIC, headers, all_message)
    gevent.sleep(0.5)

    # Query the historian
    print("query time ", time1)
    result = query_agent.vip.rpc.call(
        identity,
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
def test_invalid_query(request, historian, publish_agent, query_agent,
                       clean_db_rows):
    """
    Test query with invalid input

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param historian: instance of the historian tested
    :param clean_db_rows: fixture to clear data table 
    """

    global query_points, DEVICES_ALL_TOPIC
    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_invalid_query for {}**".format(
        request.keywords.node.name))

    # Create timestamp
    now = datetime.utcnow().isoformat(' ') + 'Z'

    # Query without topic id
    try:
        query_agent.vip.rpc.call(identity,
                                 'query',
                                 # topic=query_points['mixed_point'],
                                 start=now,
                                 count=20,
                                 order="LAST_TO_FIRST").get(timeout=10)
    except RemoteError as error:
        print ("topic required excinfo {}".format(error))
        assert '"Topic" required' in str(error.message)

    try:
        # query with wrong historian id
        query_agent.vip.rpc.call('platform.historian1',
                                 'query',
                                 topic=query_points['mixed_point'],
                                 start=now,
                                 count=20,
                                 order="LAST_TO_FIRST").get(timeout=10)
    except Exception as error:
        print ("exception: {}".format(error))
        assert "No route to host: platform.historian1" in str(error)


@pytest.mark.historian
def test_invalid_time(request, historian, publish_agent, query_agent,
                      clean_db_rows):
    """
    Test query with invalid input

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param historian: instance of the historian tested
    :param clean_db_rows: fixture to clear data table 
    """

    global query_points, DEVICES_ALL_TOPIC
    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_invalid_time for {}**".format(
        request.keywords.node.name))

    # Create timestamp
    now = '2015-12-17 60:00:00.000000'

    try:
        # query with invalid timestamp
        query_agent.vip.rpc.call(identity,
                                 'query',
                                 topic=query_points['mixed_point'],
                                 start=now,
                                 count=20,
                                 order="LAST_TO_FIRST").get(timeout=10)
    except RemoteError as error:
        print ("exception: {}".format(error))
        assert 'Syntax Error in Query' == error.message


@pytest.mark.historian
def test_analysis_topic(request, historian, publish_agent, query_agent,
                        clean_db_rows):
    """
    Test recording and querying of analysis topic
    
    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0 agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param historian: instance of the historian tested
    :param clean_db_rows: fixture to clear data table 
    """

    global query_points
    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_analysis_topic for {}**".format(
        request.keywords.node.name))
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random_uniform(30, 100)
    mixed_reading = oat_reading + random_uniform(-5, 5)
    damper_reading = random_uniform(0, 100)

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

    publish_time = (datetime.utcnow() - timedelta(days=1)).isoformat()
    print("publish_time ", publish_time)
    # publish_time = '2015-12-02T00:00:00'
    headers = {
        headers_mod.DATE: publish_time
    }

    # Publish messages
    publish(publish_agent, 'analysis/Building/LAB/Device',
            headers, all_message)
    gevent.sleep(0.5)
    abc = dict(peer=identity, method='query',
               topic=query_points['mixed_point'],
               start=publish_time,
               end=publish_time,
               count=20,
               order="LAST_TO_FIRST")
    # Query the historian
    result = query_agent.vip.rpc.call(identity,
                                      'query',
                                      topic=query_points['mixed_point'],
                                      start=publish_time,
                                      end=publish_time,
                                      count=20,
                                      order="LAST_TO_FIRST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 1)
    (now_date, now_time) = publish_time.split("T")
    if now_time[-1:] == 'Z':
        now_time = now_time[:-1]
    assert_timestamp(result['values'][0][0], now_date, now_time)
    assert (result['values'][0][1] == mixed_reading)

@pytest.mark.historian
def test_analysis_topic_replacement(request, historian, publish_agent,
                                 query_agent, clean_db_rows, volttron_instance):

    """
    Test if topic name substitutions happened.
    Publish to topic
    'analysis/PNNL/BUILDING_1/Device/MixedAirTemperature' and
    query for topic
    'PNNL/BUILDING1_ANON/Device/MixedAirTemperature'

    :param historian: instance of the historian tested
    :param publish_agent: Fake agent used to publish messages to bus
    :param query_agent: Fake agent used to query historian
    :param clean_db_rows: fixture to clear data table 
    """
    print("\n** test_analysis_topic **")
    agent_uuid = None
    try:
        new_historian = copy.copy(historian)
        new_historian["tables_def"] = {"table_prefix": "readonly",
            "data_table": "data", "topics_table": "topics",
            "meta_table": "meta"}
        # new_historian["topic_replace_list"] = [
        #     {"from": "PNNL/BUILDING_1", "to": "PNNL/BUILDING1_ANON"}]

        new_historian["topic_replace_list"] = [
            {"from": "SEB", "to": "BUILDING_1"},
            {"from": "PNNL", "to": "Campus1"}]

        # 1: Install historian agent
        # Install and start historian agent
        source = new_historian.pop('source_historian')
        agent_uuid = volttron_instance.install_agent(agent_dir=source,
            config_file=new_historian, start=True,
            vip_identity='replace_hist')
        print("agent id: ", agent_uuid)

        # Publish fake data. The format mimics the format used by VOLTTRON drivers.
        # Make some random readings
        oat_reading = random.uniform(30, 100)
        mixed_reading = oat_reading + random.uniform(-5, 5)
        damper_reading = random.uniform(0, 100)

        # Create a message for all points.
        all_message = [{'OutsideAirTemperature': oat_reading,
                        'MixedAirTemperature': mixed_reading,
                        'DamperSignal': damper_reading}, {
                           'OutsideAirTemperature': {'units': 'F', 'tz': 'UTC',
                                                     'type': 'float'},
                           'MixedAirTemperature': {'units': 'F', 'tz': 'UTC',
                                                   'type': 'float'},
                           'DamperSignal': {'units': '%', 'tz': 'UTC',
                                            'type': 'float'}}]

        # Create timestamp
        now = datetime.utcnow().isoformat() + 'Z'
        print("now is ", now)
        headers = {headers_mod.DATE: now}
        # Publish messages
        publish(publish_agent, 'analysis/pnnl/seb/device', headers,
                all_message)
        gevent.sleep(0.5)

        # pytest.set_trace()
        # Query the historian
        result = query_agent.vip.rpc.call('replace_hist', 'query',
            topic='Campus1/BUILDING_1/Device/MixedAirTemperature', start=now,
            order="LAST_TO_FIRST").get(timeout=10)
        print('Query Result', result)
        assert (len(result['values']) == 1)
        (now_date, now_time) = now.split("T")
        if now_time[-1:] == 'Z':
            now_time = now_time[:-1]
        assert_timestamp(result['values'][0][0], now_date, now_time)
        assert (result['values'][0][1] == mixed_reading)
        topic_list = query_agent.vip.rpc.call(
            'replace_hist','get_topic_list').get(timeout=5)
        print (topic_list)
        assert 'Campus1/BUILDING_1/device/OutsideAirTemperature' in topic_list
        assert 'Campus1/BUILDING_1/device/DamperSignal' in topic_list
        assert 'Campus1/BUILDING_1/device/MixedAirTemperature' in topic_list
    finally:
        if agent_uuid:
            cleanup_function = globals()["cleanup_" + connection_type]
            cleanup_function(db_connection, ['readonly_data',
                                             'readonly_topics',
                                             'readonly_meta'])
            volttron_instance.stop_agent(agent_uuid)
            volttron_instance.remove_agent(agent_uuid)


@pytest.mark.historian
def test_analysis_topic_no_meta(request, historian, publish_agent, query_agent,
                                clean_db_rows):
    """
    Test query based on same start and end time with literal 'Z' at the end
    of utc time.
    Expected result: record with timestamp == start time

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0 agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param historian: instance of the historian tested
    :param clean_db_rows: fixture to clear data table 
    """

    global query_points
    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_analysis_topic for {}**".format(
        request.keywords.node.name))
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random_uniform(30, 100)
    mixed_reading = oat_reading + random_uniform(-5, 5)
    damper_reading = random_uniform(0, 100)

    # Create a message for all points.
    all_message = {'OutsideAirTemperature': oat_reading,
                    'MixedAirTemperature': mixed_reading,
                    'DamperSignal': damper_reading}

    # Create timestamp

    publish_time = (datetime.utcnow() - timedelta(days=1)).isoformat()
    print("publish_time ", publish_time)
    # publish_time = '2015-12-02T00:00:00'
    headers = {
        headers_mod.DATE: publish_time
    }

    # Publish messages
    publish(publish_agent, 'analysis/Building/LAB/Device',
            headers, all_message)
    gevent.sleep(0.5)
    abc = dict(peer=identity, method='query',
               topic=query_points['mixed_point'],
               start=publish_time,
               end=publish_time,
               count=20,
               order="LAST_TO_FIRST")
    # Query the historian
    result = query_agent.vip.rpc.call(identity,
                                      'query',
                                      topic=query_points['mixed_point'],
                                      start=publish_time,
                                      end=publish_time,
                                      count=20,
                                      order="LAST_TO_FIRST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 1)
    (now_date, now_time) = publish_time.split("T")
    if now_time[-1:] == 'Z':
        now_time = now_time[:-1]
    assert_timestamp(result['values'][0][0], now_date, now_time)
    assert (result['values'][0][1] == mixed_reading)


@pytest.mark.historian
def test_tz_conversion_local_tz(request, historian, publish_agent, query_agent,
                                clean_db_rows):
    """
    Test query based on same start and end time with literal 'Z' at the end
    of utc time.
    Expected result: record with timestamp == start time

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0 agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param historian: instance of the historian tested
    :param clean_db_rows: fixture to clear data table 
    """

    global query_points
    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_analysis_topic for {}**".format(
        request.keywords.node.name))
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random_uniform(30, 100)
    mixed_reading = oat_reading + random_uniform(-5, 5)
    damper_reading = random_uniform(0, 100)

    # Create a message for all points.
    all_message = [{'OutsideAirTemperature': {'key1':'value1',
                                              'key2':'value2'},
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
    publish_time_naive  = datetime.now() - timedelta(days=1)
    local_tz = get_localzone()
    local_t = local_tz.localize(publish_time_naive)
    publish_time = local_t.isoformat()
    utc_publish_time = local_t.astimezone(pytz.utc).isoformat()
    print("publish_time UTC is ", utc_publish_time)
    print("publish_time local tz is ", publish_time)
    # publish_time = '2015-12-02T00:00:00'
    headers = {
        headers_mod.DATE: publish_time
    }

    # Publish messages
    publish(publish_agent, 'analysis/Building/LAB/Device',
            headers, all_message)
    gevent.sleep(0.5)

    # Query the historian
    result = query_agent.vip.rpc.call(identity,
                                      'query',
                                      topic=query_points['mixed_point'],
                                      start=publish_time,
                                      end=publish_time,
                                      count=20,
                                      order="LAST_TO_FIRST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 1)
    (now_date, now_time) = utc_publish_time.split("T")
    if now_time[-1:] == 'Z':
        now_time = now_time[:-1]
    assert_timestamp(result['values'][0][0], now_date, now_time)
    assert (result['values'][0][1] == mixed_reading)


@pytest.mark.historian
def test_tz_conversion_naive_ts(request, historian, publish_agent, query_agent,
                                clean_db_rows):
    """
    Test query based on same start and end time with literal 'Z' at the end
    of utc time.
    Expected result: record with timestamp == start time

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0 agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param historian: instance of the historian tested
    :param clean_db_rows: fixture to clear data table 
    """

    global query_points
    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_analysis_topic for {}**".format(
        request.keywords.node.name))
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random_uniform(30, 100)
    mixed_reading = oat_reading + random_uniform(-5, 5)
    damper_reading = random_uniform(0, 100)

    # Create a message for all points.
    all_message = [{'OutsideAirTemperature': {'key1':'value1',
                                              'key2':'value2'},
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
    publish_time_naive  = datetime.now() - timedelta(days=1)
    local_tz = get_localzone()
    local_t = local_tz.localize(publish_time_naive)
    utc_publish_time = local_t.astimezone(pytz.utc).isoformat()
    publish_time = publish_time_naive.isoformat()
    print("publish_time UTC is ", utc_publish_time)
    print("publish_time naive ", publish_time)
    # publish_time = '2015-12-02T00:00:00'
    headers = {
        headers_mod.DATE: publish_time
    }

    # Publish messages
    publish(publish_agent, 'analysis/Building/LAB/Device',
            headers, all_message)
    gevent.sleep(0.5)

    # Query the historian
    result = query_agent.vip.rpc.call(identity,
                                      'query',
                                      topic=query_points['mixed_point'],
                                      start=publish_time,
                                      end=publish_time,
                                      count=20,
                                      order="LAST_TO_FIRST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 1)
    (now_date, now_time) = publish_time.split("T")
    if now_time[-1:] == 'Z':
        now_time = now_time[:-1]
    assert_timestamp(result['values'][0][0], now_date, now_time)
    assert (result['values'][0][1] == mixed_reading)

@pytest.mark.historian
def test_record_topic_query(request, historian, publish_agent, query_agent,
                            clean_db_rows):
    """
    Test query based on same start with literal 'Z' at the end of utc time.
    Cannot query based on exact time as timestamp recorded is time of insert
    publish and query record topic

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param historian: instance of the historian tested
    :param clean_db_rows: fixture to clear data table 
    """

    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_exact_timestamp for {}**".format(
        request.keywords.node.name))
    # Publish int data

    # Create timestamp
    now = datetime.utcnow().isoformat() + 'Z'
    print("now is ", now)

    # Publish messages
    publish(publish_agent, topics.RECORD(subtopic="test"), None, 1)
    # sleep 1 second so that records gets inserted with unique timestamp
    # even in case of older mysql
    gevent.sleep(1)

    publish(publish_agent, topics.RECORD(subtopic="test"), None, 'value0')
    # sleep 1 second so that records gets inserted with unique timestamp
    # even in case of older mysql
    gevent.sleep(1)

    publish(publish_agent, topics.RECORD(subtopic="test"), None,
            {'key': 'value'})
    gevent.sleep(0.5)

    # pytest.set_trace()
    # Query the historian
    result = query_agent.vip.rpc.call(identity,
                                      'query',
                                      topic=topics.RECORD(subtopic="test"),
                                      start=now,
                                      count=20,
                                      order="FIRST_TO_LAST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 3)
    assert (result['values'][0][1] == 1)
    assert (result['values'][1][1] == 'value0')
    assert (result['values'][2][1] == {'key': 'value'})


@pytest.mark.historian
def test_log_topic(request, historian, publish_agent, query_agent, 
                   clean_db_rows):
    """
    Test publishing to log topic with header and no timestamp in message
    Expected result:
     Record should get entered into database with current time at time of
     insertion and should ignore timestamp in header

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param historian: instance of the historian tested
    :param clean_db_rows: fixture to clear data table 
    """

    global query_points
    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_log_topic for {}**".format(request.keywords.node.name))
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random_uniform(30, 100)
    mixed_reading = oat_reading + random_uniform(-5, 5)

    # Create a message for all points.
    message = {'MixedAirTemperature': {'Readings': mixed_reading, 'Units': 'F',
                                       'tz': 'UTC', 'type': 'float'}}

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
    publish(publish_agent, "datalogger/Building/LAB/Device", headers, message)
    gevent.sleep(1)

    # Query the historian
    result = query_agent.vip.rpc.call(
        identity,
        'query',
        topic="datalogger/Building/LAB/Device/MixedAirTemperature",
        start=current_time,
        order="LAST_TO_FIRST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 1)
    assert (result['values'][0][1] == mixed_reading)


@pytest.mark.historian
def test_log_topic_no_header(request, historian, publish_agent, query_agent,
                             clean_db_rows):
    """
    Test publishing to log topic without any header and no timestamp in message
    Expected result:
     Record should get entered into database with current time at time of
     insertion and should not complain about header

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param historian: instance of the historian tested
    :param clean_db_rows: fixture to clear data table 
    """

    global query_points
    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_log_topic for {}**".format(request.keywords.node.name))
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random_uniform(30, 100)
    mixed_reading = oat_reading + random_uniform(-5, 5)

    # Create a message for all points.
    message = {'MixedAirTemperature': {'Readings': mixed_reading, 'Units': 'F',
                                       'tz': 'UTC', 'type': 'float'}}

    # pytest.set_trace()
    # Create timestamp
    current_time = datetime.utcnow().isoformat() + 'Z'

    # Publish messages
    publish(publish_agent, "datalogger/Building/LAB/Device", None, message)
    gevent.sleep(1)

    # Query the historian
    result = query_agent.vip.rpc.call(
        identity,
        'query',
        topic="datalogger/Building/LAB/Device/MixedAirTemperature",
        start=current_time,
        order="LAST_TO_FIRST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 1)
    assert (result['values'][0][1] == mixed_reading)


@pytest.mark.historian
def test_log_topic_timestamped_readings(request, historian, publish_agent,
                                        query_agent, clean_db_rows):
    """
    Test publishing to log topic with explicit timestamp in message.
    Expected result:
     Record should get entered into database with the timestamp in
     message and not timestamp in header

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param historian: instance of the historian tested
    :param clean_db_rows: fixture to clear data table 
    """

    global query_points
    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_log_topic for {}**".format(request.keywords.node.name))
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random_uniform(30, 100)
    mixed_reading = oat_reading + random_uniform(-5, 5)

    # Create a message for all points.
    message = {'MixedAirTemperature': {'Readings': ['2015-12-02T00:00:00',
                                                    mixed_reading],
                                       'Units': 'F',
                                       'tz': 'UTC',
                                       'data_type': 'float'}}

    # pytest.set_trace()
    # Create timestamp
    now = datetime.utcnow().isoformat() + 'Z'
    print("now is ", now)
    headers = {
        headers_mod.DATE: now
    }
    # Publish messages
    publish(publish_agent, "datalogger/Building/LAB/Device", headers, message)
    gevent.sleep(1)

    # Query the historian
    result = query_agent.vip.rpc.call(
        identity,
        'query',
        topic="datalogger/Building/LAB/Device/MixedAirTemperature",
        end='2015-12-02T00:00:01', #end time is exclusive so do +1 second
        order="LAST_TO_FIRST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 1)
    assert (result['values'][0][1] == mixed_reading)
    assert_timestamp(result['values'][0][0], '2015-12-02', '00:00:00.000000')


@pytest.mark.historian
def test_get_topic_metadata(request, historian, publish_agent,
                            query_agent, clean_db_rows):
    """
    Test querying for topic metadata
    Expected result:
     Should return a map of {topic_name:metadata}
     Should work for a single topic string and list of topics
     Should throw ValueError when input is not string or list


    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param historian: instance of the historian tested
    :param clean_db_rows: fixture to clear data table 
    """

    global query_points
    # print('HOME', volttron_instance.volttron_home)
    print(
        "\n** test_get_topic_metadata for {}**".format(
            request.keywords.node.name))
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random_uniform(30, 100)
    mixed_reading = oat_reading + random_uniform(-5, 5)

    # Create a message for all points.
    message = {'temp1': {'Readings': ['2015-12-02T00:00:00',
                                      mixed_reading],
                         'Units': 'F',
                         'tz': 'UTC',
                         'data_type': 'int'},
               'temp2': {'Readings': ['2015-12-02T00:00:00',
                                      mixed_reading],
                         'Units': 'F',
                         'tz': 'UTC',
                         'data_type': 'double'},
               }

    # pytest.set_trace()
    # Create timestamp
    now = datetime.utcnow().isoformat() + 'Z'
    print("now is ", now)
    headers = {
        headers_mod.DATE: now
    }
    # Publish messages
    publish(publish_agent, "datalogger/Building/LAB/Device", headers,
            message)
    gevent.sleep(1)

    # Query the historian
    result = query_agent.vip.rpc.call(
        identity,
        'get_topics_metadata',
        topics="datalogger/Building/LAB/Device/temp1"
    ).get(timeout=10)

    print('Query Result', result)
    assert result['datalogger/Building/LAB/Device/temp1'] == \
        {'units': 'F', 'tz': 'UTC', 'type': 'int'}

    # Query the historian
    result = query_agent.vip.rpc.call(
        identity,
        'get_topics_metadata',
        topics=["datalogger/Building/LAB/Device/temp1",
                "datalogger/Building/LAB/Device/temp2"]
    ).get(timeout=10)

    print('Query Result', result)
    assert result['datalogger/Building/LAB/Device/temp1'] == \
        {'units': 'F', 'tz': 'UTC', 'type': 'int'}
    assert result['datalogger/Building/LAB/Device/temp2'] == \
        {'units': 'F', 'tz': 'UTC', 'type': 'float'}

@pytest.mark.historian
def test_insert_duplicate(request, historian, publish_agent, query_agent,
                        clean_db_rows):
    """
    Test that historians don't break when duplicate data gets published.
    historians' should ignore or update record in the database but should not
    throw exception
    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param historian: instance of the historian tested
    :param clean_db_rows: fixture to clear data table 
    """
    global query_points, DEVICES_ALL_TOPIC, db_connection

    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_insert_duplicate for {}**".format(
        request.keywords.node.name))

    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings.  Random readings are going to be
    # within the tolerance here.
    oat_reading = random_uniform(30, 100)


    float_meta = {'units': 'F', 'tz': 'UTC', 'type': 'float'}

    # Create a message for all points.
    all_message = [{'OutsideAirTemperature': oat_reading},
                   {'OutsideAirTemperature': float_meta}]

    # Create timestamp
    now = datetime.utcnow().isoformat(' ')

    # now = '2015-12-02T00:00:00'
    headers = {
        headers_mod.DATE: now
    }
    print("Published time in header: " + now)
    # Publish messages
    publish(publish_agent, DEVICES_ALL_TOPIC, headers, all_message)

    gevent.sleep(1)

    # Query the historian
    result = query_agent.vip.rpc.call(identity,
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

    #publish same data again
    publish(publish_agent, DEVICES_ALL_TOPIC, headers, all_message)

    gevent.sleep(1)

    # Query the historian
    result = query_agent.vip.rpc.call(identity, 'query',
                                      topic=query_points['oat_point'],
                                      count=20, order="LAST_TO_FIRST").get(
        timeout=100)
    print('Query Result', result)
    assert (len(result['values']) == 1)
    (now_date, now_time) = now.split(" ")
    assert_timestamp(result['values'][0][0], now_date, now_time)
    assert (result['values'][0][1] == oat_reading)
    assert set(result['metadata'].items()) == set(float_meta.items())

@pytest.mark.historian
def test_multi_topic_query(request, historian, publish_agent, query_agent,
                           clean_db_rows):
    """
    Test basic functionality of historian. Inserts three points as part
    of all topic and checks if all three got into the database
    Expected result:
    Should be able to query data based on list of topic name. Result should
    contain both data and empty metadata
    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param historian: instance of the historian tested
    :param clean_db_rows: fixture to clear data table 
    """

    global query_points, DEVICES_ALL_TOPIC, db_connection

    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_multi_topic_query for {}**".format(
        request.keywords.node.name))

    expected_result = {}
    values_dict = {query_points['oat_point']: [],
                   query_points['mixed_point']: []}
    for x in range(0, 5):
        ts, reading, meta = publish_devices_fake_data(publish_agent)
        gevent.sleep(0.5)
        if x < 3:
            values_dict[query_points['oat_point']].append(
                [ts, reading])
            values_dict[query_points['mixed_point']].append(
                [ts, reading])
    expected_result["values"] = values_dict
    expected_result["metadata"] = {}

    gevent.sleep(1)

    # Query the historian
    result = query_agent.vip.rpc.call(
        identity,
        'query',
        topic=[query_points['oat_point'], query_points['mixed_point']],
        count=3,
        order="FIRST_TO_LAST").get(timeout=100)
    print('Query Result', result)
    print('Expected Result', expected_result)

    assert result["metadata"] == expected_result["metadata"]

    for i in range(0, 3):
        expected_date, expected_time = expected_result["values"][query_points[
            'mixed_point']][i][0].split("T")
        assert_timestamp(result["values"][query_points['mixed_point']][i][0],
                         expected_date, expected_time)
        assert (result["values"][query_points['mixed_point']][i][1] ==
                expected_result["values"][query_points['mixed_point']][i][1])

        expected_date, expected_time = \
        expected_result["values"][query_points['oat_point']][i][0].split("T")
        assert_timestamp(result["values"][query_points['oat_point']][i][0],
                         expected_date, expected_time)
        assert (result["values"][query_points['oat_point']][i][1] ==
                expected_result["values"][query_points['oat_point']][i][1])


@pytest.mark.historian
def test_multi_topic_query_single_result(request, historian, publish_agent,
                                         query_agent, clean_db_rows):
    """
    Test basic functionality of historian. Inserts three points as part
    of all topic and checks if all three got into the database
    Expected result:
    Should be able to query data based on list of topic names. Result should
    contain both data and metadata
    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param historian: instance of the historian tested
    :param clean_db_rows: fixture to clear data table
    """

    global query_points, DEVICES_ALL_TOPIC, db_connection

    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_multi_topic_query_single_result for {}**".format(
        request.keywords.node.name))

    # Insert topic MixedAirTemperature with a older timestamp so query
    # will not return this
    all_message = [{'MixedAirTemperature': 1.1}]
    # Create timestamp
    old_time = (datetime.utcnow() - timedelta(days=1)).isoformat(
        'T') + "+00:00"
    # now = '2015-12-02T00:00:00'
    headers = {headers_mod.DATE: old_time}
    publish(publish_agent, DEVICES_ALL_TOPIC, headers, all_message)
    gevent.sleep(1)

    # Now publish data for oat_point using current time
    query_start = datetime.utcnow().isoformat()
    expected_result = {}
    values_dict = {query_points['oat_point']: []}
    for x in range(0, 5):
        ts, reading, meta = publish_devices_fake_data_single_topic(
            publish_agent)
        gevent.sleep(0.5)
        if x == 0:
            query_start = ts
        if x < 3:
            values_dict[query_points['oat_point']].append(
                [ts, reading])
    expected_result["values"] = values_dict
    gevent.sleep(1)

    # Query the historian with two valid topic - one with data and another with
    # no data in the queried time interval
    result = query_agent.vip.rpc.call(
        identity,
        'query',
        topic=[query_points['oat_point'], query_points['mixed_point']],
        count=3,
        start=query_start,
        order="FIRST_TO_LAST").get(timeout=100)
    print('Query Result', result)
    print('Expected Result', expected_result)

    assert result["metadata"] == {}
    assert result["values"][query_points['mixed_point']] == []
    for i in range(0, 3):
        expected_date, expected_time = \
        expected_result["values"][query_points['oat_point']][i][0].split("T")
        assert_timestamp(result["values"][query_points['oat_point']][i][0],
                         expected_date, expected_time)
        assert (result["values"][query_points['oat_point']][i][1] ==
                expected_result["values"][query_points['oat_point']][i][1])

    # Query the historian with a valid topic and an invalid topic
    result = query_agent.vip.rpc.call(identity, 'query',
        topic=[query_points['oat_point'], "device/topic/unknown"],
        count=3, start=query_start, order="FIRST_TO_LAST").get(timeout=100)
    print('Query Result', result)
    print('Expected Result', expected_result)

    assert result["metadata"] == {}
    assert len(result["values"]) == 1
    for i in range(0, 3):
        expected_date, expected_time = \
            expected_result["values"][query_points['oat_point']][i][
                0].split("T")
        assert_timestamp(result["values"][query_points['oat_point']][i][0],
                         expected_date, expected_time)
        assert (result["values"][query_points['oat_point']][i][1] ==
                expected_result["values"][query_points['oat_point']][i][1])


@pytest.mark.historian
def test_query_with_naive_timestamp(request, historian, publish_agent,
                                    query_agent, clean_db_rows):
    """
    Test basic functionality of historian. Inserts three points as part
    of all topic and checks if all three got into the database
    Expected result:
    Should be able to query data based on topic name. Result should contain
    both data and metadata
    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param historian: instance of the historian tested
    :param clean_db_rows: fixture to clear data table 
    """

    global query_points, DEVICES_ALL_TOPIC, db_connection

    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_basic_function for {}**".format(
        request.keywords.node.name))

    expected_result = {}
    values_dict = {query_points['oat_point']: [],
                   query_points['mixed_point']: []}
    current_t_local = datetime.now()
    for x in range(0, 5):
        ts, reading, meta = publish_devices_fake_data(publish_agent)
        gevent.sleep(0.5)
        if x < 3:
            values_dict[query_points['oat_point']].append(
                [ts, reading])
            values_dict[query_points['mixed_point']].append(
                [ts, reading])
    expected_result["values"] = values_dict
    expected_result["metadata"] = {}

    gevent.sleep(1)

    # Query the historian
    result = query_agent.vip.rpc.call(
        identity,
        'query',
        topic=[query_points['oat_point'], query_points['mixed_point']],
        count=3,
        start=current_t_local.isoformat(),
        end=(current_t_local + timedelta(days=1)).isoformat(),
        order="FIRST_TO_LAST").get(timeout=100)
    print('Query Result', result)
    print('Expected Result', expected_result)

    assert result["metadata"] == expected_result["metadata"]

    for i in range(0, 3):
        expected_date, expected_time = expected_result["values"][query_points[
            'mixed_point']][i][0].split("T")
        assert_timestamp(result["values"][query_points['mixed_point']][i][0],
                         expected_date, expected_time)
        assert (result["values"][query_points['mixed_point']][i][1] ==
                expected_result["values"][query_points['mixed_point']][i][1])

        expected_date, expected_time = \
        expected_result["values"][query_points['oat_point']][i][0].split("T")
        assert_timestamp(result["values"][query_points['oat_point']][i][0],
                         expected_date, expected_time)
        assert (result["values"][query_points['oat_point']][i][1] ==
                expected_result["values"][query_points['oat_point']][i][1])


@pytest.mark.historian
def test_query_with_start_end_count(request, historian, publish_agent,
                                    query_agent, clean_db_rows):
    """
    Test basic functionality of historian. Inserts three points as part
    of all topic and checks if all three got into the database
    Expected result:
    Should be able to query data based on topic name. Result should contain
    both data and metadata
    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param historian: instance of the historian tested
    :param clean_db_rows: fixture to clear data table 
    """

    global query_points, DEVICES_ALL_TOPIC, db_connection

    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_basic_function for {}**".format(
        request.keywords.node.name))

    expected_result = {}
    values_dict = {query_points['oat_point']: [],
                   query_points['mixed_point']: []}
    query_start_time = datetime.utcnow().isoformat('T') + "+00:00"
    query_end_time = ""
    for x in range(0, 5):
        ts, reading, meta = publish_devices_fake_data(publish_agent)
        gevent.sleep(0.5)
        if x == 2:
            # set to 3rd record time. query should return 1st and 2nd
            query_end_time = ts
        if x < 2:
            values_dict[query_points['oat_point']].append(
                [ts, reading])
            values_dict[query_points['mixed_point']].append(
                [ts, reading])
    expected_result["values"] = values_dict
    expected_result["metadata"] = {}

    gevent.sleep(1)
    print("Query start: {}".format(query_start_time))
    print("Query end: {}".format(query_end_time))
    # Query the historian
    result = query_agent.vip.rpc.call(
        identity,
        'query',
        topic=[query_points['oat_point'], query_points['mixed_point']],
        start=query_start_time,
        end = query_end_time,
        count=3,
        order="FIRST_TO_LAST").get(timeout=100)
    print('Query Result', result)
    print('Expected Result', expected_result)
    assert len(result["values"][query_points['mixed_point']]) == 2
    assert len(result["values"][query_points['oat_point']]) == 2
    assert result["metadata"] == expected_result["metadata"]

    for i in range(0, 2):
        expected_date, expected_time = expected_result["values"][query_points[
            'mixed_point']][i][0].split("T")
        assert_timestamp(result["values"][query_points['mixed_point']][i][0],
                         expected_date, expected_time)
        assert (result["values"][query_points['mixed_point']][i][1] ==
                expected_result["values"][query_points['mixed_point']][i][1])

        expected_date, expected_time = \
            expected_result["values"][query_points['oat_point']][i][0].split("T")
        assert_timestamp(result["values"][query_points['oat_point']][i][0],
                         expected_date, expected_time)
        assert (result["values"][query_points['oat_point']][i][1] ==
                expected_result["values"][query_points['oat_point']][i][1])

@pytest.mark.historian
def test_get_topic_list(request, historian, publish_agent, query_agent,
                        clean_db_rows, volttron_instance):
    """
    Test the get_topic_list api.
    Expected result:
    Should be able to query data based on topic name. Result should contain
    both data and metadata
    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param historian: instance of the historian tested
    :param clean_db_rows: fixture to clear data table 
    :param volttron_instance: instance of PlatformWrapper. Volttron
    instance in which agents are tested
    """

    global query_points, DEVICES_ALL_TOPIC, db_connection, topics_table, \
        connection_type

    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_basic_function for {}**".format(
        request.keywords.node.name))
    agent_uuid = None
    try:
        new_historian = copy.copy(historian)
        new_historian["tables_def"] = {
            "table_prefix": "topic_list_test",
            "data_table":"data",
            "topics_table": "topics",
            "meta_table": "meta"}

        # 1: Install historian agent
        # Install and start historian agent
        source = new_historian.pop('source_historian')
        agent_uuid = volttron_instance.install_agent(
            agent_dir=source,
            config_file=new_historian,
            start=True, vip_identity='topic_list.historian')
        print("agent id: ", agent_uuid)

        # Publish fake data. The format mimics the format used by VOLTTRON drivers.
        # Make some random readings
        oat_reading = random_uniform(30, 100)
        mixed_reading = oat_reading + random_uniform(-5, 5)
        damper_reading = random_uniform(0, 100)

        float_meta = {'units': 'F', 'tz': 'UTC', 'type': 'float'}
        percent_meta = {'units': '%', 'tz': 'UTC', 'type': 'float'}

        # Create a message for all points.
        all_message = [{'OutsideAirTemperature': oat_reading,
                        'MixedAirTemperature': mixed_reading},
                       {'OutsideAirTemperature': float_meta,
                        'MixedAirTemperature': float_meta}]

        # Create timestamp
        now = datetime.utcnow().isoformat(' ')

        # now = '2015-12-02T00:00:00'
        headers = {
            headers_mod.DATE: now
        }
        print("Published time in header: " + now)
        # Publish messages
        publish(publish_agent, DEVICES_ALL_TOPIC, headers, all_message)

        gevent.sleep(2)

        # Query the historian
        topic_list = query_agent.vip.rpc.call('topic_list.historian',
                                          'get_topic_list').get(timeout=100)
        print('Query Result', topic_list)
        assert len(topic_list) == 2
        expected = [query_points['oat_point'], query_points['mixed_point']]
        assert set(topic_list) ==  set(expected)
    finally:
        if agent_uuid:
            cleanup_function = globals()["cleanup_" + connection_type]
            cleanup_function(db_connection, ['topic_list_test_data',
                                             'topic_list_test_topics',
                                             'topic_list_test_meta'])
            volttron_instance.stop_agent(agent_uuid)
            volttron_instance.remove_agent(agent_uuid)


@pytest.mark.historian
def test_readonly_mode(request, historian, publish_agent, query_agent,
                       clean_db_rows, volttron_instance):
    """
    Test the readonly mode of historian where historian is only used to query
    and not insert anything into the database.
    Expected result:
    data published to message bus should not be recorded in the historian
    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param historian: instance of the historian tested
    :param clean_db_rows: fixture to clear data table 
    :param volttron_instance: instance of PlatformWrapper. Volttron
    instance in which agents are tested
    """

    global query_points, DEVICES_ALL_TOPIC, db_connection, topics_table, \
        connection_type

    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_readonly_mode for {}**".format(
        request.keywords.node.name))
    agent_uuid = None
    try:
        new_historian = copy.copy(historian)
        new_historian["tables_def"] = {
            "table_prefix": "readonly",
            "data_table":"data",
            "topics_table": "topics",
            "meta_table": "meta"}

        # 1: Install historian agent
        # Install and start historian agent
        source = new_historian.pop('source_historian')
        agent_uuid = volttron_instance.install_agent(
            agent_dir=source,
            config_file=new_historian,
            start=True, vip_identity='readonly.historian')
        print("agent id: ", agent_uuid)

        # Create timestamp
        query_start = datetime.utcnow().isoformat() + 'Z'
        print("query_start is ", query_start)

        # Publish messages
        publish(publish_agent, topics.RECORD(subtopic="test"), None, 1)
        # sleep 1 second so that records gets inserted with unique timestamp
        # even in case of older mysql
        gevent.sleep(1)

        # Query the historian
        result = query_agent.vip.rpc.call(
            'readonly.historian',
            'query',
            topic=topics.RECORD(subtopic="test"),
            start=query_start, count=20,
            order="FIRST_TO_LAST").get(timeout=10)
        print('Query Result', result)
        assert (len(result['values']) == 1)
        assert (result['values'][0][1] == 1)

        volttron_instance.remove_agent(agent_uuid)

        #reinstall agent this time with readonly=True

        new_historian["readonly"] = True
        agent_uuid = volttron_instance.install_agent(
            agent_dir=source,
            config_file=new_historian, start=True,
            vip_identity='readonly.historian')
        print("agent id: ", agent_uuid)

        # Publish messages
        publish(publish_agent, topics.RECORD(subtopic="test"), None, 2)
        gevent.sleep(1)

        # Query the historian
        result = query_agent.vip.rpc.call(
            'readonly.historian', 'query',
            topic=topics.RECORD(subtopic="test"), start=query_start, count=20,
            order="FIRST_TO_LAST").get(timeout=10)
        print('Query Result', result)
        assert (len(result['values']) == 1)
        assert (result['values'][0][1] == 1)

    finally:
        if agent_uuid:
            cleanup_function = globals()["cleanup_" + connection_type]
            cleanup_function(db_connection, ['readonly_data',
                                             'readonly_topics',
                                             'readonly_meta'])
            volttron_instance.stop_agent(agent_uuid)
            volttron_instance.remove_agent(agent_uuid)

def publish_devices_fake_data(publish_agent, time=None):
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    global DEVICES_ALL_TOPIC
    reading = random_uniform(30, 100)
    meta = {'units': 'F', 'tz': 'UTC', 'type': 'float'}
    # Create a message for all points.
    all_message = [{'OutsideAirTemperature': reading,
                    'MixedAirTemperature': reading,
                    'DamperSignal': reading},
                   {'OutsideAirTemperature': meta,
                    'MixedAirTemperature': meta,
                    'DamperSignal': meta
                    }]
    # Create timestamp
    if not time:
        time = datetime.utcnow().isoformat('T') + "+00:00"
    # now = '2015-12-02T00:00:00'
    headers = {
        headers_mod.DATE: time
    }
    print("Published time in header: " + time)
    # Publish messages
    publish(publish_agent, DEVICES_ALL_TOPIC, headers, all_message)
    return time, reading, meta


def publish_devices_fake_data_single_topic(publish_agent, time=None):
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    global DEVICES_ALL_TOPIC
    reading = random_uniform(30, 100)
    meta = {'units': 'F', 'tz': 'UTC', 'type': 'float'}

    # Create a message for all points.
    all_message = [{'OutsideAirTemperature': reading},
                   {'OutsideAirTemperature': meta
                    }]
    # Create timestamp
    if not time:
        time = datetime.utcnow().isoformat('T') + "+00:00"
    # now = '2015-12-02T00:00:00'
    headers = {
        headers_mod.DATE: time
    }
    print("Published time in header: " + time)
    # Publish messages
    publish(publish_agent, DEVICES_ALL_TOPIC, headers, all_message)
    return time, reading, meta

