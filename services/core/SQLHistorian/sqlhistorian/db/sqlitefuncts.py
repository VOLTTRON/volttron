# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2015, Battelle Memorial Institute
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

import errno
import logging
import os
import sqlite3
import threading

from zmq.utils import jsonapi

from basedb import DbDriver
from volttron.platform.agent import utils

utils.setup_logging()
_log = logging.getLogger(__name__)


class SqlLiteFuncts(DbDriver):

    def __init__(self, connect_params, tables_def):
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

        self.data_table = tables_def['data_table']
        self.topics_table = tables_def['topics_table']
        self.meta_table = tables_def['meta_table']

        conn = sqlite3.connect(
            self.__database,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS ''' + self.data_table +
                       ''' (ts timestamp NOT NULL,
                       topic_id INTEGER NOT NULL,
                       value_string TEXT NOT NULL,
                       UNIQUE(ts, topic_id))''')

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
        conn.commit()
        conn.close()
        
        connect_params['database'] = self.__database
        
        if 'detect_types' not in connect_params.keys():
            connect_params['detect_types'] = \
                sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        
        print (connect_params)
        super(SqlLiteFuncts, self).__init__('sqlite3', **connect_params)

    def query(self, topic_id, start=None, end=None, skip=0,
                            count=None, order="FIRST_TO_LAST"):
        """This function should return the results of a query in the form:
        {"values": [(timestamp1, value1), (timestamp2, value2), ...],
         "metadata": {"key1": value1, "key2": value2, ...}}

         metadata is not required (The caller will normalize this to {}
         for you)
         @param order:
         @param count:
         @param skip:
         @param end:
         @param start:
         @param topic_id:
        """
        query = '''SELECT ts, value_string
                   FROM ''' + self.data_table + '''
                   {where}
                   {order_by}
                   {limit}
                   {offset}'''

        where_clauses = ["WHERE topic_id = ?"]
        args = [topic_id]

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

        order_by = 'ORDER BY ts ASC'
        if order == 'LAST_TO_FIRST':
            order_by = ' ORDER BY ts DESC'

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

        values = [(utils.format_timestamp(ts),
                   jsonapi.loads(value)) for ts, value in rows]
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