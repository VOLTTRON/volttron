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
import subprocess
import shutil
import os
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime, timezone, timedelta

import pytz
import psycopg2
from psycopg2 import InterfaceError, ProgrammingError, errorcodes
from psycopg2.sql import Identifier, Literal, SQL
from psycopg2.extras import execute_values
import gevent

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
        self.db_name = connect_params.get('dbname')
        if table_names:
            self.data_table = table_names['data_table']
            self.topics_table = table_names['topics_table']
            self.meta_table = table_names['meta_table']
            self.agg_topics_table = table_names.get('agg_topics_table')
            self.agg_meta_table = table_names.get('agg_meta_table')
        self.connect_params = copy.deepcopy(connect_params)
        if "timescale_dialect" in connect_params:
            self.timescale_dialect = connect_params.get("timescale_dialect", False)
            del self.connect_params["timescale_dialect"]
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
                            WHERE table_catalog = '{self.db_name}' and table_schema = 'public'
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
                'PRIMARY KEY (topic_id, ts)'
                ')').format(Identifier(self.data_table)))
            if self.timescale_dialect:
                _log.debug("trying to create hypertable")
                self.execute_stmt(SQL(
                    "SELECT create_hypertable({}, 'ts', if_not_exists => true)").format(
                    Literal(self.data_table)))
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

        meta_map = {}
        for tid, meta in rows:
            if meta:
                if isinstance(meta, dict):
                    meta_map[tid] = meta
                else:
                    meta_map[tid] = jsonapi.loads(meta)
            else:
                meta_map[tid] = None
            
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


    def check_pg_repack_availability(self):
        """Check if pg_repack is installed and compatible"""
        return False, "Returning False for now. Yet to test with pg_repack"
        # try:
        #     # Check if pg_repack binary exists
        #     result = subprocess.run(['pg_repack', '--version'],
        #                             capture_output=True, text=True, timeout=10)
        #
        #     if result.returncode != 0:
        #         return False, "pg_repack binary not found"
        #
        #     # Parse pg_repack version
        #     repack_version_match = re.search(r'pg_repack\s+([\d\.]+)', result.stdout)
        #     repack_ver = repack_version_match.group(1) if repack_version_match else None
        #
        #     if not repack_ver:
        #         return False, "Could not parse pg_repack version"
        #
        #     # Check server extension availability
        #     ext_avail = self.select(
        #         "SELECT installed_version, default_version FROM pg_available_extensions WHERE name='pg_repack'",
        #         fetch_all=True)
        #     if not ext_avail:
        #         return False, "pg_repack extension not available on server"
        #
        #     # Check if extension is installed
        #     ext_installed = self.select("SELECT extversion FROM pg_extension WHERE extname='pg_repack'", fetch_all=True)
        #     if not ext_installed:
        #         return False, "pg_repack extension not installed on server (CREATE EXTENSION pg_repack required)"
        #
        #     # Check PostgreSQL version compatibility
        #     pg_version_result = self.select("SELECT version()", fetch_all=True)
        #     pg_version_str = pg_version_result[0][0]
        #     pg_version_match = re.search(r'PostgreSQL\s+(\d+)', pg_version_str)
        #
        #     if not pg_version_match:
        #         return False, "Could not parse PostgreSQL version"
        #
        #     pg_major = int(pg_version_match.group(1))
        #
        #     # Version compatibility check using packaging.version for proper comparison
        #     repack_version_obj = version.parse(repack_ver)
        #
        #     if pg_major >= 11 and repack_version_obj >= version.parse("1.4.0"):
        #         return True, f"pg_repack client {repack_ver}, server ext {ext_installed[0][0]}, PostgreSQL {pg_major}"
        #     elif pg_major >= 9 and repack_version_obj >= version.parse("1.3.0"):
        #         return True, f"pg_repack client {repack_ver}, server ext {ext_installed[0][0]}, PostgreSQL {pg_major}"
        #     else:
        #         return False, f"pg_repack {repack_ver} not compatible with PostgreSQL {pg_major}"
        #
        # except Exception as e:
        #     return False, f"pg_repack check failed: {e}"

    def run_pg_repack(self, connection_params):
        """Run pg_repack on data table"""

        def _run_pg_repack_subprocess():
            """Run pg_repack in subprocess within thread"""
            try:
                cmd = [
                    'pg_repack',
                    f"--host={connection_params.get('host', 'localhost')}",
                    f"--port={connection_params.get('port', 5432)}",
                    f"--username={connection_params['user']}",
                    f"--dbname={connection_params['database']}",
                    f'--table=public.{self.data_table}',
                    '--wait-timeout=3600',
                    '--no-order',
                    '--jobs=2'
                ]

                env = os.environ.copy()
                env['PGPASSWORD'] = connection_params['password']

                result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=3600)
                return result.returncode, result.stdout, result.stderr

            except Exception as e:
                return -1, "", str(e)

        try:
            # Check availability first
            is_available, message = self.check_pg_repack_availability()
            if not is_available:
                _log.warning(f"pg_repack not available: {message}")
                return False

            _log.info(f"pg_repack available: {message}")
            _log.info("Starting pg_repack...")

            # Run pg_repack in thread to avoid event loop conflicts
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_run_pg_repack_subprocess)
                try:
                    returncode, stdout, stderr = future.result(timeout=3700)  # Slightly longer than subprocess timeout
                except FutureTimeoutError:
                    _log.error("pg_repack timed out")
                    return False

            if returncode == 0:
                _log.info("pg_repack completed successfully")
                return True
            else:
                _log.error(f"pg_repack failed: {stderr}")
                return False

        except Exception as e:
            _log.warning(f"pg_repack execution failed: {e}")
            return False


    def get_database_size_gb(self):
        """Get database size in GB"""
        results = self.select("SELECT pg_database_size(current_database()) / (1024.0 * 1024.0 * 1024.0);",
                              fetch_all=True)
        size_gb = results[0][0]
        _log.debug(f"Current DB size in GB is {float(size_gb)}")
        return float(size_gb)


    def get_table_metrics(self, need_exact_count=False):
        """Get comprehensive table size metrics"""
        query = f"""
           SELECT  
               pg_total_relation_size('public.{self.data_table}')::bigint AS total_bytes,  
               pg_relation_size('public.{self.data_table}')::bigint AS heap_bytes,  
               pg_indexes_size('public.{self.data_table}')::bigint AS idx_bytes,  
               (SELECT reltuples FROM pg_class WHERE oid = 'public.{self.data_table}'::regclass) AS reltuples
           """
        result = self.select(query, fetch_all=True)[0]

        # Only do COUNT(*) when explicitly needed to avoid full table scans
        actual_count = None
        if need_exact_count:
            count_result = self.select(f"SELECT COUNT(*) FROM {self.data_table}", fetch_all=True)
            actual_count = count_result[0][0]

        return {
            'total_bytes': result[0],
            'heap_bytes': result[1],
            'idx_bytes': result[2],
            'reltuples': max(result[3], 1),  # Avoid division by zero, use minimum of 1
            'actual_count': actual_count
        }


    def check_disk_space_for_repack(self, target_bytes):
        """Check if there's enough disk space for pg_repack/CTAS"""
        try:
            # Get data directory
            data_dir_result = self.select("SHOW data_directory", fetch_all=True)
            data_dir = data_dir_result[0][0]

            # Get tablespace for data table
            tbl_tsp_result = self.select(
                f"SELECT reltablespace FROM pg_class WHERE oid = 'public.{self.data_table}'::regclass", fetch_all=True)
            tbl_tsp_oid = tbl_tsp_result[0][0]

            # Get tablespace location
            if tbl_tsp_oid == 0:
                tbl_fs = data_dir
            else:
                tbl_location_result = self.select("SELECT pg_tablespace_location(%s)", (tbl_tsp_oid,), fetch_all=True)
                tbl_fs = tbl_location_result[0][0] or data_dir

            #wal_fs = os.path.join(data_dir, 'pg_wal')

            # Check free space
            free_tbl = shutil.disk_usage(tbl_fs).free
            #free_wal = shutil.disk_usage(wal_fs).free

            # Need space for: final table size + some overhead
            required_free = int(target_bytes * 1.2)  # 20% overhead

            #return (free_tbl >= required_free and free_wal >= required_free), free_tbl, free_wal, required_free
            return (free_tbl >= required_free), free_tbl, 0, required_free

        except Exception as e:
            _log.warning(f"Could not check disk space: {e}")
            return False, 0, 0, 0


    def estimate_vacuum_full_time(self, table_size_gb):
        """Estimate VACUUM FULL duration based on table size"""
        # Rule of thumb: ~1-2 minutes per GB for VACUUM FULL on average hardware
        estimated_minutes = max(1, int(table_size_gb * 1.5))
        return estimated_minutes


    def cleanup_temp_resources(self):
        """Clean up any temporary tables left from failed operations"""
        try:
            # Clean up potential leftover tables
            cleanup_tables = [f'{self.data_table}_new', f'{self.data_table}_temp', f'{self.data_table}_old']
            for table in cleanup_tables:
                try:
                    self.execute_stmt(f"DROP TABLE IF EXISTS public.{table}")
                    _log.debug(f"Cleaned up table: {table}")
                except:
                    pass
            self.commit()
        except Exception as e:
            _log.warning(f"Error during resource cleanup: {e}")

    def manual_table_rebuild(self, keep_cutoff_timestamp=None):
        """
        Rebuild public.{self.data_table} using CTAS + swap.

        Key points:
          - Copy schema without table-level constraints or indexes
          - Build temp-named unique index and attach a temp-named UNIQUE constraint
          - Build temp-named ts index
          - Swap, drop old table (drops its indexes)
          - Rename the new indexes/constraint to canonical names:
              * UNIQUE constraint -> data_topic_id_ts_key
              * unique index     -> data_topic_id_ts_key (same name as constraint is OK)
              * ts index         -> idx_data

        Readers remain online; writers are blocked during copy (SHARE lock) and briefly during swap.
        """
        try:
            _log.info("Starting manual table rebuild (CTAS + swap, temp constraint/index names)")

            # Clean any leftover temp objects from previous runs
            self.cleanup_temp_resources()

            # Names
            tbl = f"public.{self.data_table}"
            tbl_new = f"public.{self.data_table}_new"
            tbl_old = f"public.{self.data_table}_old"

            # Unique suffix for temp names to avoid collisions
            suf = uuid.uuid4().hex  # e.g., 'a1b2c3...'

            # Temp names for constraint and indexes
            tmp_con_name = f"data_topic_id_ts_key_{suf}"
            uniq_idx_name = f"{self.data_table}_topic_id_ts_{suf}"
            ts_idx_name = f"{self.data_table}_ts_{suf}"

            # Begin transactional rebuild
            self.execute_stmt("BEGIN")

            # Block writers, keep readers
            self.execute_stmt(f"LOCK TABLE {tbl} IN SHARE MODE")

            # Copy schema without table-level constraints/indexes
            # (NOT NULL and defaults are preserved as part of column definitions)
            self.execute_stmt(
                f"CREATE TABLE {tbl_new} "
                f"(LIKE {tbl} INCLUDING DEFAULTS INCLUDING STORAGE "
                f"EXCLUDING CONSTRAINTS EXCLUDING INDEXES)"
            )

            # Copy rows to keep
            if keep_cutoff_timestamp is not None:
                self.execute_stmt(
                    f"INSERT INTO {tbl_new} SELECT * FROM {tbl} WHERE ts >= %s",
                    (keep_cutoff_timestamp,),
                )
            else:
                self.execute_stmt(f"INSERT INTO {tbl_new} SELECT * FROM {tbl}")

            # Build a unique index on (topic_id, ts) with a TEMP name
            self.execute_stmt(
                f"CREATE UNIQUE INDEX {uniq_idx_name} ON {tbl_new} (topic_id, ts)"
            )

            # Attach a TEMP-NAMED UNIQUE constraint using that index.
            # IMPORTANT: Use a temp constraint name to avoid a collision with the live table's index name.
            self.execute_stmt(
                f"ALTER TABLE {tbl_new} "
                f"ADD CONSTRAINT {tmp_con_name} UNIQUE USING INDEX {uniq_idx_name}"
            )
            # Note: Postgres will typically rename the index to match the constraint name
            # (i.e., uniq_idx_name -> tmp_con_name). We handle both names later when renaming.

            # Build the secondary index on ts (temp name)
            self.execute_stmt(f"CREATE INDEX {ts_idx_name} ON {tbl_new} (ts)")

            # Brief exclusive lock to swap tables atomically
            self.execute_stmt(f"LOCK TABLE {tbl} IN ACCESS EXCLUSIVE MODE")
            self.execute_stmt(f"ALTER TABLE {tbl} RENAME TO {self.data_table}_old")
            self.execute_stmt(f"ALTER TABLE {tbl_new} RENAME TO {self.data_table}")

            # Commit: new table is now live
            self.commit()

            # Drop old table and its indexes (outside txn to minimize lock time)
            try:
                self.execute_stmt(f"DROP TABLE {tbl_old}")
                self.commit()
            except Exception as e:
                _log.warning(f"Failed to drop old table (rebuild still successful): {e}")

            # Rename the new indexes/constraint to canonical names (now that old names are free)

            # 1) Rename the ts index to idx_data
            try:
                # Most likely name is ts_idx_name; if not found, nothing happens
                self.execute_stmt(
                    f'ALTER INDEX IF EXISTS public."{ts_idx_name}" RENAME TO "idx_data"'
                )
                self.commit()
            except Exception as e:
                _log.warning(f'Renaming ts index "{ts_idx_name}" -> "idx_data" failed: {e}')

            # 2) Rename the UNIQUE constraint to canonical name
            try:
                self.execute_stmt(
                    f'ALTER TABLE public."{self.data_table}" '
                    f'RENAME CONSTRAINT "{tmp_con_name}" TO "data_topic_id_ts_key"'
                )
                self.commit()
            except Exception as e:
                _log.warning(
                    f'Renaming constraint "{tmp_con_name}" -> "data_topic_id_ts_key" failed: {e}'
                )

            # 3) Rename the underlying unique index to canonical name
            # The index name is either uniq_idx_name or (more likely) tmp_con_name (if PG auto-renamed it).
            try:
                self.execute_stmt(
                    f'ALTER INDEX IF EXISTS public."{tmp_con_name}" RENAME TO "data_topic_id_ts_key"'
                )
                self.commit()
            except Exception:
                # If it wasn't auto-renamed to tmp_con_name, try the original uniq_idx_name
                try:
                    self.execute_stmt(
                        f'ALTER INDEX IF EXISTS public."{uniq_idx_name}" RENAME TO "data_topic_id_ts_key"'
                    )
                    self.commit()
                except Exception as e2:
                    _log.warning(
                        f'Renaming unique index to "data_topic_id_ts_key" failed: {e2}'
                    )

            _log.info("Manual table rebuild completed successfully")
            return True

        except Exception as e:
            _log.error(f"Manual table rebuild failed: {e}")
            try:
                self.execute_stmt("ROLLBACK")
            except Exception:
                pass
            # Clean up any partial resources
            self.cleanup_temp_resources()
            return False


    def delete_rows_by_chunks(self, rows_to_delete, chunk_size=5000):
        """Delete rows in fixed chunks using ctid with improved performance"""
        total_deleted = 0

        while total_deleted < rows_to_delete:
            remaining = min(chunk_size, rows_to_delete - total_deleted)

            delete_query = f"""
               WITH del AS (
                   SELECT ctid
                   FROM public.{self.data_table}
                   ORDER BY ts ASC
                   LIMIT %s
               )
               DELETE FROM public.{self.data_table} d
               USING del
               WHERE d.ctid = del.ctid
               """

            deleted_count = self.execute_stmt(delete_query, (remaining,))
            if deleted_count == 0:
                break

            total_deleted += deleted_count
            self.commit()

            _log.debug(f"Deleted {deleted_count} records, total: {total_deleted}")

            # Brief pause to allow other operations
            if total_deleted % (chunk_size * 5) == 0:  # Every 5 chunks
                gevent.sleep(0.1)

        return total_deleted


    def delete_without_rebuild(self, current_metrics, target_bytes):
        """Delete rows when there's insufficient space for table rebuild"""
        table_size_gb = current_metrics['total_bytes'] / (1024.0 * 1024.0 * 1024.0)
        estimated_vacuum_time = self.estimate_vacuum_full_time(table_size_gb)

        _log.warning("=" * 60)
        _log.warning("INSUFFICIENT DISK SPACE FOR AUTOMATIC CLEANUP")
        _log.warning(f"Current table size: {table_size_gb:.3f} GB")
        _log.warning("Space will NOT be fully reclaimed with this deletion method.")
        _log.warning("")
        _log.warning("MANUAL CLEANUP REQUIRED:")
        _log.warning(f"Run 'VACUUM FULL {self.data_table};' during scheduled downtime to reclaim disk space.")
        _log.warning(f"WARNING: VACUUM FULL will lock table for ~{estimated_vacuum_time} minutes")
        _log.warning("During this time, table will be UNAVAILABLE for reads and writes.")
        _log.warning("=" * 60)

        # Use reltuples for estimation, avoiding division by zero
        avg_bpr = current_metrics['total_bytes'] / current_metrics['reltuples']
        rows_to_delete = int((current_metrics['total_bytes'] - target_bytes) / avg_bpr)

        # Use larger chunks for better throughput
        total_deleted = self.delete_rows_by_chunks(rows_to_delete, chunk_size=5000)

        # Try to reclaim index space with REINDEX CONCURRENTLY on known indexes
        _log.info("Attempting to reclaim index space with REINDEX CONCURRENTLY...")
        try:
            self.execute_stmt(f'REINDEX (VERBOSE) INDEX CONCURRENTLY public."{self.data_table}_topic_id_ts_key"')
            self.execute_stmt(f'REINDEX (VERBOSE) INDEX CONCURRENTLY public."idx_{self.data_table}"')
            _log.info("Successfully reindexed both indexes - index space reclaimed")
        except Exception as e:
            _log.warning(f"REINDEX CONCURRENTLY failed: {e}")

        _log.warning(
            f"Deleted {total_deleted} records but table space not reclaimed - manual VACUUM FULL needed for full cleanup")

    def manage_db_size(
            self,
            history_limit_timestamp,
            storage_limit_gb,
            min_rows_floor=1000,  # do not reduce below this many rows (approx, uses reltuples) default 1000
            min_bytes_floor=16000000,  # do not reduce below this many bytes (table total) default 16 MB
            cooldown_minutes=None  # Optional: minimum minutes between heap rewrites (pg_repack/CTAS)
    ):
        _log.debug(
            "Managing store - timestamp limit: %s  GB size limit: %s  min_rows_floor: %s  min_bytes_floor: %s  cooldown_minutes: %s",
            history_limit_timestamp, storage_limit_gb, min_rows_floor, min_bytes_floor, cooldown_minutes
        )

        try:
            # Keep stats fresh for estimates
            self.execute_stmt(f"ANALYZE public.{self.data_table}")

            # Initial metrics (no COUNT to avoid full scan)
            initial_metrics = self.get_table_metrics(need_exact_count=False)
            initial_db_size_gb = self.get_database_size_gb()
            initial_table_bytes = initial_metrics['total_bytes']
            _log.info(
                "Initial DB size: %.6f GB, Table size: %.6f GB, reltuples: %d",
                initial_db_size_gb,
                initial_table_bytes / (1024.0 ** 3),
                int(initial_metrics['reltuples'])
            )

            # Step 1: Age-based cleanup (simple DELETE; use chunked if you expect very large ranges)
            if history_limit_timestamp is not None:
                deleted_age = self.execute_stmt(
                    f"DELETE FROM public.{self.data_table} WHERE ts < %s",
                    (history_limit_timestamp,)
                )
                if deleted_age:
                    _log.info("Deleted %d rows older than %s", deleted_age, history_limit_timestamp)
                    self.commit()

            # Step 2: Storage-based cleanup (DB cap)
            if storage_limit_gb is not None:
                current_db_size_gb = self.get_database_size_gb()
                current_db_bytes = int(current_db_size_gb * (1024.0 ** 3))
                target_db_bytes = int(storage_limit_gb * (1024.0 ** 3))
                _log.info("Current DB size: %.6f GB, Target: %.6f GB", current_db_size_gb, storage_limit_gb)

                if current_db_bytes <= target_db_bytes:
                    _log.info("Database size already within limit; skipping size-based cleanup")
                else:
                    db_reduction_needed_bytes = current_db_bytes - target_db_bytes
                    _log.info("Need to reduce database size by %.6f GB", db_reduction_needed_bytes / (1024.0 ** 3))

                    # Refresh table metrics after any age deletes
                    current_metrics = self.get_table_metrics(need_exact_count=False)
                    table_bytes = current_metrics['total_bytes']
                    reltuples = max(int(current_metrics['reltuples']), 1)
                    table_gb = table_bytes / (1024.0 ** 3)

                    # Max reclaim from this table is its current size
                    bytes_to_delete_from_table = min(db_reduction_needed_bytes, table_bytes)

                    # Enforce minimum BYTES floor (never delete below this many bytes of table data)
                    if min_bytes_floor is not None:
                        keep_floor_bytes = max(int(min_bytes_floor), 0)
                        allowed_delete_bytes = max(table_bytes - keep_floor_bytes, 0)
                        bytes_to_delete_from_table = min(bytes_to_delete_from_table, allowed_delete_bytes)

                    if bytes_to_delete_from_table <= 0:
                        _log.info(
                            "No table bytes can be safely reclaimed given floors (table: %.6f GB, min_bytes_floor: %s). "
                            "DB may be dominated by other relations.",
                            table_gb, min_bytes_floor
                        )
                        return

                    # Thresholds to avoid churn for tiny reductions
                    abs_threshold_bytes = 16 * 1024 * 1024  # 16 MB
                    rel_threshold_bytes = int(table_bytes * 0.10)  # 10% of table
                    threshold_bytes = max(abs_threshold_bytes, rel_threshold_bytes)

                    if bytes_to_delete_from_table < threshold_bytes:
                        _log.info(
                            "Planned reclaim (%.3f MB) is below threshold (>= %.3f MB or >= %.1f%% of table); skipping rebuild",
                            bytes_to_delete_from_table / (1024.0 ** 2),
                            threshold_bytes / (1024.0 ** 2),
                            (100.0 * rel_threshold_bytes / max(table_bytes, 1))
                        )
                        return

                    # Predict if shrinking this table alone meets the DB cap
                    predicted_db_after = current_db_bytes - bytes_to_delete_from_table
                    if predicted_db_after > target_db_bytes:
                        _log.warning(
                            "Even deleting this entire table (%.3f GB) won't reach the DB cap. "
                            "Skipping destructive shrink; investigate other large relations.",
                            table_gb
                        )
                        return

                    # Estimate rows to delete based on average bytes per row (heap+indexes)
                    avg_bpr = table_bytes / reltuples
                    rows_by_bytes = max(1, int((bytes_to_delete_from_table / avg_bpr) * 0.95))

                    # Enforce minimum ROWS floor (never delete below this many rows approx)
                    if min_rows_floor is not None:
                        keep_floor_rows = max(int(min_rows_floor), 0)
                        allowed_rows_delete = max(reltuples - keep_floor_rows, 0)
                        rows_to_delete = min(rows_by_bytes, allowed_rows_delete)
                    else:
                        rows_to_delete = rows_by_bytes

                    if rows_to_delete <= 0:
                        _log.info(
                            "Row-floor prevents further deletions (rows ~%d, min_rows_floor %s); skipping",
                            reltuples, min_rows_floor
                        )
                        return

                    _log.info(
                        "Will delete approximately %d rows (floor-aware) to free %.6f GB "
                        "(table %.6f GB -> target %.6f GB)",
                        rows_to_delete,
                        bytes_to_delete_from_table / (1024.0 ** 3),
                        table_gb,
                        (table_bytes - bytes_to_delete_from_table) / (1024.0 ** 3)
                    )

                    # Delete rows in chunks (oldest first via your helper)
                    deleted = self.delete_rows_by_chunks(rows_to_delete, chunk_size=5000)
                    _log.info("Deleted %d rows; reclaiming space...", deleted)

                    # Cooldown handling for heap rewrite (pg_repack/CTAS)
                    now_utc = datetime.now(timezone.utc)
                    last_rewrite = getattr(self, "_last_heap_rewrite_ts", None)
                    cooldown_active = False
                    if cooldown_minutes is not None and last_rewrite is not None:
                        if now_utc - last_rewrite < timedelta(minutes=cooldown_minutes):
                            cooldown_active = True
                            remaining = timedelta(minutes=cooldown_minutes) - (now_utc - last_rewrite)
                            _log.info(
                                "Cooldown active (remaining %s); skipping heap rewrite this run. "
                                "Heap file size will not shrink until next window.",
                                str(remaining).split(".")[0]
                            )

                    if cooldown_active:
                        # Optional: reclaim index space only
                        try:
                            self.execute_stmt(f'REINDEX CONCURRENTLY TABLE public."{self.data_table}"')
                            _log.info("Reindexed indexes concurrently (cooldown mode)")
                        except Exception as e:
                            _log.warning(f"REINDEX CONCURRENTLY TABLE failed: {e}")
                    else:
                        # Try pg_repack; else CTAS+swap
                        rebuilt = False
                        if self.run_pg_repack(self.connect_params):
                            _log.info("pg_repack successful - space reclaimed")
                            rebuilt = True
                        else:
                            _log.warning("pg_repack unavailable/failed; performing manual table rebuild")
                            if self.manual_table_rebuild(None):
                                rebuilt = True
                            else:
                                _log.warning("Manual table rebuild failed; indexes may still be bloated")

                        # if rebuilt:
                        #     # Record cooldown timestamp
                        #     try:
                        #         self._last_heap_rewrite_ts = now_utc
                        #     except Exception:
                        #         setattr(self, "_last_heap_rewrite_ts", now_utc)

            # Final status
            final_db_size_gb = self.get_database_size_gb()
            final_metrics = self.get_table_metrics(need_exact_count=False)
            _log.info(
                "Final DB size: %.6f GB, Table size: %.6f GB, reltuples: %d",
                final_db_size_gb,
                final_metrics['total_bytes'] / (1024.0 ** 3),
                int(final_metrics['reltuples'])
            )

        except Exception as e:
            _log.error(f"Error in manage_db_size: {e}")
            self.cleanup_temp_resources()
            raise
