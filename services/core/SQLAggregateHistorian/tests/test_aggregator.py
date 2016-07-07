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
    },
    "tables_def": {
        "table_prefix": "prefix",
        "data_table": "data_table",
        "topics_table": "topics_table",
        "meta_table": "meta_table"
    },
    "aggregations": [
        {"aggregation_period": "2m",
         "use_calendar_time_periods": True,
         "points": [
             {
                 "topic_name": "device1/out_temp",
                 "aggregation_type": "sum",
                 "min_count": 2
             },
             {
                 "topic_name": "device1/in_temp",
                 "aggregation_type": "sum",
                 "min_count": 2
             }
         ]
         },
        {"aggregation_period": "3m",
         "use_calendar_time_periods": False,
         "points": [
             {
                 "topic_name": "device1/out_temp",
                 "aggregation_type": "sum",
                 "min_count": 2
             },
             {
                 "topic_name": "device1/in_temp",
                 "aggregation_type": "sum",
                 "min_count": 2
             }
         ]
         }
    ]
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
    },
    "tables_def": {
        "table_prefix": "prefix",
        "data_table": "data_table",
        "topics_table": "topics_table",
        "meta_table": "meta_table",
    },
    "aggregations": [
        {"aggregation_period": "2m",
         "use_calendar_time_periods": False,
         "points": [
             {
                 "topic_name": "device1/out_temp",
                 "aggregation_type": "sum",
                 "min_count": 2
             },
             {
                 "topic_name": "device1/in_temp",
                 "aggregation_type": "sum",
                 "min_count": 2
             }
         ]
         },
        {"aggregation_period": "3m",
         "use_calendar_time_periods": False,
         "points": [
             {
                 "topic_name": "device1/out_temp",
                 "aggregation_type": "sum",
                 "min_count": 2
             },
             {
                 "topic_name": "device1/in_temp",
                 "aggregation_type": "sum",
                 "min_count": 2
             }
         ]
         }
    ]
}

offset = timedelta(seconds=3)
db_connection = None
MICROSECOND_SUPPORT = True

# Don't like declaring this global but I am not able to find a way
# to introspect this using pytest request object in the clean fixture
data_table = 'data'
topics_table = 'topics'
meta_table = 'meta'


@pytest.fixture(scope="module")
def query_agent(request, volttron_instance):
    # 1: Start a fake agent to query the sqlhistorian in volttron_instance2
    agent = volttron_instance.build_agent()

    # 2: add a tear down method to stop sqlhistorian agent and the fake
    # agent that published to message bus
    def stop_agent():
        print("In teardown method of query_agent")
        agent.core.stop()

    request.addfinalizer(stop_agent)
    return agent


# Fixtures for setup and teardown of sqlhistorian agent and aggregation agent
@pytest.fixture(scope="module",
                params=[
                    pytest.mark.skipif(
                        not HAS_MYSQL_CONNECTOR,
                        reason='No mysql client available.')(mysql_aggregator),
                    sqlite_aggregator
                ])
def aggregate_agent(request, volttron_instance):
    global db_connection, data_table, \
        topics_table, meta_table
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
    # each test method. Create tables and insert test topics in topics table
    if request.param['connection']['type'] == "sqlite":
        connect_sqlite(request)
    elif request.param['connection']['type'] == "mysql":
        connect_mysql(request)
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
    config['tables_def'] = request.param['tables_def']

    sql_historian_uuid = volttron_instance.install_agent(
        agent_dir="services/core/SQLHistorian",
        config_file=config,
        start=True)
    print("agent id: ", sql_historian_uuid)

    agent_uuid = volttron_instance.install_agent(
        agent_dir="services/core/SQLAggregateHistorian",
        config_file=request.param,
        start=False)
    print("agent id: ", agent_uuid)

    # 3: add a tear down method to stop sqlhistorian agent and the fake
    # agent that published to message bus
    def stop_agent():
        print("In teardown method of aggregate agent")
        if db_connection:
            db_connection.close()
            print("closed connection to db")
        if volttron_instance.is_running():
            volttron_instance.remove_agent(agent_uuid)
            volttron_instance.remove_agent(sql_historian_uuid)

    request.addfinalizer(stop_agent)
    return agent_uuid


def connect_mysql(request):
    global db_connection, MICROSECOND_SUPPORT, data_table, \
        topics_table, meta_table
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
    db_connection.commit()
    print("created mysql tables")
    # clean up any rows from older runs
    cursor = db_connection.cursor()
    cursor.execute("DELETE FROM " + data_table)
    cursor.execute("DELETE FROM " + topics_table)
    cursor.execute("INSERT INTO " + topics_table +
                   " VALUES(1,'device1/out_temp')")
    cursor.execute("INSERT INTO " + topics_table +
                   " VALUES(2,'device1/in_temp')")
    db_connection.commit()


