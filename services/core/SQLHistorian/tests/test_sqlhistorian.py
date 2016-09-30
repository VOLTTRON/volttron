# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

# }}}
'''
pytest test cases for SQLHistorian
For mysql test's to succeed
 1. MySql server should be running
 2. test database and test user should exist
 3. Test user should have all privileges on test database
 4. Refer to the dictionary object mysql_platform for the server configuration
'''
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
    "agentid": "sqlhistorian-sqlite-1",
    "connection": {
        "type": "sqlite",
        "params": {
            "database": 'test.sqlite'
        }
    }
}
# table_defs without prefix
sqlite_platform2 = {
    "agentid": "sqlhistorian-sqlite-2",
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
    "agentid": "sqlhistorian-sqlite-3",
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
    "agentid": "sqlhistorian-mysql-1",
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
    "agentid": "sqlhistorian-mysql-2",
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
    "agentid": "sqlhistorian-mysql-3",
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
identity = None

# Don't like declaring this global but I am not able to find a way
# to introspect this using pytest request object in the clean fixture
data_table = 'data'
topics_table = 'topics'
meta_table = 'meta'


@pytest.fixture(scope="module",
                params=['volttron_2', 'volttron_3'])
def publish_agent(request, volttron_instance):
    # 1: Start a fake agent to publish to message bus
    print("**In setup of publish_agent volttron is_running {}".format(
        volttron_instance.is_running))
    agent = None
    if request.param == 'volttron_2':
        if agent is None or not isinstance(PublishMixin, agent):
            agent = PublishMixin(
                volttron_instance.opts['publish_address'])
    else:
        if agent is None or isinstance(PublishMixin, agent):
            agent = volttron_instance.build_agent()

    # 2: add a tear down method to stop sqlhistorian agent and the fake
    # agent that published to message bus
    def stop_agent():
        print("In teardown method of publish_agent")
        if isinstance(agent, Agent):
            agent.core.stop()

    request.addfinalizer(stop_agent)
    return agent


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


# Fixtures for setup and teardown of sqlhistorian agent
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
def sqlhistorian(request, volttron_instance, query_agent):
    global db_connection, data_table, \
        topics_table, meta_table, identity
    
    print("** Setting up test_sqlhistorian module **")
    # Make database connection
    print("request param", request.param)
    if request.param['connection']['type'] == 'sqlite':
        request.param['connection']['params']['database'] = \
            volttron_instance.volttron_home + "/historian.sqlite"

    # 1: Install historian agent
    # Install and start sqlhistorian agent
    agent_uuid = volttron_instance.install_agent(
        agent_dir="services/core/SQLHistorian",
        config_file=request.param,
        start=True,
        vip_identity='platform.historian')
    print("agent id: ", agent_uuid)
    identity = query_agent.vip.rpc.call(
            'control', 'agent_vip_identity',
            agent_uuid).get(timeout=2)

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

    # 3: add a tear down method to stop sqlhistorian agent and the fake
    # agent that published to message bus
    def stop_agent():
        print("In teardown method of sqlagent")
        if db_connection:
            db_connection.close()
            print("closed connection to db")
        if volttron_instance.is_running():
            volttron_instance.stop_agent(agent_uuid)
        volttron_instance.remove_agent(agent_uuid)
    request.addfinalizer(stop_agent)
    return request.param['agentid']



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
    cursor.execute("DELETE FROM data")
    cursor.execute("DELETE FROM volttron_table_definitions")
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


def publish(publish_agent, topic, header, message):
    if isinstance(publish_agent, Agent):
        publish_agent.vip.pubsub.publish('pubsub',
                                         topic,
                                         headers=header,
                                         message=message).get(timeout=10)
    else:
        publish_agent.publish_json(topic, header, message)


def assert_timestamp(result, expected_date, expected_time):
    global MICROSECOND_SUPPORT
    print("MICROSECOND SUPPORT ", MICROSECOND_SUPPORT)
    print("TIMESTAMP with microseconds ", expected_time)
    print("TIMESTAMP without microseconds ", expected_time[:-7])
    if MICROSECOND_SUPPORT:
        assert (result == expected_date + 'T' + expected_time + '+00:00')
    else:
        # mysql version < 5.6.4
        assert (result == expected_date + 'T' + expected_time[:-7] +
                '.000000+00:00')


def skip_custom_tables(sqlhistorian):
    print ("agent id is *{}*".format(sqlhistorian))
    if not sqlhistorian.endswith("-1"):
        print "agent id ends with something other than -1"
        pytest.skip(msg="Need not repeat all test cases for custom table "
                        "names")

@pytest.mark.sqlhistorian
@pytest.mark.historian
def test_basic_function(request, sqlhistorian, publish_agent, query_agent,
                        clean):
    """
    Test basic functionality of sql historian. Inserts three points as part
    of all topic and checks if all three got into the database
    Expected result:
    Should be able to query data based on topic name. Result should contain
    both data and metadata
    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param sqlhistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    global query_points, ALL_TOPIC, db_connection
    

    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_basic_function for {}**".format(
        request.keywords.node.name))

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
    publish(publish_agent, ALL_TOPIC, headers, all_message)

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

@pytest.mark.sqlhistorian
@pytest.mark.historian
def test_exact_timestamp(request, sqlhistorian, publish_agent, query_agent,
                         clean):
    """
    Test query based on same start and end time with literal 'Z' at the end
    of utc time.
    Expected result: record with timestamp == start time

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param sqlhistorian: instance of the sql historian tested
    :param clean: teardown function
    """

    # skip if this test case need not repeated for this specific sqlhistorian
    skip_custom_tables(sqlhistorian)

    global query_points, ALL_TOPIC

    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_exact_timestamp for for {}**".format(
        request.keywords.node.name))
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random.uniform(30, 100)
    mixed_reading = oat_reading + random.uniform(-5, 5)

    # Create a message for all points.
    all_message = [{'MixedAirTemperature': mixed_reading},
                   {'MixedAirTemperature': {'units': 'F', 'tz': 'UTC',
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
    publish(publish_agent, ALL_TOPIC, headers, all_message)

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
    if now_time[-1:] == 'Z':
        now_time = now_time[:-1]
    assert_timestamp(result['values'][0][0], now_date, now_time)
    assert (result['values'][0][1] == mixed_reading)


@pytest.mark.sqlhistorian
@pytest.mark.historian
def test_exact_timestamp_with_z(request, sqlhistorian, publish_agent,
                                query_agent,
                                clean):
    """
    Test query based on same start and end time with literal 'Z' at the end
    of utc time.
    Expected result: record with timestamp == start time

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param sqlhistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    # skip if this test case need not repeated for this specific sqlhistorian
    skip_custom_tables(sqlhistorian)

    global query_points, ALL_TOPIC
    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_exact_timestamp_with_z for {}**".format(
        request.keywords.node.name))
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random.uniform(30, 100)
    mixed_reading = oat_reading + random.uniform(-5, 5)

    # Create a message for all points.
    all_message = [{'MixedAirTemperature': mixed_reading},
                   {'MixedAirTemperature': {'units': 'F', 'tz': 'UTC',
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
    publish(publish_agent, ALL_TOPIC, headers, all_message)

    gevent.sleep(0.5)

    # pytest.set_trace()
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
    if now_time[-1:] == 'Z':
        now_time = now_time[:-1]
    assert_timestamp(result['values'][0][0], now_date, now_time)
    assert (result['values'][0][1] == mixed_reading)

@pytest.mark.sqlhistorian
@pytest.mark.historian
def test_query_start_time(request, sqlhistorian, publish_agent, query_agent,
                          clean):
    """
    Test query based on start_time alone. Expected result record with
    timestamp>= start_time

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param sqlhistorian: instance of the sql historian tested
    :param clean: teardown function
    """

    # skip if this test case need not repeated for this specific sqlhistorian
    skip_custom_tables(sqlhistorian)

    global query_points, ALL_TOPIC
    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_query_start_time for {}**".format(
        request.keywords.node.name))
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random.uniform(30, 100)

    # Create a message for all points.
    all_message = [{'OutsideAirTemperature': oat_reading},
                   {'OutsideAirTemperature': {'units': 'F', 'tz': 'UTC',
                                              'type': 'float'}
                    }]

    # Publish messages twice
    time1 = datetime.utcnow().isoformat(' ')
    headers = {
        headers_mod.DATE: time1
    }
    publish(publish_agent, ALL_TOPIC, headers, all_message)
    gevent.sleep(0.5)
    time2 = datetime.utcnow() + offset
    time2 = time2.isoformat(' ')
    headers = {
        headers_mod.DATE: time2
    }
    publish(publish_agent, ALL_TOPIC, headers, all_message)

    gevent.sleep(0.5)
    # pytest.set_trace()
    # pytest.set_trace()
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
    (time2_date, time2_time) = time2.split(" ")
    if time2_time[-1:] == 'Z':
        time2_time = time2_time[:-1]
    # Verify order LAST_TO_FIRST.
    assert_timestamp(result['values'][0][0], time2_date, time2_time)
    assert (result['values'][0][1] == oat_reading)


@pytest.mark.sqlhistorian
@pytest.mark.historian
def test_query_start_time_with_z(request, sqlhistorian, publish_agent,
                                 query_agent,
                                 clean):
    """
    Test query based on start_time alone. Expected result record with
    timestamp>= start_time

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param sqlhistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    # skip if this test case need not repeated for this specific sqlhistorian
    skip_custom_tables(sqlhistorian)

    global query_points, ALL_TOPIC
    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_query_start_time_with_z for {}**".format(
        request.keywords.node.name))
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random.uniform(30, 100)

    # Create a message for all points.
    all_message = [{'OutsideAirTemperature': oat_reading},
                   {'OutsideAirTemperature': {'units': 'F', 'tz': 'UTC',
                                              'type': 'float'}
                    }]

    # Publish messages twice
    time1 = datetime.utcnow().isoformat(' ') + 'Z'
    headers = {
        headers_mod.DATE: time1
    }
    publish(publish_agent, ALL_TOPIC, headers, all_message)
    gevent.sleep(0.5)

    time2 = utils.format_timestamp(datetime.utcnow() + offset)
    print ('time2', time2)
    headers = {
        headers_mod.DATE: time2
    }
    publish(publish_agent, ALL_TOPIC, headers, all_message)
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
    assert_timestamp(result['values'][0][0], time2_date, time2_time)
    assert (result['values'][0][1] == oat_reading)


@pytest.mark.sqlhistorian
@pytest.mark.historian
def test_query_end_time(request, sqlhistorian, publish_agent, query_agent,
                        clean):
    """
    Test query based on end time alone. Expected result record with
    timestamp<= end time

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param sqlhistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    # skip if this test case need not repeated for this specific sqlhistorian
    skip_custom_tables(sqlhistorian)

    global query_points, ALL_TOPIC, db_connection
    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_query_end_time for {}**".format(
        request.keywords.node.name))

    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random.uniform(30, 100)
    mixed_reading = oat_reading + random.uniform(-5, 5)

    # Create a message for all points.
    all_message = [{'MixedAirTemperature': mixed_reading},
                   {'MixedAirTemperature': {'units': 'F', 'tz': 'UTC',
                                            'type': 'float'}
                    }]

    # Publish messages twice
    time1 = datetime.utcnow().isoformat(' ')
    headers = {
        headers_mod.DATE: time1
    }
    publish(publish_agent, ALL_TOPIC, headers, all_message)
    gevent.sleep(0.5)

    time2 = datetime.utcnow() + offset
    time2 = time2.isoformat(' ')
    headers = {
        headers_mod.DATE: time2
    }
    publish(publish_agent, ALL_TOPIC, headers, all_message)

    gevent.sleep(0.5)

    # pytest.set_trace()
    # Query the historian
    result = query_agent.vip.rpc.call(identity,
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

@pytest.mark.sqlhistorian
@pytest.mark.historian
def test_query_end_time_with_z(request, sqlhistorian, publish_agent,
                               query_agent,
                               clean):
    """
    Test query based on end time alone. Expected result record with
    timestamp<= end time

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param sqlhistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    # skip if this test case need not repeated for this specific sqlhistorian
    skip_custom_tables(sqlhistorian)

    global query_points, ALL_TOPIC
    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_query_end_time_with_z for {}**".format(
        request.keywords.node.name))
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random.uniform(30, 100)
    mixed_reading = oat_reading + random.uniform(-5, 5)

    # Create a message for all points.
    all_message = [{'MixedAirTemperature': mixed_reading},
                   {'MixedAirTemperature': {'units': 'F', 'tz': 'UTC',
                                            'type': 'float'}
                    }]

    # Publish messages twice
    time1 = datetime.utcnow().isoformat(' ') + 'Z'
    headers = {
        headers_mod.DATE: time1
    }
    publish(publish_agent, ALL_TOPIC, headers, all_message)
    gevent.sleep(0.5)

    time2 = datetime.utcnow() + offset
    time2 = time2.isoformat(' ') + 'Z'
    headers = {
        headers_mod.DATE: time2
    }
    publish(publish_agent, ALL_TOPIC, headers, all_message)
    gevent.sleep(0.5)

    # pytest.set_trace()
    # Query the historian
    result = query_agent.vip.rpc.call(identity,
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


@pytest.mark.sqlhistorian
@pytest.mark.historian
def test_zero_timestamp(request, sqlhistorian, publish_agent, query_agent,
                        clean):
    """
    Test query based with timestamp where time is 00:00:00. Test with and
    without Z at the end.
    Expected result: record with timestamp == 00:00:00.000001

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param sqlhistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    # skip if this test case need not repeated for this specific sqlhistorian
    skip_custom_tables(sqlhistorian)

    global query_points, ALL_TOPIC
    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_zero_timestamp for {}**".format(
        request.keywords.node.name))
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random.uniform(30, 100)
    mixed_reading = oat_reading + random.uniform(-5, 5)

    # Create a message for all points.
    all_message = [{'MixedAirTemperature': mixed_reading},
                   {'MixedAirTemperature': {'units': 'F', 'tz': 'UTC',
                                            'type': 'float'}
                    }]

    # Create timestamp
    now = '2015-12-17 00:00:00.000000Z'
    headers = {
        headers_mod.DATE: now
    }

    # Publish messages
    publish(publish_agent, ALL_TOPIC, headers, all_message)
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
    assert (result['values'][0][1] == mixed_reading)

    # Create timestamp
    now = '2015-12-17 00:00:00.000000'
    headers = {
        headers_mod.DATE: now
    }

    # Publish messages
    publish(publish_agent, ALL_TOPIC, headers, all_message)
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
    assert (result['values'][0][1] == mixed_reading)


@pytest.mark.sqlhistorian
@pytest.mark.historian
def test_topic_name_case_change(request, sqlhistorian, publish_agent,
                                query_agent,
                                clean):
    """
    When case of a topic name changes check if they are saved as two topics
    Expected result: query result should be cases sensitive

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param sqlhistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    # skip if this test case need not repeated for this specific sqlhistorian
    skip_custom_tables(sqlhistorian)

    global query_points, ALL_TOPIC, db_connection
    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_topic_name_case_change for {}**".format(
        request.keywords.node.name))
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
    publish(publish_agent, ALL_TOPIC, headers, all_message)
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
    publish(publish_agent, ALL_TOPIC, headers, all_message)
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


@pytest.mark.sqlhistorian
@pytest.mark.historian
def test_invalid_query(request, sqlhistorian, publish_agent, query_agent,
                       clean):
    """
    Test query with invalid input

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param sqlhistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    # skip if this test case need not repeated for this specific sqlhistorian
    skip_custom_tables(sqlhistorian)

    global query_points, ALL_TOPIC
    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_invalid_query for {}**".format(
        request.keywords.node.name))
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random.uniform(30, 100)
    mixed_reading = oat_reading + random.uniform(-5, 5)

    # Create a message for all points.
    all_message = [{'MixedAirTemperature': mixed_reading},
                   {'MixedAirTemperature': {'units': 'F', 'tz': 'UTC',
                                            'type': 'float'}
                    }]

    # Create timestamp
    now = datetime.utcnow().isoformat(' ') + 'Z'
    headers = {
        headers_mod.DATE: now
    }

    # Publish messages
    publish(publish_agent, ALL_TOPIC, headers, all_message)

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


