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
# from gevent import monkey
# monkey.patch_all()

import logging
import numbers
import re
import sys
from collections import defaultdict
from datetime import datetime
from datetime import timedelta
from gevent.pool import Pool

import pymongo
import pytz
from bson.objectid import ObjectId
from dateutil.tz import tzutc
from pymongo import ReplaceOne
from pymongo import UpdateOne
from pymongo.errors import BulkWriteError

from volttron.platform.agent import utils
from volttron.platform.agent.base_historian import BaseHistorian
from volttron.platform.agent.utils import get_aware_utc_now
from volttron.platform.dbutils import mongoutils
from volttron.platform.vip.agent import Core
from volttron.utils.docs import doc_inherit

try:
    import ujson
    def dumps(data):
        return ujson.dumps(data, double_precision=15)
    def loads(data_string):
        return ujson.loads(data_string, precise_float=True)
except ImportError:
    from zmq.utils.jsonapi import dumps, loads

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '2.1'
_VOLTTRON_TYPE = '__volttron_type__'


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

    identity_from_platform = kwargs.pop('identity', None)
    identity = config_dict.get('identity')

    if identity is not None:
        _log.warning("DEPRECATION WARNING: Setting a historian's VIP IDENTITY"
                     " from its configuration file will no longer be supported"
                     " after VOLTTRON 4.0")
        _log.warning(
            "DEPRECATION WARNING: Using the identity configuration setting "
            "will override the value provided by the platform. This new value "
            "will not be reported correctly by 'volttron-ctl status'")
        _log.warning("DEPRECATION WARNING: Please remove 'identity' from your "
                     "configuration file and use the new method provided by "
                     "the platform to set an agent's identity. See "
                     "scripts/core/make-mongo-historian.sh for an example of "
                     "how this is done.")
    else:
        identity = identity_from_platform

    topic_replacements = config_dict.get('topic_replace_list', None)
    _log.debug('topic_replacements are: {}'.format(topic_replacements))

    readonly = config_dict.get('readonly', False)

    MongodbHistorian.__name__ = 'MongodbHistorian'
    return MongodbHistorian(config_dict, identity=identity,
                            topic_replace_list=topic_replacements,
                            readonly=readonly, **kwargs)


