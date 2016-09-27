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
import re
from dateutil.parser import parse
from volttron.platform.messaging import headers as headers_mod

AGG_AGENT_VIP = 'aggregate_agent'

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
    print("data_values between {} and {} is {}".format(
        start_time, end_time, data_values))
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
    except NameError:
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

    agg_agent_uuid = volttron_instance.install_agent(
        agent_dir=request.param["source_agg_historian"],
        config_file={},
        vip_identity=AGG_AGENT_VIP,
        start=True)

    # 3: add a tear down method to stop sqlhistorian agent and the fake
    # agent that published to message bus
    def stop_agent():
        print("In teardown method of aggregate agent")
        # if db_connection:
        #     db_connection.close()
        #     print("closed connection to db")
        if volttron_instance.is_running():
            volttron_instance.remove_agent(historian_uuid)
            volttron_instance.remove_agent(agg_agent_uuid)

    request.addfinalizer(stop_agent)
    return request.param


def cleanup(connection_type, truncate_tables):
    global db_connection, table_names
    truncate_tables.append(table_names['data_table'])
    truncate_tables.append(table_names['agg_topics_table'])
    truncate_tables.append(table_names['agg_meta_table'])
    cleanup_function = globals()["cleanup_" + connection_type]
    cleanup_function(db_connection, truncate_tables)


@pytest.mark.aggregator
def test_get_supported_aggregations(aggregate_agent, query_agent):
    """
    :param aggregate_agent: the aggregate historian configuration
    :param query_agent: fake agent used to query historian
    :return:
    """
    # aggregate_agent['aggregations'] = [
    #     {"aggregation_period": "1m",
    #      "use_calendar_time_periods": True,
    #      "points": [
    #          {
    #              "topic_name_pattern": "device1/out_.*",
    #              "aggregation_topic_name": "device1/outsidetemp_aggregate",
    #              "aggregation_type": "sum",
    #              "min_count": 2
    #          }
    #      ]
    #      }
    # ]
    query_agent.vip.rpc.call("config.store", "manage_store",
                             AGG_AGENT_VIP, "config",
                             aggregate_agent).get()

    result = query_agent.vip.rpc.call(
        AGG_AGENT_VIP,
        'get_supported_aggregations').get(timeout=10)


    assert result
    print result
    conn =  aggregate_agent.get("connection")
    if conn:
        if conn.get("type") == "mysql":
            assert result == ['AVG', 'MIN', 'MAX', 'COUNT', 'SUM', 'BIT_AND',
                              'BIT_OR','BIT_XOR', 'GROUP_CONCAT', 'STD',
                              'STDDEV', 'STDDEV_POP', 'STDDEV_SAMP',
                              'VAR_POP', 'VAR_SAMP', 'VARIANCE']
        elif conn.get("type") == "sqlite":
            assert result == ['AVG', 'MIN', 'MAX', 'COUNT', 'SUM', 'TOTAL',
                              'GROUP_CONCAT']
        elif conn.get("type") == "mongodb":
            assert result ==['SUM', 'COUNT', 'AVG', 'MIN', 'MAX',
                             'STDDEVPOP', 'STDDEVSAMP']




