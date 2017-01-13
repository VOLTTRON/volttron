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
from collections import defaultdict
from datetime import datetime
from dateutil.relativedelta import relativedelta
from calendar import monthrange
from datetime import timedelta
from dateutil.tz import tzutc
import numbers

import gevent
import pymongo
from bson.objectid import ObjectId
from pymongo import ReplaceOne
from pymongo import UpdateOne

from pymongo.errors import BulkWriteError
from volttron.platform.agent import utils
from volttron.platform.agent.base_historian import BaseHistorian
from volttron.platform.agent.utils import get_aware_utc_now
from volttron.platform.dbutils import mongoutils
from volttron.platform.vip.agent import Core
import re
import pytz

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '2.0'


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

    MongodbHistorian.__name__ = 'MongodbHistorian'
    return MongodbHistorian(config_dict, identity=identity,
                            topic_replace_list=topic_replacements, **kwargs)


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

        # This event will be scheduled nightly to be rolled up from the daily
        # information that was added to the daily queue.
        self._daily_rollup_event = None
        self._inserted_hour_topics = set()
        self._periodic_rollup_event = None
        if config.get('initial_rollup_start_time'):
            self._initial_rollup_start_time = datetime.strptime(
                    config.get('initial_rollup_start_time'),
                    '%Y-%m-%dT%H:%M:%S.%f').replace(tzinfo=pytz.utc)
        else:
            self._initial_rollup_start_time = get_aware_utc_now()
        super(MongodbHistorian, self).__init__(**kwargs)

    @Core.periodic(10, wait=15)
    def periodic_rollup(self):
        _log.debug("periodic attempt to do daily and monthly rollup.")
        if self._client is None:
            _log.debug("historian setup not complete. "
                       "wait for next periodic call")
            return
        # Find the records that needs to be processed from data table
        db = self._client.get_default_database()
        stat = db.rollup_status.find_one({})
        find_condition = {'ts': {'$gt': self._initial_rollup_start_time}}
        if stat:
            _log.debug("ROLLING FROM last processed id {}, {}".format(
                stat["last_data_into_daily"], stat["last_data_into_monthly"]))

            if stat["last_data_into_daily"] < stat["last_data_into_monthly"]:
                find_condition = {'_id': {'$gt': stat["last_data_into_daily"]}}
            else:
                find_condition = {'_id':
                                      {'$gt': stat["last_data_into_monthly"]}}
        else:
            _log.debug("ROLLING FROM start date {}".format(
                self._initial_rollup_start_time))

        # Iterate and append to a bulk_array. Insert in batches of 1000
        bulk_publish_day = []
        bulk_publish_month = []
        day_ids = []
        month_ids = []
        d = 0
        m = 0
        last_topic_id = ''
        last_date = ''
        last_month = ''
        last_year = ''
        cursor = db[self._data_collection].find(find_condition).sort(
            [('topic_id', pymongo.ASCENDING), ('ts', pymongo.ASCENDING)])


        for row in cursor:
            if not stat or row['_id'] > stat["last_data_into_daily"] :

                if last_topic_id != row['topic_id'] \
                        or last_date != row['ts'].date():
                    self.initialize_daily(topic_id=row['topic_id'],
                                          ts=row['ts'])
                    last_topic_id = row['topic_id']
                    last_date = row['ts'].date()

                bulk_publish_day.append(
                    self.insert_to_daily(db, topic_id=row['topic_id'],
                                         ts=row['ts'], value=row['value']))
                day_ids.append(row['_id'])
                d += 1

            if not stat or row['_id'] > stat["last_data_into_monthly"]:
                if last_topic_id != row['topic_id']\
                        or (last_month != row['ts'].month \
                            and last_year != row['ts'].year):
                    self.initialize_monthly(topic_id=row['topic_id'],
                                            ts=row['ts'])
                    last_topic_id = row['topic_id']
                    last_month = row['ts'].month
                    last_year = row['ts'].year

                bulk_publish_month.append(
                    self.insert_to_monthly(db, topic_id=row['topic_id'],
                                           ts=row['ts'], value=row['value']))
                month_ids.append(row['_id'])
                m += 1

            #Perform insert if we have 1000 rows
            d_errors = m_errors = False
            if d == 3:
                _log.debug("In loop. bulk write")
                bulk_publish_day, day_ids, d_errors = \
                    self.bulk_write_rolled_up_data(
                    'daily', bulk_publish_day, day_ids, db)
                d = 0
            if m == 3:
                #gevent.sleep(20)
                bulk_publish_month, month_ids, m_errors = \
                    self.bulk_write_rolled_up_data(
                    'monthly', bulk_publish_month, month_ids, db)
                m = 0
            if d_errors or m_errors:
                # something failed in bulk write. try from last err
                # row during the next periodic call
                return

        # Perform insert for any pending records
        if bulk_publish_day:
            _log.debug("Outside loop. bulk write")
            self.bulk_write_rolled_up_data(
                'daily', bulk_publish_day, day_ids, db)
        if bulk_publish_month:
            self.bulk_write_rolled_up_data(
                'monthly', bulk_publish_month, month_ids, db)

    def bulk_write_rolled_up_data(self, time_period, requests, ids, db):
        '''
        Handle bulk inserts into daily or monthly roll up table. Find out
        the last successfully processed record adn store that in the
        rollup_status collection.
        :param time_period: "daily" or "monthly"
        :param requests: array of bulk write requests
        :param ids: array of data collection _ids that are part of the bulk
        write requests
        :param db: handle to database
        :return: emptied request array, ids array, and True if there were
        errors during write operation or False if there was none
        '''
        errors = False
        try:
            _log.debug("Before bulk write to "+time_period)
            db[time_period + '_data'].bulk_write(requests, ordered=True)
        except BulkWriteError as ex:
            _log.error(str(ex.details))
            errors = True
            error_index = ex.details['writeErrors'][0]['index']
            if error_index > 0:
                db.rollup_status.update_one({}, {"$set": {
                    "last_data_into_" + time_period: ids[error_index - 1]}})
        else:
            # Record last data row that was rolled up
            result = db.rollup_status.update_one(
                {},
                {"$set": {"last_data_into_" + time_period: ids[-1]}},
                upsert=True)
            _log.debug("Updated rollup_status")
            ids = []
            requests = []
        return requests, ids, errors

    def version(self):
        return __version__


    def initialize_hourly(self, topic_id, ts):
        ts_hour = ts.replace(minute=0, second=0, microsecond=0)

        db = self._client.get_default_database()
        needs_initializing = not db.hourly_data.find(
            {'ts': ts_hour, 'topic_id': topic_id}).count() > 0

        # _log.debug("needs_intializing? {}".format(
        #     needs_initializing
        # ))

        if needs_initializing:
            db['hourly_data'].update_one(
                {'ts': ts_hour, 'topic_id': topic_id},
                {"$setOnInsert": {'ts': ts_hour,
                                  'topic_id': topic_id,
                                  'count': 0,
                                  'sum': 0,
                                  'data': [[]] * 60}},
                upsert=True)

            _log.debug("CALLING INIT DAILY")

            return True
        return False

    def initialize_daily(self, topic_id, ts):
        ts_day = ts.replace(hour=0, minute=0, second=0, microsecond=0)

        db = self._client.get_default_database()
        needs_initializing = not db.daily_data.find(
            {'ts': ts_day, 'topic_id': topic_id}).count() > 0

        if needs_initializing:
            _log.debug("INITIALIZING DAILY DAATA")
            _log.debug(db.daily_data.find(
                {'ts': ts_day, 'topic_id': topic_id}).count())
            db.daily_data.update_one(
                {'ts': ts_day, 'topic_id': topic_id},
                {"$setOnInsert": {'ts': ts_day,
                                  'topic_id': topic_id,
                                  'count': 0,
                                  'sum': 0,
                                  'data': [[]] * 24 * 60}},
                upsert=True)


    def initialize_monthly(self, topic_id, ts):
        ts_month = ts.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        db = self._client.get_default_database()
        needs_initializing = not db.monthly_data.find(
            {'ts': ts_month, 'topic_id': topic_id}).count() > 0

        if needs_initializing:
            _log.debug("INITIALIZING MONTLHY DAATA")
            weekday, num_days = monthrange(ts_month.year,
                                           ts_month.month)
            db['monthly_data'].update_one(
                {'ts': ts_month, 'topic_id': topic_id},
                {"$setOnInsert": {'ts': ts_month,
                                  'topic_id': topic_id,
                                  'count': 0,
                                  'sum': 0,
                                  'data': [[]] * num_days * 24 * 60}},
                upsert=True)


    def insert_to_daily(self, db, topic_id, ts, value):
        rollup_day = ts.replace(hour=0, minute=0, second=0,
                                         microsecond=0)
        position = ts.hour * 60 + ts.minute
        sum_value = MongodbHistorian.value_to_sumable(value)

        return UpdateOne(
            {
                'ts': rollup_day, 'topic_id': topic_id
            },
            {
                '$push': {
                    "data." + str(position): [ts, value]
                },
                '$inc': {
                    'count': 1,
                    'sum': sum_value
                }
            }
        )

    def insert_to_monthly(self, db, topic_id, ts, value):
        rollup_month = ts.replace(day=1, hour=0, minute=0, second=0,
                                microsecond=0)
        sum_value = MongodbHistorian.value_to_sumable(value)
        position = (ts.day * 24 * 60) + (ts.hour * 60) + ts.minute

        return UpdateOne(
            {
                'ts': rollup_month, 'topic_id': topic_id
            },
            {
                '$push':{
                    "data." + str(position): [ts, value]
                },
                '$inc': {
                    'count': 1,
                    'sum': sum_value}
            }
        )

    def publish_to_historian(self, to_publish_list):
        _log.debug("publish_to_historian number of items: {}".format(
            len(to_publish_list)))

        # Use the db instance to insert/update the topics
        # and data collections
        db = self._client.get_default_database()

        bulk_publish = []
        bulk_publish_hour = []
        bulk_publish_day = []
        bulk_publish_month = []
        for x in to_publish_list:
            #_log.debug("SOURCE IS: {}".format(x['source']))
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
            rollup_hour = ts.replace(minute=0, second=0, microsecond=0)
            rollup_day = rollup_hour.replace(hour=0)
            rollup_month = rollup_day.replace(day=1)

            if topic_id is None:
                row = db[self._topic_collection].insert_one(
                    {'topic_name': topic})
                topic_id = row.inserted_id
                self._topic_id_map[topic_lower] = topic_id
                self._topic_name_map[topic_lower] = topic

                if int(self.version_nums[0]) >= 2:
                    # Since we know it's a new topic we can just initialize
                    # straight away
                    self.initialize_hourly(topic_id, ts)
                    self.initialize_daily(topic_id, ts)
                    self.initialize_monthly(topic_id, ts)

                    _log.debug("After init of rollup rows for new topic {} "
                               "hr-{} day-{} month-{}".format(db_topic_name,
                                                              rollup_day,
                                                              rollup_hour,
                                                              rollup_month))

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

            # Reformat to a filter tha bulk inserter.
            bulk_publish.append(ReplaceOne(
                {'ts': ts, 'topic_id': topic_id},
                {'ts': ts, 'topic_id': topic_id, 'source':source,
                 'value': value},
                upsert=True))

            if int(self.version_nums[0]) >= 2:
                def callback_done(type, topic_id, ts, value):
                    _log.debug("DONE WITH INIT OF {}".format(type))
                    if type == 'daily':
                        self.insert_to_daily(db, topic_id, ts, value)
                    else:
                        self.insert_to_monthly(db, topic_id, ts, value)

                self.initialize_hourly(topic_id, ts)

                sum_value = MongodbHistorian.value_to_sumable(value)

                bulk_publish_hour.append(UpdateOne(
                    {
                        'ts': rollup_hour,
                        'topic_id': topic_id
                    },
                    {
                        '$push': {
                            "data."+ str(ts.minute): [ts, value]
                        },
                        '$inc':{
                            'count': 1,
                            'sum': sum_value
                        }
                    }
                ))

        # done going through all data and adding appropriate updates stmts
        # perform bulk write into data and roll up collections
        # _log.debug("bulk_publish_hour {}".format(bulk_publish_hour))
        # _log.debug("bulk_publish_day {}".format(bulk_publish_day))
        # _log.debug("bulk_publish_month {}".format(bulk_publish_month))
        try:
            # http://api.mongodb.org/python/current/api/pymongo
            # /collection.html#pymongo.collection.Collection.bulk_write
            result = db[self._data_collection].bulk_write(bulk_publish)
            # insert into an "inserted hourly table"
        except BulkWriteError as bwe:
            _log.error("Error during bulk write to data: {}".format(
                bwe.details))
        else:  # No write errros here when
            if not result.bulk_api_result['writeErrors']:
                self.report_all_handled()
            else:
                # TODO handle when something happens during writing of
                # data.
                _log.error('SOME THINGS DID NOT WORK')

        if int(self.version_nums[0]) >= 2:
            try:
                # http://api.mongodb.org/python/current/api/pymongo
                # /collection.html#pymongo.collection.Collection.bulk_write
                result = db['hourly_data'].bulk_write(bulk_publish_hour)
            except BulkWriteError as bwe:
                _log.error("Error during bulk write to hourly data:{}".format(
                    bwe.details))

            # try:
            #     # http://api.mongodb.org/python/current/api/pymongo
            #     # /collection.html#pymongo.collection.Collection.bulk_write
            #     result = db['daily_data'].bulk_write(bulk_publish_day)
            # except BulkWriteError as bwe:
            #     _log.error("Error during bulk write to daily data:{}".format(
            #         bwe.details))
            #
            # try:
            #     # http://api.mongodb.org/python/current/api/pymongo
            #     # /collection.html#pymongo.collection.Collection.bulk_write
            #     result = db['monthly_data'].bulk_write(bulk_publish_month)
            # except BulkWriteError as bwe:
            #     _log.error("Error during bulk write to monthly data:{}".format(
            #         bwe.details))

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
        if agg_type and agg_period:
            # query aggregate data collection instead
            collection_name = agg_type + "_" + agg_period
        else:
            # See if we can use rolled up data
            if int(self.version_nums[0]) >= 2 and start and end \
                    and start != end:
                diff = (end - start).total_seconds()
                _log.debug("total seconds between end and start {}".format(
                    diff))
                if diff > 30 * 24 * 3600:
                    collection_name = "monthly_data"
                    use_rolled_up_data = True
                    query_start = start.replace(days=1,
                                                hour=0,
                                                minute=0,
                                                second=0,
                                                microsecond=0)
                    query_end = (end + relativedelta(months=1)).replace(
                        days=1,
                        hour=0,
                        minute=0,
                        second=0, microsecond=0)
                elif diff >= 24 * 3600:
                    collection_name = "daily_data"
                    use_rolled_up_data = True
                    query_start = start.replace(hour=0,
                                                minute=0,
                                                second=0,
                                                microsecond=0)
                    query_end = (end + timedelta(days=1)).replace(
                        hour=0,
                        minute=0,
                        second=0,
                        microsecond=0)
                elif diff >= 3600*3: #more than 3 hours of data
                    collection_name = "hourly_data"
                    use_rolled_up_data = True
                    query_start = start.replace(minute=0, second=0,
                                                microsecond=0)
                    query_end = (end+timedelta(hours=1)).replace(
                        minute=0,
                        second=0,
                        microsecond=0)



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
            _log.debug("Found topic id for {} as {}".format(
                topics_list, topic_ids))
        multi_topic_query = len(topic_ids) > 1
        db = self._client.get_default_database()

        ts_filter = {}
        order_by = 1
        if order == 'LAST_TO_FIRST':
            order_by = -1

        if start is not None:
            if use_rolled_up_data:
                ts_filter["$gte"] = query_start
            else:
                ts_filter["$gte"] = start
        if end is not None:
            if use_rolled_up_data:
                ts_filter["$lt"] = query_end
            else:
                ts_filter["$lt"] = end

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
        for x in topic_ids:
            find_params['topic_id'] = ObjectId(x)
            _log.debug("querying table with params {}".format(find_params))
            if use_rolled_up_data:
                project = {"_id": 0, "data": 1}
            else:
                project = {"_id": 0, "timestamp": {
                '$dateToString': {'format': "%Y-%m-%dT%H:%M:%S.%L000+00:00",
                    "date": "$ts"}}, "value": 1}
            pipeline = [{"$match": find_params}, {"$skip": skip_count},
                        {"$sort": {"ts": order_by}}, {"$limit": count}, {
                            "$project": project}]
            _log.debug("pipeline for agg query is {}".format(pipeline))
            _log.debug("collection_name is "+ collection_name)
            cursor = db[collection_name].aggregate(pipeline)

            rows = list(cursor)
            _log.debug("Time after fetch {}".format(
                datetime.utcnow() - start_time))
            if use_rolled_up_data:
                for row in rows:
                    for data in row['data']:
                        if data:
                            _log.debug("start {}".format(start))
                            _log.debug("end {}".format(end))
                            if start.tzinfo:
                                data[0] = data[0].replace(tzinfo=tzutc())
                            _log.debug("data[0] {}".format(data[0]))
                            if data[0] >= start and data[0] < end:
                                values[id_name_map[x]].append(
                                    (utils.format_timestamp(data[0]),
                                     data[1]))
                _log.debug("values len {}".format(len(values)))
            else:
                for row in rows:
                    values[id_name_map[x]].append(
                        (row['timestamp'], row['value']))
            _log.debug("Time taken to load into values {}".format(
                datetime.utcnow() - start_time))
            _log.debug("rows length {}".format(len(rows)))

        _log.debug("Time taken to load all values {}".format(
            datetime.utcnow() - start_time))
        #_log.debug("Results got {}".format(values))

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

    def historian_setup(self):
        _log.debug("HISTORIAN SETUP")
        self._client = mongoutils.get_mongo_client(self._connection_params)
        db = self._client.get_default_database()
        db[self._data_collection].create_index(
            [('topic_id', pymongo.DESCENDING), ('ts', pymongo.DESCENDING)],
            unique=True, background=True)

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

        self._inserted_hour_topics = set()
        # try:
        #     db.hourly_inserts.find()
        #     hourly_inserts = self.vip.config.get("inserted_hourly")
        # except KeyError:
        #
        # else:
        #     self._inserted_hour_topics = set(hourly_inserts['inserted'])

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
        utils.vip_main(historian, enable_store=True)
    except Exception as e:
        print(e)
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass