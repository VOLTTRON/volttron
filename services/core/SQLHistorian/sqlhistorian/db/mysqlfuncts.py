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

#from mysql import connector
from zmq.utils import jsonapi

from basedb import DbDriver
from volttron.platform.agent import utils

utils.setup_logging()
_log = logging.getLogger(__name__)

class MySqlFuncts(DbDriver):

    def __init__(self, **kwargs):
        #kwargs['dbapimodule'] = 'mysql.connector'
        super(MySqlFuncts, self).__init__('mysql.connector', **kwargs)
        self.MICROSECOND_SUPPORT = None

    def init_microsecond_support(self):
        rows = self.select("SELECT version()",None)
        version_nums = rows[0][0].split(".")
        if int(version_nums[0]) < 5:
            self.MICROSECOND_SUPPORT  = False
        elif int(version_nums[1]) <  6:
            self.MICROSECOND_SUPPORT =  False
        else:
            rev = version_nums[2]
            if 'ubuntu' in version_nums[2]:
                rev = rev[:rev.index('-')]
            print('rev is {}'.format(rev))
            rev = int(rev)
            if rev < 4 :
                self.MICROSECOND_SUPPORT = False
            else:
                self.MICROSECOND_SUPPORT = True
        
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

        if self.MICROSECOND_SUPPORT == None:
            self.init_microsecond_support()

        where_clauses = ["WHERE topics.topic_name = %s", "topics.topic_id = data.topic_id"]
        args = [topic]

        if start is not None:
            where_clauses.append("data.ts >= %s")
            if self.MICROSECOND_SUPPORT:
                args.append(start)
            else:
                start_str=start.isoformat()
                args.append(start_str[:start_str.rfind('.')])

        if end is not None:
            where_clauses.append("data.ts <= %s")
            if self.MICROSECOND_SUPPORT:
                args.append(end)
            else:
                end_str=end.isoformat()
                args.append(end_str[:end_str.rfind('.')])

        where_statement = ' AND '.join(where_clauses)

        order_by = 'ORDER BY data.ts ASC'
        if order == 'LAST_TO_FIRST':
            order_by = ' ORDER BY data.ts DESC'

        #can't have an offset without a limit
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
        _log.debug("args: "+str(args))

        rows = self.select(real_query,args)

        if rows:
            values = [(ts.isoformat(), jsonapi.loads(value)) for ts, value in rows]
        else:
            values = {}

        return {'values':values}

    def insert_data_query(self):
        return '''REPLACE INTO data values(%s, %s, %s)'''

    def insert_topic_query(self):
        return '''REPLACE INTO topics (topic_name) values (%s)'''
    
    def get_topic_map(self):
        q = "SELECT topic_id, topic_name FROM topics;"
        rows = self.select(q, None)
        return dict([(n, t) for t, n in rows])