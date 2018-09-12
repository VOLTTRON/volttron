# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2017, SLAC National Laboratory / Kisensum Inc.
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
# Government nor the United States Department of Energy, nor SLAC / Kisensum,
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
# SLAC / Kisensum. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# }}}

import random
import pytest
import gevent
import json
import pytz
from datetime import datetime, timedelta
from dateutil import parser

from volttron.platform import get_services_core
from volttron.platform.agent.utils import format_timestamp, \
                                          parse_timestamp_string, \
                                          get_aware_utc_now
from volttron.platform.messaging import headers as headers_mod


try:
    from influxdb import InfluxDBClient
    HAS_INFLUXDB = True
except ImportError:
    HAS_INFLUXDB = False

if HAS_INFLUXDB:
    from volttron.platform.dbutils import influxdbutils
    from fixtures import *



def clean_database(client, clean_updated_database=False):
    db = influxdb_config['connection']['params']['database']
    client.drop_database(db)
    if clean_updated_database:
        updated_db = updated_influxdb_config['connection']['params']['database']
        client.drop_database(updated_db)


def start_influxdb_instance(vi, config):
    return vi.install_agent(agent_dir=get_services_core("InfluxdbHistorian"),
                            config_file=config,
                            vip_identity="influxdb.historian")


def publish_some_fake_data(publish_agent, data_count, value_type='float'):
    """
    Generate some random data for all query_topics and uses the passed
    publish_agent's vip pubsub to publish all messages.


    Timestamp of these data points will be in the range of today 12:00AM to 23:59PM

    :param publish_agent: publish agent used to publish data
    :param data_count: number of data points generated
                      E.g: if data_count = 10 and number of topics is 3,
                           then 30 data points are inserted into database
    :param value_type: type of data values
    :return: the expected list of data and meta stored in database
             E.g:
             .. code-block:: python
                 {
                    'data': {
                         datetime1: {
                            topic1: value1,
                            topic2: value2,
                            ...
                         },
                         datetime2: {
                            topic1: value3,
                            topic2: value4,
                            ...
                         }
                    },
                    'meta': {
                        topic1: meta_dict1,
                        topic2: meta_dict2,
                        ...
                    }
                 }
    """

    # data[timestamp] = {oat:x, mixed:y, damper:z}
    expectation = {'data': {}, 'meta': {}}

    now = get_aware_utc_now()

    for _ in range(0, data_count):
        second = random.randint(0, 59)
        minute = random.randint(0, 59)
        hour = random.randint(0, 23)

        timestamp = datetime(now.year, now.month, now.day, hour, minute, second, 0, tzinfo=pytz.utc)

        # Make some random readings
        if value_type == 'float':
            # Round to 14 digit precision
            # as influx only store 14 digit precision
            oat_reading = round(random.uniform(30, 100), 14)
            mixed_reading = round(oat_reading + random.uniform(-5, 5), 14)
            damper_reading = round(random.uniform(0, 100), 14)
        elif value_type == 'integer':
            oat_reading = random.randint(30, 100)
            mixed_reading = oat_reading + random.randint(-5, 5)
            damper_reading = random.randint(0, 100)
        else:   # value_type = string
            oat_reading = str('123')
            mixed_reading = str('123.456')
            damper_reading = str('def')

        # Create a message for all points.
        all_message = [{
            'OutsideAirTemperature': oat_reading,
            'MixedAirTemperature': mixed_reading,
            'DamperSignal': damper_reading},
            {
                'OutsideAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                'MixedAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                'DamperSignal': {'units': '%', 'tz': 'UTC', 'type': 'float'}
            }]

        timestamp_iso = format_timestamp(timestamp)
        headers = {headers_mod.DATE: timestamp_iso}

        # Publish messages
        publish_agent.vip.pubsub.publish(
            'pubsub', DEVICES_ALL_TOPIC, headers, all_message).get(timeout=10)

        expectation['data'][timestamp_iso] = {
            query_topics['oat_point']: oat_reading,
            query_topics['mixed_point']: mixed_reading,
            query_topics['damper_point']: damper_reading
        }

    expectation['meta'] = {
        query_topics['oat_point']: {'units': 'F', 'tz': 'UTC', 'type': 'float'},
        query_topics['mixed_point']: {'units': 'F', 'tz': 'UTC', 'type': 'float'},
        query_topics['damper_point']: {'units': '%', 'tz': 'UTC', 'type': 'float'}
    }
    gevent.sleep(2)

    return expectation


def publish_data_with_updated_meta(publish_agent):
    """
    Publish a new data point containing an updated meta dictionary
    for some topics

    :param publish_agent: publish agent used to publish data
    :return: updated meta dictionaries for all topics and updated_time

            Format of returned updated meta:
            .. code-block:: python
                {
                    topic1: {
                        "updated_time": timestamp1 or None
                        "meta_dict":    (updated) metadict1
                    },
                    topic2: {
                        "updated_time": timestamp2 or None
                        "meta_dict":    (updated) metadict2
                    },
                    ...
                }

            :note: 'updated_time' = None means that there is no change for
                   the metadata of that topic
    """

    now = get_aware_utc_now()

    # Make some random readings. round to 14 digit precision
    # as influx only store 14 digit precision
    oat_reading = round(random.uniform(30, 100), 14)
    mixed_reading = round(oat_reading + random.uniform(-5, 5), 14)
    damper_reading = round(random.uniform(0, 100), 14)

    # Create a message for all points.
    all_message = [{
        'OutsideAirTemperature': oat_reading,
        'MixedAirTemperature': mixed_reading,
        'DamperSignal': damper_reading},
        {
            'OutsideAirTemperature': {'units': 'C'},                            # changed
            'MixedAirTemperature': {'tz': 'Pacific'},                           # changed
            'DamperSignal': {'units': '%', 'tz': 'UTC', 'type': 'float'}        # unchanged
        }]

    timestamp_iso = format_timestamp(now)
    headers = {headers_mod.DATE: timestamp_iso}

    # Publish messages
    publish_agent.vip.pubsub.publish(
        'pubsub', DEVICES_ALL_TOPIC, headers, all_message).get(timeout=10)

    new_metadata = {
        query_topics['oat_point']: {
            "updated_time": timestamp_iso,
            "meta_dict":    {'units': 'C', 'tz': 'UTC', 'type': 'float'}        # changed
        },
        query_topics['mixed_point']: {
            "updated_time": timestamp_iso,
            "meta_dict":    {'units': 'F', 'tz': 'Pacific', 'type': 'float'}    # changed
        },
        query_topics['damper_point']: {
            "updated_time": None,
            "meta_dict":    {'units': '%', 'tz': 'UTC', 'type': 'float'}        # unchanged
        }
    }
    gevent.sleep(1)

    return new_metadata, timestamp_iso


def publish_data_with_updated_topic_case(publish_agent, data_count):
    for _ in range(0, data_count):
        now = get_aware_utc_now() + timedelta(days=1)
        # Make some random readings. round to 14 digit precision
        # as influx only store 14 digit precision
        oat_reading = round(random.uniform(30, 100), 14)
        mixed_reading = round(oat_reading + random.uniform(-5, 5), 14)
        damper_reading = round(random.uniform(0, 100), 14)

        # Create a message for all points.
        all_message = [{
            'outsideairtemperature': oat_reading,
            'mixedairtemperature': mixed_reading,
            'dampersignal': damper_reading},
            {
                'outsideairtemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                'mixedairtemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                'dampersignal': {'units': '%', 'tz': 'UTC', 'type': 'float'}
            }]

        timestamp_iso = format_timestamp(now)
        headers = {headers_mod.DATE: timestamp_iso}

        # Publish messages
        publish_agent.vip.pubsub.publish(
            'pubsub', DEVICES_ALL_TOPIC, headers, all_message).get(timeout=10)

    gevent.sleep(2)


@pytest.mark.historian
@pytest.mark.skipif(not HAS_INFLUXDB, reason='No influxdb library. Please run \'pip install influxdb\'')
def test_installation_and_connection(volttron_instance, influxdb_client):
    """
    Test installing the InfluxdbHistorian agent and then
    connect to influxdb client.


    When it first connect to the client, there should be no
    database yet. If database already existed, clean database.
    """
    clean_database(influxdb_client)

    agent_uuid = start_influxdb_instance(volttron_instance, influxdb_config)
    assert agent_uuid is not None
    assert volttron_instance.is_agent_running(agent_uuid)

    try:
        assert influxdb_client is not None

        rs = influxdb_client.get_list_database()

        # after installing InfluxDBHistorian agent, the specified database
        # in the config file should be created
        assert len(rs) == 1
        assert {'name': '_internal'} in rs

    finally:
        volttron_instance.stop_agent(agent_uuid)
        volttron_instance.remove_agent(agent_uuid)
        clean_database(influxdb_client)


@pytest.mark.historian
@pytest.mark.skipif(not HAS_INFLUXDB, reason='No influxdb library. Please run \'pip install influxdb\'')
def test_publish_to_historian(volttron_instance, influxdb_client):
    """
    Test basic functionality of publish_to_historian.

    Inserts a specific number of data and checks if all of them
    got into the database.
    """

    clean_database(influxdb_client)
    db = influxdb_config['connection']['params']['database']
    influxdb_client.create_database(db)

    agent_uuid = start_influxdb_instance(volttron_instance, influxdb_config)
    assert agent_uuid is not None
    assert volttron_instance.is_agent_running(agent_uuid)

    try:
        assert influxdb_client is not None

        publisher = volttron_instance.build_agent()
        assert publisher is not None
        expected = publish_some_fake_data(publisher, 10)
        # print expected

        rs = influxdb_client.get_list_database()

        # the databases historian
        assert {'name': 'historian'} in rs

        # Check for measurement OutsideAirTemperature
        query = 'SELECT value FROM outsideairtemperature ' \
                'WHERE campus=\'building\' and building=\'lab\' and device=\'device\''
        rs = influxdb_client.query(query)
        rs = list(rs.get_points())
        topic = query_topics["oat_point"]

        assert len(rs) == 10

        for point in rs:
            ts = parser.parse(point['time'])
            ts = format_timestamp(ts)
            assert point["value"] == expected['data'][ts][topic]

        # Check for measurement MixedAirTemperature
        query = 'SELECT value FROM mixedairtemperature ' \
                'WHERE campus=\'building\' and building=\'lab\' and device=\'device\''
        rs = influxdb_client.query(query)
        rs = list(rs.get_points())
        topic = query_topics["mixed_point"]

        assert len(rs) == 10

        for point in rs:
            ts = parser.parse(point['time'])
            ts = format_timestamp(ts)
            assert point["value"] == expected['data'][ts][topic]

        # Check for measurement DamperSignal
        query = 'SELECT value FROM dampersignal ' \
                'WHERE campus=\'building\' and building=\'lab\' and device=\'device\''
        rs = influxdb_client.query(query)
        rs = list(rs.get_points())
        topic = query_topics["damper_point"]

        assert len(rs) == 10

        for point in rs:
            ts = parser.parse(point['time'])
            ts = format_timestamp(ts)
            assert point["value"] == expected['data'][ts][topic]

        # Check correctness of 'meta' measurement
        topic_id_map, meta_dicts = influxdbutils.get_all_topic_id_and_meta(influxdb_client)
        assert len(meta_dicts) == 3

        for topic_id in topic_id_map:
            topic = topic_id_map[topic_id]

            assert topic in expected['meta']
            assert expected['meta'][topic] == meta_dicts[topic_id]

    finally:
        volttron_instance.stop_agent(agent_uuid)
        volttron_instance.remove_agent(agent_uuid)
        clean_database(influxdb_client)


@pytest.mark.historian
@pytest.mark.skipif(not HAS_INFLUXDB, reason='No influxdb library. Please run \'pip install influxdb\'')
def test_publish_abnormal_topic_name(volttron_instance, influxdb_client):
    """
    The normal format of topic name is ``<campus>/<building>/<device>/<measurement>``,
    where campus, building and device will be stored as tags in database.

    This will test the case when a topic name doesn't follow that convention:


        1. Topic name is longer than that format. For example, if topic name is
           "CampusA/Building1/LAB/Device/OutsideAirTemperature",
           'campusa/building' will go to campus tag, 'lab' for building tag
           and 'device' for device tag


        2. Topic name is shorter than that format. For example, if topic name is
           "LAB/Device/OutsideAirTemperature", the campus tag will be empty,
           'lab' for building tag and 'device' for device tag.

    """
    clean_database(influxdb_client)
    db = influxdb_config['connection']['params']['database']
    influxdb_client.create_database(db)

    agent_uuid = start_influxdb_instance(volttron_instance, influxdb_config)
    assert agent_uuid is not None
    assert volttron_instance.is_agent_running(agent_uuid)

    try:
        assert influxdb_client is not None
        for topic in long_topics:
            value = random.randint(0, 100)
            influxdbutils.insert_data_point(client=influxdb_client, time=get_aware_utc_now(),
                                            topic_id=topic.lower(), source="scrape",
                                            value=value, value_string=str(value))

        for topic in short_topics:
            value = random.randint(0, 100)
            influxdbutils.insert_data_point(client=influxdb_client, time=get_aware_utc_now(),
                                            topic_id=topic.lower(), source="scrape",
                                            value=value, value_string=str(value))

        query = "SELECT * FROM outsideairtemperature"
        rs = influxdb_client.query(query)
        rs = list(rs.get_points())

        assert rs[0]["campus"] == "campusa/building1"
        assert rs[0]["building"] == "lab1"
        assert rs[0]["device"] == "device1"

        assert rs[1]["campus"] is None
        assert rs[1]["building"] == "lab1"
        assert rs[1]["device"] == "device1"

        query = "SELECT * FROM dampersignal"
        rs = influxdb_client.query(query)
        rs = list(rs.get_points())

        assert rs[0]["campus"] == "campusb/building2"
        assert rs[0]["building"] == "lab2"
        assert rs[0]["device"] == "device2"

        assert rs[1]["campus"] is None
        assert rs[1]["building"] == "lab2"
        assert rs[1]["device"] == "device2"

    finally:
        volttron_instance.stop_agent(agent_uuid)
        volttron_instance.remove_agent(agent_uuid)
        clean_database(influxdb_client)


@pytest.mark.historian
@pytest.mark.skipif(not HAS_INFLUXDB, reason='No influxdb library. Please run \'pip install influxdb\'')
def test_publish_with_changed_value_type(volttron_instance, influxdb_client):
    clean_database(influxdb_client)
    db = influxdb_config['connection']['params']['database']
    influxdb_client.create_database(db)

    agent_uuid = start_influxdb_instance(volttron_instance, influxdb_config)
    assert agent_uuid is not None
    assert volttron_instance.is_agent_running(agent_uuid)

    try:
        assert influxdb_client is not None
        publisher = volttron_instance.build_agent()
        assert publisher is not None

        # Publish some float first
        expected_float = publish_some_fake_data(publisher, 1)
        # Then publish some integer
        expected_int = publish_some_fake_data(publisher, 1, value_type='integer')
        # Then publish some float as string
        expected_str = publish_some_fake_data(publisher, 1, value_type='string')

        expected = expected_float['data'].copy()
        expected.update(expected_int['data'])
        expected.update(expected_str['data'])

        # Check for measurement OutsideAirTemperature
        query = 'SELECT value, value_string FROM outsideairtemperature ' \
                'WHERE campus=\'building\' and building=\'lab\' and device=\'device\''
        rs = influxdb_client.query(query)
        rs = list(rs.get_points())
        topic = query_topics["oat_point"]

        assert len(rs) == 3

        for point in rs:
            ts = parser.parse(point['time'])
            ts = format_timestamp(ts)
            assert point["value"] == float(expected[ts][topic])
            assert point["value_string"] == str(expected[ts][topic])

        # Check for measurement MixedAirTemperature
        query = 'SELECT value, value_string FROM mixedairtemperature ' \
                'WHERE campus=\'building\' and building=\'lab\' and device=\'device\''
        rs = influxdb_client.query(query)
        rs = list(rs.get_points())
        topic = query_topics["mixed_point"]

        assert len(rs) == 3

        for point in rs:
            ts = parser.parse(point['time'])
            ts = format_timestamp(ts)
            assert point["value"] == float(expected[ts][topic])
            assert point["value_string"] == str(expected[ts][topic])

        # Check for measurement DamperSignal
        query = 'SELECT value, value_string FROM dampersignal ' \
                'WHERE campus=\'building\' and building=\'lab\' and device=\'device\''
        rs = influxdb_client.query(query)
        rs = list(rs.get_points())
        topic = query_topics["damper_point"]

        assert len(rs) == 3

        for point in rs:
            ts = parser.parse(point['time'])
            ts = format_timestamp(ts)
            assert point["value_string"] == str(expected[ts][topic])
            try:
                assert point["value"] == float(expected[ts][topic])
            except ValueError:
                assert point["value"] is None

    finally:
        volttron_instance.stop_agent(agent_uuid)
        volttron_instance.remove_agent(agent_uuid)
        clean_database(influxdb_client)


@pytest.mark.historian
@pytest.mark.skipif(not HAS_INFLUXDB, reason='No influxdb library. Please run \'pip install influxdb\'')
def test_query_topic_list(volttron_instance, influxdb_client):
    """
    Test basic functionality of query_topic_list method in InfluxdbHistorian.

    Inserts a specific number of data and call 'get_topic_list' method through
    a new built agent.
    """

    clean_database(influxdb_client)
    db = influxdb_config['connection']['params']['database']
    influxdb_client.create_database(db)

    agent_uuid = start_influxdb_instance(volttron_instance, influxdb_config)
    assert agent_uuid is not None
    assert volttron_instance.is_agent_running(agent_uuid)

    try:
        assert influxdb_client is not None

        publisher = volttron_instance.build_agent()
        assert publisher is not None
        publish_some_fake_data(publisher, 3)

        lister = volttron_instance.build_agent()
        topic_list = lister.vip.rpc.call('influxdb.historian',
                                         'get_topic_list').get(timeout=5)

        assert topic_list != []
        assert set(topic_list) == set(query_topics.values())

    finally:
        volttron_instance.stop_agent(agent_uuid)
        volttron_instance.remove_agent(agent_uuid)
        clean_database(influxdb_client)


@pytest.mark.historian
@pytest.mark.skipif(not HAS_INFLUXDB, reason='No influxdb library. Please run \'pip install influxdb\'')
def test_query_historian_all_topics(volttron_instance, influxdb_client):
    """
        Test basic functionality of query_historian method in InfluxdbHistorian.

        Inserts a specific number of data and call 'query' method through
        a new built agent. The topic argument can be a single topic or a
        list of topics.

        We test a list of topics in this case.

        The method 'query' actually executes multiple times the following queries:

        .. code-block:: python

            SELECT value FROM <measurement> WHERE campus='<campus>' and building='<building>' and device='<device>'
            LIMIT 30

        :note: <measurement>, <campus>, <building> and <device> are parsed from topic_id
    """

    clean_database(influxdb_client)
    db = influxdb_config['connection']['params']['database']
    influxdb_client.create_database(db)

    agent_uuid = start_influxdb_instance(volttron_instance, influxdb_config)
    assert agent_uuid is not None
    assert volttron_instance.is_agent_running(agent_uuid)

    try:
        assert influxdb_client is not None

        publisher = volttron_instance.build_agent()
        assert publisher is not None
        expected = publish_some_fake_data(publisher, 50)

        actual = publisher.vip.rpc.call('influxdb.historian',
                                        'query',
                                        topic=query_topics.values(),
                                        count=30,
                                        order="FIRST_TO_LAST").get(timeout=60)

        assert actual is not None

        for topic in query_topics.values():
            assert topic in actual['values']

            # Check for correctness of values of all topics
            topic_values = actual['values'][topic]
            assert len(topic_values) == 30

            for i, pair in enumerate(topic_values):
                timestamp = pair[0]
                value = float(pair[1])
                assert timestamp in expected['data']
                assert value == expected['data'][timestamp][topic]

            # meta should be empty if topic argument is a list
            assert actual['metadata'] == {}

    finally:
        volttron_instance.stop_agent(agent_uuid)
        volttron_instance.remove_agent(agent_uuid)
        clean_database(influxdb_client)


@pytest.mark.historian
@pytest.mark.skipif(not HAS_INFLUXDB, reason='No influxdb library. Please run \'pip install influxdb\'')
def test_query_historian_single_topic(volttron_instance, influxdb_client):
    """
    Test basic functionality of query_historian method in InfluxdbHistorian.

    Inserts a specific number of data and call 'query' method through
    a new built agent. The topic argument can be a single topic or a
    list of topics.

    A single topic is tested in this case. Moreover, 'skip' and 'order' arguments
    are also tested.

    The method 'query' actually executes multiple times the following queries:

    .. code-block:: python

        SELECT value FROM 'OutsideAirTemperature' WHERE campus='Building' and building='LAB' and device='Device'
        ORDER BY time DESC
        LIMIT 20 OFFSET 5
    """

    clean_database(influxdb_client)
    db = influxdb_config['connection']['params']['database']
    influxdb_client.create_database(db)

    agent_uuid = start_influxdb_instance(volttron_instance, influxdb_config)
    assert agent_uuid is not None
    assert volttron_instance.is_agent_running(agent_uuid)

    try:
        assert influxdb_client is not None

        publisher = volttron_instance.build_agent()
        assert publisher is not None
        expected = publish_some_fake_data(publisher, 50)

        topic = query_topics["oat_point"]
        actual = publisher.vip.rpc.call('influxdb.historian',
                                        'query',
                                        topic=topic,
                                        count=20,
                                        skip=5,
                                        order="LAST_TO_FIRST").get(timeout=60)

        assert actual is not None

        # Check for correctness of values list
        values = actual['values']
        assert len(values) == 20

        for i, pair in enumerate(values):
            timestamp = pair[0]
            value = float(pair[1])
            assert timestamp in expected['data']
            assert value == expected['data'][timestamp][topic]

        # Check for correctness of metadata
        assert actual['metadata'] == expected['meta'][topic]

        # Check whether 'skip=5' and 'oder=LAST_TO_FIRST' are working correctly
        expected_time_list = []
        for ts in expected['data']:
            dt = parse_timestamp_string(ts)
            expected_time_list.append(dt)
        expected_time_list = sorted(expected_time_list, reverse=True)
        expected_time_list = expected_time_list[5:25]

        actual_time_list = []
        for pair in actual['values']:
            dt = parse_timestamp_string(pair[0])
            actual_time_list.append(dt)
        actual_time_list = sorted(actual_time_list, reverse=True)

        for i in range(0, 20):
            assert actual_time_list[i] == expected_time_list[i]

    finally:
        volttron_instance.stop_agent(agent_uuid)
        volttron_instance.remove_agent(agent_uuid)
        clean_database(influxdb_client)


@pytest.mark.historian
@pytest.mark.skipif(not HAS_INFLUXDB, reason='No influxdb library. Please run \'pip install influxdb\'')
def test_query_historian_all_topics_with_time(volttron_instance, influxdb_client):
    """
        Test basic functionality of query_historian method in InfluxdbHistorian.

        Inserts a specific number of data and call 'query' method through
        a new built agent. The topic argument can be a single topic or a
        list of topics.

        We test a list of topics in this case with start_time and end_time not None

        The method 'query' actually executes multiple times the following queries:

        .. code-block:: python

            SELECT value FROM <measurement> WHERE campus='<campus>' and building='<building>' and device='<device>'
            AND time >= now() - 24h AND time <= now() - 12h
            LIMIT 1000 OFFSET 2

        :note: No ``count`` argument will be provided, so count is set to default 1000
    """

    clean_database(influxdb_client)
    db = influxdb_config['connection']['params']['database']
    influxdb_client.create_database(db)

    agent_uuid = start_influxdb_instance(volttron_instance, influxdb_config)
    assert agent_uuid is not None
    assert volttron_instance.is_agent_running(agent_uuid)

    try:
        assert influxdb_client is not None

        publisher = volttron_instance.build_agent()
        assert publisher is not None
        expected = publish_some_fake_data(publisher, 50)

        now = get_aware_utc_now()
        start_time = now - timedelta(hours=now.hour, minutes=now.minute,
                                     seconds=now.second, microseconds=now.microsecond)
        end_time = start_time + timedelta(hours=12)

        actual = publisher.vip.rpc.call('influxdb.historian',
                                        'query',
                                        topic=query_topics.values(),
                                        start=format_timestamp(start_time),
                                        end=format_timestamp(end_time),
                                        skip=2,
                                        order="FIRST_TO_LAST").get(timeout=60)

        assert actual is not None

        for topic in query_topics.values():
            assert topic in actual['values']

            # Calculate expected list of timestamp

            expected_time_list = []
            for ts in expected['data']:
                dt = parse_timestamp_string(ts)
                if start_time <= dt <= end_time:
                    expected_time_list.append(dt)
            expected_time_list = sorted(expected_time_list)[2:]

            # Check for correctness of values of all topics
            topic_values = actual['values'][topic]
            actual_time_list = []

            assert len(topic_values) != 0

            for i, pair in enumerate(topic_values):
                timestamp = pair[0]
                value = float(pair[1])

                assert timestamp in expected['data']
                assert value == expected['data'][timestamp][topic]

                dt = parse_timestamp_string(timestamp)
                actual_time_list.append(dt)

            actual_time_list = sorted(actual_time_list)

            # Check correctness of list of timestamp
            for i, ts in enumerate(expected_time_list):
                assert ts == actual_time_list[i]

            # meta should be empty if topic argument is a list
            assert actual['metadata'] == {}

    finally:
        volttron_instance.stop_agent(agent_uuid)
        volttron_instance.remove_agent(agent_uuid)
        clean_database(influxdb_client)


@pytest.mark.historian
@pytest.mark.skipif(not HAS_INFLUXDB, reason='No influxdb library. Please run \'pip install influxdb\'')
def test_query_topics_metadata(volttron_instance, influxdb_client):
    """
    Test basic functionality of query_topics_metadata method in InfluxdbHistorian.

    Inserts a specific number of data and call ``get_topics_metadata`` method
    through a new built agent.
    """
    clean_database(influxdb_client)
    db = influxdb_config['connection']['params']['database']
    influxdb_client.create_database(db)

    agent_uuid = start_influxdb_instance(volttron_instance, influxdb_config)
    assert agent_uuid is not None
    assert volttron_instance.is_agent_running(agent_uuid)

    single_topic = query_topics['oat_point']
    topic_list = [query_topics['mixed_point'], query_topics['damper_point']]

    try:
        assert influxdb_client is not None

        publisher = volttron_instance.build_agent()
        assert publisher is not None
        expected = publish_some_fake_data(publisher, 3)

        # Test if topics is a string
        lister = volttron_instance.build_agent()
        topics_metadata = lister.vip.rpc.call('influxdb.historian',
                                              'get_topics_metadata',
                                              topics=single_topic).get(timeout=5)

        assert topics_metadata != {}
        assert topics_metadata == {query_topics['oat_point']: expected['meta'][query_topics['oat_point']]}

        # Test if topics is a list
        topics_metadata = lister.vip.rpc.call('influxdb.historian',
                                              'get_topics_metadata',
                                              topics=topic_list).get(timeout=5)

        assert topics_metadata != {}
        assert topics_metadata == {query_topics['mixed_point']: expected['meta'][query_topics['mixed_point']],
                                   query_topics['damper_point']: expected['meta'][query_topics['damper_point']]}

    finally:
        volttron_instance.stop_agent(agent_uuid)
        volttron_instance.remove_agent(agent_uuid)
        clean_database(influxdb_client)


@pytest.mark.historian
@pytest.mark.skipif(not HAS_INFLUXDB, reason='No influxdb library. Please run \'pip install influxdb\'')
def test_query_topics_by_pattern(volttron_instance, influxdb_client):
    """
    Test basic functionality of query_topics_by_pattern method in InfluxdbHistorian.

    Inserts a specific number of data and call ``get_topics_by_pattern`` method
    through a new built agent. The format of a query for regex pattern is:

    .. code-block:: python

        SELECT topic, topic_id FROM meta WHERE topic =~ /<pattern>/
    """
    clean_database(influxdb_client)
    db = influxdb_config['connection']['params']['database']
    influxdb_client.create_database(db)

    agent_uuid = start_influxdb_instance(volttron_instance, influxdb_config)
    assert agent_uuid is not None
    assert volttron_instance.is_agent_running(agent_uuid)

    pattern_1 = 'Building\/LAB\/Device.*'
    expected_1 = [{topic: topic.lower()} for topic in query_topics.values()]

    pattern_2 = 'Building.*MixedAir'
    expected_2 = [{query_topics["mixed_point"]: query_topics["mixed_point"].lower()}]

    pattern_3 = 'Building.*Signal$'
    expected_3 = [{query_topics["damper_point"]: query_topics["damper_point"].lower()}]

    pattern_4 = 'Air'
    expected_4 = [{query_topics["oat_point"]: query_topics["oat_point"].lower()},
                  {query_topics["mixed_point"]: query_topics["mixed_point"].lower()}]

    pattern_5 = '^Outside'
    expected_5 = []

    try:
        assert influxdb_client is not None

        publisher = volttron_instance.build_agent()
        assert publisher is not None
        publish_some_fake_data(publisher, 3)
        lister = volttron_instance.build_agent()

        # Test for pattern 1
        topics_metadata = lister.vip.rpc.call('influxdb.historian',
                                              'get_topics_by_pattern',
                                              topic_pattern=pattern_1).get(timeout=5)

        assert sorted(topics_metadata) == sorted(expected_1)

        # Test for pattern 2
        topics_metadata = lister.vip.rpc.call('influxdb.historian',
                                              'get_topics_by_pattern',
                                              topic_pattern=pattern_2).get(timeout=5)

        assert sorted(topics_metadata) == sorted(expected_2)

        # Test for pattern 3
        topics_metadata = lister.vip.rpc.call('influxdb.historian',
                                              'get_topics_by_pattern',
                                              topic_pattern=pattern_3).get(timeout=5)

        assert sorted(topics_metadata) == sorted(expected_3)

        # Test for pattern 4
        topics_metadata = lister.vip.rpc.call('influxdb.historian',
                                              'get_topics_by_pattern',
                                              topic_pattern=pattern_4).get(timeout=5)

        assert sorted(topics_metadata) == sorted(expected_4)

        # Test for pattern 5
        topics_metadata = lister.vip.rpc.call('influxdb.historian',
                                              'get_topics_by_pattern',
                                              topic_pattern=pattern_5).get(timeout=5)

        assert sorted(topics_metadata) == sorted(expected_5)

    finally:
        volttron_instance.stop_agent(agent_uuid)
        volttron_instance.remove_agent(agent_uuid)
        clean_database(influxdb_client)


@pytest.mark.historian
@pytest.mark.skipif(not HAS_INFLUXDB, reason='No influxdb library. Please run \'pip install influxdb\'')
def test_query_aggregate_with_calendar_period(volttron_instance, influxdb_client):
    """
        Test basic functionality of query with provided agg_type and agg_period
        in InfluxdbHistorian with option ``use_calendar_time_periods=True``

        We test a list of topics in this case.

        The method 'query' actually executes multiple times the following queries:

        .. code-block:: python

            SELECT SUM(value) FROM <measurement> WHERE campus='<campus>' and building='<building>' and device='<device>'
             and time >= <start-of-today>
            GROUP BY time(1d) LIMIT 10


            SELECT MAX(value) FROM <measurement> WHERE campus='<campus>' and building='<building>' and device='<device>'
             and time >= <start-of-today>
            GROUP BY time(6h) LIMIT 1000 ORDER BY time DESC
    """

    clean_database(influxdb_client)
    db = influxdb_config['connection']['params']['database']
    influxdb_client.create_database(db)

    agent_uuid = start_influxdb_instance(volttron_instance, influxdb_config)
    assert agent_uuid is not None
    assert volttron_instance.is_agent_running(agent_uuid)

    try:
        assert influxdb_client is not None

        publisher = volttron_instance.build_agent()
        assert publisher is not None
        expected = publish_some_fake_data(publisher, 50)

        now = get_aware_utc_now()
        start_time = now - timedelta(hours=now.hour, minutes=now.minute,
                                     seconds=now.second, microseconds=now.microsecond)
        end_time = start_time + timedelta(days=1) - timedelta(seconds=1)

        actual = publisher.vip.rpc.call('influxdb.historian',
                                        'query',
                                        topic=query_topics.values(),
                                        start=format_timestamp(start_time),
                                        end=format_timestamp(end_time),
                                        agg_type="SUM",
                                        agg_period="1d",
                                        count=10,
                                        order="FIRST_TO_LAST").get(timeout=60)

        assert len(actual["values"]) == 3

        expected_sums = {}
        for topic in query_topics.values():
            topic_sum = 0
            for ts in expected["data"]:
                topic_sum += expected["data"][ts][topic]
            expected_sums[topic] = topic_sum

        for topic in expected_sums:
            actual_sum = "%.10f" % actual["values"][topic][0][1]
            assert actual_sum == "%.10f" % expected_sums[topic]

        actual = publisher.vip.rpc.call('influxdb.historian',
                                        'query',
                                        topic=query_topics.values(),
                                        start=format_timestamp(start_time),
                                        end=format_timestamp(end_time),
                                        agg_type="MAX",
                                        agg_period="6h",
                                        order="LAST_TO_FIRST").get(timeout=60)

        assert len(actual["values"]) == 3
        assert len(actual["values"]['Building/LAB/Device/OutsideAirTemperature']) == 4

        expected_maxes = {}
        for topic in query_topics.values():
            max_1 = 0
            max_2 = 0
            max_3 = 0
            max_4 = 0
            for ts in expected["data"]:
                value = expected["data"][ts][topic]
                ts = parse_timestamp_string(ts)

                if start_time <= ts < start_time + timedelta(hours=6) and value > max_1:
                    max_1 = value
                elif start_time + timedelta(hours=6) <= ts < start_time + timedelta(hours=12) and value > max_2:
                    max_2 = value
                elif start_time + timedelta(hours=12) <= ts < start_time + timedelta(hours=18) and value > max_3:
                    max_3 = value
                elif start_time + timedelta(hours=18) <= ts <= end_time and value > max_4:
                    max_4 = value
            expected_maxes[topic] = [max_4, max_3, max_2, max_1]

        for topic in expected_maxes:
            for i, m in enumerate(expected_maxes[topic]):
                assert actual["values"][topic][i][1] == m

    finally:
        volttron_instance.stop_agent(agent_uuid)
        volttron_instance.remove_agent(agent_uuid)
        clean_database(influxdb_client)


@pytest.mark.skip()  # Comment this line if version of Influxdb is <= 1.2.4
@pytest.mark.historian
@pytest.mark.skipif(not HAS_INFLUXDB, reason='No influxdb library. Please run \'pip install influxdb\'')
def test_query_aggregate_without_calendar_period(volttron_instance, influxdb_client):
    """
        Test basic functionality of query with provided agg_type and agg_period
        in InfluxdbHistorian with option ``use_calendar_time_periods=False``

        We test a list of topics in this case.

        The method 'query' actually executes multiple times the following queries:

        .. code-block:: python

            SELECT SUM(value) FROM 'OutsideAirTemperature' WHERE campus='Building' and building='LAB'
             and device='Device' and time >= <start-of-today>
             GROUP BY time(1d) LIMIT 10 ORDER BY time DESC


            SELECT MIN(value) FROM 'OutsideAirTemperature' WHERE campus='Building' and building='LAB'
             and device='Device' and time >= <start-of-today>
            GROUP BY time(6h) LIMIT 3
    """

    clean_database(influxdb_client)
    db = influxdb_config['connection']['params']['database']
    influxdb_client.create_database(db)

    agent_uuid = start_influxdb_instance(volttron_instance, influxdb_config_without_calender_period)
    assert agent_uuid is not None
    assert volttron_instance.is_agent_running(agent_uuid)

    try:
        assert influxdb_client is not None

        publisher = volttron_instance.build_agent()
        assert publisher is not None
        expected = publish_some_fake_data(publisher, 50)

        now = get_aware_utc_now()
        start_time = now - timedelta(hours=now.hour, minutes=now.minute,
                                     seconds=now.second, microseconds=now.microsecond)
        end_time = start_time + timedelta(days=1) - timedelta(seconds=1)

        actual = publisher.vip.rpc.call('influxdb.historian',
                                        'query',
                                        topic=query_topics["oat_point"],
                                        start=format_timestamp(start_time),
                                        end=format_timestamp(end_time),
                                        agg_type="SUM",
                                        agg_period="1d",
                                        count=10,
                                        order="LAST_TO_FIRST").get(timeout=60)

        assert len(actual["values"]) == 2
        ts1 = parser.parse(actual["values"][0][0])
        assert ts1 - now < timedelta(minutes=2)
        ts2 = parser.parse(actual["values"][1][0])
        assert ts2 - now < timedelta(days=1, minutes=2)

        sum1 = 0
        sum2 = 0
        for ts in expected["data"]:
            if parse_timestamp_string(ts) >= ts1:
                sum1 += expected["data"][ts][query_topics["oat_point"]]
            elif ts2 <= parse_timestamp_string(ts) < ts1:
                sum2 += expected["data"][ts][query_topics["oat_point"]]
        if actual["values"][0][1] is None:
            assert sum1 == 0
        else:
            assert abs(actual["values"][0][1] - sum1) < 10 ** (-10)

        if actual["values"][1][1] is None:
            assert sum2 == 0
        else:
            assert abs(actual["values"][1][1] - sum2) < 10 ** (-10)

        actual = publisher.vip.rpc.call('influxdb.historian',
                                        'query',
                                        topic=query_topics["oat_point"],
                                        start=format_timestamp(start_time),
                                        end=format_timestamp(end_time),
                                        agg_type="MIN",
                                        agg_period="6h",
                                        count=3,
                                        order="FIRST_TO_LAST").get(timeout=60)

        assert len(actual["values"]) == 3

        min_1 = 100
        min_2 = 100
        min_3 = 100

        first_ts = parser.parse(actual["values"][0][0])

        for ts in expected["data"]:
            value = expected["data"][ts][query_topics["oat_point"]]
            ts = parse_timestamp_string(ts)

            if first_ts <= ts < first_ts + timedelta(hours=6) and value < min_1:
                min_1 = value
            elif first_ts + timedelta(hours=6) <= ts < first_ts + timedelta(hours=12) and value < min_2:
                min_2 = value
            elif first_ts + timedelta(hours=12) <= ts < first_ts + timedelta(hours=18) and value < min_3:
                min_3 = value

        assert min_1 == actual["values"][0][1]
        assert min_2 == actual["values"][1][1]
        assert min_3 == actual["values"][2][1]

    finally:
        volttron_instance.stop_agent(agent_uuid)
        volttron_instance.remove_agent(agent_uuid)
        clean_database(influxdb_client)


@pytest.mark.historian
@pytest.mark.skipif(not HAS_INFLUXDB, reason='No influxdb library. Please run \'pip install influxdb\'')
def test_update_meta(volttron_instance, influxdb_client):
    """
    Test the case when metadata for some topics are updated.

    The metadata for those topics should be changed to the new one
    Also, last_updated field in the 'meta' table in the database
    should be changed to the updated time as well.

    """

    clean_database(influxdb_client)
    db = influxdb_config['connection']['params']['database']
    influxdb_client.create_database(db)

    agent_uuid = start_influxdb_instance(volttron_instance, influxdb_config)
    assert agent_uuid is not None
    assert volttron_instance.is_agent_running(agent_uuid)

    try:
        assert influxdb_client is not None

        publisher = volttron_instance.build_agent()

        assert publisher is not None

        publish_some_fake_data(publisher, 10)
        updated_meta, updated_time = publish_data_with_updated_meta(publisher)

        query = 'SELECT * FROM meta'
        rs = influxdb_client.query(query)
        rs = list(rs.get_points())

        for meta in rs:
            topic = meta["topic"]
            meta_dict = json.loads(meta['meta_dict'].replace("u'", "\"").replace("'", "\""))
            last_updated = meta["last_updated"]

            assert meta_dict == updated_meta[topic]["meta_dict"]

            if updated_meta[topic]["updated_time"] is None:
                assert last_updated != updated_time
            else:
                assert last_updated == updated_time

    finally:
        volttron_instance.stop_agent(agent_uuid)
        volttron_instance.remove_agent(agent_uuid)
        clean_database(influxdb_client)


@pytest.mark.historian
@pytest.mark.skipif(not HAS_INFLUXDB, reason='No influxdb library. Please run \'pip install influxdb\'')
def test_update_topic_case(volttron_instance, influxdb_client):
    """
    Test the case when topic's case changes
    (e.g: some letters of topic name change from lowercase to uppercase)

    If topic's case change, 'meta' table should be updated with the latest
    actual topic name.
    """
    clean_database(influxdb_client)
    db = influxdb_config['connection']['params']['database']
    influxdb_client.create_database(db)

    agent_uuid = start_influxdb_instance(volttron_instance, influxdb_config)
    assert agent_uuid is not None
    assert volttron_instance.is_agent_running(agent_uuid)

    try:
        assert influxdb_client is not None

        publisher = volttron_instance.build_agent()
        assert publisher is not None

        publish_some_fake_data(publisher, 3)

        old_topic_list = publisher.vip.rpc.call('influxdb.historian',
                                                'get_topic_list').get(timeout=5)

        publish_data_with_updated_topic_case(publisher, 3)

        new_topic_list = publisher.vip.rpc.call('influxdb.historian',
                                                'get_topic_list').get(timeout=5)

        assert old_topic_list != new_topic_list

        assert set([t[:20] + t[20:].lower() for t in old_topic_list]) == set(new_topic_list)

    finally:
        volttron_instance.stop_agent(agent_uuid)
        volttron_instance.remove_agent(agent_uuid)
        clean_database(influxdb_client)


# Any test run after this one has to switch to 'historian' database again.
# Hence, for convenience, put this test at last in the file
# because it will drop 'test' database at last.
@pytest.mark.historian
@pytest.mark.skipif(not HAS_INFLUXDB, reason='No influxdb library. Please run \'pip install influxdb\'')
def test_update_config_store(volttron_instance, influxdb_client):
    """
    Test the case when user updates config store while an
    InfluxdbHistorian Agent is running.

    In this test, database name is updated and data should be
    stored in the updated one.
    """
    clean_database(influxdb_client)
    db = influxdb_config['connection']['params']['database']
    updated_db = updated_influxdb_config['connection']['params']['database']
    influxdb_client.create_database(db)
    influxdb_client.create_database(updated_db)

    agent_uuid = start_influxdb_instance(volttron_instance, influxdb_config)
    assert agent_uuid is not None
    assert volttron_instance.is_agent_running(agent_uuid)

    try:
        assert influxdb_client is not None

        publisher = volttron_instance.build_agent()
        assert publisher is not None
        publish_some_fake_data(publisher, 5)

        # Update config store
        publisher.vip.rpc.call('config.store', 'manage_store',
                               'influxdb.historian','config',
                               json.dumps(updated_influxdb_config), config_type="json").get(timeout=10)
        publish_some_fake_data(publisher, 5)

        influxdb_client.switch_database(db)
        query = 'SELECT topic, meta_dict FROM meta'
        rs = influxdb_client.query(query)
        meta_historian = list(rs.get_points())

        assert len(meta_historian) == 3

        influxdb_client.switch_database(updated_db)
        query = 'SELECT topic, meta_dict FROM meta'
        rs = influxdb_client.query(query)
        meta_updated_historian = list(rs.get_points())

        assert len(meta_updated_historian) == 3

        for i, d in enumerate(meta_historian):
            assert d["topic"] == meta_updated_historian[i]["topic"]
            assert d["meta_dict"].replace("u", "") == meta_updated_historian[i]["meta_dict"].replace("u", "")

    finally:
        volttron_instance.stop_agent(agent_uuid)
        volttron_instance.remove_agent(agent_uuid)
        clean_database(influxdb_client, clean_updated_database=True)

