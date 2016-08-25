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
from volttron.platform.messaging import headers as headers_mod



try:
    import mysql.connector as mysql

    HAS_MYSQL_CONNECTOR = True
except:
    HAS_MYSQL_CONNECTOR = False


# table_defs with prefix
sqlite_aggregator = {
    "agentid": "aggregate-sqlite",
    "identity": "aggregate-hist-sqlite",
    "connection": {
        "type": "sqlite",
        "params": {
            "database": 'test.sqlite'
        }
    }
}

# Create a database "historian", create user "historian" with passwd
# "historian" and grant historian user access to "historian" database

# table_defs with prefix
mysql_aggregator = {
    "agentid": "aggregate-mysql",
    "identity": "aggregate-hist-mysql",
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

offset = timedelta(seconds=3)
db_connection = None
MICROSECOND_SUPPORT = True

# Don't like declaring this global but I am not able to find a way
# to introspect this using pytest request object in the clean fixture
truncate_tables = []


@pytest.fixture(scope="module")
def agent(request, volttron_instance):
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
                    pytest.mark.skipif(
                        not HAS_MYSQL_CONNECTOR,
                        reason='No mysql client available.')(
                    mysql_aggregator),
                    sqlite_aggregator
                ])
def aggregate_agent(request, volttron_instance):
    global db_connection, truncate_tables
    print("** Setting up test_sqlhistorian module **")

    # Fix sqlite db path
    print("request param", request.param)
    if request.param['connection']['type'] == 'sqlite':
        request.param['connection']['params']['database'] = \
            volttron_instance.volttron_home + "/historian.sqlite"

    # figure out db table names from config
    # Set this hear so that we can create these table after connecting to db
    if request.param.get('tables_def', None) is None:
        data_table = 'data'
        topics_table = 'topics'
        meta_table = 'meta'
        agg_topics_table = 'aggregate_topics'
        agg_meta_table = 'aggregate_meta'
    elif request.param['tables_def']['table_prefix']:
        data_table = request.param['tables_def']['table_prefix'] + "_" + \
            request.param['tables_def']['data_table']
        topics_table = request.param['tables_def']['table_prefix'] + "_" + \
            request.param['tables_def']['topics_table']
        meta_table = request.param['tables_def']['table_prefix'] + "_" + \
            request.param['tables_def']['meta_table']
        agg_topics_table = request.param['tables_def']['table_prefix'] + \
            "_" + \
            "aggregate_" + \
            request.param['tables_def']['topics_table']
        agg_meta_table = request.param['tables_def']['table_prefix'] + "_" + \
            "aggregate_" + \
            request.param['tables_def']['meta_table']
    else:
        data_table = request.param['tables_def']['data_table']
        topics_table = request.param['tables_def']['topics_table']
        meta_table = request.param['tables_def']['meta_table']
        agg_topics_table = "aggregate_" + \
            request.param['tables_def']['topics_table']
        agg_meta_table = "aggregate_" + \
            request.param['tables_def']['meta_table']

    truncate_tables.append(data_table)

    # 2: Open db connection that can be used for row deletes after
    # each test method. Create tables and insert test topics in topics table
    if request.param['connection']['type'] == "sqlite":
        connect_sqlite(request)
    elif request.param['connection']['type'] == "mysql":
        connect_mysql(request, data_table, topics_table, meta_table,
                      agg_topics_table, agg_meta_table)
    else:
        print("Invalid database type specified " + request.param['connection'][
            'type'])
        pytest.fail(msg="Invalid database type specified " +
                        request.param['connection']['type'])

    # 2. Install agents - sqlhistorian, sqlaggregatehistorian
    config = dict()
    config['agentid'] = 'sqlhistorian'
    config['identity'] = 'platform.historian'
    config['connection'] = request.param['connection']
    config['tables_def'] = request.param.get('tables_def', None)

    sql_historian_uuid = volttron_instance.install_agent(
        vip_identity='platform.historian',
        agent_dir="services/core/SQLHistorian",
        config_file=config,
        start=True)
    print("agent id: ", sql_historian_uuid)

    # 3: add a tear down method to stop sqlhistorian agent and the fake
    # agent that published to message bus
    def stop_agent():
        print("In teardown method of aggregate agent")
        if db_connection:
            db_connection.close()
            print("closed connection to db")
        if volttron_instance.is_running():
            volttron_instance.remove_agent(sql_historian_uuid)

    request.addfinalizer(stop_agent)
    return request.param


@pytest.fixture
def cleanup():
    global db_connection, truncate_tables
    cleanup_parameters = []
    cursor = db_connection.cursor()

    for table in truncate_tables:
        cursor.execute("DELETE FROM " + table)
    for table in cleanup_parameters:
        cursor.execute("DELETE FROM " + table)

    db_connection.commit()
    return cleanup_parameters