@pytest.mark.sqlhistorian
@pytest.mark.historian
def test_invalid_time(request, sqlhistorian, publish_agent, query_agent,
                      clean):
    """
    Test query with invalid input

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param sqlhistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    # skip if this test case need not repeated for this specific sqlhistorian
    skip_custom_tables(sqlhistorian)

    global query_points, ALL_TOPIC
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
        assert 'hour must be in 0..23' == error.message


@pytest.mark.sqlhistorian
@pytest.mark.historian
def test_analysis_topic(request, sqlhistorian, publish_agent, query_agent,
                        clean):
    """
    Test query based on same start and end time with literal 'Z' at the end
    of utc time.
    Expected result: record with timestamp == start time

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0 agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param sqlhistorian: instance of the sqlhistorian tested
    :param clean: teardown function
    """
    # skip if this test case need not repeated for this specific sqlhistorian
    skip_custom_tables(sqlhistorian)

    global query_points
    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_analysis_topic for {}**".format(
        request.keywords.node.name))
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
    publish(publish_agent, 'analysis/Building/LAB/Device',
            headers, all_message)
    gevent.sleep(0.5)
    abc = dict(peer=identity, method='query',
                                      topic=query_points['mixed_point'],
                                      start=now,
                                      end=now,
                                      count=20,
                                      order="LAST_TO_FIRST")
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
    if now_time[-1:] == 'Z':
        now_time = now_time[:-1]
    assert_timestamp(result['values'][0][0], now_date, now_time)
    assert (result['values'][0][1] == mixed_reading)


@pytest.mark.sqlhistorian
@pytest.mark.historian
def test_record_topic_query(request, sqlhistorian, publish_agent, query_agent,
                            clean):
    """
    Test query based on same start with literal 'Z' at the end of utc time.
    Cannot query based on exact time as timestamp recorded is time of insert
    publish and query record topic

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param sqlhistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    # skip if this test case need not repeated for this specific sqlhistorian
    skip_custom_tables(sqlhistorian)

    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_exact_timestamp for {}**".format(
        request.keywords.node.name))
    # Publish int data

    # Create timestamp
    now = datetime.utcnow().isoformat() + 'Z'
    print("now is ", now)

    # Publish messages
    publish(publish_agent, topics.RECORD, None, 1)
    # sleep 1 second so that records gets inserted with unique timestamp
    # even in case of older mysql
    gevent.sleep(1)

    publish(publish_agent, topics.RECORD, None, 'value0')
    # sleep 1 second so that records gets inserted with unique timestamp
    # even in case of older mysql
    gevent.sleep(1)

    publish(publish_agent, topics.RECORD, None, {'key': 'value'})
    gevent.sleep(0.5)

    # pytest.set_trace()
    # Query the historian
    result = query_agent.vip.rpc.call(identity,
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


@pytest.mark.sqlhistorian
@pytest.mark.historian
def test_log_topic(request, sqlhistorian, publish_agent, query_agent, clean):
    """
    Test publishing to log topic with header and no timestamp in message
    Expected result:
     Record should get entered into database with current time at time of
     insertion and should ignore timestamp in header

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param sqlhistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    # skip if this test case need not repeated for this specific sqlhistorian
    skip_custom_tables(sqlhistorian)

    global query_points
    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_log_topic for {}**".format(request.keywords.node.name))
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random.uniform(30, 100)
    mixed_reading = oat_reading + random.uniform(-5, 5)

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


@pytest.mark.sqlhistorian
@pytest.mark.historian
def test_log_topic_no_header(request, sqlhistorian, publish_agent, query_agent,
                             clean):
    """
    Test publishing to log topic without any header and no timestamp in message
    Expected result:
     Record should get entered into database with current time at time of
     insertion and should not complain about header

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param sqlhistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    # skip if this test case need not repeated for this specific sqlhistorian
    skip_custom_tables(sqlhistorian)

    global query_points
    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_log_topic for {}**".format(request.keywords.node.name))
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random.uniform(30, 100)
    mixed_reading = oat_reading + random.uniform(-5, 5)

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


@pytest.mark.sqlhistorian
@pytest.mark.historian
def test_log_topic_timestamped_readings(request, sqlhistorian, publish_agent,
                                        query_agent, clean):
    """
    Test publishing to log topic with explicit timestamp in message.
    Expected result:
     Record should get entered into database with the timestamp in
     message and not timestamp in header

    :param request: pytest request object
    :param publish_agent: instance of volttron 2.0/3.0agent used to publish
    :param query_agent: instance of fake volttron 3.0 agent used to query
    using rpc
    :param sqlhistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    # skip if this test case need not repeated for this specific sqlhistorian
    skip_custom_tables(sqlhistorian)

    global query_points
    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_log_topic for {}**".format(request.keywords.node.name))
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random.uniform(30, 100)
    mixed_reading = oat_reading + random.uniform(-5, 5)

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
        end='2015-12-02T00:00:00',
        order="LAST_TO_FIRST").get(timeout=10)
    print('Query Result', result)
    assert (len(result['values']) == 1)
    assert (result['values'][0][1] == mixed_reading)
    assert_timestamp(result['values'][0][0], '2015-12-02', '00:00:00.000000')

@pytest.mark.sqlhistorian
@pytest.mark.historian
def test_get_topic_metadata(request, sqlhistorian, publish_agent,
                            query_agent, clean):
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
    :param sqlhistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    # skip if this test case need not repeated for this specific sqlhistorian
    skip_custom_tables(sqlhistorian)

    global query_points
    # print('HOME', volttron_instance.volttron_home)
    print(
    "\n** test_get_topic_metadata for {}**".format(request.keywords.node.name))
    # Publish fake data. The format mimics the format used by VOLTTRON drivers.
    # Make some random readings
    oat_reading = random.uniform(30, 100)
    mixed_reading = oat_reading + random.uniform(-5, 5)

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
    assert result['datalogger/Building/LAB/Device/temp1'] ==\
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

    try:
        query_agent.vip.rpc.call(
            identity,
            'get_topics_metadata',
            topics=123
        ).get(timeout=10)

    except RemoteError as e:
        assert e.message == "Please provide a valid topic name string " \
                            "or a list of topic names. Invalid input 123"




