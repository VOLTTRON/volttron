# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2015, Battelle Memorial Institute
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
from pymongo import InsertOne, ReplaceOne
from pymongo.errors import BulkWriteError

from volttron.platform.agent import utils
from volttron.platform.agent.base_historian import BaseHistorian

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

    identity = config.get('identity', kwargs.pop('identity', None))
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

            self._data_collection = 'data'
            self._meta_collection = 'meta'
            self._topic_collection = 'topics'
            self._initial_params = connection['params']
            self._client = None

            self._topic_id_map = {}
            self._topic_name_map = {}
            self._topic_meta = {}

        def _get_mongo_client(self, connection_params):

            database_name = connection_params['database']
            hosts = connection_params['host']
            ports = connection_params['port']
            user = connection_params['user']
            passwd = connection_params['passwd']

            if isinstance(hosts, list):
                if not ports:
                    hosts = ','.join(hosts)
                else:
                    if len(ports) != len(hosts):
                        raise StandardError(
                            'port an hosts must have the same number of items'
                        )
                    hostports = zip(hosts, ports)
                    hostports = [str(e[0]) + ':' + str(e[1]) for e in
                                 hostports]
                    hosts = ','.join(hostports)
            else:
                if isinstance(ports, list):
                    raise StandardError(
                        'port cannot be a list if hosts is not also a list.'
                    )
                hosts = '{}:{}'.format(hosts, ports)

            params = {'hostsandports': hosts, 'user': user,
                      'passwd': passwd, 'database': database_name}

            mongo_uri = "mongodb://{user}:{passwd}@{hostsandports}/{database}"
            mongo_uri = mongo_uri.format(**params)
            mongoclient = pymongo.MongoClient(mongo_uri)

            return mongoclient

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

            #                bulk_publish.append(InsertOne(
            #                    {'ts': ts, 'topic_id': topic_id, 'value': value}))

            try:
                # http://api.mongodb.org/python/current/api/pymongo/collection.html#pymongo.collection.Collection.bulk_write
                result = db[self._data_collection].bulk_write(bulk_publish)
            except BulkWriteError as bwe:
                _log.error("{}".format(bwe.details))

            else:  # No write errros here when
                if not result.bulk_api_result['writeErrors']:
                    self.report_all_handled()
                else:
                    # TODO handle when something happens during writing of data.
                    _log.error('SOME THINGS DID NOT WORK')

        def query_historian(self, topic, start=None, end=None, skip=0,
                            count=None, order="FIRST_TO_LAST"):
            """ Returns the results of the query from the mongo database.

            This historian stores data to the nearest second.  It will not
            store subsecond resolution data.  This is an optimisation based
            upon storage for the database.

            This function should return the results of a query in the form:
            {"values": [(timestamp1, value1), (timestamp2, value2), ...],
             "metadata": {"key1": value1, "key2": value2, ...}}

             metadata is not required (The caller will normalize this to {}
             for you)
             @param order:
             @param count:
             @param skip:
             @param end:
             @param start:
             @param topic:
            """

            topic_lower = topic.lower()
            topic_id = self._topic_id_map.get(topic_lower, None)

            if not topic_id:
                _log.debug('Topic id was None for topic: {}'.format(topic))
                return {}

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

            find_params = {"topic_id": ObjectId(topic_id)}
            if ts_filter:
                find_params['ts'] = ts_filter

            cursor = db[self._data_collection].find(find_params)
            cursor = cursor.skip(skip_count).limit(count)
            cursor = cursor.sort([("ts", order_by)])
            _log.debug('cursor count is: {}'.format(cursor.count()))

            # Create list of tuples for return values.
            values = [(utils.format_timestamp(row['ts']), row['value']) for
                      row
                      in cursor]
            if len(values) > 0:
                return {
                    'values': values,
                    'metadata': self._topic_meta.get(topic_id, {})
                }
            else:
                return {}

        def query_topic_list(self):
            db = self._client.get_default_database()
            cursor = db[self._topic_collection].find()

            res = []
            for document in cursor:
                res.append(document['topic_name'])

            return res

        def _load_topic_map(self):
            _log.debug('loading topic map')
            db = self._client.get_default_database()
            cursor = db[self._topic_collection].find()

            for document in cursor:
                self._topic_id_map[document['topic_name'].lower()] = document[
                    '_id']
                self._topic_name_map[document['topic_name'].lower()] = \
                    document['topic_name']

        def _load_meta_map(self):
            _log.debug('loading meta map')
            db = self._client.get_default_database()
            cursor = db[self._meta_collection].find()

            for document in cursor:
                self._topic_meta[document['topic_id']] = document['meta']

        def historian_setup(self):
            _log.debug("HISTORIAN SETUP")
            self._client = self._get_mongo_client(
                connection['params'])
            self._load_topic_map()
            self._load_meta_map()

    MongodbHistorian.__name__ = 'MongodbHistorian'
    return MongodbHistorian(
        identity=identity, topic_replace_list=topic_replacements, **kwargs)


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
