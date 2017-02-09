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
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
# OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are
# those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD Project.
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

import hashlib
import logging
import sys
import pytz
from collections import defaultdict
from datetime import datetime

from crate.client.exceptions import ConnectionError
from dateutil.relativedelta import relativedelta
from calendar import monthrange
from datetime import timedelta
from dateutil.tz import tzutc

from crate import client
from zmq.utils import jsonapi

from volttron.platform.agent import utils
from volttron.platform.agent.base_historian import BaseHistorian
from volttron.platform.dbutils.cratedriver import create_schema

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '1.0'


def historian(config_path, **kwargs):
    """
    This method is called by the :py:func:`mongodb.historian.main` to parse
    the passed config file or configuration dictionary object, validate the
    configuration entries, and create an instance of MongodbHistorian

    :param config_path: could be a path to a configuration file or can be a
                        dictionary object
    :param kwargs: additional keyword arguments if any
    :return: an instance of :py:class:`MongodbHistorian`
    """
    if isinstance(config_path, dict):
        config_dict = config_path
    else:
        config_dict = utils.load_config(config_path)
    connection = config_dict.get('connection', None)
    assert connection is not None

    database_type = connection.get('type', None)
    assert database_type is not None

    params = connection.get('params', None)
    assert params is not None

    topic_replacements = config_dict.get('topic_replace_list', None)
    _log.debug('topic_replacements are: {}'.format(topic_replacements))

    CrateHistorian.__name__ = 'CrateHistorian'
    return CrateHistorian(config_dict, topic_replace_list=topic_replacements,
                          **kwargs)