@pytest.mark.aggregator
def test_single_topic_pattern(aggregate_agent, query_agent):
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
    1. Aggregate data should be computed correctly after restart as well.
    2. Aggregate topics should be get updated instead of inserting a new record
    3. aggregate topic should be based on user provided
    aggregation_topic_name even though the second time around we are
    aggregating for a single topic

    :param aggregate_agent: the aggregate historian configuration
    :param query_agent: fake agent used to query historian
    """

    # Publish fake data.
    start_time = datetime.utcnow() - timedelta(minutes=2)
    publish_test_data(query_agent, start_time, 0, 10)
    gevent.sleep(0.5)
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
        query_agent.vip.rpc.call("config.store", "manage_store",
                                 AGG_AGENT_VIP, "config",
                                 aggregate_agent).get()

        result1 = query_agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic='device1/outsidetemp_aggregate',
            agg_type='sum',
            agg_period='1m',
            count=20,
            order="FIRST_TO_LAST").get(timeout=10)

        print(result1)
        assert (result1['metadata']) == {}

        result2 = query_agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic='device1/intemp_aggregate',
            agg_type='sum',
            agg_period='1m',
            count=20,
            order="FIRST_TO_LAST").get(timeout=10)

        # point1 and point2 configured within the same aggregation group should
        # be time synchronized
        assert (result2['values'][0][0] == result1['values'][0][0])
        # Now verify the computed sum
        expected_sum = get_expected_sum(query_agent,
                                        'device1/in_temp',
                                        result2['values'][0][0], 1)
        assert (result1['values'][0][1] == expected_sum)
        assert (result2['values'][0][1] == expected_sum)
        assert (result2['metadata']) == {}

        # Query if both the aggregate topics have been recorded into db
        result = query_agent.vip.rpc.call('platform.historian',
                                          'get_aggregate_topics').get(10)
        print("agg topic list {}".format(result))

        # Expected result
        expected_list = [
            ['device1/outsidetemp_aggregate', 'sum', '1m', 'device1/out_.*'],
            ['device1/intemp_aggregate', 'sum', '1m', 'device1/in_*']]
        assert len(result) == 2
        for row in result:
            expected_list.remove(row)

        assert len(expected_list) == 0
    finally:
        cleanup(aggregate_agent['connection']['type'], ['sum_1m'])


@pytest.mark.timeout(180)
@pytest.mark.aggregator
def test_single_topic(aggregate_agent, query_agent):
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

    :param aggregate_agent: the aggregate historian configuration
    :param query_agent: fake agent used to publish to and query historian
    """
    # Publish fake data.
    start_time = datetime.utcnow() - timedelta(minutes=2)
    publish_test_data(query_agent, start_time, 0, 30)
    gevent.sleep(0.5)
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
        query_agent.vip.rpc.call("config.store", "manage_store",
                                 AGG_AGENT_VIP, "config",
                                 aggregate_agent).get()
        gevent.sleep(2.5 * 60)  # sleep till we see two rows in aggregate table

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

        diff = compute_timediff_seconds(result2['values'][0][0],
                                        result2['values'][1][0])
        assert diff == 60

        assert (result1['metadata']) == (result2['metadata']) == \
            {'units': 'F', 'tz': 'UTC', 'type': 'float'}

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

        diff = compute_timediff_seconds(result2['values'][0][0],
                                        result2['values'][1][0])
        assert diff == 120

        # Now verify the computed sum
        expected_sum = get_expected_sum(query_agent, 'device1/in_temp',
                                        result2['values'][0][0], 2)
        assert (result1['values'][0][1] == expected_sum)
        assert (result2['values'][0][1] == expected_sum)

        expected_sum = get_expected_sum(query_agent, 'device1/in_temp',
                                        result2['values'][1][0], 2)
        assert (result1['values'][1][1] == expected_sum)
        assert (result2['values'][1][1] == expected_sum)

        # Since the aggregate is on a single topic, metadata of the topic
        # should
        # be returned correctly
        assert (result1['metadata']) == (result2['metadata']) == \
            {'units': 'F', 'tz': 'UTC', 'type': 'float'}

        # Query if all four aggregate topics have been recorded into db
        result = query_agent.vip.rpc.call('platform.historian',
                                          'get_aggregate_topics').get(10)
        print("agg topic list {}".format(result))

        assert len(result) == 4
        # Expected result
        expected_list = [['device1/in_temp', 'sum', '1m',
                          'device1/in_temp'],
                         ['device1/out_temp', 'sum', '1m',
                          ['device1/out_temp']],
                         ['device1/in_temp', 'sum', '2m', ['device1/in_temp']],
                         ['device1/out_temp', 'sum', '2m',
                          ['device1/out_temp']]]
        for row in result:
            assert [row[0]] == row[3]
            assert row[1] == 'sum'
            assert row[2] == '1m' or row[2] == '2m'

    finally:
        cleanup(aggregate_agent['connection']['type'], ['sum_1m', 'sum_2m'])


