# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
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
# Government nor the United States Department of Energy, nor Battelle,
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
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}
import ast
import errno
import logging
import sqlite3
import threading
from datetime import datetime

import os
import re
from basedb import DbDriver
from volttron.platform.agent import utils
from zmq.utils import jsonapi

utils.setup_logging()
_log = logging.getLogger(__name__)


class SqlLiteFuncts(DbDriver):
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
                    db_dir = './data'
                    self.__database = os.path.join(db_dir, self.__database)

                os.makedirs(db_dir)
            except OSError as exc:
                if exc.errno != errno.EEXIST or not os.path.isdir(db_dir):
                    raise

        connect_params['database'] = self.__database

        if 'detect_types' not in connect_params.keys():
            connect_params['detect_types'] = \
                sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES

        print (connect_params)
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

        super(SqlLiteFuncts, self).__init__('sqlite3', **connect_params)

    def setup_historian_tables(self):

        conn = sqlite3.connect(
            self.__database,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS ''' + self.data_table +
                       ''' (ts timestamp NOT NULL,
                       topic_id INTEGER NOT NULL,
                       value_string TEXT NOT NULL,
                       UNIQUE(topic_id, ts))''')
        cursor.execute('''CREATE INDEX IF NOT EXISTS data_idx
                                ON ''' + self.data_table + ''' (ts ASC)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS ''' +
                       self.topics_table +
                       ''' (topic_id INTEGER PRIMARY KEY,
                            topic_name TEXT NOT NULL,
                            UNIQUE(topic_name))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS ''' + self.meta_table +
                       '''(topic_id INTEGER PRIMARY KEY,
                        metadata TEXT NOT NULL)''')
        _log.debug("Created data topics and meta tables")

        conn.commit()
        conn.close()

    def record_table_definitions(self, table_defs, meta_table_name):
        _log.debug(
            "In record_table_def {} {}".format(table_defs, meta_table_name))
        conn = sqlite3.connect(
            self.__database,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        cursor = conn.cursor()

        cursor.execute(
            'CREATE TABLE IF NOT EXISTS ' + meta_table_name +
            ' (table_id TEXT PRIMARY KEY, \
               table_name TEXT NOT NULL, \
               table_prefix TEXT);')

        table_prefix = table_defs.get('table_prefix', "")

        cursor.execute('INSERT OR REPLACE INTO ' + meta_table_name
                       + ' VALUES (?, ?, ?)',
                       ['data_table', table_defs['data_table'], table_prefix])
        cursor.execute('INSERT OR REPLACE INTO ' + meta_table_name
                       + ' VALUES (?, ?, ?)',
                       ['topics_table', table_defs['topics_table'],
                        table_prefix])
        cursor.execute('INSERT OR REPLACE INTO ' + meta_table_name +
                       ' VALUES (?, ?, ?)',
                       ['meta_table', table_defs['meta_table'], table_prefix])

        conn.commit()

    def setup_aggregate_historian_tables(self, meta_table_name):
        table_names = self.read_tablenames_from_db(meta_table_name)

        self.data_table = table_names['data_table']
        self.topics_table = table_names['topics_table']
        self.meta_table = table_names['meta_table']
        self.agg_topics_table = table_names.get('agg_topics_table', None)
        self.agg_meta_table = table_names.get('agg_meta_table', None)

        conn = sqlite3.connect(
            self.__database,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        cursor = conn.cursor()

        cursor.execute(
            'CREATE TABLE IF NOT EXISTS ' + self.agg_topics_table +
            ' (agg_topic_id INTEGER PRIMARY KEY, \
               agg_topic_name TEXT NOT NULL, \
               agg_type TEXT NOT NULL, \
               agg_time_period TEXT NOT NULL, \
               UNIQUE(agg_topic_name, agg_type, agg_time_period));')
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS ' + self.agg_meta_table +
            '(agg_topic_id INTEGER NOT NULL PRIMARY KEY, \
              metadata TEXT NOT NULL);')
        _log.debug("Created aggregate topics and meta tables")
        conn.commit()
        conn.close()

    def query(self, topic_ids, id_name_map, start=None, end=None,
              agg_type=None, agg_period=None, skip=0, count=None,
              order="FIRST_TO_LAST"):
        """This function should return the results of a query in the form:
        {"values": [(timestamp1, value1), (timestamp2, value2), ...],
         "metadata": {"key1": value1, "key2": value2, ...}}

         metadata is not required (The caller will normalize this to {}
         for you)
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
        if len(topic_ids) > 1:
            where_str = "WHERE topic_id IN ("
            for _ in topic_ids:
                where_str += "?, "
            where_str = where_str[:-2]  # strip last comma and space
            where_str += ") "
            where_clauses = [where_str]
            args = topic_ids

        if start is not None:
            start_str = start.isoformat(' ')
            where_clauses.append("ts >= ?")
            if start_str[-6:] != "+00:00":
                start_str += "+00:00"
            args.append(start_str)

        if end is not None:
            end_str = end.isoformat(' ')
            where_clauses.append("ts <= ?")
            if end_str[-6:] != "+00:00":
                end_str += "+00:00"
            args.append(end_str)

        where_statement = ' AND '.join(where_clauses)

        order_by = 'ORDER BY topic_id ASC, ts ASC'
        if order == 'LAST_TO_FIRST':
            order_by = ' ORDER BY topic_id DESC, ts DESC'

        # can't have an offset without a limit
        # -1 = no limit and allows the user to
        # provied just an offset
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

        c = sqlite3.connect(
            self.__database,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        rows = c.execute(real_query, args)
        if len(topic_ids) > 1:
            values = [(id_name_map[topic_id], utils.format_timestamp(ts),
                       jsonapi.loads(value)) for topic_id, ts, value in rows]
        else:
            values = [(utils.format_timestamp(ts),
                       jsonapi.loads(value)) for topic_id, ts, value in rows]

        _log.debug("QueryResults: " + str(values))
        return {'values': values}

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


    def insert_agg_topic(self, topic, agg_type, agg_time_period):
        _log.debug("In sqlitefuncts insert aggregate topic")
        conn = sqlite3.connect(
            self.__database,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)

        if conn is None:
            return False

        cursor = conn.cursor()

        cursor.execute(self.insert_agg_topic_stmt(),
                       (topic, agg_type, agg_time_period))
        row = [cursor.lastrowid]
        conn.commit()
        conn.close()
        return row

    def insert_agg_topic_stmt(self):
        return '''INSERT INTO ''' + self.agg_topics_table + '''
               (agg_topic_name, agg_type, agg_time_period )
               values (?, ?, ?)'''

    def update_agg_topic(self, agg_id, agg_topic_name):
        _log.debug("In sqlitefuncts update aggregate topic")
        conn = sqlite3.connect(
            self.__database,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)

        if conn is None:
            return False

        cursor = conn.cursor()

        cursor.execute(self.update_agg_topic_stmt(),
                       (agg_id, agg_topic_name))
        conn.commit()
        conn.close()

    def update_agg_topic_stmt(self):
        return '''UPDATE ''' + self.agg_topics_table + ''' SET
        agg_topic_name = ? WHERE agg_topic_id = ? '''

    def insert_agg_meta(self, topic_id, metadata):
        _log.debug("In sqlitefuncts insert aggregate meta")
        conn = sqlite3.connect(
            self.__database,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)

        if conn is None:
            return False

        cursor = conn.cursor()
        cursor.execute(self.insert_agg_meta_stmt(),
                       (topic_id, jsonapi.dumps(metadata)))
        conn.commit()
        conn.close()
        return True

    def insert_agg_meta_stmt(self):
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
            query = "SELECT agg_topic_name, agg_type, agg_time_period, " \
                    "metadata FROM " + self.agg_topics_table + " as t, " + \
                    self.agg_meta_table + " as m WHERE t.agg_topic_id = " \
                                          "m.agg_topic_id "
            rows = self.select(query, None)
            topics = []
            for row in rows:
                _log.debug("rows from aggregate_t")
                meta = ast.literal_eval(row[3])['configured_topics']
                topics.append((row[0], row[1], row[2], meta))
            return topics
        except sqlite3.Error as e:
            if e.message[0:13] == 'no such table':
                _log.warn("No such table : {}".format(self.agg_topics_table))
                return []
            else:
                raise

    def get_agg_topic_map(self):
        try:
            _log.debug("in get_agg_topic_map")
            q = "SELECT agg_topic_id, agg_topic_name, agg_type, " \
                "agg_time_period " \
                "FROM " + self.agg_topics_table
            rows = self.select(q, None)
            _log.debug("loading agg_topic map from db")
            id_map = dict()
            for row in rows:
                _log.debug("rows from aggregate_t")
                id_map[(row[1].lower(), row[2], row[3])] = row[0]
            return id_map
        except sqlite3.Error as e:
            if e.message[0:13] == 'no such table':
                _log.warn("No such table : {}".format(self.agg_topics_table))
                return {}
            else:
                raise

    @staticmethod
    def regexp(expr, item):
        _log.debug("item {} matched against expr {}".format(item, expr))
        return re.search(expr, item, re.IGNORECASE) is not None

    def regex_select(self, query, args):
        conn = sqlite3.connect(
            self.__database,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)

        if conn is None:
            _log.error("Unable to connect to sqlite database {} ".format(
                self.__database))
            return []

        conn.create_function("REGEXP", 2, SqlLiteFuncts.regexp)
        _log.debug(" REGEXP query {}  ARGS: {}".format(query, args))
        cursor = conn.cursor()
        if args is not None:
            cursor.execute(query, args)
        else:
            cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        return rows

    def find_topics_by_pattern(self, topic_pattern):
        id_map, name_map = self.get_topic_map()
        _log.debug("Contents of topics table {}".format(id_map.keys()))
        q = "SELECT topic_id, topic_name FROM " + self.topics_table + \
            " WHERE topic_name REGEXP '" + topic_pattern + "';"

        rows = self.regex_select(q, None)
        _log.debug("loading topic map from db")
        id_map = dict()
        for t, n in rows:
            id_map[n.lower()] = t
        _log.debug("topics that matched the pattern {} : {}".format(
            topic_pattern, id_map))
        return id_map

    def create_aggregate_store(self, agg_type, period):

        table_name = agg_type + '''_''' + period

        # period = sqlutils.parse_time_period(period)
        stmt = "CREATE TABLE IF NOT EXISTS " + table_name + \
               " (ts timestamp NOT NULL, topic_id INTEGER NOT NULL, " \
               "value_string TEXT NOT NULL, topics TEXT, " \
               "UNIQUE(topic_id, ts)); "
        c = sqlite3.connect(
            self.__database,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        c.execute(stmt)

        stmt = "CREATE INDEX IF NOT EXISTS idx_" + table_name + " ON " + \
               table_name + "(ts ASC);"

        c.execute(stmt)
        c.commit()
        return True

    def insert_aggregate_stmt(self, table_name):
        return '''INSERT OR REPLACE INTO ''' + table_name + \
               ''' values(?, ?, ?, ?)'''

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
                raise ValueError(
                    "Invalid aggregation type {}".format(agg_type))
        query = '''SELECT ''' \
                + agg_type + '''(value_string), count(value_string) FROM ''' \
                + self.data_table + ''' {where}'''

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

        if start is not None:
            start_str = start.isoformat(' ')
            where_clauses.append("ts >= ?")
            if start_str[-6:] != "+00:00":
                start_str += "+00:00"
            args.append(start_str)

        if end is not None:
            end_str = end.isoformat(' ')
            where_clauses.append("ts < ?")
            if end_str[-6:] != "+00:00":
                end_str += "+00:00"
            args.append(end_str)

        where_statement = ' AND '.join(where_clauses)

        real_query = query.format(where=where_statement)
        _log.debug("Real Query: " + real_query)
        _log.debug("args: " + str(args))

        c = sqlite3.connect(
            self.__database,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        cursor = c.execute(real_query, args)
        results = cursor.fetchone()
        if results:
            _log.debug("results got {}, {}".format(results[0], results[1]))
            return results[0], results[1]
        else:
            return 0, 0


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
    functs.collect_aggregate('device1/in_temp',
                             'sum',
                             datetime.strptime(
                                 '2016-06-05 22:47:02.417604+00:00',
                                 "%Y-%m-%d %H:%M:%S.%f+00:00"),
                             datetime.strptime(
                                 '2016-06-05 22:49:02.417604+00:00',
                                 "%Y-%m-%d %H:%M:%S.%f+00:00")
                             )
