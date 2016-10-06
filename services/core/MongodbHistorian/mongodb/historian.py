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

import logging
import sys

import pymongo
from bson.objectid import ObjectId
from pymongo import ReplaceOne
from pymongo.errors import BulkWriteError
from volttron.platform.agent import utils
from volttron.platform.agent.base_historian import BaseHistorian
from volttron.platform.dbutils import mongoutils

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.1'


def historian(config_path, **kwargs):
    config = utils.load_config(config_path)
    connection = config.get('connection', None)
    assert connection is not None

    database_type = connection.get('type', None)
    assert database_type is not None

    params = connection.get('params', None)
    assert params is not None

    identity_from_platform = kwargs.pop('identity', None)
    identity = config.get('identity')

    if identity is not None:
        _log.warning("DEPRECATION WARNING: Setting a historian's VIP IDENTITY"
                     " from its configuration file will no longer be supported after VOLTTRON 4.0")
        _log.warning("DEPRECATION WARNING: Using the identity configuration setting will override"
                     " the value provided by the platform. This new value will not be reported"
                     " correctly by 'volttron-ctl status'")
        _log.warning("DEPRECATION WARNING: Please remove 'identity' from your configuration file"
                     " and use the new method provided by the platform to set an agent's identity."
                     " See scripts/core/make-mongo-historian.sh for an example of how this is done.")
    else:
        identity = identity_from_platform

    topic_replacements = config.get('topic_replace_list', None)
    _log.debug('topic_replacements are: {}'.format(topic_replacements))

    class MongodbHistorian(BaseHistorian):
        """This is a simple example of a historian agent that writes stuff
        to a SQLite database. It is designed to test some of the functionality
        of the BaseHistorianAgent.
        """

        def __init__(self, **kwargs):
            """ Initialise the historian.

            The historian makes a mongoclient connection to the mongodb server.
            This connection is thread-safe and therefore we create it before
            starting the main loop of the agent.

            In addition, the topic_map and topic_meta are used for caching meta
            data and topics respectively.

            :param kwargs:
            :return:
            """
            super(MongodbHistorian, self).__init__(**kwargs)
            self.tables_def, table_names = self.parse_table_def(config)
            self._data_collection = table_names['data_table']
            self._meta_collection = table_names['meta_table']
            self._topic_collection = table_names['topics_table']
            self._agg_topic_collection = table_names['agg_topics_table']
            self._agg_meta_collection = table_names['agg_meta_table']
            self._initial_params = connection['params']
            self._client = None

            self._topic_id_map = {}
            self._topic_name_map = {}
            self._topic_meta = {}
            self._agg_topic_id_map = {}

        def publish_to_historian(self, to_publish_list):
            _log.debug("publish_to_historian number of items: {}"
                       .format(len(to_publish_list)))

            # Use the db instance to insert/update the topics
            # and data collections
            db = self._client.get_default_database()

            bulk_publish = []
            for x in to_publish_list:
                ts = x['timestamp']
                topic = x['topic']
                value = x['value']
                meta = x['meta']

                # look at the topics that are stored in the database already
                # to see if this topic has a value
                topic_lower = topic.lower()
                topic_id = self._topic_id_map.get(topic_lower, None)
                db_topic_name = self._topic_name_map.get(topic_lower, None)
                if topic_id is None:
                    row = db[self._topic_collection].insert_one(
                        {'topic_name': topic})
                    topic_id = row.inserted_id
                    self._topic_id_map[topic_lower] = topic_id
                    self._topic_name_map[topic_lower] = topic
                elif db_topic_name != topic:
                    _log.debug('Updating topic: {}'.format(topic))

                    result = db[self._topic_collection].update_one(
                        {'_id': ObjectId(topic_id)},
                        {'$set': {'topic_name': topic}})
                    assert result.matched_count
                    self._topic_name_map[topic_lower] = topic

                old_meta = self._topic_meta.get(topic_id, {})
                if set(old_meta.items()) != set(meta.items()):
                    _log.debug('Updating meta for topic: {} {}'.format(
                        topic, meta
                    ))
                    db[self._meta_collection].insert_one(
                        {'topic_id': topic_id, 'meta': meta})
                    self._topic_meta[topic_id] = meta

                # Reformat to a filter tha bulk inserter.
                bulk_publish.append(
                    ReplaceOne({'ts': ts, 'topic_id': topic_id},
                               {'ts': ts, 'topic_id': topic_id,
                                'value': value}, upsert=True))

            # bulk_publish.append(InsertOne(
            #                    {'ts': ts, 'topic_id': topic_id, 'value':
            # value}))

            try:
                # http://api.mongodb.org/python/current/api/pymongo
                # /collection.html#pymongo.collection.Collection.bulk_write
                result = db[self._data_collection].bulk_write(bulk_publish)
            except BulkWriteError as bwe:
                _log.error("{}".format(bwe.details))

            else:  # No write errros here when
                if not result.bulk_api_result['writeErrors']:
                    self.report_all_handled()
                else:
                    # TODO handle when something happens during writing of
                    # data.
                    _log.error('SOME THINGS DID NOT WORK')

        def query_historian(self, topic, start=None, end=None, agg_type=None,
                            agg_period=None, skip=0, count=None,
                            order="FIRST_TO_LAST"):
            """ Returns the results of the query from the mongo database.

            This historian stores data to the nearest second.  It will not
            store subsecond resolution data.  This is an optimisation based
            upon storage for the database.

            This function should return the results of a query in the form:
            {"values": [(timestamp1, value1), (timestamp2, value2), ...],
             "metadata": {"key1": value1, "key2": value2, ...}}

            metadata is not required (The caller will normalize this to {}
            for you)
            @param topic: Topic or topics to query for
            @param start: Start of query timestamp as a datetime
            @param end: End of query timestamp as a datetime
            @param agg_type: If this is a query for aggregate data, the type of
            aggregation ( for example, sum, avg)
            @param agg_period: If this is a query for aggregate data, the time
            period of aggregation
            @param skip: Skip this number of results
            @param count: Limit results to this value
            @param order: How to order the results, either "FIRST_TO_LAST" or
            "LAST_TO_FIRST"
            @return: Results of the query
            """
            collection_name = self._data_collection

            if agg_type and agg_period:
                # query aggregate data collection instead
                collection_name = agg_type + "_" + agg_period

            topics_list = []
            if isinstance(topic, str):
                topics_list.append(topic)
            elif isinstance(topic, list):
                topics_list = topic

            topic_ids = []
            id_name_map = {}
            for topic in topics_list:
                # find topic if based on topic table entry
                topic_id = self._topic_id_map.get(topic.lower(), None)

                if agg_type:
                    agg_type = agg_type.lower()
                    # replace id from aggregate_topics table
                    topic_id = self._agg_topic_id_map.get(
                        (topic.lower(), agg_type, agg_period), None)
                    if topic_id is None:
                        # load agg topic id again as it might be a newly
                        # configured aggregation
                        self._agg_topic_id_map = mongoutils.get_agg_topic_map(
                            self._client, self._agg_topic_collection)
                        topic_id = self._agg_topic_id_map.get(
                            (topic.lower(), agg_type, agg_period), None)
                if topic_id:
                    topic_ids.append(topic_id)
                    id_name_map[ObjectId(topic_id)] = topic
                else:
                    _log.warn('No such topic {}'.format(topic))

            if not topic_ids:
                return {}
            else:
                _log.debug("Found topic id for {} as {}".format(topics_list,
                                                                topic_ids))
            multi_topic_query = len(topic_ids) > 1
            db = self._client.get_default_database()

            ts_filter = {}
            order_by = 1
            if order == 'LAST_TO_FIRST':
                order_by = -1
            if start is not None:
                ts_filter["$gte"] = start
            if end is not None:
                ts_filter["$lte"] = end
            if count is None:
                count = 100
            skip_count = 0
            if skip > 0:
                skip_count = skip

            find_params = {"topic_id": ObjectId(topic_ids[0])}
            if multi_topic_query:
                obj_ids = [ObjectId(x) for x in topic_ids]
                find_params = {"topic_id": {"$in": obj_ids}}
            if ts_filter:
                find_params['ts'] = ts_filter

            _log.debug("querying table with params {}".format(find_params))
            cursor = db[collection_name].find(find_params)
            cursor = cursor.skip(skip_count).limit(count)
            if multi_topic_query:
                cursor = cursor.sort(
                    [("topic_id", order_by), ("ts", order_by)])
            else:
                cursor = cursor.sort([("ts", order_by)])
            _log.debug('cursor count is: {}'.format(cursor.count()))

            # Create list of tuples for return values.
            if multi_topic_query:
                values = [(id_name_map[row['topic_id']],
                           utils.format_timestamp(row['ts']),
                           row['value']) for row in cursor]
            else:
                values = [(utils.format_timestamp(row['ts']), row['value']) for
                          row
                          in cursor]

            if len(values) > 0:
                # If there are results add metadata if it is a query on a
                # single
                # topic
                if not multi_topic_query:

                    if agg_type:
                        # if aggregation is on single topic find the topic id
                        # in the topics table.
                        _log.debug("Single topic aggregate query. Try to get "
                                   "metadata")
                        topic_id = self._topic_id_map.get(topic.lower(), None)
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
                        metadata = self._topic_meta.get(topic_ids[0], {})

                    return {
                        'values': values,
                        'metadata': metadata
                    }
                else:
                    return {'values': values}
            else:
                return {}

        def query_topic_list(self):
            db = self._client.get_default_database()
            cursor = db[self._topic_collection].find()

            res = []
            for document in cursor:
                res.append(document['topic_name'])

            return res

        def query_topics_metadata(self, topics):

            meta = {}
            if isinstance(topics, str):
                topic_id = self._topic_id_map.get(topics.lower())
                if topic_id:
                    meta = {topics: self._topic_meta.get(topic_id)}
            elif isinstance(topics, list):
                for topic in topics:
                    topic_id = self._topic_id_map.get(topic.lower())
                    if topic_id:
                        meta[topic] = self._topic_meta.get(topic_id)
            return meta

        def query_aggregate_topics(self):
            return mongoutils.get_agg_topics(
                self._client,
                self._agg_topic_collection, self._agg_meta_collection)

        def _load_topic_map(self):
            _log.debug('loading topic map')
            db = self._client.get_default_database()
            cursor = db[self._topic_collection].find()

            # Hangs when using cursor as iterable.
            # See https://github.com/VOLTTRON/volttron/issues/643
            for num in xrange(cursor.count()):
                document = cursor[num]
                self._topic_id_map[document['topic_name'].lower()] = document[
                    '_id']
                self._topic_name_map[document['topic_name'].lower()] = \
                    document['topic_name']

        def _load_meta_map(self):
            _log.debug('loading meta map')
            db = self._client.get_default_database()
            cursor = db[self._meta_collection].find()
            # Hangs when using cursor as iterable.
            # See https://github.com/VOLTTRON/volttron/issues/643
            for num in xrange(cursor.count()):
                document = cursor[num]
                self._topic_meta[document['topic_id']] = document['meta']

        def historian_setup(self):
            _log.debug("HISTORIAN SETUP")
            self._client = mongoutils.get_mongo_client(
                connection['params'])
            db = self._client.get_default_database()
            db[self._data_collection].create_index(
                [('topic_id', pymongo.DESCENDING),
                 ('ts', pymongo.DESCENDING)],
                unique=True, background=True)

            self._topic_id_map, self._topic_name_map = \
                mongoutils.get_topic_map(self._client, self._topic_collection)
            self._load_meta_map()

            if self._agg_topic_collection in db.collection_names():
                _log.debug("found agg_topics_collection ")
                self._agg_topic_id_map = mongoutils.get_agg_topic_map(
                    self._client, self._agg_topic_collection)
            else:
                _log.debug("no agg topics to load")
                self._agg_topic_id_map = {}

        def record_table_definitions(self, meta_table_name):
            _log.debug("In record_table_def  table:{}".format(
                meta_table_name))

            db = self._client.get_default_database()
            db[meta_table_name].bulk_write([
                ReplaceOne({'table_id': 'data_table'},
                           {'table_id': 'data_table',
                            'table_name': self._data_collection,
                            'table_prefix': ''}, upsert=True),
                ReplaceOne({'table_id': 'topics_table'},
                           {'table_id': 'topics_table',
                            'table_name': self._topic_collection,
                            'table_prefix': ''}, upsert=True),
                ReplaceOne({'table_id': 'meta_table'},
                           {'table_id': 'meta_table',
                            'table_name': self._meta_collection,
                            'table_prefix': ''}, upsert=True)
            ])

    MongodbHistorian.__name__ = 'MongodbHistorian'
    return MongodbHistorian(identity=identity, topic_replace_list=topic_replacements, **kwargs)


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
