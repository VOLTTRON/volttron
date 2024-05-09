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

"""
pytest test cases for historian database drivers.

Prerequisites:

 1. Server process should be running
 2. Test database and user should exist
 3. Test user should have all privileges on test database
 4. Refer to the parameters passed to the historian fixture for the
    server configuration

This test case is a generic test case that all historian drivers should
satisfy. To test a specific historian implementation through this test
suite do the following:

 1. Create a Test<DriverType> class that subclasses Suite
 2. Implement the transact method as a context manager that can perform
    any setup before yielding the tuple (DriverClass, connection_params)
    and cleans up afterward.
"""

import ast
import contextlib
import tempfile
from datetime import datetime, timedelta
import inspect
import random
import sqlite3

import pytest
import pytz
import shutil

from volttron.platform.dbutils import basedb
from volttron.platform.dbutils.sqlitefuncts import SqlLiteFuncts

try:
    import psycopg2
    import psycopg2.errorcodes
    import psycopg2.sql

    HAVE_POSTGRESQL = True
except ImportError:
    HAVE_POSTGRESQL = False
else:
    from volttron.platform.dbutils.postgresqlfuncts import PostgreSqlFuncts
    from volttron.platform.dbutils.redshiftfuncts import RedshiftFuncts

redshift_params = {}
if HAVE_POSTGRESQL:
    try:
        with open('redshift.params') as file:
            redshift_params = ast.literal_eval(file.read(4096))
    except (IOError, OSError):
        pass


postgres_connection_params = {
                                'dbname': 'test_historian',
                                'port': 5432,
                                'host': '127.0.0.1',
                                'user' : 'historian',
                                'password': 'historian'
                            }
def random_uniform(a, b):
    return float('{.13f}'.format(random.uniform(a, b)))

def drop_tables(names):
    '''Marks methods creating additional tables for cleanup'''
    def wrapper(fn):
        fn.drop_tables = names
        return fn
    return wrapper


@pytest.mark.historian
class Suite:
    #@pytest.fixture(scope='class', params=['', 'test'])
    @pytest.fixture(scope='class', params=[''])
    def state(self, request):
        prefix = request.param
        pre = prefix + '_' if prefix else ''
        table_names = {
            'data_table': pre + 'data',
            'topics_table': pre + 'topics',
            'meta_table': pre + 'meta',
            'agg_topics_table': pre + 'aggregate_topics',
            'agg_meta_table': pre + 'aggregate_meta',
        }
        tables_def = table_names.copy()
        tables_def['table_prefix'] = prefix
        meta_table_name = pre + 'volttron_table_definitions'
        state = type('State', (object,), {
            'meta_table_name': meta_table_name,
            'table_names': table_names,
        })
        truncate_tables = list(table_names.values()) + [meta_table_name]
        drop_tables = []
        for _, method in inspect.getmembers(self, inspect.ismethod):
            drop_tables.extend(getattr(method, 'drop_tables', []))
        with self.transact(truncate_tables, drop_tables) as (cls, params), \
                contextlib.closing(cls(params, tables_def)) as state.driver:
            yield state

    def create_driver(self, state):
        driver = state.driver
        driver.setup_historian_tables()
        return driver

    @pytest.fixture
    def suite_driver(self, state):
        return self.create_driver(state)

    @contextlib.contextmanager
    def transact(self, truncate_tables, drop_tables):
        pass

    def test_topic_name_case_change(self, suite_driver):
        topic_id = suite_driver.insert_topic('This/is/some/Topic')
        assert topic_id
        id_map1, name_map1 = suite_driver.get_topic_map()
        suite_driver.update_topic('This/is/some/topic', topic_id)
        id_map2, name_map2 = suite_driver.get_topic_map()
        assert id_map1 == id_map2
        assert name_map1.pop('this/is/some/topic') == 'This/is/some/Topic'
        assert name_map2.pop('this/is/some/topic') == 'This/is/some/topic'
        assert name_map1 == name_map2

    def test_query_topic_pattern(self, suite_driver):
        topics = {'This/is/a/pattern/topic',
                  'This/is/another/pattern/topic',
                  'This/is/some/pattern/topic'}
        for topic in topics:
            topic_id = suite_driver.insert_topic(topic)
            assert topic_id
        suite_driver.commit()
        assert len(set(suite_driver.query_topics_by_pattern('this/is/a.*/pattern/topic').keys()) & topics) == 2
        assert len(set(suite_driver.query_topics_by_pattern('this/is/some/.*/topic').keys()) & topics) == 1
        assert len(set(suite_driver.query_topics_by_pattern('.*').keys()) & topics) == 3

    def test_curser_for_closed_connection(self, suite_driver):
        cursor = suite_driver.cursor()
        assert cursor is not None
        cursor.connection.close()
        cursor = suite_driver.cursor()
        assert cursor is not None


