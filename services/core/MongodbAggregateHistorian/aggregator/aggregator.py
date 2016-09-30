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

from __future__ import absolute_import

import logging
import sys

import bson
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

    def find_topics_by_pattern(self, topics_pattern):
        db = self.dbclient.get_default_database()
        topics_pattern = topics_pattern.replace('/', '\/')
        pattern = {'topic_name': {'$regex': topics_pattern, '$options': 'i'}}
        cursor = db[self._topic_collection].find(pattern)
        topic_id_map = dict()
        for document in cursor:
            topic_id_map[document['topic_name'].lower()] = document[
                '_id']
        return topic_id_map

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
            row = cursor.next()
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
        utils.vip_main(MongodbAggregateHistorian)
    except Exception as e:
        _log.exception('unhandled exception' + e.message)


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