class CrateHistorian(BaseHistorian):
    """
    Historian that stores the data into mongodb collections.

    """

    def __init__(self, config, **kwargs):
        """
        Initialise the historian.

        The historian makes a mongoclient connection to the mongodb server.
        This connection is thread-safe and therefore we create it before
        starting the main loop of the agent.

        In addition, the topic_map and topic_meta are used for caching meta
        data and topics respectively.

        :param kwargs: additional keyword arguments. (optional identity and
                       topic_replace_list used by parent classes)

        """
        super(CrateHistorian, self).__init__(**kwargs)
        self.tables_def, table_names = self.parse_table_def(config)
        self._data_collection = table_names['data_table']
        self._meta_collection = table_names['meta_table']
        self._topic_collection = table_names['topics_table']
        self._agg_topic_collection = table_names['agg_topics_table']
        self._agg_meta_collection = table_names['agg_meta_table']
        self._connection_params = config['connection']['params']
        self._schema = config.get('schema', 'historian')
        self._client = None
        self._connection = None

        self._topic_id_map = {}
        self._topic_to_table_map = {}
        self._topic_to_datatype_map = {}
        self._topic_name_map = {}
        self._topic_meta = {}
        self._agg_topic_id_map = {}

    def _get_topic_table(self, source, db_datatype):
        table = None

        if source == 'device':
            if db_datatype == 'string':
                table = 'device'
            else:
                table = 'device_double'

        if source == 'log':
            if db_datatype == 'string':
                table = 'datalogger'
            else:
                table = 'datalogger_double'

        if source == 'analysis':
            if db_datatype == 'string':
                table = 'analysis'
            else:
                table = 'analysis_double'

        if source == 'record':
            table = 'record'

        assert source

        return "{schema}.{table}".format(schema=self._schema, table=table)

    def publish_to_historian(self, to_publish_list):
        _log.debug("publish_to_historian number of items: {}".format(
            len(to_publish_list)))

        def insert_data(cursor, topic_id, ts, data):
            insert_query = """INSERT INTO {} (topic_id, ts, result)
                              VALUES(?, ?, ?)
                              ON DUPLICATE KEY UPDATE result=result
                            """.format(self._topic_to_table_map[topic_id])
            _log.debug("QUERY: {}".format(insert_query))
            _log.debug("PARAMS: {}".format(topic_id, ts, data))
            ts_formatted = utils.format_timestamp(ts)

            cursor.execute(insert_query, (topic_id, ts_formatted,
                                          data, data))
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            for x in to_publish_list:
                _id = x['_id']  # A base_historian reference to internal id.
                ts = x['timestamp']
                source = x['source']
                topic = x['topic']
                value = x['value']
                meta = x['meta']

                if source == 'scrape':
                    source = 'device'
                if source == 'log':
                    source = 'datalogger'

                meta_type = meta.get('type', None)
                db_datatype = None
                try:
                    if meta_type == 'integer':
                        value = int(value)
                        db_datatype = 'numeric'
                    elif meta_type == 'float':
                        value = float(value)
                        db_datatype = 'numeric'
                    else:
                        try:
                            value = float(value)
                            db_datatype = 'numeric'
                        except ValueError:
                            db_datatype = 'string'
                except ValueError:
                    _log.error(
                        "Topic: {} "
                        "Couldn't cast value {} to {}".format(topic,
                                                              value,
                                                              meta_type))
                    # since this isn't going to be fixed we mark it as
                    # handled
                    self.report_handled(_id)
                    continue

                _log.debug('META IS: {}'.format(meta))
                # look at the topics that are stored in the database already
                # to see if this topic has a value
                topic_lower = topic.lower()
                topic_id = hashlib.md5(topic_lower).hexdigest()
                db_topic_name = self._topic_name_map.get(topic_lower, None)

                if db_topic_name is None:
                    topic_table = self._get_topic_table(source, db_datatype)

                    if not topic_table:
                        _log.error(
                            "Invalid topic table for topic: {} source: {} invalid".format(
                                topic, source)
                        )
                        continue

                    cursor.execute(
                        """ INSERT INTO {schema}.topic(
                              id, name, data_table, data_type)
                            VALUES(?, ?, ?, ?)
                            ON DUPLICATE KEY UPDATE name=name
                        """.format(schema=self._schema),
                        (topic_id, topic, topic_table, db_datatype))
                    self._topic_to_table_map[topic_id] = topic_table
                    self._topic_to_table_map[topic_lower] = topic_table
                    self._topic_to_datatype_map[topic_id] = db_datatype
                    self._topic_to_datatype_map[topic_lower] = db_datatype
                    self._topic_name_map[topic_lower] = topic
                    self._topic_id_map[topic_lower] = topic_id

                elif db_topic_name != topic:
                    _log.debug('Updating topic: {}'.format(topic))

                    result = cursor.execute(
                        """
                          UPDATE {schema}.topic set name=? WHERE id=?
                        """.format(schema=self._schema), (topic, topic_id))
                    self._topic_name_map[topic_lower] = topic

                insert_data(cursor, topic_id, ts, value)

                old_meta = self._topic_meta.get(topic_id, {})

                if old_meta.get(topic_id) is None or \
                                str(old_meta.get(topic_id)) != str(meta):
                    _log.debug(
                        'Updating meta for topic: {} {}'.format(topic, meta))
                    meta_insert = """INSERT INTO {schema}.meta(topic_id, meta_data)
                                     VALUES(?,?)
                                     ON DUPLICATE KEY UPDATE meta_data=meta_data
                                  """.format(schema=self._schema)
                    cursor.execute(meta_insert, (topic_id, jsonapi.dumps(meta)))
                    self._topic_meta[topic_id] = meta

            self.report_all_handled()
        except ConnectionError:
            _log.error("Cannot connect to crate service.")
            self._connection = None
        finally:
            if cursor is not None:
                cursor.close()
                cursor = None

    def _build_single_topic_query(self, start, end, agg_type, agg_period, skip,
                                  count, order, table_name, topic_id):
        query = '''SELECT topic_id,
                    date_format('%Y-%m-%dT%h:%i:%s.%f+00:00', ts) as ts, result
                        FROM ''' + table_name + '''
                        {where}
                        {order_by}
                        {limit}
                        {offset}'''

        where_clauses = ["WHERE topic_id =?"]
        args = [topic_id]
        if start and end and start == end:
            where_clauses.append("ts = ?")
            args.append(start)
        elif start:
            where_clauses.append("ts >= ?")
            args.append(start)
        elif end:
            where_clauses.append("ts < ?")
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

        if count > 1000:
            _log.warn("Limiting count to <= 1000")
            count = 1000

        limit_statement = 'LIMIT ?'
        args.append(int(count))

        offset_statement = ''
        if skip > 0:
            offset_statement = 'OFFSET ?'
            args.append(skip)

        real_query = query.format(where=where_statement,
                                  limit=limit_statement,
                                  offset=offset_statement,
                                  order_by=order_by)

        _log.debug("Real Query: " + real_query)
        return real_query, args

    def query_historian(self, topic, start=None, end=None, agg_type=None,
                        agg_period=None, skip=0, count=None,
                        order="FIRST_TO_LAST"):
        """ Returns the results of the query from the mongo database.

        This historian stores data to the nearest second.  It will not
        store subsecond resolution data.  This is an optimisation based
        upon storage for the database.
        Please see
        :py:meth:`volttron.platform.agent.base_historian.BaseQueryHistorianAgent.query_historian`
        for input parameters and return value details
        """
        #try:

        # Final results that are sent back to the client.
        results = {}

        # A list or a single topic is now accepted for the topic parameter.
        if not isinstance(topic, list):
            topics = [topic]
        else:
            # Copy elements into topic list
            topics = [x for x in topic]

        # topic_list is what will query against the database.
        topic_list = [x.lower() for x in topics]

        # The following could have None items in it so we must prepare for that
        # below.
        table_names = [self._topic_to_table_map.get(x) for x in topic_list]
        topic_ids = [self._topic_id_map.get(x) for x in topic_list]

        values = defaultdict(list)

        multi_topic_query = len(topics) > 1
        metadata = {}

        cursor = self.get_connection().cursor()
        # Log that one of the topics is not valid.
        for i in xrange(len(table_names)):

            topic_lower = topic_list[i]
            table_name = table_names[i]
            topic_id = topic_ids[i]
            original_topic = topics[i]

            if table_names[i] is None:
                _log.warn("Invalid topic presented to query: {}".format(
                    topics[i]
                ))

                # Handle when a query doesn't have a presence in the database
                # by returning empty values and possible empty metadata.
                if not multi_topic_query:
                    results['values'] = []
                    results['metadata'] = self._topic_meta.get(topic_id, {})

                continue

            query, args = self._build_single_topic_query(
                start, end, agg_type, agg_period, skip, count, order,
                table_name, topic_id)

            cursor.execute(query, args)

            for _id, ts, value in cursor.fetchall():
                values[original_topic].append(
                    (
                        utils.format_timestamp(
                            utils.parse_timestamp_string(ts)),
                        value
                    )
                )
            _log.debug("query result values {}".format(values))

            if len(values) > 0:
                # If there are results add metadata if it is a query on a
                # single topic
                if not multi_topic_query:
                    values = values.values()[0]
                    if agg_type:
                        # if aggregation is on single topic find the topic id
                        # in the topics table that corresponds to agg_topic_id
                        # so that we can grab the correct metadata
                        _log.debug("Single topic aggregate query. Try to get "
                                   "metadata")
                        if topic_id:
                            _log.debug("aggregation of a single topic, "
                                       "found topic id in topic map. "
                                       "topic_id={}".format(topic_id))
                            metadata = self._topic_meta.get(topic_id, {})
                        else:
                            # if topic name does not have entry in topic_id_map
                            # it is a user configured aggregation_topic_name
                            # which denotes aggregation across multiple points
                            metadata = {}
                    else:
                        # this is a query on raw data, get metadata for
                        # topic from topic_meta map
                        metadata = self._topic_meta.get(topic_id, {})

                    return dict(values=values, metadata=metadata)
            else:
                results=dict()

        results['values'] = values
        results['metadata'] = metadata

        return results

    def query_topic_list(self):
        _log.debug("Querying topic list")
        cursor = self.get_connection().cursor()
        sql = """
            SELECT name, lower(name)
            FROM {schema}.topic
        """.format(schema=self._schema)

        cursor.execute(sql)

        results = [x[0] for x in cursor.fetchall()]
        return results

    def query_topics_metadata(self, topics):
        pass
        # meta = {}
        # if isinstance(topics, str):
        #     topic_id = self._topic_id_map.get(topics.lower())
        #     if topic_id:
        #         meta = {topics: self._topic_meta.get(topic_id)}
        # elif isinstance(topics, list):
        #     for topic in topics:
        #         topic_id = self._topic_id_map.get(topic.lower())
        #         if topic_id:
        #             meta[topic] = self._topic_meta.get(topic_id)
        # return meta

    def query_aggregate_topics(self):
        pass

        # return mongoutils.get_agg_topics(
        #     self._client,
        #     self._agg_topic_collection,
        #     self._agg_meta_collection)

    def _load_topic_map(self):
        _log.debug('loading topic map')
        cursor = self._connection.cursor()

        cursor.execute("""
            SELECT id, name, lower(name) AS lower_name, data_table, data_type
            FROM {schema}.topic
            ORDER BY lower(name)
        """.format(schema=self._schema))

        for row in cursor.fetchall():
            _log.debug('loading: {}'.format(row[2]))
            self._topic_to_datatype_map[row[2]] = row[4]
            self._topic_to_datatype_map[row[0]] = row[4]
            self._topic_to_table_map[row[2]] = row[3]
            self._topic_to_table_map[row[0]] = row[3]
            self._topic_id_map[row[2]] = row[0]
            self._topic_name_map[row[2]] = row[1]

        cursor.close()

    def _load_meta_map(self):
        _log.debug('loading meta map')
        cursor = self._connection.cursor()

        cursor.execute("""
            SELECT topic_id, meta_data
            FROM {schema}.meta
        """.format(schema=self._schema))

        for row in cursor.fetchall():
            self._topic_meta[row[0]] = jsonapi.loads(row[1])

        cursor.close()

    def get_connection(self):
        if self._connection is None:
            self._connection = client.connect(self._connection_params['host'],
                                              error_trace=True)
        return self._connection

    def historian_setup(self):
        _log.debug("HISTORIAN SETUP")

        self._connection = self.get_connection()

        create_schema(self._connection, self._schema)

        self._load_topic_map()
        self._load_meta_map()

        # self._client = mongoutils.get_mongo_client(self._connection_params)
        # db = self._client.get_default_database()
        # db[self._data_collection].create_index(
        #     [('topic_id', pymongo.DESCENDING), ('ts', pymongo.DESCENDING)],
        #     unique=True, background=True)

        # self._topic_id_map, self._topic_name_map = \
        #     mongoutils.get_topic_map(
        #         self._client, self._topic_collection)
        # self._load_meta_map()
        #
        # if self._agg_topic_collection in db.collection_names():
        #     _log.debug("found agg_topics_collection ")
        #     self._agg_topic_id_map = mongoutils.get_agg_topic_map(
        #         self._client, self._agg_topic_collection)
        # else:
        #     _log.debug("no agg topics to load")
        #     self._agg_topic_id_map = {}

    def record_table_definitions(self, meta_table_name):
        _log.debug("In record_table_def  table:{}".format(meta_table_name))
        pass
        #
        # db = self._client.get_default_database()
        # db[meta_table_name].bulk_write([
        #     ReplaceOne(
        #         {'table_id': 'data_table'},
        #         {'table_id': 'data_table',
        #          'table_name': self._data_collection, 'table_prefix': ''},
        #         upsert=True),
        #     ReplaceOne(
        #         {'table_id': 'topics_table'},
        #         {'table_id': 'topics_table',
        #          'table_name': self._topic_collection, 'table_prefix': ''},
        #         upsert=True),
        #     ReplaceOne(
        #         {'table_id': 'meta_table'},
        #         {'table_id': 'meta_table',
        #          'table_name': self._meta_collection, 'table_prefix': ''},
        #         upsert=True)])



def main(argv=sys.argv):
    """Main method called by the eggsecutable.
    @param argv:
    """
    try:
        utils.vip_main(historian)
    except Exception as e:
        print(e)
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
