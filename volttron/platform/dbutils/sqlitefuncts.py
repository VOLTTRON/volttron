# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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

import ast
import errno
import logging
import sqlite3
import pytz
import threading
import os
import re
from .basedb import DbDriver
from collections import defaultdict
from datetime import datetime
from math import ceil

from volttron.platform.agent import utils
from volttron.platform import jsonapi
from volttron.platform.agent.utils import fix_sqlite3_datetime

utils.setup_logging()
_log = logging.getLogger(__name__)

# Make sure sqlite3 datetime adapters are updated.
fix_sqlite3_datetime()


class SqlLiteFuncts(DbDriver):
    """
    Implementation of SQLite3 database operation for
    :py:class:`sqlhistorian.historian.SQLHistorian` and
    :py:class:`sqlaggregator.aggregator.SQLAggregateHistorian`
    For method details please refer to base class
    :py:class:`volttron.platform.dbutils.basedb.DbDriver`
    """
    def __init__(self, connect_params, table_names):
        database = connect_params['database']
        thread_name = threading.currentThread().getName()
        _log.debug(
            "initializing sqlitefuncts in thread {}".format(thread_name))
        if database == ':memory:':
            self.__database = database
        else:
            self.__database = os.path.expandvars(os.path.expanduser(database))
            db_dir = os.path.dirname(self.__database)

            # If the db does not exist create it in case we are started
            # before the historian.
            try:
                if db_dir == '':
                    if utils.is_secure_mode():
                        data_dir = os.path.basename(os.getcwd()) + ".agent-data"
                        db_dir = os.path.join(os.getcwd(), data_dir)
                    else:
                        db_dir = './data'
                    self.__database = os.path.join(db_dir, self.__database)

                os.makedirs(db_dir)
            except OSError as exc:
                if exc.errno != errno.EEXIST or not os.path.isdir(db_dir):
                    raise

        connect_params['database'] = self.__database

        if 'detect_types' not in connect_params:
            connect_params['detect_types'] = sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        if 'timeout' not in connect_params.keys():
            connect_params['timeout'] = 10

        self.data_table = None
        self.topics_table = None
        self.meta_table = None
        self.agg_topics_table = None
        self.agg_meta_table = None

        if table_names:
            self.data_table = table_names['data_table']
            self.topics_table = table_names['topics_table']
            self.meta_table = table_names['meta_table']
            self.agg_topics_table = table_names['agg_topics_table']
            self.agg_meta_table = table_names['agg_meta_table']
        _log.debug("In sqlitefuncts connect params {}".format(connect_params))
        super(SqlLiteFuncts, self).__init__('sqlite3', **connect_params)

    def setup_historian_tables(self):

        result = self.select('''PRAGMA auto_vacuum''')
        auto_vacuum = result[0][0]

        if auto_vacuum != 1:
            _log.info("auto_vacuum set to 0 (None), updating to 1 (full).")
            _log.info("VACCUUMing DB to cause new auto_vacuum setting to take effect. "
                      "This could be slow on a large database.")
            self.select('''PRAGMA auto_vacuum=1''')
            self.select('''VACUUM;''')

        self.execute_stmt(
            '''CREATE TABLE IF NOT EXISTS ''' + self.data_table +
            ''' (ts timestamp NOT NULL,
                 topic_id INTEGER NOT NULL,
                 value_string TEXT NOT NULL,
                 UNIQUE(topic_id, ts))''', commit=False)
        self.execute_stmt(
            '''CREATE INDEX IF NOT EXISTS data_idx 
            ON ''' + self.data_table + ''' (ts ASC)''', commit=False)
        self.execute_stmt(
            '''CREATE TABLE IF NOT EXISTS ''' + self.topics_table +
            ''' (topic_id INTEGER PRIMARY KEY,
                 topic_name TEXT NOT NULL,
                 UNIQUE(topic_name))''', commit=False)
        self.execute_stmt(
            '''CREATE TABLE IF NOT EXISTS ''' + self.meta_table +
            '''(topic_id INTEGER PRIMARY KEY,
                metadata TEXT NOT NULL)''', commit=True)
        _log.debug("Created data topics and meta tables")

    def record_table_definitions(self, table_defs, meta_table_name):
        _log.debug("In record_table_def {} {}".format(table_defs, meta_table_name))
        self.execute_stmt(
            'CREATE TABLE IF NOT EXISTS ' + meta_table_name +
            ' (table_id TEXT PRIMARY KEY, \
               table_name TEXT NOT NULL, \
               table_prefix TEXT);')

        table_prefix = table_defs.get('table_prefix', "")

        self.execute_stmt(
            'INSERT OR REPLACE INTO ' + meta_table_name + ' VALUES (?, ?, ?)',
            ['data_table', table_defs['data_table'], table_prefix])
        self.execute_stmt(
            'INSERT OR REPLACE INTO ' + meta_table_name + ' VALUES (?, ?, ?)',
            ['topics_table', table_defs['topics_table'], table_prefix])
        self.execute_stmt(
            'INSERT OR REPLACE INTO ' + meta_table_name + ' VALUES (?, ?, ?)',
            ['meta_table', table_defs['meta_table'], table_prefix])
        self.commit()

    def setup_aggregate_historian_tables(self, meta_table_name):
        table_names = self.read_tablenames_from_db(meta_table_name)

        self.data_table = table_names['data_table']
        self.topics_table = table_names['topics_table']
        self.meta_table = table_names['meta_table']
        self.agg_topics_table = table_names.get('agg_topics_table', None)
        self.agg_meta_table = table_names.get('agg_meta_table', None)

        self.execute_stmt(
            'CREATE TABLE IF NOT EXISTS ' + self.agg_topics_table +
            ' (agg_topic_id INTEGER PRIMARY KEY, \
               agg_topic_name TEXT NOT NULL, \
               agg_type TEXT NOT NULL, \
               agg_time_period TEXT NOT NULL, \
               UNIQUE(agg_topic_name, agg_type, agg_time_period));')
        self.execute_stmt(
            'CREATE TABLE IF NOT EXISTS ' + self.agg_meta_table +
            '(agg_topic_id INTEGER NOT NULL PRIMARY KEY, \
              metadata TEXT NOT NULL);')
        _log.debug("Created aggregate topics and meta tables")
        self.commit()

    def query(self, topic_ids, id_name_map, start=None, end=None, agg_type=None, agg_period=None, skip=0, count=None,
              order="FIRST_TO_LAST"):
        """
        This function should return the results of a query in the form:

        .. code-block:: python

            {"values": [(timestamp1, value1), (timestamp2, value2), ...],
             "metadata": {"key1": value1, "key2": value2, ...}}

        metadata is not required (The caller will normalize this to {} for you)
        @param topic_ids: topic_ids to query data for
        @param id_name_map: dictionary containing topic_id:topic_name
        @param start:
        @param end:
        @param agg_type:
        @param agg_period:
        @param skip:
        @param count:
        @param order:
        """
        table_name = self.data_table
        if agg_type and agg_period:
            table_name = agg_type + "_" + agg_period

        query = '''SELECT topic_id, ts, value_string
                   FROM ''' + table_name + '''
                   {where}
                   {order_by}
                   {limit}
                   {offset}'''

        where_clauses = ["WHERE topic_id = ?"]
        args = [topic_ids[0]]

        # base historian converts naive timestamps to UTC, but if the start and end had explicit timezone info then they
        # need to get converted to UTC since sqlite3 only store naive timestamp
        if start:
            start = start.astimezone(pytz.UTC)
        if end:
            end = end.astimezone(pytz.UTC)

        if start and end and start == end:
            where_clauses.append("ts = ?")
            args.append(start)
        else:
            if start:
                where_clauses.append("ts >= ?")
                args.append(start)
            if end:
                where_clauses.append("ts < ?")
                args.append(end)

        where_statement = ' AND '.join(where_clauses)

        order_by = 'ORDER BY topic_id ASC, ts ASC'
        if order == 'LAST_TO_FIRST':
            order_by = ' ORDER BY topic_id DESC, ts DESC'

        # can't have an offset without a limit
        # -1 = no limit and allows the user to provide just an offset
        if count is None:
            count = -1

        limit_statement = 'LIMIT ?'
        args.append(count)

        offset_statement = ''
        if skip > 0:
            offset_statement = 'OFFSET ?'
            args.append(skip)

        real_query = query.format(where=where_statement,
                                  limit=limit_statement,
                                  offset=offset_statement,
                                  order_by=order_by)
        _log.debug("Real Query: " + real_query)
        _log.debug("args: " + str(args))

        values = defaultdict(list)
        start_t = datetime.utcnow()
        for topic_id in topic_ids:
            args[0] = topic_id
            values[id_name_map[topic_id]] = []
            cursor = self.select(real_query, args, fetch_all=False)
            if cursor:
                for _id, ts, value in cursor:
                    values[id_name_map[topic_id]].append((utils.format_timestamp(ts), jsonapi.loads(value)))
                cursor.close()

        _log.debug("Time taken to load results from db:{}".format(datetime.utcnow()-start_t))
        return values

    def manage_db_size(self, history_limit_timestamp, storage_limit_gb):
        """
        Manage database size.
        :param history_limit_timestamp: remove all data older than this timestamp
        :param storage_limit_gb: remove oldest data until database is smaller than this value.
        """

        _log.debug("Managing store - timestamp limit: {}  GB size limit: {}".format(
            history_limit_timestamp, storage_limit_gb))

        commit = False

        if history_limit_timestamp is not None:
            count = self.execute_stmt(
                '''DELETE FROM ''' + self.data_table +
                ''' WHERE ts < ?''', (history_limit_timestamp,))

            if count is not None and count > 0:
                _log.debug("Deleted {} old items from historian. (TTL exceeded)".format(count))
                commit = True

        if storage_limit_gb is not None:
            result = self.select('''PRAGMA page_size''')
            page_size = result[0][0]
            max_storage_bytes = storage_limit_gb * 1024 ** 3
            max_pages = int(ceil(max_storage_bytes / page_size))

            def page_count():
                result = self.select("PRAGMA page_count")
                return result[0][0]

            while page_count() >= max_pages:
                count = self.execute_stmt(
                    '''DELETE FROM ''' + self.data_table +
                    '''
                    WHERE ts IN
                    (SELECT ts FROM ''' + self.data_table +
                    '''
                    ORDER BY ts ASC LIMIT 100)''')

                _log.debug("Deleted 100 old items from historian. (Managing store size)".format(count))
                commit = True

        if commit:
            _log.debug("Committing changes for manage_db_size.")
            self.commit()

    def insert_meta_query(self):
        return '''INSERT OR REPLACE INTO ''' + self.meta_table + \
               ''' values(?, ?)'''

    def insert_data_query(self):
        return '''INSERT OR REPLACE INTO ''' + self.data_table + \
               ''' values(?, ?, ?)'''

    def insert_topic_query(self):
        return '''INSERT INTO ''' + self.topics_table + \
               ''' (topic_name) values (?)'''

    def update_topic_query(self):
        return '''UPDATE ''' + self.topics_table + ''' SET topic_name = ?
            WHERE topic_id = ?'''

    def get_aggregation_list(self):
        return ['AVG', 'MIN', 'MAX', 'COUNT', 'SUM', 'TOTAL', 'GROUP_CONCAT']

    def insert_agg_topic_stmt(self):
        return '''INSERT INTO ''' + self.agg_topics_table + '''
               (agg_topic_name, agg_type, agg_time_period )
               values (?, ?, ?)'''

    def update_agg_topic_stmt(self):
        return '''UPDATE ''' + self.agg_topics_table + ''' SET
        agg_topic_name = ? WHERE agg_topic_id = ? '''

    def replace_agg_meta_stmt(self):
        return '''INSERT OR REPLACE INTO ''' + self.agg_meta_table + '''
        values(?, ?)'''

    def get_topic_map(self):
        _log.debug("in get_topic_map")
        q = "SELECT topic_id, topic_name FROM " + self.topics_table
        rows = self.select(q, None)
        _log.debug("loading topic map from db")
        id_map = dict()
        name_map = dict()
        for t, n in rows:
            id_map[n.lower()] = t
            name_map[n.lower()] = n
        return id_map, name_map

    def get_agg_topics(self):
        try:
            _log.debug("in get_agg_topics")
            query = "SELECT agg_topic_name, agg_type, agg_time_period, metadata FROM " + self.agg_topics_table + \
                    " as t, " + self.agg_meta_table + " as m WHERE t.agg_topic_id = m.agg_topic_id "
            rows = self.select(query, None)
            topics = []
            for row in rows:
                _log.debug("rows from aggregate_t")
                meta = ast.literal_eval(row[3])['configured_topics']
                topics.append((row[0], row[1], row[2], meta))
            return topics
        except sqlite3.Error as e:
            if e.args[0][0:13] == 'no such table':
                _log.warning("No such table : {}".format(self.agg_topics_table))
                return []
            else:
                raise

    def get_agg_topic_map(self):
        try:
            _log.debug("in get_agg_topic_map")
            q = "SELECT agg_topic_id, agg_topic_name, agg_type, agg_time_period FROM " + self.agg_topics_table
            rows = self.select(q, None)
            _log.debug("loading agg_topic map from db")
            id_map = dict()
            for row in rows:
                _log.debug("rows from aggregate_t")
                id_map[(row[1].lower(), row[2], row[3])] = row[0]
            return id_map
        except sqlite3.Error as e:
            if e.args[0][0:13] == 'no such table':
                _log.warning("No such table : {}".format(self.agg_topics_table))
                return {}
            else:
                raise

    @staticmethod
    def regexp(expr, item):
        _log.debug("item {} matched against expr {}".format(item, expr))
        return re.search(expr, item, re.IGNORECASE) is not None

    def set_cache(self, cache_size):
        self.execute_stmt("PRAGMA CACHE_SIZE={}".format(cache_size))

    def regex_select(self, query, args, fetch_all=True, cache_size=None):
        conn = None
        cursor = None
        try:
            conn = sqlite3.connect(self.__database, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)

            if conn is None:
                _log.error("Unable to connect to sqlite database {} ".format(self.__database))
                return []
            conn.create_function("REGEXP", 2, SqlLiteFuncts.regexp)
            if cache_size:
                conn.execute("PRAGMA CACHE_SIZE={}".format(cache_size))
            _log.debug("REGEXP query {}  ARGS: {}".format(query, args))
            cursor = conn.cursor()
            if args is not None:
                cursor.execute(query, args)
            else:
                _log.debug("executing query")
                cursor.execute(query)
            if fetch_all:
                rows = cursor.fetchall()
                _log.debug("Regex returning {}".format(rows))
                return rows
            else:
                return cursor, conn
        except Exception as e:
            _log.error("Exception querying database based on regular expression:{}".format(e.args))
        finally:
            if fetch_all:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()

    def query_topics_by_pattern(self, topic_pattern):
        id_map, name_map = self.get_topic_map()
        _log.debug("Contents of topics table {}".format(list(id_map.keys())))
        q = "SELECT topic_id, topic_name FROM " + self.topics_table + " WHERE topic_name REGEXP '" + topic_pattern + \
            "';"

        rows = self.regex_select(q, None)
        _log.debug("loading topic map from db")
        id_map = dict()
        for t, n in rows:
            id_map[n] = t
        _log.debug("topics that matched the pattern {} : {}".format(topic_pattern, id_map))
        return id_map

    def create_aggregate_store(self, agg_type, period):
        table_name = agg_type + '''_''' + period

        stmt = "CREATE TABLE IF NOT EXISTS " + table_name + \
               " (ts timestamp NOT NULL, topic_id INTEGER NOT NULL, " \
               "value_string TEXT NOT NULL, topics TEXT, " \
               "UNIQUE(topic_id, ts)); "
        self.execute_stmt(stmt)

        stmt = "CREATE INDEX IF NOT EXISTS idx_" + table_name + " ON " + table_name + "(ts ASC);"

        self.execute_stmt(stmt, commit=True)
        return True

    def insert_aggregate_stmt(self, table_name):
        return '''INSERT OR REPLACE INTO ''' + table_name + ''' values(?, ?, ?, ?)'''

    def collect_aggregate(self, topic_ids, agg_type, start=None, end=None):
        """
        This function should return the results of a aggregation query
        @param topic_ids: list of single topics
        @param agg_type: type of aggregation
        @param start: start time
        @param end: end time
        @return: aggregate value, count of number of records over which
        aggregation was computed
        """
        if isinstance(agg_type, str):
            if agg_type.upper() not in ['AVG', 'MIN', 'MAX', 'COUNT', 'SUM']:
                raise ValueError("Invalid aggregation type {}".format(agg_type))
        query = '''SELECT ''' + agg_type + '''(value_string), count(value_string) FROM ''' + \
                self.data_table + ''' {where}'''

        where_clauses = ["WHERE topic_id = ?"]
        args = [topic_ids[0]]
        if len(topic_ids) > 1:
            where_str = "WHERE topic_id IN ("
            for _ in topic_ids:
                where_str += "?, "
            where_str = where_str[:-2]  # strip last comma and space
            where_str += ") "
            where_clauses = [where_str]
            args = topic_ids[:]

        # base historian converts naive timestamps to UTC, but if the start and end had explicit timezone info then they
        # need to get converted to UTC since sqlite3 only store naive timestamp
        if start:
            start = start.astimezone(pytz.UTC)
        if end:
            end = end.astimezone(pytz.UTC)

        if start and end and start == end:
            where_clauses.append("ts = ?")
            args.append(start)
        else:
            if start:
                where_clauses.append("ts >= ?")
                args.append(start)
            if end:
                where_clauses.append("ts < ?")
                args.append(end)

        where_statement = ' AND '.join(where_clauses)

        real_query = query.format(where=where_statement)
        _log.debug("Real Query: " + real_query)
        _log.debug("args: " + str(args))

        results = self.select(real_query, args)
        if results:
            _log.debug("results got {}, {}".format(results[0][0], results[0][1]))
            return results[0][0], results[0][1]
        else:
            return 0, 0

    @staticmethod
    def get_tagging_query_from_ast(topic_tags_table, tup, tag_refs):
        """
        Get a query condition syntax tree and generate sqlite query to query
        topic names by tags. It calls the get_compound_query to parse the
        abstract syntax tree tuples and then fixes the precedence

        Example:
        # User input query string :

        .. code-block::

        campus.geoPostalCode="20500" and equip and boiler and "equip_tag 7" > 4

        # Example output sqlite query

        .. code-block::

        SELECT topic_prefix from test_topic_tags WHERE tag="campusRef"
         and value  IN(
          SELECT topic_prefix from test_topic_tags WHERE tag="campus" and
          value=1
          INTERSECT
          SELECT topic_prefix  from test_topic_tags WHERE tag="geoPostalCode"
          and value="20500"
         )
        INTERSECT
        SELECT topic_prefix from test_tags WHERE tag="equip" and value=1
        INTERSECT
        SELECT topic_prefix from test_tags WHERE tag="boiler" and value=1
        INTERSECT
        SELECT topic_prefix from test_tags WHERE tag = "equip_tag 7" and
        value > 4

        :param topic_tags_table: table to query
        :param tup: parsed query string (abstract syntax tree)
        :param tag_refs: dictionary of ref tags and its parent tag
        :return: sqlite query
        :rtype str
        """
        query = SqlLiteFuncts._get_compound_query(topic_tags_table, tup, tag_refs)
        # Verify for parent tag finally. if present convert to subquery
        # Process parent tag
        # Convert
        # WHERE tag='campusRef.geoPostalCode' AND value="20500"
        # to
        # where tag='campusRef' and value  IN (
        #  SELECT topic_prefix FROM test_topic_tags
        #    WHERE tag='campus' AND value=1
        #  INTERSECT
        #  SELECT topic_prefix  FROM test_topic_tags
        #    WHERE tag='geoPostalCode'  and value="20500"
        # )
        parent = ""

        search_pattern = r"WHERE\s+tag='(.+)\.(.+)'\s+AND\s+value\s+(.+)($|\n)"
        results = re.findall(search_pattern, query, flags=re.IGNORECASE)
        # Example result :<type 'list'>: [('campusRef', 'tag1', '= 2', '\n'),
        #                                 ('siteRef', 'tag2', '= 3 ', '\n')]
        # Loop through and replace comparison operation with sub query
        for result in results:
            parent = tag_refs[result[0]]
            replace_pattern = r"WHERE tag = '\1' AND value IN \n  (" \
                              r"SELECT topic_prefix " \
                              r"FROM {table} WHERE tag = '{parent}' AND " \
                              r"value = 1\n  " \
                              r"INTERSECT\n  " \
                              r"SELECT topic_prefix FROM {table} WHERE " \
                              r"tag = '\2' " \
                              r"AND " \
                              r"value \3 \4)".format(table=topic_tags_table,
                                                     parent=parent)
            query = re.sub(search_pattern, replace_pattern, query, count=1, flags=re.I)

        _log.debug("Returning sqlite query condition {}".format(query))
        return query

    @staticmethod
    def _get_compound_query(topic_tags_table, tup, tag_refs, root=True):
        """
        Get a query condition syntax tree and generate sqlite query to query
        topic names by tags

        Example:
        # User input query string :
        campus.geoPostalCode="20500" and equip and boiler and "equip_tag 7" > 4


        SELECT topic_prefix FROM test_topic_tags WHERE tag="campusRef"
         and value  IN(
          SELECT topic_prefix FROM test_topic_tags WHERE tag="campus" AND
            value=1
          INTERSECT
          SELECT topic_prefix  FROM test_topic_tags WHERE tag="geoPostalCode"
            AND value="20500"
         )
        INTERSECT
        SELECT topic_prefix FROM test_tags WHERE tag="equip" AND value=1
        INTERSECT
        SELECT topic_prefix FROM test_tags WHERE tag="boiler" AND value=1
        INTERSECT
        SELECT topic_prefix FROM test_tags WHERE tag = "equip_tag 7" AND
          value > 4

        :param topic_tags_table: table to query
        :param tup: parsed query string (abstract syntax tree)
        :param tag_refs: dictionary of ref tags and its parent tag
        :param root: Boolean to indicate if it is the top most tuple in the
        abstract syntax tree.
        :return: sqlite query
        :rtype str
        """

        # Instead of using sqlite LIKE operator we use python regular expression and sqlite REGEXP operator
        reserved_words = {'and': 'INTERSECT', "or": 'UNION', 'not': 'NOT', 'like': 'REGEXP'}
        prefix = 'SELECT topic_prefix FROM {} WHERE '.format(topic_tags_table)
        if tup is None:
            return tup
        if not isinstance(tup[1], tuple):
            left = repr(tup[1])  # quote the tag
        else:
            left = SqlLiteFuncts._get_compound_query(topic_tags_table, tup[1], tag_refs, False)
        if not isinstance(tup[2], tuple):
            if isinstance(tup[2],str):
                right = repr(tup[2])
            elif isinstance(tup[2], bool):
                right = 1 if tup[2] else 0
            else:
                right = tup[2]
        else:
            right = SqlLiteFuncts._get_compound_query(topic_tags_table, tup[2], tag_refs, False)

        assert isinstance(tup[0], str)

        lower_tup0 = tup[0].lower()
        operator = lower_tup0
        if lower_tup0 in reserved_words:
            operator = reserved_words[lower_tup0]

        if operator == 'NOT':
            query = SqlLiteFuncts._negate_condition(right, topic_tags_table)
        elif operator == 'INTERSECT' or operator == 'UNION':
            if root:
                query = "{left}\n{operator}\n{right}".format(left=left, operator=operator, right=right)
            else:
                query = 'SELECT topic_prefix FROM ({left} \n{operator}\n{right})'.format(
                    left=left, operator=operator, right=right)
        else:
            query = "{prefix} tag={tag} AND value {operator} {value}".format(
                prefix=prefix, tag=left, operator=operator, value=right)

        return query

    @staticmethod
    def _negate_condition(condition, table_name):
        """
        change NOT(bool_expr AND bool_expr) to NOT(bool_expr) OR NOT(bool_expr)
        recursively. In sqlite syntax:
        TO negate the following sql query:

        SELECT * FROM
          (SELECT * FROM
            (SELECT topic_prefix FROM topic_tags WHERE  tag='tag3' AND value > 1
            INTERSECT
            SELECT topic_prefix FROM topic_tags WHERE  tag='tag2' AND value > 2)
          UNION
          SELECT topic_prefix FROM topic_tags WHERE  tag='tag4' AND value < 2)

        We have to change it to:

        SELECT * FROM
          (SELECT * FROM
            (SELECT topic_prefix FROM topic_tags WHERE topic_prefix NOT IN
              (SELECT topic_prefix FROM topic_tags WHERE tag='tag3' AND
                value > 1)
            UNION
            SELECT topic_prefix FROM topic_tags WHERE topic_prefix NOT IN
             (SELECT topic_prefix FROM topic_tags WHERE  tag='tag2' AND
                value > 2))
          INTERSECT
          SELECT topic_prefix FROM topic_tags WHERE topic_prefix NOT IN(
            SELECT topic_prefix FROM topic_tags WHERE  tag='tag4' AND
             value < 2))

        :param condition: select query that needs to be negated. It could be a
        compound query.
        :return: negated select query
        :rtype str
        """
        _log.debug("Query condition to negate: {}".format(condition))
        # Change and to or and or to and
        condition = condition.replace('INTERSECT\n', 'UNION_1\n')
        condition = condition.replace('UNION\n', 'INTERSECT\n')
        condition = condition.replace('UNION_1\n', 'UNION\n')
        # Now negate all SELECT... value<operator><value> with
        # SELECT topic_prefix FROM topic_tags WHERE topic_prefix NOT IN (SELECT....value<operator><value>)

        search_pattern = r'(SELECT\s+topic_prefix\s+FROM\s+' + table_name + \
                         r'\s+WHERE\s+tag=\'.*\'\s+AND\s+value.*($|\n))'

        replace_pattern = r'SELECT topic_prefix FROM ' + table_name + r' WHERE topic_prefix NOT IN (\1)\2'
        c = re.search(search_pattern, condition)
        condition = re.sub(search_pattern,
                           replace_pattern,
                           condition,
                           flags=re.I
                           )
        _log.debug("Condition after negation: {}".format(condition))
        return condition


if __name__ == '__main__':
    con = {
        "database": '/tmp/tmpgLzWr3/historian.sqlite'
    }
    tables_def = {
        "table_prefix": "prefix",
        "data_table": "data_table",
        "topics_table": "topics_table",
        "meta_table": "meta_table"
    }
    functs = SqlLiteFuncts(con, tables_def)
    functs.collect_aggregate('device1/in_temp', 'sum',
                             datetime.strptime('2016-06-05 22:47:02.417604+00:00', "%Y-%m-%d %H:%M:%S.%f+00:00"),
                             datetime.strptime('2016-06-05 22:49:02.417604+00:00', "%Y-%m-%d %H:%M:%S.%f+00:00"))
