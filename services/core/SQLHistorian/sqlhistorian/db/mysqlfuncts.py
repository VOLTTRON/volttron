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

import logging
import pytz
import re
from zmq.utils import jsonapi

from basedb import DbDriver
from volttron.platform.agent import utils

utils.setup_logging()
_log = logging.getLogger(__name__)


class MySqlFuncts(DbDriver):
    def __init__(self, connect_params, tables_def):
        # kwargs['dbapimodule'] = 'mysql.connector'
        super(MySqlFuncts, self).__init__('mysql.connector', **connect_params)
        self.MICROSECOND_SUPPORT = None
        self.data_table = tables_def['data_table']
        self.topics_table = tables_def['topics_table']
        self.meta_table = tables_def['meta_table']

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

    def query(self, topic_id, start=None, end=None, skip=0,
              count=None, order="FIRST_TO_LAST"):
        """This function should return the results of a query in the form:
        {"values": [(timestamp1, value1), (timestamp2, value2), ...],
         "metadata": {"key1": value1, "key2": value2, ...}}

         metadata is not required (The caller will normalize this to {}
         for you)
        """
        query = '''SELECT ts, value_string
                FROM ''' + self.data_table + '''
                {where}
                {order_by}
                {limit}
                {offset}'''

        if self.MICROSECOND_SUPPORT is None:
            self.init_microsecond_support()

        where_clauses = ["WHERE topic_id = %s"]
        args = [topic_id]

        if start is not None:
            where_clauses.append("ts >= %s")
            if self.MICROSECOND_SUPPORT:
                args.append(start)
            else:
                start_str = start.isoformat()
                args.append(start_str[:start_str.rfind('.')])

        if end is not None:
            where_clauses.append("ts <= %s")
            if self.MICROSECOND_SUPPORT:
                args.append(end)
            else:
                end_str = end.isoformat()
                args.append(end_str[:end_str.rfind('.')])

        where_statement = ' AND '.join(where_clauses)

        order_by = 'ORDER BY ts ASC'
        if order == 'LAST_TO_FIRST':
            order_by = ' ORDER BY ts DESC'

        # can't have an offset without a limit
        # -1 = no limit and allows the user to
        # provied just an offset
        if count is None:
            count = 100

        limit_statement = 'LIMIT %s'
        args.append(count)

        offset_statement = ''
        if skip > 0:
            offset_statement = 'OFFSET %s'
            args.append(skip)

        _log.debug("About to do real_query")

        real_query = query.format(where=where_statement,
                                  limit=limit_statement,
                                  offset=offset_statement,
                                  order_by=order_by)
        _log.debug("Real Query: " + real_query)
        _log.debug("args: " + str(args))

        rows = self.select(real_query, args)
        if rows:
            values = [(utils.format_timestamp(ts.replace(tzinfo=pytz.UTC)),
                       jsonapi.loads(
                value)) for ts, value in rows]
        else:
            values = {}

        return {'values': values}

    def insert_meta_query(self):
        return '''REPLACE INTO ''' + self.meta_table + ''' values(%s, %s)'''

    def insert_data_query(self):
        return '''REPLACE INTO ''' + self.data_table + \
            '''  values(%s, %s, %s)'''

    def insert_topic_query(self):
        return '''INSERT INTO ''' + self.topics_table + ''' (topic_name)
            values (%s)'''

    def update_topic_query(self):
        return '''UPDATE ''' + self.topics_table + ''' SET topic_name = %s
            WHERE topic_id = %s'''

    #@property
    def get_topic_map(self):
        _log.debug("in get_topic_map")
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
