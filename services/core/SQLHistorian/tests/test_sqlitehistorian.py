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

import os
import json
import random
import sqlite3
import gevent
import pytest
from pytest import approx
from datetime import datetime, timedelta

from volttron.platform import get_services_core
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod
from volttron.platform.vip.agent import Agent

db_connection = None

DEVICES_ALL_TOPIC = "devices/Building/LAB/Device/all"

# test config
sqlite_platform = {
    "connection": {
        "type": "sqlite",
        "params": {
            "database": 'test.sqlite'
        }
    }
}

# default config included in agent dir
config_path = os.path.join(get_services_core("SQLHistorian"), "config.sqlite")
with open(config_path, "r") as config_file:
    default_config = json.load(config_file)
assert isinstance(default_config, dict)

QUERY_POINTS = {
    "oat_point": "Building/LAB/Device/OutsideAirTemperature",
    "mixed_point": "Building/LAB/Device/MixedAirTemperature",
    "damper_point": "Building/LAB/Device/DamperSignal"
}


def random_uniform(a, b):
    """
    Creates a random uniform value for using within our tests.  This function
    will chop a float off at a specific uniform number of decimals.
    :param a: lower bound of range for return value
    :param b: upper bound of range for return value
    :return: A pseudo random uniform float.
    :type a: int
    :type b: int
    :rtype: float
    """
    format_spec = "{0:.13f}"
    return float(format_spec.format(random.uniform(a, b)))


def setup_sqlite(connection_params):
    print("setup sqlite")
    database_path = connection_params['database']
    print("connecting to sqlite path " + database_path)
    db_connection = sqlite3.connect(database_path)
    print("successfully connected to sqlite")
    db_connection.commit()
    return db_connection, 6.


def cleanup_sql(truncate_tables):
    global db_connection
    cursor = db_connection.cursor()
    for table in truncate_tables:
        cursor.execute("DELETE FROM " + table)
    db_connection.commit()


def get_table_names(config):
    default_table_def = {"table_prefix": "",
                         "data_table": "data",
                         "topics_table": "topics",
                         "meta_table": "meta"}
    tables_def = config.get('tables_def', default_table_def)
    table_names = dict(tables_def)
    table_names["agg_topics_table"] = "aggregate_" + tables_def["topics_table"]
    table_names["agg_meta_table"] = "aggregate_" + tables_def["meta_table"]

    # table_prefix = tables_def.get('table_prefix', None)
    # table_prefix = table_prefix + "_" if table_prefix else ""
    # if table_prefix:
    #     for key, value in table_names.items():
    #         table_names[key] = table_prefix + table_names[key]

    return table_names


@pytest.fixture(scope="module")
def publish_agent(request, volttron_instance):
    # 1: Start a fake agent to publish to message bus
    print("**In setup of publish_agent volttron is_running {}".format(volttron_instance.is_running))

    agent = volttron_instance.build_agent()

    # 2: add a tear down method to stop the fake agent that published to message bus
    def stop_agent():
        print("In teardown method of publish_agent")
        if isinstance(agent, Agent):
            agent.core.stop()

    request.addfinalizer(stop_agent)
    return agent


# @pytest.fixture(params=[sqlite_platform, default_config])
# def clean(request):
#     global db_connection
#
#     table_names = get_table_names(request.param)
#     table_names.pop("table_prefix")
#
#     def delete_rows():
#         cleanup_sql(table_names.values())
#     request.addfinalizer(delete_rows)


def publish(publish_agent, topic, header, message):
    if isinstance(publish_agent, Agent):
        publish_agent.vip.pubsub.publish('pubsub', topic, headers=header, message=message).get(timeout=10)
    else:
        publish_agent.publish_json(topic, header, message)


@pytest.mark.historian
@pytest.mark.sqlhistorian
@pytest.mark.parametrize("config", [sqlite_platform, default_config])
def test_sqlite_timeout(request, publish_agent, volttron_instance, config):
    """
    Test basic functionality of historian. Inserts three points as part
    of all topic and checks if all three got into the database
    Expected result:
    Should be able to query data based on topic name. Result should contain
    both data and metadata
    :param request: pytest request object
    :param publish_agent: instance of agent used to publish
    :param clean: teardown function
    :param config: historian config
    """
    global db_connection
    db_connection, microsecond_precision = setup_sqlite(config['connection']['params'])

    print("\n** test_sqlite_timeout for {}**".format(request.keywords.node.name))

    agent_uuid = None
    table_names = {}
    try:
        config["connection"]["params"]["timeout"] = 15
        table_names = get_table_names(config)
        config["tables_def"] = table_names

        # 1: Install historian agent
        # Install and start historian agent
        agent_uuid = volttron_instance.install_agent(agent_dir=get_services_core("SQLHistorian"),
                                                     config_file=config, start=True,
                                                     vip_identity='sqlite.historian')
        print("agent id: ", agent_uuid)

        # Publish fake data. The format mimics the format used by VOLTTRON drivers.
        # Make some random readings.  Random readings are going to be within the tolerance here.
        oat_reading = random_uniform(30, 100)
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
        result = publish_agent.vip.rpc.call('sqlite.historian', 'query',
                                            topic=QUERY_POINTS['oat_point'],
                                            count=20,
                                            order="LAST_TO_FIRST").get(timeout=100)
        print('Query Result', result)
        assert (len(result['values']) == 1)
        (now_date, now_time) = now.split("T")
        assert result['values'][0][0] == now_date + 'T' + now_time + '+00:00'
        assert (result['values'][0][1] == approx(oat_reading))
        assert set(result['metadata'].items()) == set(float_meta.items())
    except Exception as e:
        print(e)
    finally:
        if agent_uuid and table_names:
            volttron_instance.stop_agent(agent_uuid)
            volttron_instance.remove_agent(agent_uuid)
            # table_names.pop("table_prefix")
            # cleanup_sql(['topics'])