def compute_timediff_seconds(time1_str, time2_str):
    if re.match('\+[0-9][0-9]:[0-9][0-9]', time1_str[-6:]):
        time1_str = time1_str[:-6]
        time2_str = time2_str[:-6]
    datetime1 = datetime.strptime(time1_str,
                                  '%Y-%m-%dT%H:%M:%S.%f')
    datetime2 = datetime.strptime(time2_str,
                                  '%Y-%m-%dT%H:%M:%S.%f')
    print("time difference {}".format((datetime2 - datetime1)))
    diff = (datetime2 - datetime1).total_seconds()
    return diff


@pytest.mark.aggregator
def test_multiple_topic_pattern(aggregate_agent, query_agent):
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

    :param aggregate_agent: the aggregate historian configuration
    :param  query_agent: fake agent used to query historian
    """

    # Publish fake data.
    start_time = datetime.utcnow() - timedelta(minutes=2)
    publish_test_data(query_agent, start_time, 0, 10)
    gevent.sleep(0.5)
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

        query_agent.vip.rpc.call("config.store", "manage_store",
                                 AGG_AGENT_VIP, "config",
                                 aggregate_agent).get()

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

        assert (result1['metadata']) == {}

        # Query if all four aggregate topics have been recorded into db
        result = query_agent.vip.rpc.call('platform.historian',
                                          'get_aggregate_topics').get(10)
        print("agg topic list {}".format(result))

        assert len(result) == 1
        # Expected result
        assert result[0][0] == 'device1/all'
        assert result[0][1] == 'sum'
        assert result[0][2] == '1m'
        assert result[0][3] == 'device1/*'
    finally:
        cleanup(aggregate_agent['connection']['type'], ['sum_1m'])


@pytest.mark.aggregator
def test_multiple_topic_list(aggregate_agent, query_agent):
    """
    Test aggregate historian when aggregating across multiple topics
    that are identified by explicit list of topic names
    1. Publish fake data
    2. Start aggregator agent with configuration to collect sum of data in
    two different intervals.
    3. Sleep for 1 minute
    4. Do an rpc call to historian to verify data

    :param aggregate_agent: the aggregate historian configuration
    :param query_agent: fake agent used to query historian
    """

    # Publish fake data.
    start_time = datetime.utcnow() - timedelta(minutes=2)
    publish_test_data(query_agent, start_time, 0, 5)
    gevent.sleep(0.5)
    try:

        aggregate_agent['aggregations'] = [
            {"aggregation_period": "1m",
             "use_calendar_time_periods": True,
             "points": [
                 {
                     "topic_names": ["device1/out_temp", "device1/in_temp"],
                     "aggregation_topic_name": "device1/all2",
                     "aggregation_type": "sum",
                     "min_count": 2
                 }
             ]
             }
        ]

        query_agent.vip.rpc.call("config.store", "manage_store",
                                 AGG_AGENT_VIP, "config",
                                 aggregate_agent).get()

        result1 = query_agent.vip.rpc.call('platform.historian',
                                           'query',
                                           topic='device1/all2',
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

        assert (result1['metadata']) == {}

        # Query if all four aggregate topics have been recorded into db
        result = query_agent.vip.rpc.call('platform.historian',
                                          'get_aggregate_topics').get(10)
        print("agg topic list {}".format(result))

        assert len(result) == 1
        # Expected result
        assert result[0][0] == 'device1/all2'
        assert result[0][1] == 'sum'
        assert result[0][2] == '1m'
        assert set(result[0][3]) == {"device1/in_temp", "device1/out_temp"}
    finally:
        cleanup(aggregate_agent['connection']['type'], ['sum_1m'])


@pytest.mark.aggregator
def test_topic_reconfiguration(aggregate_agent, query_agent):
    """
    Test aggregate historian when topic names/topic pattern is updated and
    restarted. Check if aggregate topic list gets updated correctly and doesn't
    cause any issue with historian
    1. Publish fake data
    2. Start aggregator agent with configuration to collect sum of data in
    two different intervals.
    3. Sleep for 1 minute
    4. Do an rpc call to historian to verify data


    :param aggregate_agent: the aggregate historian configuration
    :param query_agent: fake agent used to query historian
    """

    # Publish fake data.

    try:
        start_time = datetime.utcnow() - timedelta(minutes=2)
        publish_test_data(query_agent, start_time, 0, 5)
        gevent.sleep(0.5)
        aggregate_agent['aggregations'] = [
            {"aggregation_period": "1m",
             "use_calendar_time_periods": True,
             "points": [
                 {
                     "topic_names": ["device1/out_temp", "device1/in_temp"],
                     "aggregation_topic_name": "device1/aggregation_name",
                     "aggregation_type": "sum",
                     "min_count": 2
                 }
             ]
             }
        ]

        query_agent.vip.rpc.call("config.store", "manage_store",
                                 AGG_AGENT_VIP, "config",
                                 aggregate_agent).get()

        result1 = query_agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic='device1/aggregation_name',
            agg_type='sum',
            agg_period='1m',
            count=20,
            order="FIRST_TO_LAST").get(timeout=10)

        print(result1)
        # Now verify the computed sum
        expected_sum = get_expected_sum(query_agent,
                                        ['device1/in_temp',
                                         'device1/out_temp'],
                                        result1['values'][0][0], 1)
        assert (result1['values'][0][1] == expected_sum)

        assert (result1['metadata']) == {}

        # Query if all four aggregate topics have been recorded into db
        result = query_agent.vip.rpc.call('platform.historian',
                                          'get_aggregate_topics').get(10)
        print("agg topic list {}".format(result))

        assert len(result) == 1
        # Expected result
        assert result[0][0] == 'device1/aggregation_name'
        assert result[0][1] == 'sum'
        assert result[0][2] == '1m'
        assert set(result[0][3]) == {"device1/in_temp", "device1/out_temp"}

        # Reconfigure changing topic names list for the same aggregate topic
        start_time = datetime.utcnow() - timedelta(minutes=1)
        publish_test_data(query_agent, start_time, 0, 5)

        # Update topic names
        aggregate_agent['aggregations'][0]["points"][0]["topic_names"] = \
            ["device1/out_temp"]
        print("Before reinstall current time is {}".format(datetime.utcnow()))

        query_agent.vip.rpc.call("config.store", "manage_store",
                                 AGG_AGENT_VIP, "config",
                                 aggregate_agent).get()

        print ("After configure\n\n")

        result1 = query_agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic='device1/aggregation_name',
            agg_type='sum',
            agg_period='1m',
            count=20,
            order="FIRST_TO_LAST").get(timeout=10)

        print("Result:{}".format(result1))
        lindex = len(result1['values']) - 1
        print("lindex = {}".format(lindex))
        expected_sum = get_expected_sum(query_agent,
                                        ['device1/out_temp'],
                                        result1['values'][lindex][0], 1)
        assert (result1['values'][lindex][1] == expected_sum)
        assert (result1['metadata']) == {}

        # Query if all four aggregate topics have been recorded into db
        result = query_agent.vip.rpc.call('platform.historian',
                                          'get_aggregate_topics').get(10)
        print("agg topic list {}".format(result))

        assert len(result) == 1
        # Expected result
        assert result[0][0] == 'device1/aggregation_name'
        assert result[0][1] == 'sum'
        assert result[0][2] == '1m'
        assert result[0][3] == ["device1/out_temp"]

    finally:
        cleanup(aggregate_agent['connection']['type'], ['sum_1m'])