def connect_mysql(request, data_table, topics_table, meta_table,
                  agg_topics_table, agg_meta_table):
    global db_connection, MICROSECOND_SUPPORT, truncate_tables
    print ("connect to mysql")
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

    cursor.execute(
        'CREATE TABLE IF NOT EXISTS ' + agg_topics_table +
        ' (agg_topic_id INTEGER NOT NULL AUTO_INCREMENT, \
           agg_topic_name varchar(512) NOT NULL, \
           agg_type varchar(512) NOT NULL, \
           agg_time_period varchar(512) NOT NULL, \
           PRIMARY KEY (agg_topic_id), \
           UNIQUE(agg_topic_name, agg_type, agg_time_period));')

    cursor.execute(
        'CREATE TABLE IF NOT EXISTS ' + agg_meta_table +
        '(agg_topic_id INTEGER NOT NULL, \
          metadata TEXT NOT NULL, \
          PRIMARY KEY(agg_topic_id));')

    db_connection.commit()
    print("created mysql tables")
    # clean up any rows from older runs
    cursor = db_connection.cursor()
    cursor.execute("DELETE FROM " + data_table)
    cursor.execute("DELETE FROM " + topics_table)
    cursor.execute("DELETE FROM " + meta_table)
    cursor.execute("DELETE FROM " + agg_topics_table)
    cursor.execute("DELETE FROM " + agg_meta_table)
    db_connection.commit()


def connect_sqlite(request):
    global db_connection, MICROSECOND_SUPPORT
    database_path = request.param['connection']['params']['database']
    print ("connecting to sqlite path " + database_path)
    db_connection = sqlite3.connect(database_path)
    print ("successfully connected to sqlite")
    MICROSECOND_SUPPORT = True
    db_connection.commit()


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
        time = time + timedelta(minutes=1)