def connect_sqlite(request):
    global db_connection, MICROSECOND_SUPPORT
    database_path = request.param['connection']['params']['database']
    print ("connecting to sqlite path " + database_path)
    db_connection = sqlite3.connect(database_path)
    print ("successfully connected to sqlite")
    MICROSECOND_SUPPORT = True
    cursor = db_connection.cursor()
    cursor.execute(
        'CREATE TABLE IF NOT EXISTS ' + data_table +
        ' (ts timestamp NOT NULL,\
         topic_id INTEGER NOT NULL, \
         value_string TEXT NOT NULL, \
         UNIQUE(ts, topic_id))')

    cursor.execute(
        'CREATE TABLE IF NOT EXISTS ' + topics_table +
        ' (topic_id INTEGER PRIMARY KEY, \
         topic_name TEXT NOT NULL, \
         UNIQUE(topic_name))')

    cursor.execute(
        'CREATE TABLE IF NOT EXISTS ' + meta_table +
        '(topic_id INTEGER PRIMARY KEY, \
          metadata TEXT NOT NULL);'
    )
    cursor.execute("INSERT INTO " + topics_table +
                   " VALUES(1,'device1/out_temp')")
    cursor.execute("INSERT INTO " + topics_table +
                   " VALUES(2,'device1/in_temp')")
    db_connection.commit()


def publish_test_data(start_time, start_reading, count):
    global db_connection, data_table
    cursor = db_connection.cursor()
    reading = start_reading
    time = start_time
    print ("publishing test data starttime is {} utcnow is {}".format(
        start_time, datetime.utcnow()))
    print ("publishing test data value string {} at {}".format(reading,
                                                               datetime.now()))
    insert_stmt = "INSERT INTO " + data_table + " VALUES (%s, %s, %s)"
    if isinstance(db_connection, sqlite3.Connection):
        insert_stmt = "INSERT INTO " + data_table + " VALUES (?, ?, ?)"
    for i in range(0, count):
        cursor.execute(insert_stmt, (time, 1, reading))
        cursor.execute(insert_stmt, (time, 2, reading))
        reading += 1
        time = time + timedelta(minutes=1)

    db_connection.commit()


@pytest.mark.aggregator
def test_basic_function(volttron_instance, aggregate_agent, query_agent):
    """
    Test the basic functionality of mongo historian.
    1. Publish fake data
    2. Start aggregator agent with configurtion to collect sum of data in
    two different intervals.
    3. Sleep for 4 minutes
    4. Do an rpc call to historian to verify data
    @param volttron_instance: volttron instance on which test agents are
    installed and run
    @param aggregate_agent: the aggregate historian being test
    @param query_agent: fake agent used to publish and query historian
    """
    global db_connection

    # Publish fake data.
    start_time = datetime.utcnow() - timedelta(minutes=2)
    publish_test_data(start_time, 0, 5)
    gevent.sleep(0.5)
    cursor = db_connection.cursor()
    if HAS_MYSQL_CONNECTOR and isinstance(db_connection, \
                                          mysql.connection.MySQLConnection):
        cursor.execute("DELETE FROM sum_2m")
        cursor.execute("DELETE FROM sum_3m")
        db_connection.commit()
    volttron_instance.start_agent(aggregate_agent)
    # gevent.sleep(2)
    gevent.sleep(5 * 60)  # sleep till we see two rows in aggregate table

    result = query_agent.vip.rpc.call('platform.historian',
                                      'query',
                                      topic='device1/out_temp',
                                      agg_type='sum',
                                      agg_period='2m',
                                      count=20,
                                      order="FIRST_TO_LAST").get(timeout=100)

    print(result)
    assert (result['values'][0][1] == 3.0)
    assert (result['values'][1][1] == 7.0)

    result = query_agent.vip.rpc.call('platform.historian',
                                      'query',
                                      topic='device1/in_temp',
                                      agg_type='sum',
                                      agg_period='2m',
                                      count=20,
                                      order="FIRST_TO_LAST").get(timeout=100)
    assert (result['values'][0][1] == 3.0)
    assert (result['values'][1][1] == 7.0)

    result = query_agent.vip.rpc.call('platform.historian',
                                      'query',
                                      topic='device1/in_temp',
                                      agg_type='sum',
                                      agg_period='3m',
                                      count=20,
                                      order="FIRST_TO_LAST").get(timeout=100)
    assert (result['values'][0][1] == 3.0)
    assert (result['values'][1][1] == 7.0)

    result = query_agent.vip.rpc.call('platform.historian',
                                      'query',
                                      topic='device1/out_temp',
                                      agg_type='sum',
                                      agg_period='3m',
                                      count=20,
                                      order="FIRST_TO_LAST").get(timeout=100)

    assert (result['values'][0][1] == 3.0)
    assert (result['values'][1][1] == 7.0)
