# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
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

import logging
from multiprocessing import cpu_count # used to default number of shards.
from pkg_resources import parse_version


def select_all_topics_query(schema):
    return "SELECT topic FROM {schema}.topic".format(schema=schema)


def insert_topic_query(schema):
    return "INSERT INTO {schema}.topic (topic) VALUES(?)".format(schema=schema)


def insert_data_query(schema):
    query = """INSERT INTO {schema}.data
              (ts, topic, source, string_value, meta)
              VALUES(?,?,?,?,?)
              on duplicate key update
                source = source,
                string_value = string_value,
                meta = meta
              """.format(schema=schema)
    return query.replace("\n", " ")


def drop_schema(connection, truncate=False, schema=None):
    _log = logging.getLogger(__name__)
    if not schema:
        _log.error("Invalid schema passed to drop schema function")
        return
    tables = ["data", "topic"]
    cursor = connection.cursor()
    for t in tables:
        if truncate:
            query = "DELETE FROM {schema}.{table}".format(schema=schema,
                                                          table=t)
        else:
            query = "DROP TABLE {schema}.{table}".format(schema=schema,
                                                         table=t)
        cursor.execute(query)


def create_schema(connection, schema="historian", num_replicas='0-1',
                  num_shards=6, use_v2=True):
    _log = logging.getLogger(__name__)
    _log.debug("Creating crate tables if necessary.")
    # crate can take a string parameter such as 0-1 rather than just a plain
    # integer for writing data.
    try:
        num_replicas = int(num_replicas)
    except ValueError:
        num_replicas = "'{}'".format(num_replicas)

    create_queries = []

    data_table_v1 = """
        CREATE TABLE IF NOT EXISTS {schema}.data(
            source string,
            topic string primary key,
            ts timestamp NOT NULL primary key,
            string_value string,
            meta object,
            -- Dynamically generated column that will either be a double
            -- or a NULL based on the value in the string_value column.
            double_value as  try_cast(string_value as double),
            -- Full texted search index on the topic string
            INDEX topic_ft using fulltext (topic),
            -- must be part of primary key because of partitioning on monthly
            -- table and the column is set on the table.
            month as date_trunc('month', ts) primary key)
        partitioned by (month)
        CLUSTERED INTO {num_shards} SHARDS
        with ("number_of_replicas" = {num_replicas})
    """

    tokenizer = """
        CREATE ANALYZER "tree" (
            TOKENIZER tree WITH (
                type = 'path_hierarchy',
                delimiter = '/'
            )
        )"""

    data_table_v2 = """
        CREATE TABLE IF NOT EXISTS "{schema}"."data"(
            source string,
            topic string primary key,
            ts timestamp NOT NULL primary key,
            string_value string,
            meta object,
            -- Dynamically generated column that will either be a double
            -- or a NULL based on the value in the string_value column.
            double_value as  try_cast(string_value as double),
            INDEX "taxonomy" USING FULLTEXT (topic) WITH (analyzer='tree'),
            -- Full texted search index on the topic string
            INDEX topic_ft using fulltext (topic),
            week_generated TIMESTAMP GENERATED ALWAYS AS date_trunc('week', ts) primary key) -- ,
            -- must be part of primary key because of partitioning on monthly
            -- table and the column is set on the table.
            -- month as date_trunc('month', ts) primary key)
        CLUSTERED BY (topic) INTO {num_shards} SHARDS PARTITIONED BY (week_generated)
        with ("number_of_replicas" = {num_replicas})
    """

    topic_table = """
    
        CREATE TABLE IF NOT EXISTS {schema}.topic(
            topic string PRIMARY KEY
        )
        CLUSTERED INTO 3 SHARDS
    """

    if use_v2:
        create_queries.append(tokenizer)
        create_queries.append(data_table_v2)
    else:
        create_queries.append(data_table_v1)

    create_queries.append(topic_table)

    try:
        cursor = connection.cursor()
        for t in create_queries:
            cursor.execute(t.format(schema=schema, num_replicas=num_replicas,
                                    num_shards=num_shards))
    except Exception as ex:
        _log.error("Exception creating tables.")
        _log.error(ex.args)
    finally:
        cursor.close()
