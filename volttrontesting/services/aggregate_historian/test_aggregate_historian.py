# pytest test cases for SQLHistorian
# For mysql test's to succeed
# 1. MySql server should be running
# 2. test database and test user should exist
# 3. Test user should have all privileges on test database
# 4. Refer to the dictionary object mysql_platform for the server configuration
import sqlite3
from datetime import datetime, timedelta

import gevent
import pytest
from volttron.platform.messaging import headers as headers_mod
from dateutil.parser import parse

try:
    import mysql.connector as mysql

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
# table_defs with prefix
sqlite_aggregator = {
    "source_historian": "services/core/SQLHistorian",
    "source_agg_historian": "services/core/SQLAggregateHistorian",
    "connection": {
        "type": "sqlite",
        "params": {
            "database": 'test.sqlite'
        }
    },
    "tables_def": {
        "table_prefix": "volttron",
        "data_table": "data_table",
        "topics_table": "topics_table",
        "meta_table": "meta_table",
    }
}

# Create a database "historian", create user "historian" with passwd
# "historian" and grant historian user access to "historian" database

# table_defs with prefix
mysql_aggregator = {
    "source_historian": "services/core/SQLHistorian",
    "source_agg_historian": "services/core/SQLAggregateHistorian",
    "agent_id": "test",
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

mongo_aggregator = {
    "source_historian": "services/core/MongodbHistorian",
    "source_agg_historian": "services/core/MongodbAggregateHistorian",
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
table_names = dict()
connection_type = None


def setup_mysql(connection_params, table_names):
    print ("setup mysql")
    db_connection = mysql.connect(**connection_params)
    # clean up any rows from older runs
    cursor = db_connection.cursor()
    cursor.execute("DELETE FROM " + table_names['data_table'])
    cursor.execute("DELETE FROM " + table_names['topics_table'])
    cursor.execute("DELETE FROM " + table_names['meta_table'])
    cursor.execute("DELETE FROM " + table_names['agg_topics_table'])
    cursor.execute("DELETE FROM " + table_names['agg_meta_table'])
    db_connection.commit()
    return db_connection


def setup_sqlite(connection_params, table_names):
    print ("setup sqlite")
    database_path = connection_params['database']
    print ("connecting to sqlite path " + database_path)
    db_connection = sqlite3.connect(database_path)
    print ("successfully connected to sqlite")
    db_connection.commit()
    return db_connection


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
    db[table_names['agg_topics_table']].remove()
    db[table_names['agg_meta_table']].remove()
    return db


def cleanup_sql(db_connection, truncate_tables):
    cursor = db_connection.cursor()
    for table in truncate_tables:
        cursor.execute("DELETE FROM " + table)
    db_connection.commit()


def cleanup_sqlite(db_connection, truncate_tables):
    cleanup_sql(db_connection, truncate_tables)
    pass


def cleanup_mysql(db_connection, truncate_tables):
    cleanup_sql(db_connection, truncate_tables)


def cleanup_mongodb(db_connection, truncate_tables):
    for collection in truncate_tables:
        db_connection[collection].remove()


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


def publish_test_data(publish_agent, start_time, start_reading, count):
    reading = start_reading
    time = start_time
    print ("publishing test data starttime is {} utcnow is {}".format(
        start_time, datetime.utcnow()))
    print ("publishing test data value string {} at {}".format(reading,
                                                               datetime.now()))

    float_meta = {'units': 'F', 'tz': 'UTC', 'type': 'float'}
    for i in range(0, count):
        # Create a message for all points.
        all_message = [{'in_temp': reading,
                        'out_temp': reading},
                       {'in_temp': float_meta,
                        'out_temp': float_meta
                        }]
        headers = {
            headers_mod.DATE: time.isoformat()
        }
        publish_agent.vip.pubsub.publish('pubsub',
                                         "devices/device1/all",
                                         headers=headers,
                                         message=all_message).get(timeout=10)

        reading += 1
        time = time + timedelta(seconds=30)


def get_expected_sum(query_agent, topic, end_time, minutes_delta):
    start_time = parse(end_time) - timedelta(minutes=minutes_delta)
    start_time = start_time.isoformat('T')
    data_values = query_agent.vip.rpc.call(
        'platform.historian',
        'query',
        topic=topic,
        start=start_time,
        end=end_time,
        count=20,
        order="FIRST_TO_LAST").get(timeout=100)
    expected_data = 0
    print("data_values {}".format(data_values))
    for d in data_values['values']:
        if isinstance(topic, list) and len(topic) > 1:
            expected_data += int(d[2])
        else:
            expected_data += int(d[1])
    return expected_data


@pytest.fixture(scope="module")
def query_agent(request, volttron_instance):
    # 1: Start a fake fake_agent to query the sqlhistorian in volttron_instance
    fake_agent = volttron_instance.build_agent()

    # 2: add a tear down method to stop sqlhistorian fake_agent and the fake
    # fake_agent that published to message bus
    def stop_agent():
        print("In teardown method of fake_agent")
        fake_agent.core.stop()

    request.addfinalizer(stop_agent)
    return fake_agent


# Fixtures for setup and teardown of sqlhistorian agent and aggregation agent
@pytest.fixture(scope="module",
                params=[
                    mysql_skipif(mysql_aggregator),
                    sqlite_aggregator,
                    pymongo_skipif(mongo_aggregator)
                ])
def aggregate_agent(request, volttron_instance):
    global db_connection, table_names, connection_type
    print("** Setting up test_sqlhistorian module **")

    # Fix sqlite db path
    print("request param", request.param)
    connection_type = request.param['connection']['type']
    if connection_type == 'sqlite':
        request.param['connection']['params']['database'] = \
            volttron_instance.volttron_home + "/historian.sqlite"

    # figure out db table names from config
    # Set this hear so that we can create these table after connecting to db
    table_names = get_table_names(request.param)

    # 2: Open db connection that can be used for row deletes after
    # each test method. Create tables
    function_name = "setup_" + connection_type
    try:
        setup_function = globals()[function_name]
        db_connection = setup_function(request.param['connection']['params'],
                                       table_names)
    except NameError as n:
        pytest.fail(msg="No setup method({}) found for connection type {} "
                    .format(function_name, connection_type))

    print ("request.param -- {}".format(request.param))
    # 2. Install agents - sqlhistorian, sqlaggregatehistorian
    historian_uuid = volttron_instance.install_agent(
        vip_identity='platform.historian',
        agent_dir=request.param['source_historian'],
        config_file=request.param,
        start=True)
    print("agent id: ", historian_uuid)

    # 3: add a tear down method to stop sqlhistorian agent and the fake
    # agent that published to message bus
    def stop_agent():
        print("In teardown method of aggregate agent")
        # if db_connection:
        #     db_connection.close()
        #     print("closed connection to db")
        if volttron_instance.is_running():
            volttron_instance.remove_agent(historian_uuid)

    request.addfinalizer(stop_agent)
    return request.param


def cleanup(connection_type, truncate_tables):
    global db_connection, table_names
    truncate_tables.append(table_names['data_table'])
    cleanup_function = globals()["cleanup_" + connection_type]
    cleanup_function(db_connection, truncate_tables)


@pytest.mark.aggregator
def test_single_topic_pattern(volttron_instance, aggregate_agent, query_agent):
    """
    Test the basic functionality of aggregate historian when aggregating a
    single topic that is identified by topic_name_pattern instead of
    explicit topic
    1. Publish fake data
    2. Start aggregator agent with configurtion to collect sum of data in
    two different intervals.
    3. Sleep for 1 minute
    4. Do an rpc call to historian to verify data

    Expected result:
    1. Aggregate data should be computed for both 2m for the two configured
    points.
    2. timestamp for both points within a single aggregation group should be
    time synchronized

    @param volttron_instance: volttron instance on which test agents are
    installed and run
    @param aggregate_agent: the aggregate historian configuration
    @param query_agent: fake agent used to query historian
    @param clean: clean up method that is called at the end of each test case
    """

    # Publish fake data.
    start_time = datetime.utcnow() - timedelta(minutes=1)
    publish_test_data(query_agent, start_time, 0, 5)
    gevent.sleep(0.5)
    agent_uuid = None
    try:

        aggregate_agent['aggregations'] = [
            {"aggregation_period": "1m",
             "use_calendar_time_periods": True,
             "points": [
                 {
                     "topic_name_pattern": "device1/out_.*",
                     "aggregation_topic_name": "device1/outsidetemp_aggregate",
                     "aggregation_type": "sum",
                     "min_count": 2
                 },
                 {
                     "topic_name_pattern": "device1/in_*",
                     "aggregation_topic_name": "device1/intemp_aggregate",
                     "aggregation_type": "sum",
                     "min_count": 2
                 }
             ]
             }
        ]

        agent_uuid = volttron_instance.install_agent(
            agent_dir=aggregate_agent["source_agg_historian"],
            config_file=aggregate_agent,
            start=True)
        print("agent id: ", agent_uuid)

        result1 = query_agent.vip.rpc.call('platform.historian',
                                           'query',
                                           topic='device1/outsidetemp_aggregate',
                                           agg_type='sum',
                                           agg_period='1m',
                                           count=20,
                                           order="FIRST_TO_LAST").get(
            timeout=100)

        print(result1)
        # assert (result1['metadata']) == \
        #        {'units': 'F', 'tz': 'UTC', 'type': 'float'}

        result2 = query_agent.vip.rpc.call('platform.historian',
                                           'query',
                                           topic='device1/intemp_aggregate',
                                           agg_type='sum',
                                           agg_period='1m',
                                           count=20,
                                           order="FIRST_TO_LAST").get(
            timeout=100)

        # point1 and point2 configured within the same aggregation group should
        # be time synchronized
        assert (result2['values'][0][0] == result1['values'][0][0])
        # Now verify the computed sum
        expected_sum = get_expected_sum(query_agent,
                                        'device1/in_temp',
                                        result2['values'][0][0], 1)
        assert (result1['values'][0][1] == expected_sum)
        assert (result2['values'][0][1] == expected_sum)


    finally:
        cleanup(aggregate_agent['connection']['type'], ['sum_1m'])
        if agent_uuid is not None:
            volttron_instance.remove_agent(agent_uuid)


@pytest.mark.aggregator
def test_single_topic(request, volttron_instance, aggregate_agent,
                      query_agent):
    """
    Test the basic functionality of aggregate historian when aggregating a
    single topic
    1. Publish fake data
    2. Start aggregator agent with configurtion to collect sum of data in
    two different intervals.
    3. Sleep for 4 minutes
    4. Do an rpc call to historian to verify data

    Expected result:
    1. Aggregate data should be computed for both 2m and 3m intervals and
    for both the configured points.
    2. timestamp for both points within a single aggregation group should be
    time synchronized.

    @param volttron_instance: volttron instance on which test agents are
    installed and run
    @param aggregate_agent: the aggregate historian configuration
    @param publish_agent: fake agent used to publish to and query historian
    @param cleanup: clean up method that is called at the end of each test case
    """
    # Publish fake data.
    start_time = datetime.utcnow() - timedelta(minutes=2)
    publish_test_data(query_agent, start_time, 0, 10)
    gevent.sleep(0.5)
    agent_uuid = None
    try:
        aggregate_agent['aggregations'] = [
            {
                "aggregation_period": "1m",
                "use_calendar_time_periods": True,
                "points": [
                    {"topic_names": ["device1/out_temp"],
                     "aggregation_type": "sum", "min_count": 2},
                    {"topic_names": ["device1/in_temp"],
                     "aggregation_type": "sum", "min_count": 2}
                ]
            },
            {
                "aggregation_period": "2m",
                "use_calendar_time_periods": False,
                "points": [
                    {"topic_names": ["device1/out_temp"],
                     "aggregation_type": "sum", "min_count": 2},
                    {"topic_names": ["device1/in_temp"],
                     "aggregation_type": "sum", "min_count": 2}
                ]
            }
        ]
        agent_uuid = volttron_instance.install_agent(
            agent_dir=aggregate_agent["source_agg_historian"],
            config_file=aggregate_agent,
            start=True)
        print("agent id: ", agent_uuid)
        gevent.sleep(140)  # sleep till we see two rows in aggregate table

        result1 = query_agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic='device1/out_temp',
            agg_type='sum',
            agg_period='1m',
            count=20,
            order="FIRST_TO_LAST").get(timeout=100)

        print("result1: {}".format(result1))

        result2 = query_agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic='device1/in_temp',
            agg_type='sum',
            agg_period='1m',
            count=20,
            order="FIRST_TO_LAST").get(timeout=100)

        print("result2: {}".format(result2))

        # point1 and point2 configured within the same aggregation group should
        # be time synchronized
        assert (result2['values'][0][0] == result1['values'][0][0])
        assert (result2['values'][1][0] == result1['values'][1][0])

        # Now verify the computed sum
        expected_sum = get_expected_sum(query_agent,
                                        'device1/in_temp',
                                        result2['values'][0][0], 1)
        assert (result1['values'][0][1] == expected_sum)
        assert (result2['values'][0][1] == expected_sum)

        expected_sum = get_expected_sum(query_agent,
                                        'device1/in_temp',
                                        result2['values'][1][0], 1)
        assert (result1['values'][1][1] == expected_sum)
        assert (result2['values'][1][1] == expected_sum)

        result1 = query_agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic='device1/in_temp',
            agg_type='sum',
            agg_period='2m',
            count=20,
            order="FIRST_TO_LAST").get(timeout=100)

        result2 = query_agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic='device1/out_temp',
            agg_type='sum',
            agg_period='2m',
            count=20,
            order="FIRST_TO_LAST").get(timeout=100)

        # point1 and point2 configured within the same aggregation group should
        # be time synchronized
        assert (result2['values'][0][0] == result1['values'][0][0])
        assert (result2['values'][1][0] == result1['values'][1][0])

        # Now verify the computed sum
        expected_sum = get_expected_sum(query_agent, 'device1/in_temp',
                                        result2['values'][0][0], 2)
        assert (result1['values'][0][1] == expected_sum)
        assert (result2['values'][0][1] == expected_sum)

        expected_sum = get_expected_sum(query_agent, 'device1/in_temp',
                                        result2['values'][1][0], 2)
        assert (result1['values'][1][1] == expected_sum)
        assert (result2['values'][1][1] == expected_sum)


    finally:
        cleanup(aggregate_agent['connection']['type'], ['sum_1m', 'sum_2m'])
        if agent_uuid is not None:
            volttron_instance.remove_agent(agent_uuid)


