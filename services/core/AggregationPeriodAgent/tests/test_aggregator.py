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
from volttron.platform.jsonrpc import RemoteError
from volttron.platform.agent import PublishMixin
from volttron.platform.vip.agent import Agent

try:
    import mysql.connector as mysql

    HAS_MYSQL_CONNECTOR = True
except:
    HAS_MYSQL_CONNECTOR = False


# table_defs with prefix
sqlite_platform = {
    "agentid": "sqlhistorian-sqlite-3",
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
    },
    "aggregation_period": "2m",
    "aggregate_details":[
        {
        "topic_name": "device1/out_temp",
        "aggregation_type": "average",
        "min_count": 2
        },
        {
        "topic_name": "device1/in_temp",
        "aggregation_type": "average",
        "min_count": 2
        }
    ]
}

# Create a database "historian", create user "historian" with passwd
# "historian" and grant historian user access to "historian" database

# table_defs with prefix
mysql_platform = {
    "agentid": "sqlhistorian-mysql-3",
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
    },
    "aggregation_period": "2m",
    "aggregate_details":[
        {
        "topic_name": "device1/out_temp",
        "aggregation_type": "average",
        "min_count": 2
        },
        {
        "topic_name": "device1/in_temp",
        "aggregation_type": "average",
        "min_count": 2
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
def publish_agent(request, volttron_instance):
    # 1: Start a fake agent to publish to message bus
    print("**In setup of publish_agent volttron is_running {}".format(
        volttron_instance.is_running))
    agent = volttron_instance.build_agent()

    # 2: add a tear down method to stop sqlhistorian agent and the fake
    # agent that published to message bus
    def stop_agent():
        print("In teardown method of publish_agent")
        agent.core.stop()

    request.addfinalizer(stop_agent)
    return agent

# Fixtures for setup and teardown of sqlhistorian agent and aggregation agent
@pytest.fixture(scope="module",
                params=[
                    # pytest.mark.skipif(
                    #     not HAS_MYSQL_CONNECTOR,
                    #     reason='No mysql client available.')(mysql_platform),
                    sqlite_platform
                ])
def aggregate_agent(request, volttron_instance):
    global db_connection, data_table, \
        topics_table, meta_table
    print("** Setting up test_sqlhistorian module **")
    # Make database connection
    agent_uuid = volttron_instance.install_agent(
        agent_dir="services/core/AggregationPeriodAgent",
        config_file=request.param,
        start=True)
    print("agent id: ", agent_uuid)

    print("request param", request.param)
    if request.param['connection']['type'] == 'sqlite':
        request.param['connection']['params']['database'] = \
            volttron_instance.volttron_home + "/historian.sqlite"


    # figure out db table names from config
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


    # 3: add a tear down method to stop sqlhistorian agent and the fake
    # agent that published to message bus
    def stop_agent():
        print("In teardown method of sqlagent")
        if db_connection:
            db_connection.close()
            print("closed connection to db")
        if volttron_instance.is_running():
            volttron_instance.stop_agent(agent_uuid)

    request.addfinalizer(stop_agent)
    return agent_uuid


def connect_mysql(request):
    global db_connection, MICROSECOND_SUPPORT, data_table, \
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
    cursor.execute("DELETE FROM " + data_table)
    cursor.execute("DELETE FROM " + topics_table)
    cursor.execute("INSERT INTO TOPICS VALUES(1,'device1/out_temp')")
    cursor.execute("INSERT INTO TOPICS VALUES(2,'device1/in_temp')")
    db_connection.commit()


def connect_sqlite(request):
    global db_connection, MICROSECOND_SUPPORT
    database_path = request.param['connection']['params']['database']
    print "connecting to sqlite path " + database_path
    db_connection = sqlite3.connect(database_path)
    print "successfully connected to sqlite"
    MICROSECOND_SUPPORT = True
    cursor = db_connection.cursor()
    cursor.execute("DELETE FROM " + data_table)
    cursor.execute("DELETE FROM " + topics_table)
    cursor.execute("INSERT INTO TOPICS VALUES(1,'device1/out_temp')")
    cursor.execute("INSERT INTO TOPICS VALUES(2,'device1/in_temp')")
    db_connection.commit()

#
# @pytest.fixture()
# def clean(request):
#     def delete_rows():
#         global db_connection, data_table
#         cursor = db_connection.cursor()
#         cursor.execute("DELETE FROM " + data_table)
#         db_connection.commit()
#         print("deleted test records from " + data_table)
#
#     request.addfinalizer(delete_rows)

# def assert_timestamp(result, expected_date, expected_time):
#     global MICROSECOND_SUPPORT
#     print("MICROSECOND SUPPORT ", MICROSECOND_SUPPORT)
#     print("TIMESTAMP with microseconds ", expected_time)
#     print("TIMESTAMP without microseconds ", expected_time[:-7])
#     if MICROSECOND_SUPPORT:
#         assert (result == expected_date + 'T' + expected_time + '+00:00')
#     else:
#         # mysql version < 5.6.4
#         assert (result == expected_date + 'T' + expected_time[:-7] +
#                 '.000000+00:00')

def publish_test_data(start_time, start_reading, count):
    global db_connection, data_table
    cursor = db_connection.cursor()

    for i in range(0, count):
        reading = start_reading + i
        cursor.execute("INSERT INTO "+ data_table + " VALUES (1, "
                       + reading + ")" )
        cursor.execute("INSERT INTO " + data_table + " VALUES (2, "
                       + reading + ")")
    cursor.commit()

@pytest.mark.dev
def test_basic_function(aggregate_agent,volttron_instance):
    """

    @param aggregate_agent:
    @return:
    """
    global query_points, db_connection
    # print('HOME', volttron_instance1.volttron_home)


    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random.uniform(30, 100)
    damper_reading = random.uniform(0, 100)


    # Create timestamp
    start_time = datetime.utcnow() - timedelta(seconds=3)
    start_reading = random.uniform(30, 100)
    publish_test_data(start_time, start_reading, 3)
    volttron_instance.start_agent(aggregate_agent)
    # assert (len(result['values']) == 1)
    # (now_date, now_time) = now.split(" ")
    # assert_timestamp(result['values'][0][0], now_date, now_time)
    # assert (result['values'][0][1] == damper_reading)
    # assert set(result['metadata'].items()) == set(percent_meta.items())

