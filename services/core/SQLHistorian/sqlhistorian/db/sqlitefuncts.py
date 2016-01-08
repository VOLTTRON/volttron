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
#}}}

import errno
import logging
import os
import sqlite3

from zmq.utils import jsonapi

from basedb import DbDriver
from volttron.platform.agent import utils

utils.setup_logging()
_log = logging.getLogger(__name__)

class SqlLiteFuncts(DbDriver):

    def __init__(self, database, **kwargs):
        print ("initializing historian database")
        if database == ':memory:':
            self.__database = database
        else:

            self.__database = os.path.expandvars(os.path.expanduser(database))
            db_dir  = os.path.dirname(self.__database)

            #If the db does not exist create it
            # in case we are started before the historian.
            try:
                if db_dir == '':
                    db_dir = './data'
                    self.__database=os.path.join(db_dir, self.__database)
                    
                os.makedirs(db_dir)
            except OSError as exc:
                if exc.errno != errno.EEXIST or not os.path.isdir(db_dir):
                    raise
            
        conn = sqlite3.connect(self.__database, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS data
                                (ts timestamp NOT NULL,
                                 topic_id INTEGER NOT NULL,
                                 value_string TEXT NOT NULL,
                                 UNIQUE(ts, topic_id))''')

        cursor.execute('''CREATE INDEX IF NOT EXISTS data_idx
                                ON data (ts ASC)''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS topics
                                (topic_id INTEGER PRIMARY KEY,
                                 topic_name TEXT NOT NULL,
                                 UNIQUE(topic_name))''')
        conn.commit()
        conn.close()
        
        try:
            kwargs.pop('database')
        except:
            pass
        finally:
            kwargs['database'] = self.__database
        
        if 'detect_types' not in kwargs.keys():
            kwargs['detect_types'] = sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES
        
        print (kwargs)    
        super(SqlLiteFuncts, self).__init__('sqlite3', **kwargs)
        


    def query(self, topic, start=None, end=None, skip=0,
                            count=None, order="FIRST_TO_LAST"):
        """This function should return the results of a query in the form:
        {"values": [(timestamp1, value1), (timestamp2, value2), ...],
         "metadata": {"key1": value1, "key2": value2, ...}}

         metadata is not required (The caller will normalize this to {} for you)
        """
        query = '''SELECT data.ts, data.value_string
                   FROM data, topics
                   {where}
                   {order_by}
                   {limit}
                   {offset}'''

        where_clauses = ["WHERE topics.topic_name = ?", "topics.topic_id = data.topic_id"]
        args = [topic]

        if start is not None:
            start_str=start.isoformat(' ')
            where_clauses.append("data.ts >= ?")
            if start_str[-6:] != "+00:00":
                start_str = start_str + "+00:00"
            args.append(start_str)

        if end is not None:
            end_str = end.isoformat(' ')
            where_clauses.append("data.ts <= ?")
            if end_str[-6:] != "+00:00":
                end_str = end_str + "+00:00"
            args.append(end_str)

        where_statement = ' AND '.join(where_clauses)

        order_by = 'ORDER BY data.ts ASC'
        if order == 'LAST_TO_FIRST':
            order_by = ' ORDER BY data.ts DESC'

        #can't have an offset without a limit
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

        _log.debug("About to do real_query")

        real_query = query.format(where=where_statement,
                                  limit=limit_statement,
                                  offset=offset_statement,
                                  order_by=order_by)
        _log.debug("Real Query: " + real_query)
        _log.debug("args: "+str(args))

        c = sqlite3.connect(self.__database, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
        rows = c.execute(real_query,args)

        values = [(ts.isoformat(), jsonapi.loads(value)) for ts, value in rows]
        _log.debug("QueryResults: " + str(values))
        return {'values':values}

    def insert_data_query(self):
        return '''INSERT OR REPLACE INTO data values(?, ?, ?)'''
    
    def insert_topic_query(self):
        return '''INSERT OR REPLACE INTO topics (topic_name) values (?)'''

    def get_topic_map(self):
        q = "SELECT topic_id, topic_name FROM topics"
        rows = self.select(q, None)
        return dict([(n, t) for t, n in rows])