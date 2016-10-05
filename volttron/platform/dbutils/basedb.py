# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
# this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
# IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are
# those
# of the authors and should not be interpreted as representing official
# policies,
# either expressed or implied, of the FreeBSD Project.
#

# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization
# that has cooperated in the development of these materials, makes
# any warranty, express or implied, or assumes any legal liability
# or responsibility for the accuracy, completeness, or usefulness or
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does
# not necessarily constitute or imply its endorsement, recommendation,
# r favoring by the United States Government or any agency thereof,
# or Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

# }}}
from __future__ import absolute_import, print_function

import importlib
import logging
import threading

from abc import abstractmethod
from volttron.platform.agent import utils
from zmq.utils import jsonapi

utils.setup_logging()
_log = logging.getLogger(__name__)


class DbDriver(object):
    def __init__(self, dbapimodule, **kwargs):
        thread_name = threading.currentThread().getName()
        _log.debug("Constructing Driver for {} in thread: {}".format(
            dbapimodule, thread_name)
        )

        self.__dbmodule = importlib.import_module(dbapimodule)
        self.__connection = None
        self.__cursor = None
        self.__connect_params = kwargs

    def __connect(self):
        try:
            if self.__connection is None:
                self.__connection = self.__dbmodule.connect(
                    **self.__connect_params)
            if self.__cursor is None:
                self.__cursor = self.__connection.cursor()

        except Exception as e:
            _log.warning(e.__class__.__name__ + "couldn't connect to database")

        return self.__connection is not None

    def read_tablenames_from_db(self, meta_table_name):
        rows = self.select("SELECT table_id, table_name, table_prefix from " +
                           meta_table_name, None)
        table_names = dict()
        table_prefix = ""
        table_map = {}

        for row in rows:
            table_map[row[0].lower()] = row[1]
            table_prefix = row[2] + "_" if row[2] else ""
            table_names[row[0]] = table_prefix + row[1]

        table_names['agg_topics_table'] = table_prefix + \
            'aggregate_' + table_map['topics_table']
        table_names['agg_meta_table'] = table_prefix + 'aggregate_' + \
            table_map['meta_table']
        return table_names

    @abstractmethod
    def setup_historian_tables(self):
        """
        Create historian tables if necessary
        """
        pass

    @abstractmethod
    def get_topic_map(self):
        pass

    @abstractmethod
    def get_agg_topics(self):
        """
        Get the list of aggregate topics available
        :return: list of tuples containing
        (agg_topic_name, agg_type, agg_time_period, configured topics/topic
        name pattern)
        """
        pass

    @abstractmethod
    def get_agg_topic_map(self):
        """
        Get a map of aggregate_topics to aggregate_topic_id
        :return: dict of format
        {(agg_topic_name, agg_type, agg_time_period):agg_topic_id}
        """
        pass

    @abstractmethod
    def find_topics_by_pattern(self, topic_pattern):
        """
        Return a map of {topi_name.lower():topic_id} that matches the given
        pattern
        :param topic_pattern: pattern to match against topic_name
        :return:
        """
        pass

    @abstractmethod
    def insert_data_query(self):
        pass

    @abstractmethod
    def insert_topic_query(self):
        pass

    @abstractmethod
    def update_topic_query(self):
        pass

    @abstractmethod
    def insert_meta_query(self):
        pass

    @abstractmethod
    def get_aggregation_list(self):
        """
        Return list of aggregation supported by the specific data store
        :return: list of aggregations
        """
        pass

    @abstractmethod
    def insert_agg_topic_stmt(self):
        pass

    @abstractmethod
    def update_agg_topic_stmt(self):
        pass

    @abstractmethod
    def insert_agg_meta_stmt(self):
        pass

    def insert_stmt(self, stmt, args):
        if not self.__connect():
            return False

        self.__cursor.execute(stmt, args)
        return True

    def insert_meta(self, topic_id, metadata):
        if not self.__connect():
            return False

        self.__cursor.execute(self.insert_meta_query(),
                              (topic_id, jsonapi.dumps(metadata)))
        return True

    def insert_data(self, ts, topic_id, data):
        if not self.__connect():
            return False

        self.__cursor.execute(self.insert_data_query(),
                              (ts, topic_id, jsonapi.dumps(data)))
        return True

    def insert_topic(self, topic):
        if not self.__connect():
            return False

        self.__cursor.execute(self.insert_topic_query(), (topic,))
        row = [self.__cursor.lastrowid]
        return row

    def update_topic(self, topic, topic_id):

        self.__connect()

        if self.__connection is None:
            return False

        if not self.__cursor:
            self.__cursor = self.__connection.cursor()

        self.__cursor.execute(self.update_topic_query(), (topic, topic_id))

        return True

    def insert_agg_meta(self, topic_id, metadata):
        if not self.__connect():
            return False

        if self.__connection is None:
            return False

        if not self.__cursor:
            self.__cursor = self.__connection.cursor()
        self.__cursor.execute(self.insert_agg_meta_stmt(),
                              (topic_id, jsonapi.dumps(metadata)))
        return True

    def insert_agg_topic(self, topic, agg_type, agg_time_period):
        if not self.__connect():
            return False

        if self.__connection is None:
            return False

        if not self.__cursor:
            self.__cursor = self.__connection.cursor()

        self.__cursor.execute(self.insert_agg_topic_stmt(),
                              (topic, agg_type, agg_time_period))
        row = [self.__cursor.lastrowid]
        return row

    def update_agg_topic(self, agg_id, agg_topic_name):
        if not self.__connect():
            return False

        if self.__connection is None:
            return False

        if not self.__cursor:
            self.__cursor = self.__connection.cursor()

        self.__cursor.execute(self.update_agg_topic_stmt(),
                              (agg_id, agg_topic_name))
        self.commit()

    def commit(self):
        successful = False
        if self.__connection is not None:
            self.__connection.commit()
            self.__connection.close()
            successful = True
        else:
            _log.warning('connection was null during commit phase.')

        self.__cursor = None
        self.__connection = None
        return successful

    def rollback(self):
        successful = False
        if self.__connection is not None:
            self.__connection.rollback()
            self.__connection.close()
            successful = True
        else:
            _log.warning('connection was null during rollback phase.')

        self.__cursor = None
        self.__connection = None
        return successful

    def select(self, query, args):
        try:
            conn = self.__dbmodule.connect(**self.__connect_params)
        except Exception as e:
            _log.warning(e.__class__.__name__ + "couldn't connect to database")
            conn = None

        if conn is None:
            return []

        cursor = conn.cursor()
        if args is not None:
            cursor.execute(query, args)
        else:
            cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        return rows

    def execute_stmt(self, stmt):
        try:
            conn = self.__dbmodule.connect(**self.__connect_params)
        except Exception as e:
            _log.warning(e.__class__.__name__ + "couldn't connect to database")
            conn = None

        if conn is None:
            return []

        cursor = conn.cursor()
        cursor.execute(stmt)
        conn.commit()
        conn.close()
        return True

    @abstractmethod
    def query(self, topic_ids, id_name_map, start=None, end=None,
              agg_type=None,
              agg_period=None, skip=0, count=None, order="FIRST_TO_LAST"):
        """This function should return the results of a query in the form:
        {"values": [(timestamp1, value1), (timestamp2, value2), ...],
         "metadata": {"key1": value1, "key2": value2, ...}}

         metadata is not required (The caller will normalize this to {} for
         you)
        """
        pass

    @abstractmethod
    def create_aggregate_store(self, agg_type, period):
        pass

    @abstractmethod
    def insert_aggregate_stmt(self, table_name):
        pass

    def insert_aggregate(self, agg_topic_id, agg_type, period, ts,
                         data, topic_ids):

        if not self.__connect():
            print("connect to database failed.......")
            return False
        table_name = agg_type + '_' + period
        _log.debug("Inserting aggregate: {} {} {} {} into table {}".format(
            ts, agg_topic_id, jsonapi.dumps(data), str(topic_ids), table_name))
        self.__cursor.execute(
            self.insert_aggregate_stmt(table_name),
            (ts, agg_topic_id, jsonapi.dumps(data), str(topic_ids)))
        self.commit()
        return True

    @abstractmethod
    def collect_aggregate(self, topic_ids, agg_type, start=None, end=None):
        pass
