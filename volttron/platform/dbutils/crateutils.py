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

# without this we can get random batch process query failure with the error
# 'Cannot switch to different thread'
import socket
from importlib import reload
reload(socket)
import logging



def select_all_topics_query(schema, table_name):
    return "SELECT topic FROM {schema}.{table}".format(schema=schema, table=table_name)


def select_topics_metadata_query(schema, table_name):
    return "SELECT topic, meta FROM {schema}.{table}".format(schema=schema, table=table_name)


def insert_topic_query(schema, table_name):
    return "INSERT INTO {schema}.{table} (topic, meta) VALUES(?, ?)".format(schema=schema, table=table_name)


def update_topic_query(schema, table_name):
    return "UPDATE {schema}.{table} SET meta = ? WHERE topic ~* ?".format(schema=schema, table=table_name)


def insert_data_query(schema, table_name):
    query = """INSERT INTO {schema}.{table}
              (ts, topic, source, string_value, meta)
              VALUES(?,?,?,?,?)
              on duplicate key update
                source = source,
                string_value = string_value,
                meta = meta
              """.format(schema=schema, table=table_name)
    return query.replace("\n", " ")


def drop_schema(connection, truncate_tables, schema=None, truncate=True):
    _log = logging.getLogger(__name__)

    if not schema:
        _log.error("Invalid schema passed to drop schema function")
        return

    cursor = connection.cursor()
    cursor.execute("SHOW tables in {}".format(schema))
    result = cursor.fetchall()
    tables = [t[0] for t in result]
    cursor.close()
    cursor = connection.cursor()

    for t in truncate_tables:
        if t not in tables:
            continue
        if truncate:
            query = "DELETE FROM {schema}.{table}".format(schema=schema,
                                                          table=t)
        else:
            query = "DROP TABLE {schema}.{table}".format(schema=schema,
                                                         table=t)
        _log.debug("Droping table:{schema}.{table}".format(schema=schema,
                                                         table=t))
        cursor.execute(query)


def create_schema(connection, schema="historian", table_names={}, num_replicas='0-1',
                  num_shards=6, use_v2=True):
    _log = logging.getLogger(__name__)
    _log.debug("Creating crate tables if necessary.")
    # crate can take a string parameter such as 0-1 rather than just a plain
    # integer for writing data.
    try:
        num_replicas = int(num_replicas)
    except ValueError:
        num_replicas = "'{}'".format(num_replicas)
    data_table = table_names.get("data_table", "data")
    topic_table = table_names.get("topics_table", "topics")

    create_queries = []

    data_table_v1 = """
        CREATE TABLE IF NOT EXISTS {schema}.{data_table}(
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
        CREATE TABLE IF NOT EXISTS "{schema}".{data_table}(
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

    topic_table_query = """
    
        CREATE TABLE IF NOT EXISTS {schema}.{topic_table}(
            topic string PRIMARY KEY,
            meta object
        )
        CLUSTERED INTO 3 SHARDS
    """

    if use_v2:
        create_queries.append(tokenizer)
        create_queries.append(data_table_v2)
    else:
        create_queries.append(data_table_v1)

    cursor = connection.cursor()
    stmt = "SHOW columns in {} in {}".format(topic_table, schema)
    cursor.execute(stmt)
    result = cursor.fetchall()
    columns = [t[0] for t in result]
    _log.debug("result of {} is  {}".format(stmt, columns))
    cursor.close()

    if len(columns) == 0:
        # no such table. create
        _log.debug("Creating topic table")
        create_queries.append(topic_table_query.format(schema=schema, topic_table=topic_table))
    elif len(columns) == 1:
        _log.info("topics table created by cratedb version < 3.0. Alter to add metadata column")
        #topics table created by cratedb version < 3.0. Alter to add metadata column
        create_queries.append("ALTER TABLE {schema}.{topic_table} ADD COLUMN meta object".format(
            schema=schema, topic_table=topic_table))
    else:
        _log.debug("topics table {}.{} exists".format(schema, topic_table))

    try:
        cursor = connection.cursor()
        for t in create_queries:
            cursor.execute(t.format(schema=schema, data_table=data_table,
                                    num_replicas=num_replicas, num_shards=num_shards))
    except Exception as ex:
        _log.error("Exception creating tables.")
        _log.error(ex.args)
    finally:
        cursor.close()
