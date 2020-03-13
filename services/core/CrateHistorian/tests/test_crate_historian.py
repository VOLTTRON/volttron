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


import gevent
import pytest
import os
import json
try:
    from crate import client
    HAS_CRATE = True
except ImportError:
    HAS_CRATE = False

from volttron.platform import get_services_core
from volttron.platform.messaging.health import STATUS_GOOD


crate_config = {
    "schema": "testing",
    "connection": {
        "type": "crate",
        "params": {
            "host": "localhost:4200"
        }
    }
}

crate_config_no_schema = {
    "connection": {
        "type": "crate",
        "params": {
            "host": "localhost:4200"
        }
    }
}

expected_table_list = [
    u'data',
    u'topics'
]

# used only in one test function. And clean up should happen between
# different volttron_instance types
@pytest.fixture()
def crate_connection1():
    host = crate_config_no_schema['connection']['params']['host']
    conn = client.connect(host, error_trace=True)
    clean_schema_from_database(conn, "historian")
    yield conn

    clean_schema_from_database(conn, "historian")
    conn.close()


# used only in one test function. And clean up should happen between
# different volttron_instance types
@pytest.fixture()
def crate_connection2():
    host = crate_config['connection']['params']['host']
    conn = client.connect(host, error_trace=True)
    # clean up at the start of test and end
    clean_schema_from_database(conn, "testing")
    yield conn

    clean_schema_from_database(conn, "testing")
    conn.close()


def clean_schema_from_database(connection, schema):
    tables = retrieve_tables_from_schema(connection, schema)
    cursor = connection.cursor()
    for tbl in tables:
        query = "DROP TABLE IF EXISTS {schema}.{table}".format(table=tbl, schema=schema)
        cursor.execute(query)
    cursor.close()


def retrieve_tables_from_schema(connection, schema):
    try:
        cursor = connection.cursor()
        query = "show tables in {schema}".format(schema=schema)
        cursor.execute(query)
        rows = [row[0] for row in cursor.fetchall()]
    except Exception as e:
        print("Exception {}".format(e))
        rows = []
    finally:
        cursor.close()
    return rows


@pytest.mark.historian
@pytest.mark.skipif(not HAS_CRATE, reason="No crate database driver installed.")
def test_creates_default_table_prefixes(volttron_instance, crate_connection1):
    agent_uuid = None
    try:
        vi = volttron_instance
        assert not retrieve_tables_from_schema(crate_connection1, "historian")

        agent_uuid = vi.install_agent(agent_dir=get_services_core("CrateHistorian"), config_file=crate_config_no_schema)

        gevent.sleep(2)
        tables = retrieve_tables_from_schema(crate_connection1, "historian")

        assert len(expected_table_list) == len(tables)
        assert set(expected_table_list) == set(tables)
    finally:
        if agent_uuid:
            vi.remove_agent(agent_uuid)


@pytest.mark.historian
@pytest.mark.skipif(not HAS_CRATE, reason="No crate database driver installed.")
def test_creates_schema_prefix_tables(volttron_instance, crate_connection2):
    agent_uuid = None
    try:
        vi = volttron_instance
        assert not retrieve_tables_from_schema(crate_connection2, "testing")

        agent_uuid = vi.install_agent(agent_dir=get_services_core("CrateHistorian"), config_file=crate_config)
        gevent.sleep(2)
        tables = retrieve_tables_from_schema(crate_connection2, "testing")

        assert len(expected_table_list) == len(tables)
        assert set(expected_table_list) == set(tables)

    finally:
        if agent_uuid:
            vi.remove_agent(agent_uuid)


@pytest.mark.historian
def test_crate_default_config(volttron_instance):
    """
    Test the default configuration file included with the agent
    """
    publish_agent = volttron_instance.build_agent(identity="test_agent")
    gevent.sleep(1)

    config_path = os.path.join(get_services_core("CrateHistorian"), "config")
    with open(config_path, "r") as config_file:
        config_json = json.load(config_file)
    assert isinstance(config_json, dict)
    volttron_instance.install_agent(
        agent_dir=get_services_core("CrateHistorian"),
        config_file=config_json,
        start=True,
        vip_identity="health_test")
    assert publish_agent.vip.rpc.call("health_test", "health.get_status").get(timeout=10).get('status') == STATUS_GOOD