@pytest.mark.sql_aggregator
@pytest.mark.aggregator
def test_single_topic_pattern(volttron_instance, aggregate_agent,
                                    agent, cleanup):
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
    @param agent: fake agent used to query historian
    @param clean: clean up method that is called at the end of each test case
    """

    # Publish fake data.
    start_time = datetime.utcnow() - timedelta(minutes=2)
    publish_test_data(agent, start_time, 0, 5)
    gevent.sleep(0.5)
    agent_uuid = None
    try:

        aggregate_agent['aggregations'] = [
            {"aggregation_period": "2m",
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
            agent_dir="services/core/SQLAggregateHistorian",
            config_file=aggregate_agent,
            start=False)
        print("agent id: ", agent_uuid)
        volttron_instance.start_agent(agent_uuid)
        gevent.sleep(30)  # sleep till we see a row in aggregate table

        result1 = agent.vip.rpc.call('platform.historian',
                                     'query',
                                     topic='device1/outsidetemp_aggregate',
                                     agg_type='sum',
                                     agg_period='2m',
                                     count=20,
                                     order="FIRST_TO_LAST").get(timeout=100)

        print(result1)
        assert (result1['values'][0][1] == 3.0)
        # assert (result1['metadata']) == \
        #        {'units': 'F', 'tz': 'UTC', 'type': 'float'}

        result2 = agent.vip.rpc.call('platform.historian',
                                     'query',
                                     topic='device1/intemp_aggregate',
                                     agg_type='sum',
                                     agg_period='2m',
                                     count=20,
                                     order="FIRST_TO_LAST").get(timeout=100)
        assert (result2['values'][0][1] == 3.0)

        # point1 and point2 configured within the same aggregation group should
        # be time synchronized
        assert (result2['values'][0][0] == result1['values'][0][0])
    finally:
        cleanup.append("sum_2m")
        if agent_uuid is not None:
            volttron_instance.remove_agent(agent_uuid)

@pytest.mark.sql_aggregator
@pytest.mark.aggregator
def test_single_topic(volttron_instance, aggregate_agent,
                            agent, cleanup):
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
    publish_test_data(agent, start_time, 0, 5)
    gevent.sleep(0.5)
    agent_uuid = None
    try:
        aggregate_agent['aggregations'] =[
            {
                "aggregation_period": "2m",
                "use_calendar_time_periods": True,
                "points": [
                    {"topic_names": ["device1/out_temp"],
                        "aggregation_type": "sum", "min_count": 2},
                    {"topic_names": ["device1/in_temp"],
                        "aggregation_type": "sum", "min_count": 2}
                ]
            },
            {
                "aggregation_period": "3m",
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
            agent_dir="services/core/SQLAggregateHistorian",
            config_file=aggregate_agent,
            start=True)
        print("agent id: ", agent_uuid)
        gevent.sleep(5 * 60)  # sleep till we see two rows in aggregate table

        result1 = agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic='device1/out_temp',
            agg_type='sum',
            agg_period='2m',
            count=20,
            order="FIRST_TO_LAST").get(timeout=100)

        print(result1)
        assert (result1['values'][0][1] == 3.0)
        assert (result1['values'][1][1] == 7.0)

        result2 = agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic='device1/in_temp',
            agg_type='sum',
            agg_period='2m',
            count=20,
            order="FIRST_TO_LAST").get(timeout=100)
        assert (result2['values'][0][1] == 3.0)
        assert (result2['values'][1][1] == 7.0)

        # point1 and point2 configured within the same aggregation group should
        # be time synchronized
        assert (result2['values'][0][0] == result1['values'][0][0])
        assert (result2['values'][1][0] == result1['values'][1][0])

        result = agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic='device1/in_temp',
            agg_type='sum',
            agg_period='3m',
            count=20,
            order="FIRST_TO_LAST").get(timeout=100)
        assert (result['values'][0][1] == 3.0)
        assert (result['values'][1][1] == 7.0)

        result = agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic='device1/out_temp',
            agg_type='sum',
            agg_period='3m',
            count=20,
            order="FIRST_TO_LAST").get(timeout=100)

        assert (result['values'][0][1] == 3.0)
        assert (result['values'][1][1] == 7.0)
    finally:
        cleanup.append("sum_2m")
        cleanup.append("sum_3m")
        if agent_uuid is not None:
            volttron_instance.remove_agent(agent_uuid)

@pytest.mark.sql_aggregator
@pytest.mark.aggregator
def test_multiple_topic_pattern(volttron_instance, aggregate_agent,
                                    agent, cleanup):
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
    @param agent: fake agent used to query historian
    @param clean: clean up method that is called at the end of each test case
    """

    # Publish fake data.
    start_time = datetime.utcnow() - timedelta(minutes=2)
    publish_test_data(agent, start_time, 0, 5)
    gevent.sleep(0.5)
    agent_uuid = None
    try:

        aggregate_agent['aggregations'] = [
            {"aggregation_period": "2m",
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
            agent_dir="services/core/SQLAggregateHistorian",
            config_file=aggregate_agent,
            start=False)
        print("agent id: ", agent_uuid)
        volttron_instance.start_agent(agent_uuid)
        gevent.sleep(30)  # sleep till we see a row in aggregate table

        result1 = agent.vip.rpc.call('platform.historian',
                                     'query',
                                     topic='device1/all',
                                     agg_type='sum',
                                     agg_period='2m',
                                     count=20,
                                     order="FIRST_TO_LAST").get(timeout=100)

        print(result1)
        assert (result1['values'][0][1] == 6.0)
        # assert (result1['metadata']) == \
        #        {'units': 'F', 'tz': 'UTC', 'type': 'float'}

    finally:
        #cleanup.append("sum_2m")
        if agent_uuid is not None:
            volttron_instance.remove_agent(agent_uuid)


@pytest.mark.sql_aggregator
@pytest.mark.aggregator
def test_multiple_topic_list(volttron_instance, aggregate_agent,
                                    agent, cleanup):
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
    @param agent: fake agent used to query historian
    @param clean: clean up method that is called at the end of each test case
    """

    # Publish fake data.
    start_time = datetime.utcnow() - timedelta(minutes=2)
    publish_test_data(agent, start_time, 0, 5)
    gevent.sleep(0.5)
    agent_uuid = None
    try:

        aggregate_agent['aggregations'] = [
            {"aggregation_period": "2m",
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
            agent_dir="services/core/SQLAggregateHistorian",
            config_file=aggregate_agent,
            start=False)
        print("agent id: ", agent_uuid)
        volttron_instance.start_agent(agent_uuid)
        gevent.sleep(30)  # sleep till we see a row in aggregate table

        result1 = agent.vip.rpc.call('platform.historian',
                                     'query',
                                     topic='device1/all',
                                     agg_type='sum',
                                     agg_period='2m',
                                     count=20,
                                     order="FIRST_TO_LAST").get(timeout=100)

        print(result1)
        assert (result1['values'][0][1] == 6.0)
        # assert (result1['metadata']) == \
        #        {'units': 'F', 'tz': 'UTC', 'type': 'float'}

    finally:
        cleanup.append("sum_2m")
        if agent_uuid is not None:
            volttron_instance.remove_agent(agent_uuid)