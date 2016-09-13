# pytest test cases for SQLHistorian
# For mysql test's to succeed
# 1. MySql server should be running
# 2. test database and test user should exist
# 3. Test user should have all privileges on test database
# 4. Refer to the dictionary object mysql_platform for the server configuration
import re
import sqlite3
from datetime import datetime, timedelta

import gevent
import pytest
from dateutil.parser import parse
from volttron.platform.messaging import headers as headers_mod

try:
    import pymongo

    HAS_PYMONGO = True
except:
    HAS_PYMONGO = False

pymongo_skipif = pytest.mark.skipif(not HAS_PYMONGO,
                                    reason='No pymongo client available.')

mongo_aggregator = {
    "source_historian": "services/core/MongodbHistorian",
    "source_agg_historian": "services/core/MongodbAggregateHistorian",
    "connection": {
        "type": "mongodb",
        "params": {
            "host": "vc-db1.pnl.gov",
            "port": 27017,
            "database": "historian_dev2",
            "user": "hdev",
            "passwd": ""
        }
    }
}

offset = timedelta(seconds=3)
db_connection = None
table_names = dict()
connection_type = None


def setup_mongodb(connection_params, table_names):
    print ("setup mongodb")
    mongo_conn_str = 'mongodb://{user}:{passwd}@{host}:{port}/{database}'
    params = connection_params
    mongo_conn_str = mongo_conn_str.format(**params)
    mongo_client = pymongo.MongoClient(mongo_conn_str)
    print ("Got mongo client")
    db = mongo_client[connection_params['database']]
    print ("Got mongo default db")
    # db[table_names['data_table']].remove()
    # db[table_names['topics_table']].remove()
    # db[table_names['meta_table']].remove()
    db[table_names['agg_topics_table']].remove()
    db[table_names['agg_meta_table']].remove()
    print ("Done setup mongodb")
    return db


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
    #truncate_tables.append(table_names['data_table'])
    truncate_tables.append(table_names['agg_topics_table'])
    truncate_tables.append(table_names['agg_meta_table'])
    cleanup_function = globals()["cleanup_" + connection_type]
    cleanup_function(db_connection, truncate_tables)