class MongodbHistorian(BaseHistorian):
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

        self.tables_def, table_names = self.parse_table_def(config)
        self._data_collection = table_names['data_table']
        self._meta_collection = table_names['meta_table']
        self._topic_collection = table_names['topics_table']
        self._agg_topic_collection = table_names['agg_topics_table']
        self._agg_meta_collection = table_names['agg_meta_table']
        self._connection_params = config['connection']['params']
        self._client = None

        self._topic_id_map = {}
        self._topic_name_map = {}
        self._topic_meta = {}
        self._agg_topic_id_map = {}
        _log.debug("version number is {}".format(__version__))
        self.version_nums = __version__.split(".")
        self.DAILY_COLLECTION = "daily_data"
        self.HOURLY_COLLECTION = "hourly_data"

        try:
            if config.get('initial_rollup_start_time'):
                self._initial_rollup_start_time = datetime.strptime(
                    config.get('initial_rollup_start_time'),
                    '%Y-%m-%dT%H:%M:%S.%f').replace(tzinfo=pytz.utc)
            else:
                self._initial_rollup_start_time = get_aware_utc_now()

            # Date from which rolled up data exists in hourly_data and
            # daily_data collection
            if config.get('rollup_query_start'):
                self.rollup_query_start = datetime.strptime(
                    config.get('rollup_query_start'),
                    '%Y-%m-%dT%H:%M:%S.%f').replace(tzinfo=pytz.utc)
            else:
                self.rollup_query_start = get_aware_utc_now() + \
                                          timedelta(days=1)

            # topic_patterns for which queries can be run against rolled up
            # tables. This is needed only till batch processing of older data
            # is complete and everything gets loaded into hourly and daily
            # collections
            self.topics_rolled_up = config.get('rollup_topic_pattern')
            try:
                if self.topics_rolled_up:
                    self.topics_rolled_up = re.compile(self.topics_rolled_up)
            except Exception as e:
                _log.error(
                    "Invalid rollup_topic_pattern in configuration. {} is "
                    "not a valid regular expression. "
                    "\nException: {} ".format(self.topics_rolled_up, e.args))

            # number of days before current time, that can be used as end
            # date for queries from hourly or daily data collections. This is
            # to account for the time it takes the periodic_rollup to process
            # records in data table and insert into daily_data and hourly_data
            # collection
            self.rollup_query_end = config.get('rollup_query_end')
            if self.rollup_query_end is not None:
                self.rollup_query_end = float(self.rollup_query_end)
            else:
                self.rollup_query_end = 1 # default 1 day
                # current time(at the time of query)

            #how minutes ones should the periodic rollup function be run
            if config.get('periodic_rollup_frequency') is not None:
                self.periodic_rollup_frequency = \
                    float(config.get('periodic_rollup_frequency')) * 60
            else:
                self.periodic_rollup_frequency = 60 #run every minute

            # Number of minutes to wait before calling the periodic_rollup
            # function for the first time
            if config.get('periodic_rollup_initial_wait') is not None:
                self.periodic_rollup_initial_wait = float(config.get(
                    'periodic_rollup_initial_wait')) * 60
            else:
                self.periodic_rollup_initial_wait = 10
                # by default wait for 10 seconds
                # before running the periodic_rollup for the first time.

            #Done with all init call super.init
            super(MongodbHistorian, self).__init__(**kwargs)
        except ValueError as e:
            _log.error("Error processing configuration: {}".format(e))
            return

    @Core.receiver("onstart")
    def starting_mongo(self, sender, **kwargs):
        _log.debug("In on start method. scheduling periodic call to rollup "
                   "data")
        if not self._readonly:
            self.core.periodic(self.periodic_rollup_frequency,
                               self.periodic_rollup,
                               wait=self.periodic_rollup_initial_wait)

    def periodic_rollup(self):
        _log.info("periodic attempt to do hourly and daily rollup.")
        if self._client is None:
            _log.debug("historian setup not complete. "
                       "wait for next periodic call")
            return
        # Find the records that needs to be processed from data table
        db = self._client.get_default_database()
        stat = {}
        stat["last_data_into_daily"] = self.get_last_updated_data(
            db, self.DAILY_COLLECTION)

        stat["last_data_into_hourly"] = self.get_last_updated_data(
            db, self.HOURLY_COLLECTION)
        find_condition = {}
        if stat["last_data_into_daily"]:
            find_condition['_id'] = {'$gt': stat["last_data_into_daily"]}
        if stat["last_data_into_hourly"]:
            if stat["last_data_into_daily"] and stat[
                "last_data_into_hourly"] < \
                    stat["last_data_into_daily"]:
                find_condition['_id'] = {'$gt': stat["last_data_into_hourly"]}
        if not stat["last_data_into_hourly"] and not stat[
            "last_data_into_daily"]:
            stat = {}
            find_condition['ts']= {'$gt': self._initial_rollup_start_time}
            _log.info("ROLLING FROM start date {}".format(
                self._initial_rollup_start_time))
        else:
            _log.info("ROLLING FROM last processed id {}".format(
                find_condition['_id']))

        _log.debug("query condition is {} ".format(find_condition))


        # Iterate and append to a bulk_array. Insert in batches of 1000
        bulk_publish_hour = []
        bulk_publish_day = []
        hour_ids = []
        day_ids = []
        h = 0
        d = 0
        last_topic_id = ''
        last_date = ''
        cursor = db[self._data_collection].find(
            find_condition).sort("_id", pymongo.ASCENDING)
        _log.debug("rollup query returned. Looping through to updated db")
        for row in cursor:
            if not stat or row['_id'] > stat["last_data_into_hourly"]:
                self.initialize_hourly(topic_id=row['topic_id'], ts=row['ts'])
                bulk_publish_hour.append(
                    MongodbHistorian.insert_to_hourly(db,
                                          row['_id'],
                                          topic_id=row['topic_id'],
                                          ts=row['ts'],
                                          value=row['value']))
                hour_ids.append(row['_id'])
                h += 1

            if not stat or row['_id'] > stat["last_data_into_daily"]:
                self.initialize_daily(topic_id=row['topic_id'],
                                      ts=row['ts'])
                bulk_publish_day.append(
                    MongodbHistorian.insert_to_daily(db,
                                         row['_id'],
                                         topic_id=row['topic_id'],
                                         ts=row['ts'], value=row['value']))
                day_ids.append(row['_id'])
                d += 1
            # Perform insert if we have 5000 rows
            d_errors = h_errors = False
            if h == 5000:
                bulk_publish_hour, hour_ids, h_errors = \
                    MongodbHistorian.bulk_write_rolled_up_data(
                        self.HOURLY_COLLECTION, bulk_publish_hour,
                        hour_ids, db)
                h = 0
            if d == 5000:
                bulk_publish_day, day_ids, d_errors = \
                    MongodbHistorian.bulk_write_rolled_up_data(
                        self.DAILY_COLLECTION, bulk_publish_day, day_ids, db)
                d = 0
            if d_errors or h_errors:
                # something failed in bulk write. try from last err
                # row during the next periodic call
                _log.warn("bulk publish errors. last_processed_data would "
                          "have got recorded in collection. returning from "
                          "periodic call to try again during next scheduled "
                          "call")
                return

        # Perform insert for any pending records
        if bulk_publish_hour:
            _log.debug("bulk_publish outside loop")
            MongodbHistorian.bulk_write_rolled_up_data(
                self.HOURLY_COLLECTION, bulk_publish_hour, hour_ids, db)
        if bulk_publish_day:
            _log.debug("bulk_publish outside loop")
            MongodbHistorian.bulk_write_rolled_up_data(
                self.DAILY_COLLECTION, bulk_publish_day, day_ids, db)

    def get_last_updated_data(self, db, collection):
        id = ""
        cursor = db[collection].find({}).sort(
            "last_updated_data", pymongo.DESCENDING).limit(1)
        for row in cursor:
            id = row.get('last_updated_data')
        return id

    @staticmethod
    def bulk_write_rolled_up_data(collection_name, requests, ids, db):
        '''
        Handle bulk inserts into daily or hourly roll up table.
        :param collection_name: name of the collection on which the bulk
        operation should happen
        :param requests: array of bulk write requests
        :param ids: array of data collection _ids that are part of the bulk
        write requests
        :param db: handle to database
        :return: emptied request array, ids array, and True if there were
        errors during write operation or False if there was none
        '''
        errors = False
        try:
            db[collection_name].bulk_write(requests, ordered=True)
        except BulkWriteError as ex:
            _log.error(str(ex.details))
            errors = True

        else:
            ids = []
            requests = []
        return requests, ids, errors

    def version(self):
        return __version__

    def initialize_hourly(self, topic_id, ts):
        ts_hour = ts.replace(minute=0, second=0, microsecond=0)

        db = self._client.get_default_database()
        # use update+upsert instead of insert cmd as the external script
        # to back fill data could have initialized this same row
        db[self.HOURLY_COLLECTION].update_one(
            {'ts': ts_hour, 'topic_id': topic_id},
            {"$setOnInsert": {'ts': ts_hour,
                              'topic_id': topic_id,
                              'count': 0,
                              'sum': 0,
                              'data': [[]] * 60,
                              'last_updated_data': ''}
            },
            upsert=True)

    def initialize_daily(self, topic_id, ts):
        ts_day = ts.replace(hour=0, minute=0, second=0, microsecond=0)

        db = self._client.get_default_database()
        db[self.DAILY_COLLECTION].update_one(
            {'ts': ts_day, 'topic_id': topic_id},
            {"$setOnInsert": {'ts': ts_day,
                              'topic_id': topic_id,
                              'count': 0,
                              'sum': 0,
                              'data': [[]] * 24 * 60,
                              'last_updated_data': ''}},
            upsert=True)

    @staticmethod
    def insert_to_hourly(db, data_id, topic_id, ts, value):
        sum_value = MongodbHistorian.value_to_sumable(value)
        rollup_hour = ts.replace(minute=0, second=0, microsecond=0)

        return UpdateOne({'ts': rollup_hour, 'topic_id': topic_id},
                {'$push': {"data." + str(ts.minute): [ts, value]},
                 '$inc': {'count': 1, 'sum': sum_value},
                 '$set': {'last_updated_data': data_id}})

    @staticmethod
    def insert_to_daily(db, data_id, topic_id, ts, value):
        rollup_day = ts.replace(hour=0, minute=0, second=0,
                                         microsecond=0)
        position = ts.hour * 60 + ts.minute
        sum_value = MongodbHistorian.value_to_sumable(value)

        one = UpdateOne({'ts': rollup_day, 'topic_id': topic_id},
                        {'$push': {"data." + str(position): [ts, value]},
                         '$inc': {'count': 1, 'sum': sum_value},
                         '$set': {'last_updated_data': data_id}})
        return one

    @doc_inherit
    def publish_to_historian(self, to_publish_list):
        _log.debug("publish_to_historian number of items: {}".format(
            len(to_publish_list)))
        # self.report_all_handled()
        # return
        # Use the db instance to insert/update the topics
        # and data collections
        db = self._client.get_default_database()

        bulk_publish = db[self._data_collection].initialize_ordered_bulk_op()

        for x in to_publish_list:
            ts = x['timestamp']
            topic = x['topic']
            value = x['value']
            meta = x['meta']
            source = x['source']

            if source == 'scrape':
                source = 'devices'

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
                _log.debug(
                    'Updating meta for topic: {} {}'.format(topic, meta))
                db[self._meta_collection].insert_one(
                    {'topic_id': topic_id, 'meta': meta})
                self._topic_meta[topic_id] = meta

            if isinstance(value, dict):
                # Do this so that we need not worry about dict keys with $ or .
                value_str = dumps(value)
                # create a dict with __volttron_type__ so we can do
                # loads() when we query for this data
                value = {_VOLTTRON_TYPE: 'json',
                         'string_value': value_str}

            bulk_publish.find(
                    {'ts': ts, 'topic_id': topic_id}).upsert().replace_one(
                    {'ts': ts, 'topic_id': topic_id, 'source': source,
                     'value': value})


        try:
            result = bulk_publish.execute()
        except BulkWriteError as bwe:
            _log.error("Error during bulk write to data: {}".format(
                bwe.details))
            if bwe.details['writeErrors'] :
                index = bwe.details['writeErrors'][0]['index']
                if index > 0:
                    _log.debug(
                        "bulk operation processed {} records before "
                        "failing".format(bwe.details['writeErrors'][0]['index']))
                    self.report_handled(to_publish_list[0:index])
        else:  # No write errros here when
            self.report_all_handled()

    @staticmethod
    def value_to_sumable(value):
        # Handle the case where value is not a number so we don't
        # increment the sum for that instance.
        if isinstance(value, numbers.Number) and not isinstance(value, bool):
            sum_value = value
        else:
            sum_value = 0
        return sum_value

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
        start_time = datetime.utcnow()
        collection_name = self._data_collection
        use_rolled_up_data = False
        query_start = start
        query_end = end
        topics_list = []
        if isinstance(topic, str):
            topics_list.append(topic)
        elif isinstance(topic, list):
            topics_list = topic

        if agg_type and agg_period:
            # query aggregate data collection instead
            collection_name = agg_type + "_" + agg_period
        else:
            name, query_start, query_end = \
                self.verify_use_of_rolledup_data(start, end, topics_list)
            if name:
                collection_name = name
                use_rolled_up_data = True
        _log.debug("Using collection {} for query:".format(collection_name))

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
            _log.debug("Found topic id for {} as {}".format(
                topics_list, topic_ids))
        multi_topic_query = len(topic_ids) > 1
        db = self._client.get_default_database()

        ts_filter = {}
        order_by = 1
        if order == 'LAST_TO_FIRST':
            order_by = -1

        if query_start is not None:
            ts_filter["$gte"] = query_start

        if query_end is not None:
            ts_filter["$lt"] = query_end


        if count is None:
            count = 100
        skip_count = 0
        if skip > 0:
            skip_count = skip

        find_params = {}
        if ts_filter:
            if start == end :
                find_params = {'ts' : start}
            else:
                find_params = {'ts': ts_filter}

        values = defaultdict(list)
        pool = Pool(size=10)
        try:
            for topic_id in topic_ids:
                # Query for one topic at a time in a loop instead of topic_id
                # $in in order to apply $limit to each topic searched instead
                # of the combined result
                _log.debug("Spawning thread for topic {}".format(topic_id))
                pool.spawn(self.query_topic_data, topic_id, collection_name,
                           start, end, count, skip_count, order_by, find_params,
                           id_name_map, use_rolled_up_data, values)
            pool.join()
            _log.debug("Time taken to load all values {}".format(
                datetime.utcnow() - start_time))
            # _log.debug("Results got {}".format(values))

            return self.add_metadata_to_query_result(agg_type,
                                                     multi_topic_query,
                                                     topic,
                                                     topic_ids,
                                                     values)
        finally:
            pool.kill()


    def query_topic_data(self, topic_id, collection_name, start,
                         end, count, skip_count, order_by, find_params,
                         id_name_map, use_rolled_up_data, values):
        start_time = datetime.utcnow()
        db = self._client.get_default_database()
        _log.info("Mongo client created with min pool size {}".format(
            self._client.min_pool_size))
        find_params['topic_id'] = ObjectId(topic_id)
        _log.debug("querying table with params {}".format(find_params))
        if use_rolled_up_data:
            project = {"_id": 0, "data": 1}
        else:
            project = {"_id": 0, "timestamp": {
                '$dateToString': {'format': "%Y-%m-%dT%H:%M:%S.%L000+00:00",
                                  "date": "$ts"}}, "value": 1}
        pipeline = [{"$match": find_params}, {"$skip": skip_count},
                    {"$sort": {"ts": order_by}}, {"$limit": count},
                    {"$project": project}]
        _log.debug("pipeline for agg query is {}".format(pipeline))
        _log.debug("collection_name is "+ collection_name)
        cursor = db[collection_name].aggregate(pipeline)

        rows = list(cursor)
        _log.debug("Time after fetch {}".format(
            datetime.utcnow() - start_time))
        if use_rolled_up_data:
            for row in rows:
                if order_by == 1:
                    for minute_data in row['data']:
                        if minute_data:
                            # there could be more than data entry during the
                            # same minute
                            for data in minute_data:
                                self.update_values(data, topic_id, start, end,
                                                   id_name_map,
                                                   values)
                else:
                    for minute_data in reversed(row['data']):
                        if minute_data:
                            # there could be more than data entry during the
                            # same minute
                            for data in reversed(minute_data):
                                self.update_values(data, topic_id, start, end,
                                                   id_name_map,
                                                   values)
            _log.debug("values len {}".format(len(values)))
        else:
            for row in rows:
                result_value = self.json_string_to_dict(row['value'])
                values[id_name_map[topic_id]].append(
                    (row['timestamp'], result_value))
        _log.debug("Time taken to load into values {}".format(
            datetime.utcnow() - start_time))
        _log.debug("rows length {}".format(len(rows)))

    def update_values(self, data, topic_id, start, end, id_name_map, values):
        if start.tzinfo:
            data[0] = data[0].replace(tzinfo=tzutc())
        if data[0] >= start and data[0] < end:
            result_value = self.json_string_to_dict(data[1])
            values[id_name_map[topic_id]].append(
                (utils.format_timestamp(data[0]), result_value))



    def json_string_to_dict(self, value):
        """
        Verify if the value was converted to json string at the time of
        storing into db. If so, convert it back to dict and return
        :param value:
        :return:
        """
        result_value = value
        if isinstance(result_value, dict) and result_value.get(_VOLTTRON_TYPE):
            if result_value[_VOLTTRON_TYPE] == 'json':
                result_value = loads(result_value['string_value'])
        return result_value

    def verify_use_of_rolledup_data(self, start, end, topics_list):
        """
        See if we can use rolled up data only be done with version >2,
        with valid time period verify start is >= from when rolled up data
        is available verify end date is < current time - configured lag time
        (config.rollup_query_end) this is to account for any lag between
        the main historian thread and the thread that periodically rolls up
        data. Also check rolled up data exists for the topics queried
        :param start: query start time
        :param end: query end time
        :param topics_list: list of topics in queried
        :return:
        """
        #
        collection_name = ""
        query_start = start
        query_end = end
        # if it is the right version of historian and
        # if start and end dates are within the range for which rolled up
        # data is available, use hourly_data or monthly_data collection
        rollup_end = get_aware_utc_now() - timedelta(
            days=self.rollup_query_end)
        _log.debug("historian version:{}".format(self.version_nums[0]))
        _log.debug("start  {} and end {}".format(start, end))
        _log.debug("rollup query start {}".format(self.rollup_query_start))
        _log.debug("rollup query end {}".format(rollup_end))
        if int(self.version_nums[0]) < 2:
            return collection_name, query_start, query_end

        match_list = [True]
        if self.topics_rolled_up:
            match_list = [bool(self.topics_rolled_up.match(t)) for t in
                          topics_list]

        # For now use rolledup data collections only if all topics in query
        # are present in rolled up format. Mainly because this topic_pattern
        # match is only a temporary fix. We want all topics to get loaded
        # into hourly or daily collections
        if not (False in match_list) and start and end and start != end and \
                        start >= self.rollup_query_start and end < rollup_end:

            diff = (end - start).total_seconds()
            _log.debug("total seconds between end and start {}".format(diff))
            if diff >= 24 * 3600:
                collection_name = self.DAILY_COLLECTION
                query_start = start.replace(hour=0, minute=0, second=0,
                                            microsecond=0)
                query_end = (end + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0)
            elif diff >= 3600 * 3:  # more than 3 hours of data
                collection_name = self.HOURLY_COLLECTION
                query_start = start.replace(minute=0, second=0,
                                            microsecond=0)
                query_end = (end + timedelta(hours=1)).replace(
                    minute=0, second=0, microsecond=0)
        return collection_name, query_start, query_end

    def add_metadata_to_query_result(self, agg_type, multi_topic_query,
                                     topic, topic_ids, values):
        '''
        Adds metadata to query results. If query is based on multiple topics
        does not add any metadata. If query is based on single topic return
        the metadata of it. If topic is an aggregate topic, returns the
        metadata of underlying topic
        :param agg_type:
        :param multi_topic_query:
        :param topic:
        :param topic_ids:
        :param values:
        :return:
        '''
        if len(values) > 0:
            # If there are results add metadata if it is a query on a
            # single
            # topic
            if not multi_topic_query:
                values = values.values()[0]
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
                    _log.debug("Single topic regular query. Get "
                               "metadata from meta map for {}".format(
                        topic_ids[0]))
                    metadata = self._topic_meta.get(topic_ids[0], {})
                    _log.debug("Metadata found {}".format(metadata))
                return {'values': values, 'metadata': metadata}
            else:
                _log.debug("return values without metadata for multi "
                           "topic query")
                return {'values': values}
        else:
            return {}

    @doc_inherit
    def query_topic_list(self):
        db = self._client.get_default_database()
        cursor = db[self._topic_collection].find()

        res = []
        for document in cursor:
            res.append(document['topic_name'])

        return res

    @doc_inherit
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
            self._agg_topic_collection,
            self._agg_meta_collection)

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

    @doc_inherit
    def historian_setup(self):
        _log.debug("HISTORIAN SETUP")
        self._client = mongoutils.get_mongo_client(self._connection_params,
                                                   minPoolSize=10)
        _log.info("Mongo client created with min pool size {}".format(
                  self._client.min_pool_size))
        db = self._client.get_default_database()
        col_list = db.collection_names()
        create_index1 = True
        create_index2 = True

        if self._readonly:
            create_index1 = False
            create_index2 = False
        # if data collection exists check if necessary indexes exists
        elif self._data_collection in col_list:
            index_info = db[self._data_collection].index_information()
            index_list = [value['key'] for value in index_info.viewvalues()]
            index_new_list = []
            for index in index_list:
                keys = set()
                for key in index:
                    keys.add(key[0])
                index_new_list.append(keys)

            _log.debug("Index list got from db is {}. formatted list is ".format(
                index_list, index_new_list))
            i1 = {'topic_id', 'ts'}
            if i1 in index_new_list:
                create_index1 = False
            i2 = {'ts'}
            if i2 in index_new_list:
                create_index2 = False

        # create data indexes if needed
        if create_index1:
            db[self._data_collection].create_index(
                [('topic_id', pymongo.DESCENDING),
                 ('ts', pymongo.DESCENDING)],
                unique=True, background=True)
        if create_index2:
            db[self._data_collection].create_index(
                [('ts', pymongo.DESCENDING)], background=True)

        self._topic_id_map, self._topic_name_map = \
            mongoutils.get_topic_map(
                self._client, self._topic_collection)
        self._load_meta_map()

        if self._agg_topic_collection in db.collection_names():
            _log.debug("found agg_topics_collection ")
            self._agg_topic_id_map = mongoutils.get_agg_topic_map(
                self._client, self._agg_topic_collection)
        else:
            _log.debug("no agg topics to load")
            self._agg_topic_id_map = {}

        if not self._readonly:
            db[self.HOURLY_COLLECTION].create_index(
                [('topic_id', pymongo.DESCENDING), ('ts', pymongo.DESCENDING)],
                unique=True, background=True)
            db[self.HOURLY_COLLECTION].create_index(
                [('last_updated_data', pymongo.DESCENDING)], background=True)
            db[self.DAILY_COLLECTION].create_index(
                [('topic_id', pymongo.DESCENDING), ('ts', pymongo.DESCENDING)],
                unique=True, background=True)
            db[self.DAILY_COLLECTION].create_index(
                [('last_updated_data', pymongo.DESCENDING)],
                background=True)

    def record_table_definitions(self, meta_table_name):
        _log.debug("In record_table_def  table:{}".format(meta_table_name))

        db = self._client.get_default_database()
        db[meta_table_name].bulk_write([
            ReplaceOne(
                {'table_id': 'data_table'},
                {'table_id': 'data_table',
                 'table_name': self._data_collection, 'table_prefix': ''},
                upsert=True),
            ReplaceOne(
                {'table_id': 'topics_table'},
                {'table_id': 'topics_table',
                 'table_name': self._topic_collection, 'table_prefix': ''},
                upsert=True),
            ReplaceOne(
                {'table_id': 'meta_table'},
                {'table_id': 'meta_table',
                 'table_name': self._meta_collection, 'table_prefix': ''},
                upsert=True)])


def main(argv=sys.argv):
    """Main method called by the eggsecutable.
    @param argv:
    """
    try:
        utils.vip_main(historian, version=__version__)
    except Exception as e:
        print(e)
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass