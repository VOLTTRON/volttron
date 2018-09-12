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

"""
This file provides helper functions for Influxdb database operation
used in:

:py:class:`services.core.InfluxdbHistorian.influx.historian.InfluxdbHistorian`
"""

import logging
import json
import re
from requests.exceptions import ConnectionError

from dateutil import parser
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError

from volttron.platform.agent.utils import format_timestamp

_log = logging.getLogger(__name__)
__version__ = '0.1'

SUPPORTED_AGG_TYPE = ["COUNT", "DISTINCT", "INTEGRAL", "MEAN", "MEDIAN", "MODE",
                      "SPREAD", "STDDEV", "SUM", "FIRST", "LAST", "MAX", "MIN",
                      "CEILING", "CUMULATIVE_SUM", "DERIVATIVE", "DIFFERENCE",
                      "ELAPSED", "NON_NEGATIVE_DERIVATIVE", "NON_NEGATIVE_DIFFERENCE"]

TOPIC_REGEX = r"^[-\w\/]+$"  # Alphanumeric + '_' + '-' + '/'
AGG_PERIOD_REGEX = r"^\d+[mhdw]$"   # Number + 'm'/'h'/'d'/'w'


def value_type_matching(value_type, value):
    if value_type == 'integer':
        return int(value)
    elif value_type == 'float':
        return float(value)
    elif value_type == 'boolean':
        return bool(value)
    else:
        return str(value)


def get_client(connection_params):
    """
    Connect to InfluxDB client

    :param connection_params: This is what would be provided in the config file
    :return: an instance of InfluxDBClient
    """
    db = connection_params['database']
    host = connection_params['host']
    port = connection_params['port']
    user = connection_params.get('user', None)
    passwd = connection_params.get('passwd', None)

    try:
        client = InfluxDBClient(host, port, user, passwd, db)
        dbs = client.get_list_database()
        if {"name": db} not in dbs:
            _log.error("Database {} does not exist.".format(db))
            return None
    except ConnectionError, err:
        _log.error("Cannot connect to host {}. {}".format(host, err))
        return None
    except InfluxDBClientError, err:
        _log.error(err)
        return None

    return client


def get_all_topics(client):
    """
    Execute query to return the topic list we stored.
    This information should take from 'meta' measurement in the InfluxDB database.

    :param client: Influxdb client we connected in historian_setup method.
    :return: a list of all unique topics published.
    """
    topic_list = []

    query = 'SELECT topic FROM meta'
    rs = client.query(query)
    rs = list(rs.get_points())

    for point in rs:
        topic_list.append(point['topic'])

    return topic_list


def get_topic_values(client, topic_id, start, end,
                     agg_type, agg_period, skip, count, order,
                     use_calendar_time_periods):
    """
    This is a helper for function query_historian in InfluxdbHistorian class.
    Execute query to return a list of values of specific topic(s)
    'topic_id' will be split into 3 tags 'campus', 'building', 'device' and measurement name.


    See Schema description for InfluxDB Historian in README


    Please see
    :py:meth:`volttron.platform.agent.base_historian.BaseQueryHistorianAgent.query_historian`
    for input parameters
    """

    # Make sure topic_id doesn't contain any special character
    if not re.search(TOPIC_REGEX, topic_id):
        raise ValueError("Topic id contains special character(s) that not allowed")

    tags_values = topic_id.rsplit('/', 3)
    measurement = tags_values.pop()
    tags_title = ["device", "building", "campus"]
    tags_conditions = ''

    # Construct tag condition, which is part of WHERE statement
    # E.g: if topic = a/b/c/d, measurement=d and condition of
    #      tag is: "campus='a' and building='b' and device='c'"
    for i, tag in enumerate(tags_values[::-1]):
        tags_conditions += '{}=\'{}\''.format(tags_title[i], tag)
        if i != len(tags_values) - 1:
            tags_conditions += " and "

    if agg_type:
        agg_type = agg_type.upper()
        if agg_type not in SUPPORTED_AGG_TYPE:
            raise ValueError("Aggregation function {} is not supported".format(agg_type))

        query = 'SELECT {}(value) as value FROM {}'.format(agg_type, measurement)
        if tags_conditions:
            query += ' WHERE {}'.format(tags_conditions)
        if not start and not end:
            raise ValueError("Either start time or end time must be provided when executing "
                             "aggregation queries")
    else:
        query = 'SELECT value FROM {}'.format(measurement)
        if tags_conditions:
            query += ' WHERE {}'.format(tags_conditions)

    if start:
        start_time = format_timestamp(start)
        query += ' AND time >= \'%s\'' % start_time
    if end:
        end_time = format_timestamp(end)
        query += ' AND time <= \'%s\'' % end_time

    if agg_period:
        if not re.search(AGG_PERIOD_REGEX, agg_period):
            raise ValueError("Aggregation period {} is in wrong format".format(agg_period))
        elif agg_period[:-1] == 'M':  # Influxdb only support m, h, d and w but not M (month)
            raise InfluxDBClientError("Influxdb hasn't supported GROUP BY month yet")

        if use_calendar_time_periods:
            query += 'GROUP BY time(%s)' % agg_period
        else:
            # @TODO: offset by now() is removed in new version.
            # Using InfluxDB version <1.2.4 to get this work.
            query += 'GROUP BY time(%s, now())' % agg_period
    if order == "LAST_TO_FIRST":
        query += ' ORDER BY time DESC'

    query += ' LIMIT %d' % count
    if skip:
        query += ' OFFSET %d' % skip

    try:
        rs = client.query(query)
        rs = list(rs.get_points())
    except InfluxDBClientError as e:
        _log.error("Query: {}".format(query))
        raise e

    values = []
    for point in rs:
        ts = parser.parse(point['time'])
        ts = format_timestamp(ts)
        values.append((ts, point['value']))

    return values


def get_topic_meta(client, topic_id):
    """
    Execute query to return the meta dictionary of a specific topic (lowercase name)
    This information should take from 'meta' measurement in the InfluxDB database.
    """
    query = 'SELECT meta_dict FROM meta WHERE topic_id=\'%s\'' % topic_id
    rs = client.query(query)
    rs = list(rs.get_points())
    meta = rs[0]['meta_dict'].replace("u'", "\"").replace("'", "\"")
    return json.loads(meta)


def get_all_topic_id_and_meta(client):
    """
    Execute query to return meta dict for all topics.
    This information should take from 'meta' measurement in the InfluxDB database.

    :param client: InfluxDB client connected in historian_setup method.
    :return: a dictionary that maps topic_id to its actual topic name and
             a dictionary that maps each topic to its metadata
    """

    topic_id_map = {}
    meta_dicts = {}

    query = 'SELECT topic, meta_dict, topic_id FROM meta'
    rs = client.query(query)
    rs = list(rs.get_points())

    for point in rs:
        topic_id_map[point['topic_id']] = point['topic']
        meta = point['meta_dict'].replace("u'", "\"").replace("'", "\"")
        meta_dicts[point['topic_id']] = json.loads(meta)

    return topic_id_map, meta_dicts


def insert_meta(client, topic_id, topic, meta, updated_time):
    """
    Insert or update metadata dictionary of a specific topic into the database.
    It will insert into 'meta' table.

    :param client: InfluxDB client connected in historian_setup method.
    :param topic_id: lowercase of topic name
    :param topic: actual topic name that holds the metadata
    :param meta: metadata dictionary need to be inserted into database
    :param updated_time: timestamp that the metadata is inserted into database
    """

    json_body = [
        {
            "measurement": "meta",
            "tags": {
                "topic_id": topic_id
            },
            "time": 0,
            "fields": {
                "topic": topic,
                "meta_dict": str(meta),
                "last_updated": updated_time
            }
        }
    ]

    client.write_points(json_body)


def insert_data_point(client, time, topic_id, source, value, value_string):
    """
    Insert one data point of a specific topic into the database.
    Measurement name is parsed from topic_id.


    See Schema description for InfluxDB Historian in README
    """
    tags_values = topic_id.rsplit('/', 3)
    measurement = tags_values.pop()
    tags_title = ["device", "building", "campus"]
    tags_dict = {}

    for i, tag in enumerate(tags_values[::-1]):
        tags_dict[tags_title[i]] = tag

    tags_dict["source"] = source

    json_body = [
        {
            "measurement": measurement,
            "tags": tags_dict,
            "time": time,
            "fields": {
                "value": value,
                "value_string": value_string
            }
        }
    ]

    try:
        client.write_points(json_body)
    except InfluxDBClientError as e:
        matching = re.findall('type \w+', json.loads(e.content)["error"])
        inserted_type = matching[1]
        existed_type = matching[2]
        _log.warning('{} value exists as {}, while inserted value={} has {}'.format(measurement,
                                                                                    existed_type,
                                                                                    value,
                                                                                    inserted_type))
        existed_type = existed_type[5:]
        try:
            value = value_type_matching(existed_type, value)
        except ValueError:
            _log.warning('Cannot cast value={} {} to type {}. \'value\' field will be empty'.format(value,
                                                                                                    inserted_type,
                                                                                                    existed_type))
            value = None

        json_body[0]["fields"]["value"] = value
        client.write_points(json_body)


def get_topics_by_pattern(client, pattern):
    """

    :param client: InfluxDB client connected in historian_setup method.
    :param pattern: topic_patterns to get matches. Should be a regex pattern
    :return: a list of dictionaries in format:

    .. code-block:: python

            [
                {topic1: topic_id1},
                {topic2: topic_id2},
                ...
            ]

    """
    topics_id_list = []
    query = 'SELECT topic, topic_id FROM meta WHERE topic =~ /%s/' % pattern
    rs = client.query(query)
    rs = list(rs.get_points())

    for point in rs:
        topics_id_list.append({point["topic"]: point["topic_id"]})

    return topics_id_list