class AggregationSuite(Suite):

    @pytest.fixture
    def driver(self, state, suite_driver):
        #driver = super(AggregationSuite, self).driver(state)
        suite_driver.setup_aggregate_historian_tables()
        return suite_driver

    @pytest.mark.aggregator
    def test_create_agg_table(self, driver, state):
        driver.create_aggregate_store('sum', '1m')

    @pytest.mark.aggregator
    @drop_tables(['sum_1m', 'max_1m'])
    def test_aggregation(self, driver):
        ts = start = datetime(year=2015, month=4, day=14, hour=9, minute=26,
                              second=53, microsecond=59, tzinfo=pytz.UTC)
        delta = timedelta(seconds=1)
        for i in range(100):
            value = float(i)
            for topic_id in range(1, 4):
                driver.insert_data(ts, topic_id, value)
            ts += delta
        driver.commit()
        assert driver.collect_aggregate(list(range(1, 4)), 'sum', start, ts) == (14850.0, 300)
        assert driver.collect_aggregate(list(range(1, 4)), 'avg', start, ts) == (49.5, 300)
        assert driver.collect_aggregate([1, 6], 'sum', start, ts) == (4950, 100)
        assert driver.collect_aggregate([1, 6], 'avg', start, ts) == (49.5, 100)
        start += delta
        ts = start + delta
        assert driver.collect_aggregate(list(range(1, 4)), 'sum', start, ts) == (3.0, 3)
        assert driver.collect_aggregate(list(range(1, 4)), 'avg', start, ts) == (1, 3)
        driver.create_aggregate_store('max', '1m')
        topic_id = driver.insert_agg_topic('aggregate/max/1m/topic', 'max', '1m')
        assert topic_id
        driver.insert_agg_meta(topic_id, {'units': 'X', 'tz': 'UTC', 'type': 'float'})
        driver.insert_aggregate(topic_id, 'max', '1m', ts, '12.345', [1, 2, 3])

    def test_query_topic_pattern(self, driver):
        topics = {'This/is/a/pattern/topic',
                  'This/is/another/pattern/topic',
                  'This/is/some/pattern/topic'}
        for topic in topics:
            topic_id = driver.insert_topic(topic)
            assert topic_id
        assert len(set(driver.query_topics_by_pattern('this/is/a.*/pattern/topic').keys()) & topics) == 2
        assert len(set(driver.query_topics_by_pattern('this/is/some/.*/topic').keys()) & topics) == 1
        assert len(set(driver.query_topics_by_pattern('.*').keys()) & topics) == 3

    def test_curser_for_closed_connection(self, driver):
        cursor = driver.cursor()
        assert cursor is not None
        cursor.connection.close()
        cursor = driver.cursor()
        assert cursor is not None


@pytest.mark.skipif(not HAVE_POSTGRESQL, reason='missing psycopg2 package')
class TestPostgreSql(AggregationSuite):
    @contextlib.contextmanager
    def _transact(self, params, truncate_tables, drop_tables):
        pg = psycopg2.sql
        with contextlib.closing(psycopg2.connect(**params)) as connection:
            def cleanup():
                def clean(op, tables):
                    query = pg.SQL(op + ' TABLE {}')
                    for table in tables:
                        with connection.cursor() as cursor:
                            try:
                                cursor.execute(query.format(pg.Identifier(table)))
                            except psycopg2.ProgrammingError as exc:
                                if exc.pgcode != psycopg2.errorcodes.UNDEFINED_TABLE:
                                    raise
                clean('TRUNCATE', truncate_tables)
                clean('DROP', drop_tables)
            connection.autocommit = True
            cleanup()
            yield
            cleanup()

    @contextlib.contextmanager
    def transact(self, truncate_tables, drop_tables):
        global postgres_connection_params
        with self._transact(postgres_connection_params, truncate_tables, drop_tables):
            yield PostgreSqlFuncts, postgres_connection_params

    def test_closing_interfaceerror(self):
        with basedb.closing(FauxConnection(psycopg2.InterfaceError)):
            pass


@pytest.mark.skipif(not redshift_params, reason=(
    'missing redshift params' if HAVE_POSTGRESQL else 'missing psycopg2 package'))
class TestRedshift(TestPostgreSql):
    @contextlib.contextmanager
    def transact(self, truncate_tables, drop_tables):
        with self._transact(redshift_params, truncate_tables, drop_tables):
            yield RedshiftFuncts, redshift_params


class TestSqlite(AggregationSuite):
    @contextlib.contextmanager
    def transact(self, truncate_tables, drop_tables):
        tmpdir = tempfile.mkdtemp()
        try:
            params = {'database': '{}/test.sqlite'.format(tmpdir)}
            def cleanup():
                with contextlib.closing(sqlite3.connect(**params)) as connection, \
                        connection:
                    cursor = connection.cursor()
                    def clean(query, tables):
                        for table in tables:
                            try:
                                cursor.execute('{} "{}"'.format(
                                    query, table.replace('"', '""')))
                            except sqlite3.OperationalError as exc:
                                if not str(exc).startswith('no such table'):
                                    raise
                    clean('DELETE FROM', truncate_tables)
                    clean('DROP TABLE', drop_tables)
            cleanup()
            yield SqlLiteFuncts, params
            cleanup()
        finally:
            shutil.rmtree(tmpdir, True)

    @pytest.mark.skip(reason='missing regexp library')
    def test_query_topic_pattern(self, driver):
        pass


class FauxConnection:
    def __init__(self, exc_class):
        self.exc_class = exc_class

    def close(self):
        raise self.exc_class


class TestClosing:

    def test_closing_exception(self):
        with pytest.raises(Exception), basedb.closing(FauxConnection(Exception)):
            pass

    def test_closing_standarderror_builtin_subclass(self):
        with pytest.raises(ValueError), basedb.closing(FauxConnection(ValueError)):
            pass

    def test_closing_standarderror_subclass(self):
        class SubclassedError(Exception):
            pass
        with basedb.closing(FauxConnection(SubclassedError)):
            pass