@pytest.mark.timeout(180)
@pytest.mark.dev
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
    1. Aggregate data should be computed correctly after restart as well.
    2. Aggregate topics should be get updated instead of inserting a new record
    3. aggregate topic should be based on user provided
    aggregation_topic_name even though the second time around we are
    aggregating for a single topic

    @param volttron_instance: volttron instance on which test agents are
    installed and run
    @param aggregate_agent: the aggregate historian configuration
    @param query_agent: fake agent used to query historian
    @param clean: clean up method that is called at the end of each test case
    """

    agent_uuid = None
    try:

        aggregate_agent['aggregations'] = [
            {"aggregation_period": "3m",
             "use_calendar_time_periods": True,
             "points": [
                 {
                     # ZoneTemperature
                     "topic_name_pattern":
                         "PNNL/SEB/AHU3/VAV112/ZoneTemperature$",
                     "aggregation_topic_name":
                         "PNNL/SEB/AHU3/VAV112/zonetemp_aggregate",
                     "aggregation_type": "sum",
                     "min_count": 2
                 },
                 {
                     # PNNL/SEB/AHU3/VAV112/ZoneAirFlow
                     "topic_name_pattern":
                         "PNNL/SEB/AHU3/VAV112/ZoneAirFlow$",
                     "aggregation_topic_name":
                         "PNNL/SEB/AHU3/VAV112/zone_air_flow_agg",
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

        result1 = query_agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic='PNNL/SEB/AHU3/VAV112/zonetemp_aggregate',
            agg_type='sum',
            agg_period="3m",
            count=20,
            order="FIRST_TO_LAST").get(timeout=10)

        print(result1)
        assert (result1['metadata']) == {}

        result2 = query_agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic='PNNL/SEB/AHU3/VAV112/zone_air_flow_agg',
            agg_type='sum',
            agg_period="3m",
            count=20,
            order="FIRST_TO_LAST").get(timeout=10)

        # point1 and point2 configured within the same aggregation group should
        # be time synchronized
        assert (result2['values'][0][0] == result1['values'][0][0])
        # Now verify the computed sum
        expected_sum = get_expected_sum(
            query_agent,
            'PNNL/SEB/AHU3/VAV112/ZoneTemperature',
            result1['values'][0][0], 3)
        assert (result1['values'][0][1] == expected_sum)

        expected_sum = get_expected_sum(
            query_agent,
            'PNNL/SEB/AHU3/VAV112/ZoneAirFlow',
            result1['values'][0][0], 3)
        assert (result2['values'][0][1] == expected_sum)
        assert (result2['metadata']) == {}

        # Query if both the aggregate topics have been recorded into db
        result = query_agent.vip.rpc.call('platform.historian',
                                          'get_aggregate_topics').get(10)
        print("agg topic list {}".format(result))

        # Expected result
        expected_list = [
            ['PNNL/SEB/AHU3/VAV112/zonetemp_aggregate', 'sum', "3m",
             'PNNL/SEB/AHU3/VAV112/ZoneTemperature$'],
            ['PNNL/SEB/AHU3/VAV112/zone_air_flow_agg', 'sum', "3m",
             'PNNL/SEB/AHU3/VAV112/ZoneAirFlow$']]
        assert len(result) == 2
        for row in result:
            expected_list.remove(row)

        assert len(expected_list) == 0


    finally:
        cleanup(aggregate_agent['connection']['type'], ['sum_3m'])
        if agent_uuid is not None:
            volttron_instance.remove_agent(agent_uuid)


@pytest.mark.timeout(180)
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
    1. Aggregate data should be computed for both 5m and 3m intervals and
    for both the configured points.
    2. timestamp for both points within a single aggregation group should be
    time synchronized.

    @param volttron_instance: volttron instance on which test agents are
    installed and run
    @param aggregate_agent: the aggregate historian configuration
    @param publish_agent: fake agent used to publish to and query historian
    @param cleanup: clean up method that is called at the end of each test case
    """

    agent_uuid = None
    try:
        aggregate_agent['aggregations'] = [
            {
                "aggregation_period": "3m",
                "use_calendar_time_periods": True,
                "points": [
                    {"topic_names": ["PNNL/SEB/AHU3/VAV112/ZoneTemperature"],
                     "aggregation_type": "sum", "min_count": 2},
                    {"topic_names": [
                        "PNNL/SEB/AHU3/VAV112/ZoneAirFlow"],
                     "aggregation_type": "sum", "min_count": 2}
                ]
            },
            {
                "aggregation_period": "5m",
                "use_calendar_time_periods": False,
                "points": [
                    {"topic_names": ["PNNL/SEB/AHU3/VAV112/ZoneTemperature"],
                     "aggregation_type": "sum", "min_count": 2},
                    {"topic_names": [
                        "PNNL/SEB/AHU3/VAV112/ZoneAirFlow"],
                     "aggregation_type": "sum", "min_count": 2}
                ]
            }
        ]
        agent_uuid = volttron_instance.install_agent(
            agent_dir=aggregate_agent["source_agg_historian"],
            config_file=aggregate_agent,
            start=True)
        print("agent id: ", agent_uuid)
        print("time before sleep {}".format(datetime.utcnow()))
        gevent.sleep(5.5 * 60)  # sleep till we see two rows in aggregate table

        result1 = query_agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic='PNNL/SEB/AHU3/VAV112/ZoneTemperature',
            agg_type='sum',
            agg_period="3m",
            count=20,
            order="FIRST_TO_LAST").get(timeout=100)

        print("result1: {}".format(result1))

        result2 = query_agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic='PNNL/SEB/AHU3/VAV112/ZoneAirFlow',
            agg_type='sum',
            agg_period="3m",
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

        assert (result1['metadata']) == {"units": "degreesFahrenheit",
                                         "type": "integer",
                                         "tz": "US/Pacific"}
        assert (result2['metadata']) == {"units": "cubicFeetPerMinute",
                                         "type": "integer",
                                         "tz": "US/Pacific"}

        # Now verify the computed sum
        expected_sum = get_expected_sum(query_agent,
                                        'PNNL/SEB/AHU3/VAV112/ZoneTemperature',
                                        result1['values'][0][0], 3)
        assert (result1['values'][0][1] == expected_sum)

        expected_sum = get_expected_sum(query_agent,
                                        'PNNL/SEB/AHU3/VAV112/ZoneAirFlow',
                                        result2['values'][0][0], 3)
        assert (result2['values'][0][1] == expected_sum)

        # Query 5 min aggregation
        result1 = query_agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic='PNNL/SEB/AHU3/VAV112/ZoneAirFlow',
            agg_type='sum',
            agg_period='5m',
            count=20,
            order="FIRST_TO_LAST").get(timeout=100)

        result2 = query_agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic='PNNL/SEB/AHU3/VAV112/ZoneTemperature',
            agg_type='sum',
            agg_period='5m',
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
        expected_sum = get_expected_sum(query_agent,
                                        'PNNL/SEB/AHU3/VAV112/ZoneTemperature',
                                        result1['values'][0][0], 5)
        assert (result1['values'][0][1] == expected_sum)


        expected_sum = get_expected_sum(query_agent,
                                        'PNNL/SEB/AHU3/VAV112/ZoneAirFlow',
                                        result2['values'][1][0], 5)
        assert (result2['values'][1][1] == expected_sum)

        # Since the aggregate is on a single topic, metadata of the topic
        # should
        # be returned correctly
        assert (result1['metadata']) == {"units": "degreesFahrenheit",
                                         "type": "integer",
                                         "tz": "US/Pacific"}
        assert (result2['metadata']) == {"units": "cubicFeetPerMinute",
                                         "type": "integer",
                                         "tz": "US/Pacific"}

        # Query if all four aggregate topics have been recorded into db
        result = query_agent.vip.rpc.call('platform.historian',
                                          'get_aggregate_topics').get(10)
        print("agg topic list {}".format(result))

        assert len(result) == 4
        # Expected result
        expected_list = [
            ['PNNL/SEB/AHU3/VAV112/ZoneAirFlow', 'sum', "3m",
             'PNNL/SEB/AHU3/VAV112/ZoneAirFlow'],
            ['PNNL/SEB/AHU3/VAV112/ZoneTemperature', 'sum', "3m",
             ['PNNL/SEB/AHU3/VAV112/ZoneTemperature']],
            ['PNNL/SEB/AHU3/VAV112/ZoneAirFlow', 'sum', '5m',
             ['PNNL/SEB/AHU3/VAV112/ZoneAirFlow']],
            ['PNNL/SEB/AHU3/VAV112/ZoneTemperature', 'sum', '5m',
             ['PNNL/SEB/AHU3/VAV112/ZoneTemperature']]]
        for row in result:
            assert [row[0]] == row[3]
            assert row[1] == 'sum'
            assert row[2] == "3m" or row[2] == '5m'

    finally:
        cleanup(aggregate_agent['connection']['type'], ['sum_3m', 'sum_5m'])
        if agent_uuid is not None:
            volttron_instance.remove_agent(agent_uuid)


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
    1. Aggregate data should be computed for both 5m for the two configured
    points.
    2. timestamp for both points within a single aggregation group should be
    time synchronized

    @param volttron_instance: volttron instance on which test agents are
    installed and run
    @param aggregate_agent: the aggregate historian configuration
    @param  query_agent: fake agent used to query historian
    @param clean: clean up method that is called at the end of each test case
    """

    agent_uuid = None
    try:

        aggregate_agent['aggregations'] = [
            {"aggregation_period": "3m",
             "use_calendar_time_periods": True,
             "points": [
                 {
                     # ZoneTemperature and ZoneDischargeAirTemperature
                     "topic_name_pattern":
                         "PNNL/SEB/AHU3/VAV112/Zone.*Temperature$",
                     "aggregation_topic_name":
                         "PNNL/SEB/AHU3/VAV112/zone_and_zone_discharge_temp",
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
            topic='PNNL/SEB/AHU3/VAV112/zone_and_zone_discharge_temp',
            agg_type='sum',
            agg_period="3m",
            count=20,
            order="FIRST_TO_LAST").get(timeout=100)

        print(result1)

        # Now verify the computed sum
        expected_sum = get_expected_sum(
            query_agent,
            ['PNNL/SEB/AHU3/VAV112/ZoneDischargeAirTemperature',
                'PNNL/SEB/AHU3/VAV112/ZoneTemperature'],
            result1['values'][0][0], 3)
        assert (result1['values'][0][1] == expected_sum)

        assert (result1['metadata']) == {}

        # Query if all four aggregate topics have been recorded into db
        result = query_agent.vip.rpc.call('platform.historian',
                                          'get_aggregate_topics').get(10)
        print("agg topic list {}".format(result))

        assert len(result) == 1
        # Expected result
        assert result[0][0] == \
               'PNNL/SEB/AHU3/VAV112/zone_and_zone_discharge_temp'
        assert result[0][1] == 'sum'
        assert result[0][2] == "3m"
        assert result[0][3] == 'PNNL/SEB/AHU3/VAV112/Zone.*Temperature$'


    finally:
        cleanup(aggregate_agent['connection']['type'], ['sum_3m'])
        if agent_uuid is not None:
            volttron_instance.remove_agent(agent_uuid)


@pytest.mark.aggregator
def test_multiple_topic_list(request, volttron_instance, aggregate_agent,
                             query_agent):
    """
    Test aggregate historian when aggregating across multiple topics
    that are identified by explicit list of topic names
    1. Publish fake data
    2. Start aggregator agent with configuration to collect sum of data in
    two different intervals.
    3. Sleep for 1 minute
    4. Do an rpc call to historian to verify data

    @param volttron_instance: volttron instance on which test agents are
    installed and run
    @param aggregate_agent: the aggregate historian configuration
    @param query_agent: fake agent used to query historian
    @param clean: clean up method that is called at the end of each test case
    """

    agent_uuid = None
    try:

        aggregate_agent['aggregations'] = [
            {"aggregation_period": "3m",
             "use_calendar_time_periods": True,
             "points": [
                 {
                     "topic_names": ["PNNL/SEB/AHU3/VAV112/ZoneTemperature",
                                     "PNNL/SEB/AHU3/VAV112/ZoneDischargeAirTemperature"],
                     "aggregation_topic_name":
                         "PNNL/SEB/AHU3/VAV112/multi_list",
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
                                           topic='PNNL/SEB/AHU3/VAV112/multi_list',
                                           agg_type='sum',
                                           agg_period="3m",
                                           count=20,
                                           order="FIRST_TO_LAST").get(
            timeout=100)

        print(result1)
        # Now verify the computed sum
        expected_sum = get_expected_sum(query_agent,
                                        [
                                            'PNNL/SEB/AHU3/VAV112/ZoneDischargeAirTemperature',
                                            'PNNL/SEB/AHU3/VAV112/ZoneTemperature'],
                                        result1['values'][0][0], 3)
        assert (result1['values'][0][1] == expected_sum)

        assert (result1['metadata']) == {}

        # Query if all four aggregate topics have been recorded into db
        result = query_agent.vip.rpc.call('platform.historian',
                                          'get_aggregate_topics').get(10)
        print("agg topic list {}".format(result))

        assert len(result) == 1
        # Expected result
        assert result[0][0] == 'PNNL/SEB/AHU3/VAV112/multi_list'
        assert result[0][1] == 'sum'
        assert result[0][2] == "3m"
        assert set(result[0][3]) == set(
            ("PNNL/SEB/AHU3/VAV112/ZoneDischargeAirTemperature",
             "PNNL/SEB/AHU3/VAV112/ZoneTemperature"))
    finally:
        cleanup(aggregate_agent['connection']['type'], ['sum_3m'])
        if agent_uuid is not None:
            volttron_instance.remove_agent(agent_uuid)


@pytest.mark.aggregator
def test_topic_reconfiguration(request, volttron_instance, aggregate_agent,
                               query_agent):
    """
    Test aggregate historian when topic names/topic pattern is updated and
    restarted. Check if aggregate topic list gets updated correctly and doesn't
    cause any issue with historian
    1. Publish fake data
    2. Start aggregator agent with configuration to collect sum of data in
    two different intervals.
    3. Sleep for 1 minute
    4. Do an rpc call to historian to verify data


    @param volttron_instance: volttron instance on which test agents are
    installed and run
    @param aggregate_agent: the aggregate historian configuration
    @param query_agent: fake agent used to query historian
    @param clean: clean up method that is called at the end of each test case
    """

    # Publish fake data.

    try:

        agent_uuid = None
        aggregate_agent['aggregations'] = [
            {"aggregation_period": "3m",
             "use_calendar_time_periods": True,
             "points": [
                 {
                     "topic_names": ["PNNL/SEB/AHU3/VAV112/ZoneTemperature",
                                     "PNNL/SEB/AHU3/VAV112/ZoneDischargeAirTemperature"],
                     "aggregation_topic_name":
                         "PNNL/SEB/AHU3/VAV112/aggregation_name",
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
            topic='PNNL/SEB/AHU3/VAV112/aggregation_name',
            agg_type='sum',
            agg_period="3m",
            count=20,
            order="FIRST_TO_LAST").get(timeout=10)

        print(result1)
        # Now verify the computed sum
        expected_sum = get_expected_sum(query_agent,
                                        [
                                            'PNNL/SEB/AHU3/VAV112/ZoneDischargeAirTemperature',
                                            'PNNL/SEB/AHU3/VAV112/ZoneTemperature'],
                                        result1['values'][0][0], 3)
        assert (result1['values'][0][1] == expected_sum)

        assert (result1['metadata']) == {}

        # Query if all four aggregate topics have been recorded into db
        result = query_agent.vip.rpc.call('platform.historian',
                                          'get_aggregate_topics').get(10)
        print("agg topic list {}".format(result))

        assert len(result) == 1
        # Expected result
        assert result[0][0] == 'PNNL/SEB/AHU3/VAV112/aggregation_name'
        assert result[0][1] == 'sum'
        assert result[0][2] == "3m"
        assert set(result[0][3]) == set(
            ("PNNL/SEB/AHU3/VAV112/ZoneDischargeAirTemperature",
             "PNNL/SEB/AHU3/VAV112/ZoneTemperature"))
        volttron_instance.remove_agent(agent_uuid)

        # Restart after changing topic names list for the same aggregate topic
        agent_uuid = None
        # Update topic names
        aggregate_agent['aggregations'][0]["points"][0]["topic_names"] = \
            ["PNNL/SEB/AHU3/VAV112/ZoneTemperature"]
        print("Before reinstall current time is {}".format(datetime.utcnow()))

        agent_uuid = volttron_instance.install_agent(
            agent_dir=aggregate_agent["source_agg_historian"],
            config_file=aggregate_agent,
            start=True)

        print ("After reinstall\n\n")

        result1 = query_agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic='PNNL/SEB/AHU3/VAV112/aggregation_name',
            agg_type='sum',
            agg_period="3m",
            count=20,
            order="FIRST_TO_LAST").get(timeout=10)

        print(result1)
        lindex = len(result1) - 1
        expected_sum = get_expected_sum(query_agent,
                                        [
                                            'PNNL/SEB/AHU3/VAV112/ZoneTemperature'],
                                        result1['values'][lindex][0], 3)
        assert (result1['values'][lindex][1] == expected_sum)
        assert (result1['metadata']) == {}

        # Query if all four aggregate topics have been recorded into db
        result = query_agent.vip.rpc.call('platform.historian',
                                          'get_aggregate_topics').get(10)
        print("agg topic list {}".format(result))

        assert len(result) == 1
        # Expected result
        assert result[0][0] == 'PNNL/SEB/AHU3/VAV112/aggregation_name'
        assert result[0][1] == 'sum'
        assert result[0][2] == "3m"
        assert result[0][3] == ["PNNL/SEB/AHU3/VAV112/ZoneTemperature"]

    finally:
        cleanup(aggregate_agent['connection']['type'], ['sum_3m'])
        if agent_uuid is not None:
            volttron_instance.remove_agent(agent_uuid)