@pytest.mark.aggregator
def test_multiple_topic_pattern(request, volttron_instance, aggregate_agent,
                                query_agent):
    """
    Test aggregate historian when aggregating across multiple topics
    that are identified by topic_name_pattern instead of explicit topic name
    1. Publish fake data
    2. Start aggregator agent with configurtion to collect sum of data in
    two different intervals.
    3. Sleep for 1 minute
    4. Do an rpc call to historian to verify data

    Expected result:
    1. Aggregate data should be computed for both 2m for the two configured
    points.
    2. timestamp for both points within a single aggregation group should be
    time synchronized

    @param volttron_instance: volttron instance on which test agents are
    installed and run
    @param aggregate_agent: the aggregate historian configuration
    @param  query_agent: fake agent used to query historian
    @param clean: clean up method that is called at the end of each test case
    """

    # Publish fake data.
    start_time = datetime.utcnow() - timedelta(minutes=1)
    publish_test_data(query_agent, start_time, 0, 5)
    gevent.sleep(0.5)
    agent_uuid = None
    try:

        aggregate_agent['aggregations'] = [
            {"aggregation_period": "1m",
             "use_calendar_time_periods": True,
             "points": [
                 {
                     "topic_name_pattern": "device1/*",
                     "aggregation_topic_name": "device1/all",
                     "aggregation_type": "sum",
                     "min_count": 2
                 }
             ]
             }
        ]

        agent_uuid = volttron_instance.install_agent(
            agent_dir=aggregate_agent["source_agg_historian"],
            config_file=aggregate_agent,
            start=True)
        result1 = query_agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic='device1/all',
            agg_type='sum',
            agg_period='1m',
            count=20,
            order="FIRST_TO_LAST").get(timeout=100)

        print(result1)

        # Now verify the computed sum
        expected_sum = get_expected_sum(query_agent,
                                        ['device1/in_temp',
                                         'device1/out_temp'],
                                        result1['values'][0][0], 1)
        assert (result1['values'][0][1] == expected_sum)

    finally:
        cleanup(aggregate_agent['connection']['type'], ['sum_1m'])
        if agent_uuid is not None:
            volttron_instance.remove_agent(agent_uuid)


