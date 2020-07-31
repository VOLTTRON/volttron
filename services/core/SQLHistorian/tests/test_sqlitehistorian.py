# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
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
pytest test cases for SQLite Historian
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
from pytest import approx
import re
import pytz

from volttron.platform import get_volttron_root, get_services_core
from volttron.platform.agent import utils
from volttron.platform.jsonrpc import RemoteError
from volttron.platform.messaging import headers as headers_mod
from volttron.platform.messaging import topics
from volttron.platform.vip.agent import Agent

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
## NOTE - In the below configuration, source_historian' is added
## only for test case setup purposes. It is removed from config before
## using the configuration for installing the agent.

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


offset = timedelta(seconds=3)
db_connection = None
identity = None

# Don't like declaring this global but I am not able to find a way
# to introspect this using pytest request object in the clean fixture
data_table = 'data'
topics_table = 'topics'
meta_table = 'meta'



def setup_sqlite(connection_params, table_names):
    print ("setup sqlite")
    database_path = connection_params['database']
    print ("connecting to sqlite path " + database_path)
    db_connection = sqlite3.connect(database_path)
    print ("successfully connected to sqlite")
    db_connection.commit()
    return db_connection, 6


def cleanup_sql(db_connection, truncate_tables):
    cursor = db_connection.cursor()
    for table in truncate_tables:
        cursor.execute("DELETE FROM " + table)
    db_connection.commit()



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


@pytest.fixture(scope="module",
                params=['volttron_3'])
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
    # 1: Start a fake agent to query the historian agent in volttron_instance
    agent = volttron_instance.build_agent()

    # 2: add a tear down method to stop the fake
    # agent that published to message bus
    def stop_agent():
        print("In teardown method of query_agent")
        agent.core.stop()

    request.addfinalizer(stop_agent)
    return agent


# Fixtures for setup and teardown of historian agent
@pytest.fixture(scope="module")
def historian(request, volttron_instance, query_agent):
    global db_connection, table_names, \
        connection_type, identity

    print("** Setting up test_historian module **")
    # Make database connection
    sqlite_platform['connection']['params']['database'] = \
        volttron_instance.volttron_home + "/historian.sqlite"

    table_names = get_table_names(sqlite_platform)

    # 2: Open db connection that can be used for row deletes after
    # each test method. Create tables
    db_connection, MICROSECOND_PRECISION = \
            setup_sqlite(sqlite_platform['connection']['params'], table_names)

    print ("sqlite_platform -- {}".format(sqlite_platform))
    # 2. Install agent - historian
    temp_config = copy.copy(sqlite_platform)
    source = temp_config.pop('source_historian')
    historian_uuid = volttron_instance.install_agent(
        vip_identity='platform.historian',
        agent_dir=source,
        config_file=temp_config,
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

    return sqlite_platform


@pytest.fixture()
def clean(request):
    global db_connection, connection_type, table_names
    def delete_rows():
        cleanup_sql(db_connection, [table_names['data_table']])
    request.addfinalizer(delete_rows)


def publish(publish_agent, topic, header, message):
    if isinstance(publish_agent, Agent):
        publish_agent.vip.pubsub.publish('pubsub',
                                         topic,
                                         headers=header,
                                         message=message).get(timeout=10)
    else:
        publish_agent.publish_json(topic, header, message)


@pytest.mark.historian
def test_sqlite_timeout(request, historian, publish_agent, query_agent,
                        clean, volttron_instance):
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
    :param clean: teardown function
    """
    global query_points, DEVICES_ALL_TOPIC, db_connection

    # print('HOME', volttron_instance.volttron_home)
    print(
    "\n** test_sqlite_timeout for {}**".format(request.keywords.node.name))
    agent_uuid = None
    try:
        new_historian = copy.copy(historian)
        new_historian["connection"]["params"]["timeout"] = 15
        new_historian["tables_def"] = {"table_prefix": "timeout_param",
            "data_table": "data", "topics_table": "topics",
            "meta_table": "meta"}

        # 1: Install historian agent
        # Install and start historian agent
        source = new_historian.pop('source_historian')
        agent_uuid = volttron_instance.install_agent(agent_dir=source,
            config_file=new_historian, start=True,
            vip_identity='sqlite.historian')
        print("agent id: ", agent_uuid)


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
                        'DamperSignal': damper_reading},
                       {'OutsideAirTemperature': float_meta,
                        'DamperSignal': percent_meta
                        }]

        # Create timestamp
        now = utils.format_timestamp(datetime.utcnow())

        # now = '2015-12-02T00:00:00'
        headers = {
            headers_mod.DATE: now,
            headers_mod.TIMESTAMP: now
        }
        print("Published time in header: " + now)
        # Publish messages
        publish(publish_agent, DEVICES_ALL_TOPIC, headers, all_message)

        gevent.sleep(1)

        # Query the historian
        result = query_agent.vip.rpc.call('sqlite.historian',
                                          'query',
                                          topic=query_points['oat_point'],
                                          count=20,
                                          order="LAST_TO_FIRST").get(timeout=100)
        print('Query Result', result)
        assert (len(result['values']) == 1)
        (now_date, now_time) = now.split("T")
        assert result['values'][0][0] == now_date + 'T' + now_time + '+00:00'
        assert (result['values'][0][1] == approx(oat_reading))
        assert set(result['metadata'].items()) == set(float_meta.items())
    finally:
        if agent_uuid:
            cleanup_sql(db_connection, ['timeout_param_data',
                                        'timeout_param_topics',
                                        'timeout_param_meta'])
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
        time = utils.format_timestamp(datetime.utcnow())
    # now = '2015-12-02T00:00:00'
    headers = {
        headers_mod.DATE: time,
        headers_mod.TIMESTAMP: time
    }
    print("Published time in header: " + time)
    # Publish messages
    publish(publish_agent, DEVICES_ALL_TOPIC, headers, all_message)
    return time, reading, meta
