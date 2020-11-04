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
import ast
import logging
from collections import defaultdict

import pytz
import re
from .basedb import DbDriver
from mysql.connector import Error as MysqlError
from mysql.connector import errorcode as mysql_errorcodes
from volttron.platform.agent import utils
from volttron.platform import jsonapi

utils.setup_logging()
_log = logging.getLogger(__name__)

"""
Implementation of Mysql database operation for
:py:class:`sqlhistorian.historian.SQLHistorian` and
:py:class:`sqlaggregator.aggregator.SQLAggregateHistorian`
For method details please refer to base class
:py:class:`volttron.platform.dbutils.basedb.DbDriver`
"""
class MySqlFuncts(DbDriver):
    def __init__(self, connect_params, table_names):
        # kwargs['dbapimodule'] = 'mysql.connector'
        self.MICROSECOND_SUPPORT = None

        self.data_table = None
        self.topics_table = None
        self.meta_table = None
        self.agg_topics_table = None
        self.agg_meta_table = None

        if table_names:
            self.data_table = table_names['data_table']
            self.topics_table = table_names['topics_table']
            self.meta_table = table_names['meta_table']
            self.agg_topics_table = table_names.get('agg_topics_table', None)
            self.agg_meta_table = table_names.get('agg_meta_table', None)
        # This is needed when reusing the same connection. Else cursor returns
        # cached data even if we create a new cursor for each query and
        # close the cursor after fetching results
        connect_params['autocommit'] = True
        super(MySqlFuncts, self).__init__('mysql.connector', auth_plugin='mysql_native_password',
                                          **connect_params)

    def init_microsecond_support(self):
        rows = self.select("SELECT version()", None)
        p = re.compile('(\d+)\D+(\d+)\D+(\d+)\D*')
        version_nums = p.match(rows[0][0]).groups()
        if int(version_nums[0]) < 5:
            self.MICROSECOND_SUPPORT = False
        elif int(version_nums[1]) < 6:
            self.MICROSECOND_SUPPORT = False
        elif int(version_nums[2]) < 4:
            self.MICROSECOND_SUPPORT = False
        else:
            self.MICROSECOND_SUPPORT = True

    def setup_historian_tables(self):
        if self.MICROSECOND_SUPPORT is None:
            self.init_microsecond_support()

        rows = self.select("show tables like %s", [self.data_table])
        if rows:
            _log.debug("Found table {}. Historian table exists".format(
                self.data_table))
            return

        try:
            if self.MICROSECOND_SUPPORT:
                self.execute_stmt(
                    'CREATE TABLE ' + self.data_table +
                    ' (ts timestamp(6) NOT NULL,\
                     topic_id INTEGER NOT NULL, \
                     value_string TEXT NOT NULL, \
                     UNIQUE(topic_id, ts))')
            else:
                self.execute_stmt(
                    'CREATE TABLE ' + self.data_table +
                    ' (ts timestamp NOT NULL,\
                     topic_id INTEGER NOT NULL, \
                     value_string TEXT NOT NULL, \
                     UNIQUE(topic_id, ts))')

            self.execute_stmt('''CREATE INDEX data_idx
                                    ON ''' + self.data_table + ''' (ts ASC)''')
            self.execute_stmt('''CREATE TABLE  ''' +
                              self.topics_table +
                              ''' (topic_id INTEGER NOT NULL AUTO_INCREMENT,
                                   topic_name varchar(512) NOT NULL,
                                   PRIMARY KEY (topic_id),
                                   UNIQUE(topic_name))''')
            self.execute_stmt('''CREATE TABLE  '''
                              + self.meta_table +
                              '''(topic_id INTEGER NOT NULL,
                               metadata TEXT NOT NULL,
                               PRIMARY KEY(topic_id))''')
            self.commit()
            _log.debug("Created data topics and meta tables")
        except MysqlError as err:
            err_msg = "Error creating " \
                      "historian tables as the configured user. " \
                      "Please create the tables manually before " \
                      "restarting historian. Please refer to " \
                      "mysql-create*.sql files for create " \
                      "statements"
            if err.errno == mysql_errorcodes.ER_TABLEACCESS_DENIED_ERROR:
                err_msg = "Access denied : " + err_msg
            else:
                err_msg = err.msg + " : " + err_msg
            raise RuntimeError(err_msg)

    def record_table_definitions(self, tables_def, meta_table_name):
        _log.debug(
            "In record_table_def {} {}".format(tables_def, meta_table_name))

        rows = self.select("show tables like %s", [meta_table_name])
        if rows:
            _log.debug("Found meta data table {}. ".format(meta_table_name))
        else:
            self.execute_stmt(
                'CREATE TABLE ' + meta_table_name +
                ' (table_id varchar(512) PRIMARY KEY, \
                   table_name varchar(512) NOT NULL, \
                   table_prefix varchar(512));')

        table_prefix = tables_def.get('table_prefix', "")

        insert_stmt = 'REPLACE INTO ' + meta_table_name + \
                      ' VALUES (%s, %s, %s)'
        self.execute_stmt(insert_stmt,
                         ('data_table', tables_def['data_table'],
                          table_prefix))
        self.execute_stmt(insert_stmt,
                         ('topics_table', tables_def['topics_table'],
                          table_prefix))
        self.execute_stmt(
            insert_stmt,
            ('meta_table', tables_def['meta_table'], table_prefix),
            commit=True)

    def setup_aggregate_historian_tables(self, meta_table_name):
        _log.debug("CREATING AGG TABLES")
        table_names = self.read_tablenames_from_db(meta_table_name)

        self.data_table = table_names['data_table']
        self.topics_table = table_names['topics_table']
        _log.debug("In setup_aggregate_historian self.topics_table"
                   " {}".format(self.topics_table))
        self.meta_table = table_names['meta_table']
        self.agg_topics_table = table_names.get('agg_topics_table', None)
        self.agg_meta_table = table_names.get('agg_meta_table', None)

        rows = self.select("show tables like %s", [self.agg_topics_table])
        if rows:
            _log.debug("Found table {}. Historian table exists".format(
                self.agg_topics_table))
        else:
            self.execute_stmt(
                'CREATE TABLE ' + self.agg_topics_table +
                ' (agg_topic_id INTEGER NOT NULL AUTO_INCREMENT, \
                   agg_topic_name varchar(512) NOT NULL, \
                   agg_type varchar(512) NOT NULL, \
                   agg_time_period varchar(512) NOT NULL, \
                   PRIMARY KEY (agg_topic_id), \
                   UNIQUE(agg_topic_name, agg_type, agg_time_period));')

            self.execute_stmt(
                'CREATE TABLE ' + self.agg_meta_table +
                '(agg_topic_id INTEGER NOT NULL, \
                  metadata TEXT NOT NULL, \
                  PRIMARY KEY(agg_topic_id));')
            self.commit()
        _log.debug("Created aggregate topics and meta tables")

    def query(self, topic_ids, id_name_map, start=None, end=None, skip=0,
              agg_type=None, agg_period=None, count=None,
              order="FIRST_TO_LAST"):

        table_name = self.data_table
        if agg_type and agg_period:
            table_name = agg_type + "_" + agg_period

        query = '''SELECT topic_id, ts, value_string
                FROM ''' + table_name + '''
                {where}
                {order_by}
                {limit}
                {offset}'''

        if self.MICROSECOND_SUPPORT is None:
            self.init_microsecond_support()

        where_clauses = ["WHERE topic_id = %s"]
        args = [topic_ids[0]]

        if start is not None:
            if start.tzinfo != pytz.UTC:
                start = start.astimezone(pytz.UTC)
            if not self.MICROSECOND_SUPPORT:
                start_str = start.isoformat()
                start = start_str[:start_str.rfind('.')]

        if end is not None:
            if end.tzinfo !=pytz.UTC:
                end = end.astimezone(pytz.UTC)
            if not self.MICROSECOND_SUPPORT:
                end_str = end.isoformat()
                end = end_str[:end_str.rfind('.')]

        if start and end and start == end:
            where_clauses.append("ts = %s")
            args.append(start)
        else:
            if start:
                where_clauses.append("ts >= %s")
                args.append(start)
            if end:
                where_clauses.append("ts < %s")
                args.append(end)

        where_statement = ' AND '.join(where_clauses)

        order_by = 'ORDER BY ts ASC'
        if order == 'LAST_TO_FIRST':
            order_by = ' ORDER BY topic_id DESC, ts DESC'

        # can't have an offset without a limit
        # -1 = no limit and allows the user to
        # provide just an offset
        if count is None:
            count = 100

        limit_statement = 'LIMIT %s'
        args.append(int(count))

        offset_statement = ''
        if skip > 0:
            offset_statement = 'OFFSET %s'
            args.append(skip)

        _log.debug("About to do real_query")
        values = defaultdict(list)
        for topic_id in topic_ids:
            args[0] = topic_id
            values[id_name_map[topic_id]] = []
            real_query = query.format(where=where_statement,
                                      limit=limit_statement,
                                      offset=offset_statement,
                                      order_by=order_by)
            _log.debug("Real Query: " + real_query)
            _log.debug("args: " + str(args))

            cursor = self.select(real_query, args, fetch_all=False)
            if cursor:
                for _id, ts, value in cursor:
                    values[id_name_map[topic_id]].append(
                        (utils.format_timestamp(ts.replace(tzinfo=pytz.UTC)),
                         jsonapi.loads(value)))

            if cursor is not None:
                cursor.close()
        return values

    def insert_meta_query(self):
        return '''REPLACE INTO ''' + self.meta_table + ''' values(%s, %s)'''

    def insert_data_query(self):
        return '''REPLACE INTO ''' + self.data_table + \
               '''  values(%s, %s, %s)'''

    def insert_topic_query(self):
        _log.debug("In insert_topic_query - self.topic_table "
                   "{}".format(self.topics_table))
        return '''INSERT INTO ''' + self.topics_table + ''' (topic_name)
            values (%s)'''

    def update_topic_query(self):
        return '''UPDATE ''' + self.topics_table + ''' SET topic_name = %s
            WHERE topic_id = %s'''

    def get_aggregation_list(self):
        return ['AVG', 'MIN', 'MAX', 'COUNT', 'SUM', 'BIT_AND', 'BIT_OR',
                'BIT_XOR', 'GROUP_CONCAT', 'STD', 'STDDEV', 'STDDEV_POP',
                'STDDEV_SAMP', 'VAR_POP', 'VAR_SAMP', 'VARIANCE']

    def insert_agg_topic_stmt(self):
        _log.debug("Insert aggregate topics stmt inserts "
                   "into {}".format(self.agg_topics_table))
        return '''INSERT INTO ''' + self.agg_topics_table + '''
            (agg_topic_name, agg_type, agg_time_period )
            values (%s, %s, %s)'''

    def update_agg_topic_stmt(self):
        return '''UPDATE ''' + self.agg_topics_table + ''' SET
        agg_topic_name = %s WHERE agg_topic_id = %s '''

    def replace_agg_meta_stmt(self):
        return '''REPLACE INTO ''' + self.agg_meta_table + ''' values(%s,
        %s)'''

    def get_topic_map(self):
        q = "SELECT topic_id, topic_name FROM " + self.topics_table + ";"
        rows = self.select(q, None)
        _log.debug("loading topic map from db")
        id_map = dict()
        name_map = dict()
        for t, n in rows:
            id_map[n.lower()] = t
            name_map[n.lower()] = n
        _log.debug(id_map)
        _log.debug(name_map)
        return id_map, name_map

    def get_agg_topics(self):
        _log.debug("in get_agg_topics")
        try:
            query = "SELECT agg_topic_name, agg_type, agg_time_period, " \
                    "metadata FROM " + self.agg_topics_table + " as t, " + \
                    self.agg_meta_table + " as m WHERE t.agg_topic_id = " \
                                          "m.agg_topic_id "
            rows = self.select(query, None)
            topics = []
            for row in rows:
                meta = ast.literal_eval(row[3])['configured_topics']
                topics.append((row[0], row[1], row[2], meta))
            return topics
        except MysqlError as e:
            if e.errno == mysql_errorcodes.ER_NO_SUCH_TABLE:
                return []
            else:
                raise

    def get_agg_topic_map(self):
        _log.debug("in get_agg_topic_map")
        try:
            q = "SELECT agg_topic_id, agg_topic_name, agg_type, " \
                "agg_time_period " \
                "FROM " + self.agg_topics_table
            rows = self.select(q, None)
            _log.debug("loading agg_topic map from db")
            id_map = dict()
            for row in rows:
                _log.debug("rows from aggregate_topics {}".format(row))
                id_map[(row[1].lower(), row[2], row[3])] = row[0]
            return id_map
        except MysqlError as e:
            if e.errno == mysql_errorcodes.ER_NO_SUCH_TABLE:
                return {}
            else:
                raise

    def query_topics_by_pattern(self, topic_pattern):
        q = "SELECT topic_id, topic_name FROM " + self.topics_table + \
            " WHERE lower(topic_name) REGEXP lower('" + topic_pattern + "');"

        rows = self.select(q, None)
        _log.debug("loading topic map from db")
        id_map = dict()
        for t, n in rows:
            id_map[n] = t
        _log.debug("topics that matched the pattern {} : {}".format(
            topic_pattern, id_map))
        return id_map

    def create_aggregate_store(self, agg_type, agg_time_period):
        table_name = agg_type + '''_''' + agg_time_period
        if self.MICROSECOND_SUPPORT is None:
            self.init_microsecond_support()

        rows = self.select("show tables like %s", [table_name])
        if rows:
            _log.debug("Found table {}. Historian table exists".format(table_name))
        else:
            stmt = "CREATE TABLE " + table_name + \
                   " (ts timestamp(6) NOT NULL, topic_id INTEGER NOT NULL, " \
                   "value_string TEXT NOT NULL, topics_list TEXT," \
                   " UNIQUE(topic_id, ts)," \
                   "INDEX (ts ASC))"
            if not self.MICROSECOND_SUPPORT:
                stmt = "CREATE TABLE " + table_name + \
                       " (ts timestamp NOT NULL, topic_id INTEGER NOT NULL, " \
                       "value_string TEXT NOT NULL, topics_list TEXT," \
                       " UNIQUE(topic_id, ts)," \
                       "INDEX (ts ASC))"
            return self.execute_stmt(stmt, commit=True)

    def insert_aggregate_stmt(self, table_name):
        return '''REPLACE INTO ''' + table_name + \
               ''' values(%s, %s, %s, %s)'''

    def collect_aggregate(self, topic_ids, agg_type, start=None, end=None):
        if isinstance(agg_type, str):
            if agg_type.upper() not in ['AVG', 'MIN', 'MAX', 'COUNT', 'SUM']:
                raise ValueError(
                    "Invalid aggregation type {}".format(agg_type))
        query = '''SELECT ''' \
                + agg_type + '''(value_string), count(value_string) FROM ''' \
                + self.data_table + ''' {where}'''
        where_clauses = ["WHERE topic_id = %s"]
        args = [topic_ids[0]]
        if len(topic_ids) > 1:
            where_str = "WHERE topic_id IN ("
            for _ in topic_ids:
                where_str += "%s, "
            where_str = where_str[:-2]  # strip last comma and space
            where_str += ") "
            where_clauses = [where_str]
            args = topic_ids[:]

        if start is not None:
            where_clauses.append("ts >= %s")
            if self.MICROSECOND_SUPPORT:
                args.append(start)
            else:
                start_str = start.isoformat()
                args.append(start_str[:start_str.rfind('.')])

        if end is not None:
            where_clauses.append("ts < %s")
            if self.MICROSECOND_SUPPORT:
                args.append(end)
            else:
                end_str = end.isoformat()
                args.append(end_str[:end_str.rfind('.')])

        where_statement = ' AND '.join(where_clauses)

        real_query = query.format(where=where_statement)
        _log.debug("Real Query: " + real_query)
        _log.debug("args: " + str(args))

        rows = self.select(real_query, args)
        if rows:
            return rows[0][0], rows[0][1]
        else:
            return 0, 0