@pytest.mark.aggregator
def test_multiple_topic_list(request, volttron_instance, aggregate_agent,
                             query_agent):
    """
    Test aggregate historian when aggregating across multiple topics
    that are identified by explicit list of topic names
    1. Publish fake data
    2. Start aggregator agent with configurtion to collect sum of data in
    two different intervals.
    3. Sleep for 1 minute
    4. Do an rpc call to historian to verify data

    Expected result:
    1. Aggregate data should be computed for both 2m for the two configured
    points.
    2. timestamp for both points within a single aggregation group should be
    time synchronized

    @param volttron_instance: volttron instance on which test agents are
    installed and run
    @param aggregate_agent: the aggregate historian configuration
    @param query_agent: fake agent used to query historian
    @param clean: clean up method that is called at the end of each test case
    """

    # Publish fake data.
    start_time = datetime.utcnow() - timedelta(minutes=2)
    publish_test_data(query_agent, start_time, 0, 5)
    gevent.sleep(0.5)
    agent_uuid = None
    try:

        aggregate_agent['aggregations'] = [
            {"aggregation_period": "1m",
             "use_calendar_time_periods": True,
             "points": [
                 {
                     "topic_names": ["device1/out_temp", "device1/in_temp"],
                     "aggregation_topic_name": "device1/all",
                     "aggregation_type": "sum",
                     "min_count": 2
                 }
             ]
             }
        ]

        agent_uuid = volttron_instance.install_agent(
            agent_dir=aggregate_agent["source_agg_historian"],
            config_file=aggregate_agent,
            start=True)

        result1 = query_agent.vip.rpc.call('platform.historian',
                                           'query',
                                           topic='device1/all',
                                           agg_type='sum',
                                           agg_period='1m',
                                           count=20,
                                           order="FIRST_TO_LAST").get(
            timeout=100)

        print(result1)
        # Now verify the computed sum
        expected_sum = get_expected_sum(query_agent,
                                        ['device1/in_temp',
                                         'device1/out_temp'],
                                        result1['values'][0][0], 1)
        assert (result1['values'][0][1] == expected_sum)


    finally:
        cleanup(aggregate_agent['connection']['type'], ['sum_1m'])
        if agent_uuid is not None:
            volttron_instance.remove_agent(agent_uuid)
