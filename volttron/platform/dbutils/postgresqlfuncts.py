# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2018, 8minutenergy Renewables
#
# Licensed under the Apache License, Version 2.0 (the "License"); you
# may not use this file except in compliance with the License. You may
# obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the License for the specific language governing
# permissions and limitations under the License.
# }}}

import ast
import contextlib
import logging
import copy

import pytz
import psycopg2
from psycopg2 import InterfaceError, ProgrammingError, errorcodes
from psycopg2.sql import Identifier, Literal, SQL
from psycopg2.extras import execute_values

from volttron.platform.agent import utils
from volttron.platform import jsonapi

from .basedb import DbDriver

utils.setup_logging()
_log = logging.getLogger(__name__)


"""
Implementation of PostgreSQL database operation for
:py:class:`sqlhistorian.historian.SQLHistorian` and
:py:class:`sqlaggregator.aggregator.SQLAggregateHistorian`
For method details please refer to base class
:py:class:`volttron.platform.dbutils.basedb.DbDriver`
"""
class PostgreSqlFuncts(DbDriver):
    def __init__(self, connect_params, table_names):
        if table_names:
            self.data_table = table_names['data_table']
            self.topics_table = table_names['topics_table']
            self.meta_table = table_names['meta_table']
            self.agg_topics_table = table_names.get('agg_topics_table')
            self.agg_meta_table = table_names.get('agg_meta_table')
        connect_params = copy.deepcopy(connect_params)
        if "timescale_dialect" in connect_params:
            self.timescale_dialect = connect_params.get("timescale_dialect", False)
            del connect_params["timescale_dialect"]
        else:
            self.timescale_dialect = False
        def connect():
            connection = psycopg2.connect(**connect_params)
            connection.autocommit = True
            with connection.cursor() as cursor:
                cursor.execute('SET TIME ZONE UTC')
            return connection
        connect.__name__ = 'psycopg2'
        super(PostgreSqlFuncts, self).__init__(connect)

    @contextlib.contextmanager
    def bulk_insert(self):
        """
        This function implements the bulk insert requirements for postgresql historian by overriding the
        DbDriver::bulk_insert() in basedb.py and yields necessary data insertion method needed for bulk inserts

        :yields: insert method
        """
        records = []

        def insert_data(ts, topic_id, data):
            """
            Inserts data records to the list

            :param ts: time stamp
            :type string
            :param topic_id: topic ID
            :type string
            :param data: data value
            :type any valid JSON serializable value
            :return: Returns True after insert
            :rtype: bool
            """
            value = jsonapi.dumps(data)
            records.append((ts, topic_id, value))
            return True

        yield insert_data

        if records:
            query = SQL('INSERT INTO {} VALUES %s '
                        'ON CONFLICT (ts, topic_id) DO UPDATE '
                        'SET value_string = EXCLUDED.value_string').format(
                            Identifier(self.data_table))
            execute_values(self.cursor(), query, records)

    @contextlib.contextmanager
    def bulk_insert_meta(self):
        """
        This function implements the bulk insert requirements for Redshift historian by overriding the
        DbDriver::bulk_insert_meta() in basedb.py and yields necessary data insertion method needed for bulk inserts

        :yields: insert method
        """
        records = []

        def insert_meta(topic_id, metadata):
            """
            Inserts metadata records to the list

            :param topic_id: topic ID
            :type string
            :param metadata: metadata dictionary
            :type dict
            :return: Returns True after insert
            :rtype: bool
            """
            value = jsonapi.dumps(metadata)
            records.append((topic_id, value))
            return True

        yield insert_meta

        if records:
            _log.debug(f"###DEBUG bulk inserting meta of len {len(records)}")
            _log.debug(f"###DEBUG bulk inserting meta of len {records}")

            query = SQL('INSERT INTO {} VALUES %s'
                        'ON CONFLICT (topic_id) DO UPDATE '
                        'SET metadata = EXCLUDED.metadata').format(
                            Identifier(self.meta_table))
            execute_values(self.cursor(), query, records)

    def rollback(self):
        try:
            return super(PostgreSqlFuncts, self).rollback()
        except InterfaceError:
            return False

    def setup_historian_tables(self):
        rows = self.select(f"""SELECT table_name FROM information_schema.tables
                            WHERE table_catalog = 'test_historian' and table_schema = 'public' 
                            AND table_name = '{self.data_table}'""")
        if rows:
            _log.debug("Found table {}. Historian table exists".format(
                self.data_table))
            rows = self.select(f"""SELECT column_name FROM information_schema.columns
                                WHERE table_name = '{self.topics_table}' and column_name = 'metadata'""")
            if rows:
                # metadata is in topics table
                self.meta_table = self.topics_table
        else:
            self.execute_stmt(SQL(
                'CREATE TABLE IF NOT EXISTS {} ('
                    'ts TIMESTAMP NOT NULL, '
                    'topic_id INTEGER NOT NULL, '
                    'value_string TEXT NOT NULL, '
                    'UNIQUE (topic_id, ts)'
                ')').format(Identifier(self.data_table)))
            if self.timescale_dialect:
                _log.debug("trying to create hypertable")
                self.execute_stmt(SQL(
                    "SELECT create_hypertable({}, 'ts', if_not_exists => true)").format(
                    Literal(self.data_table)))
                self.execute_stmt(SQL(
                    'CREATE INDEX IF NOT EXISTS {} ON {} (topic_id, ts)').format(
                    Identifier(f"idx_{self.data_table}"),
                    Identifier(self.data_table))
                )
            else:
                self.execute_stmt(SQL(
                    'CREATE INDEX IF NOT EXISTS {} ON {} (ts ASC)').format(
                    Identifier('idx_' + self.data_table),
                    Identifier(self.data_table)))

            self.execute_stmt(SQL(
                'CREATE TABLE IF NOT EXISTS {} ('
                    'topic_id SERIAL PRIMARY KEY NOT NULL, '
                    'topic_name VARCHAR(512) NOT NULL, '
                    'metadata TEXT, '
                    'UNIQUE (topic_name)'
                ')').format(Identifier(self.topics_table)))
            # metadata is in topics table
            self.meta_table = self.topics_table
            self.commit()

    def setup_aggregate_historian_tables(self):

        self.execute_stmt(SQL(
            'CREATE TABLE IF NOT EXISTS {} ('
                'agg_topic_id SERIAL PRIMARY KEY NOT NULL, '
                'agg_topic_name VARCHAR(512) NOT NULL, '
                'agg_type VARCHAR(20) NOT NULL, '
                'agg_time_period VARCHAR(20) NOT NULL, '
                'UNIQUE (agg_topic_name, agg_type, agg_time_period)'
            ')').format(Identifier(self.agg_topics_table)))
        self.execute_stmt(SQL(
            'CREATE TABLE IF NOT EXISTS {} ('
                'agg_topic_id INTEGER PRIMARY KEY NOT NULL, '
                'metadata TEXT NOT NULL'
            ')').format(Identifier(self.agg_meta_table)))
        self.commit()

    def query(self, topic_ids, id_name_map, start=None, end=None, skip=0,
              agg_type=None, agg_period=None, count=None,
              order='FIRST_TO_LAST'):
        if agg_type and agg_period:
            table_name = agg_type + '_' + agg_period
            value_col = 'agg_value'
        else:
            table_name = self.data_table
            value_col = 'value_string'

        topic_id = Literal(0)
        query = [SQL(
            '''SELECT to_char(ts, 'YYYY-MM-DD"T"HH24:MI:SS.USOF:00'), ''' + value_col + ' \n'
            'FROM {}\n'
            'WHERE topic_id = {}'
        ).format(Identifier(table_name), topic_id)]
        if start and start.tzinfo != pytz.UTC:
            start = start.astimezone(pytz.UTC)
        if end and end.tzinfo != pytz.UTC:
            end = end.astimezone(pytz.UTC)
        if start and start == end:
            query.append(SQL(' AND ts = {}').format(Literal(start)))
        else:
            if start:
                query.append(SQL(' AND ts >= {}').format(Literal(start)))
            if end:
                query.append(SQL(' AND ts < {}').format(Literal(end)))
        query.append(SQL('ORDER BY ts {}'.format(
            'DESC' if order == 'LAST_TO_FIRST' else 'ASC')))
        if skip or count:
            query.append(SQL('LIMIT {} OFFSET {}').format(
                Literal(None if not count or count < 0 else count),
                Literal(None if not skip or skip < 0 else skip)))
        query = SQL('\n').join(query)
        values = {}
        if value_col == 'agg_value':
            for topic_id._wrapped in topic_ids:
                name = id_name_map[topic_id.wrapped]
                with self.select(query, fetch_all=False) as cursor:
                    values[name] = [(ts, value)
                                    for ts, value in cursor]
        else:
            for topic_id._wrapped in topic_ids:
                name = id_name_map[topic_id.wrapped]
                with self.select(query, fetch_all=False) as cursor:
                    values[name] = [(ts, jsonapi.loads(value))
                                    for ts, value in cursor]
        return values

    def insert_topic(self, topic, **kwargs):
        meta = kwargs.get('metadata')
        with self.cursor() as cursor:
            if self.meta_table == self.topics_table and topic and meta:
                cursor.execute(self.insert_topic_and_meta_query(), (topic, jsonapi.dumps(meta)))
            else:
                cursor.execute(self.insert_topic_query(), {'topic': topic})
            return cursor.fetchone()[0]

    def insert_agg_topic(self, topic, agg_type, agg_time_period):
        with self.cursor() as cursor:
            cursor.execute(self.insert_agg_topic_stmt(),
                           (topic, agg_type, agg_time_period))
            return cursor.fetchone()[0]

    def insert_meta_query(self):
        return SQL(
            'INSERT INTO {} VALUES (%s, %s) '
            'ON CONFLICT (topic_id) DO UPDATE '
            'SET metadata = EXCLUDED.metadata').format(
            Identifier(self.meta_table))

    def insert_data_query(self):
        return SQL(
            'INSERT INTO {} VALUES (%s, %s, %s) '
            'ON CONFLICT (ts, topic_id) DO UPDATE '
            'SET value_string = EXCLUDED.value_string').format(
            Identifier(self.data_table))

    def insert_topic_query(self):
        return SQL(
            'INSERT INTO {} (topic_name) VALUES (%(topic)s) '
            'RETURNING topic_id').format(Identifier(self.topics_table))

    def insert_topic_and_meta_query(self):
        return SQL(
            'INSERT INTO {} (topic_name, metadata) VALUES (%s, %s) '
            'RETURNING topic_id').format(Identifier(self.topics_table))

    def update_topic_query(self):
        return SQL(
            'UPDATE {} SET topic_name = %s '
            'WHERE topic_id = %s').format(Identifier(self.topics_table))

    def update_topic_and_meta_query(self):
        return SQL(
            'UPDATE {} SET topic_name = %s , metadata= %s '
            'WHERE topic_id = %s').format(Identifier(self.topics_table))

    def update_meta_query(self):
        return SQL(
            'UPDATE {} SET metadata= %s '
            'WHERE topic_id = %s').format(Identifier(self.meta_table))

    def get_aggregation_list(self):
        return ['AVG', 'MIN', 'MAX', 'COUNT', 'SUM', 'BIT_AND', 'BIT_OR',
                'BOOL_AND', 'BOOL_OR', 'MEDIAN', 'STDDEV', 'STDDEV_POP',
                'STDDEV_SAMP', 'VAR_POP', 'VAR_SAMP', 'VARIANCE']

    def insert_agg_topic_stmt(self):
        return SQL(
            'INSERT INTO {} (agg_topic_name, agg_type, agg_time_period) '
            'VALUES (%s, %s, %s)'
            'RETURNING agg_topic_id').format(Identifier(self.agg_topics_table))

    def update_agg_topic_stmt(self):
        return SQL(
            'UPDATE {} SET agg_topic_name = %s '
            'WHERE agg_topic_id = %s').format(
            Identifier(self.agg_topics_table))

    def replace_agg_meta_stmt(self):
        return SQL(
            'INSERT INTO {} VALUES (%s, %s) '
            'ON CONFLICT (agg_topic_id) DO UPDATE '
            'SET metadata = EXCLUDED.metadata').format(
            Identifier(self.agg_meta_table))

    def get_topic_map(self):
        query = SQL(
            'SELECT topic_id, topic_name, LOWER(topic_name) '
            'FROM {}').format(Identifier(self.topics_table))
        rows = self.select(query)
        id_map = {key: tid for tid, _, key in rows}
        name_map = {key: name for _, name, key in rows}
        return id_map, name_map

    def get_topic_meta_map(self):
        query = SQL(
            'SELECT topic_id, metadata '
            'FROM {}').format(Identifier(self.meta_table))
        rows = self.select(query)
        meta_map = {tid: jsonapi.loads(meta) if meta else None for tid, meta in rows}
        return meta_map

    def get_agg_topics(self):
        query = SQL(
            'SELECT agg_topic_name, agg_type, agg_time_period, metadata '
            'FROM {} as t, {} as m '
            'WHERE t.agg_topic_id = m.agg_topic_id').format(
            Identifier(self.agg_topics_table), Identifier(self.agg_meta_table))
        try:
            rows = self.select(query)
        except ProgrammingError as exc:
            if exc.pgcode == errorcodes.UNDEFINED_TABLE:
                return []
            raise
        return [(name, type_, tp, ast.literal_eval(meta)['configured_topics'])
                for name, type_, tp, meta in rows]

    def get_agg_topic_map(self):
        query = SQL(
            'SELECT agg_topic_id, LOWER(agg_topic_name), '
                'agg_type, agg_time_period '
            'FROM {}').format(Identifier(self.agg_topics_table))
        try:
            rows = self.select(query)
        except ProgrammingError as exc:
            if exc.pgcode == errorcodes.UNDEFINED_TABLE:
                return {}
            raise
        return {(name, type_, tp): id_ for id_, name, type_, tp in rows}

    def query_topics_by_pattern(self, topic_pattern):
        query = SQL(
            'SELECT topic_name, topic_id '
            'FROM {} '
            'WHERE topic_name ~* %s').format(Identifier(self.topics_table))
        return dict(self.select(query, (topic_pattern,)))

    def create_aggregate_store(self, agg_type, agg_time_period):
        table_name = agg_type + '_' + agg_time_period
        self.execute_stmt(SQL(
            'CREATE TABLE IF NOT EXISTS {} ('
                'ts TIMESTAMP NOT NULL, '
                'topic_id INTEGER NOT NULL, '
                'agg_value DOUBLE PRECISION NOT NULL, '
                'topics_list TEXT, '
                'UNIQUE (ts, topic_id)'
            ')').format(Identifier(table_name)))
        self.execute_stmt(SQL(
            'CREATE INDEX IF NOT EXISTS {} ON {} (ts ASC)').format(
            Identifier('idx_' + table_name),
            Identifier(table_name)))
        self.commit()

    def insert_aggregate_stmt(self, table_name):
        return SQL(
            'INSERT INTO {} VALUES (%s, %s, %s, %s) '
            'ON CONFLICT (ts, topic_id) DO UPDATE '
            'SET agg_value = EXCLUDED.agg_value, '
                'topics_list = EXCLUDED.topics_list').format(
            Identifier(table_name))

    def collect_aggregate(self, topic_ids, agg_type, start=None, end=None):
        if (isinstance(agg_type, str) and
                agg_type.upper() not in self.get_aggregation_list()):
            raise ValueError('Invalid aggregation type {}'.format(agg_type))
        query = [
            SQL('SELECT {}(CAST(value_string as float)), COUNT(value_string)'.format(
                agg_type.upper())),
            SQL('FROM {}').format(Identifier(self.data_table)),
            SQL('WHERE topic_id in ({})').format(
                SQL(', ').join(Literal(tid) for tid in topic_ids)),
        ]
        if start is not None:
            query.append(SQL(' AND ts >= {}').format(Literal(start)))
        if end is not None:
            query.append(SQL(' AND ts < {}').format(Literal(end)))
        rows = self.select(SQL('\n').join(query))
        return rows[0] if rows else (0, 0)
