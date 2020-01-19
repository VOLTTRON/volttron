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



import logging
import sys

import bson
from bson import ObjectId
import pymongo
from volttron.platform.agent import utils
from volttron.platform.agent.base_aggregate_historian import AggregateHistorian
from volttron.platform.dbutils import mongoutils

utils.setup_logging(logging.DEBUG)
_log = logging.getLogger(__name__)
__version__ = '1.0'


class MongodbAggregateHistorian(AggregateHistorian):
    """
    Agent to aggregate data in historian based on a specific time period.
    This aggregegate historian aggregates data collected by mongo historian.
    """

    def __init__(self, config_path, **kwargs):
        """
        Validate configuration, create connection to historian, create
        aggregate tables if necessary and set up a periodic call to
        aggregate data
        :param config_path: configuration file path
        :param kwargs:
        """
        self.dbclient = None
        self._data_collection = None
        self._meta_collection = None
        self._topic_collection = None
        self._agg_meta_collection = None
        self._agg_topic_collection = None
        self.topic_id_map = {}
        super(MongodbAggregateHistorian, self).__init__(config_path, **kwargs)

    def configure(self, config_name, action, config):

        if not config or not isinstance(config, dict):
            raise ValueError("Configuration should be a valid json")

        connection = config.get('connection')
        self.dbclient = mongoutils.get_mongo_client(connection['params'])

        # Why are we not letting users configure data and topic collection
        # names in mongo similar to sqlhistorian
        # tables_def = sqlutils.get_table_def(self.config)

        db = self.dbclient.get_default_database()
        cursor = db[self.volttron_table_defs].find()
        table_map = {}
        prefix = ""
        for document in cursor:
            table_map[document['table_id'].lower()] = document[
                'table_name']
            prefix = document.get('table_prefix') + "_" if document.get(
                'table_prefix') else ''
        self._data_collection = prefix + table_map.get('data_table', 'data')
        self._meta_collection = prefix + table_map.get('meta_table', 'meta')
        self._topic_collection = prefix + table_map.get('topics_table',
                                                        'topics')
        self._agg_meta_collection = prefix + 'aggregate_' \
            + table_map.get('meta_table', 'meta')
        self._agg_topic_collection = prefix + 'aggregate_' \
            + table_map.get('topics_table', 'topics')

        db[self._agg_topic_collection].create_index(
            [('agg_topic_name', pymongo.DESCENDING),
             ('agg_type', pymongo.DESCENDING),
             ('agg_time_period', pymongo.DESCENDING)],
            unique=True, background=True)

        # 2. load topic name and topic id.
        self.topic_id_map, name_map = self.get_topic_map()
        super(MongodbAggregateHistorian, self).configure(config_name,
                                                         action, config)

    def get_topic_map(self):
        return mongoutils.get_topic_map(self.dbclient, self._topic_collection)

    def get_agg_topic_map(self):
        return mongoutils.get_agg_topic_map(self.dbclient,
                                            self._agg_topic_collection)

    def get_aggregation_list(self):
        return  ['SUM', 'COUNT', 'AVG', 'MIN', 'MAX', 'STDDEVPOP',
                 'STDDEVSAMP']


    def initialize_aggregate_store(self, aggregation_topic_name, agg_type,
                                   agg_time_period, topics_meta):

        db = self.dbclient.get_default_database()
        agg_collection = agg_type + '''_''' + agg_time_period
        db[agg_collection].create_index(
            [('topic_id', pymongo.DESCENDING),
             ('ts', pymongo.DESCENDING)],
            unique=True, background=True)

        row = db[self._agg_topic_collection].insert_one(
            {'agg_topic_name': aggregation_topic_name,
             'agg_type': agg_type,
             'agg_time_period': agg_time_period})

        agg_id = row.inserted_id
        _log.debug("Inserted aggregate topic in {} agg id is{}".format(
            self._agg_topic_collection, agg_id))
        db[self._agg_meta_collection].insert_one({'agg_topic_id': agg_id,
                                                  'meta': topics_meta})
        return agg_id

    def update_aggregate_metadata(self, agg_id, aggregation_topic_name,
                                  topic_meta):
        db = self.dbclient.get_default_database()

        result = db[self._agg_topic_collection].update_one(
            {'_id': bson.objectid.ObjectId(agg_id)},
            {'$set': {'agg_topic_name': aggregation_topic_name}})
        _log.debug("Updated topic name for {} records".format(
            result.matched_count))

        result = db[self._agg_meta_collection].update_one(
            {'agg_topic_id': bson.objectid.ObjectId(agg_id)},
            {'$set': {'meta': topic_meta}})

        _log.debug("Updated meta name for {} records".format(
            result.matched_count))

    def collect_aggregate(self, topic_ids, agg_type, start_time, end_time):

        db = self.dbclient.get_default_database()
        _log.debug("collect_aggregate: params {}, {}, {}, {}".format(
            topic_ids, agg_type, start_time, end_time))
        # because topic_ids might be got by making rpc call to historian
        # in which case historian would have returned object ids as strings
        # in order to be serializable
        if not isinstance(topic_ids[0], ObjectId):
            topic_ids = [ObjectId(x) for x in topic_ids]

        match_conditions = [{"topic_id": {"$in": topic_ids}}]
        if start_time is not None:
            match_conditions.append({"ts": {"$gte": start_time}})
        if end_time is not None:
            match_conditions.append({"ts": {"$lt": end_time}})

        match = {"$match": {"$and": match_conditions}}
        group = {"$group": {"_id": "null", "count": {"$sum": 1},
                            "aggregate": {"$" + agg_type: "$value"}}}

        pipeline = [match, group]

        _log.debug("collect_aggregate: pipeline: {}".format(pipeline))
        cursor = db[self._data_collection].aggregate(pipeline)
        try:
            row = next(cursor)
            _log.debug("collect_aggregate: got result as {}".format(row))
            return row['aggregate'], row['count']
        except StopIteration:
            return 0, 0

    def insert_aggregate(self, topic_id, agg_type, period, end_time,
                         value, topic_ids):

        db = self.dbclient.get_default_database()
        table_name = agg_type + '_' + period
        db[table_name].replace_one(
            {'ts': end_time, 'topic_id': topic_id},
            {'ts': end_time, 'topic_id': topic_id, 'value': value,
             'topics_list': topic_ids},
            upsert=True)


def main(argv=sys.argv):
    """Main method called by the eggsecutable."""
    try:
        utils.vip_main(MongodbAggregateHistorian, version=__version__)
    except Exception as e:
        _log.exception('unhandled exception' + str(e))


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
