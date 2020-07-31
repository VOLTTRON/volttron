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



import copy
import logging
from datetime import datetime, timedelta

import pytz
from abc import abstractmethod

from volttron.platform.agent import utils
from volttron.platform.agent.known_identities import (PLATFORM_HISTORIAN)
from volttron.platform.vip.agent import Agent
from volttron.platform.vip.agent.subsystems import RPC

_log = logging.getLogger(__name__)
__version__ = '1.0'


class AggregateHistorian(Agent):
    """
    Base agent to aggregate data in historian based on a specific time period.
    Different subclasses of this agent is needed to interact with different
    type of historians. Subclasses should implement the following methods

    - :py:meth:`get_topic_map() <AggregateHistorian.get_topic_map>`
    - :py:meth:`get_agg_topic_map() <AggregateHistorian.get_agg_topic_map>`
    - :py:meth:`initialize_aggregate_store() <AggregateHistorian.initialize_aggregate_store>`
    - :py:meth:`update_aggregate_metadata() <AggregateHistorian.update_aggregate_metadata>`
    - :py:meth:`collect_aggregate() <AggregateHistorian.collect_aggregate>`
    - :py:meth:`insert_aggregate() <AggregateHistorian.insert_aggregate>`
    - :py:meth:`get_aggregation_list() <AggregateHistorian.get_aggregation_list>`

    """

    def __init__(self, config_path, **kwargs):
        """
        Call super init class. Loads config file

        :param config_path: configuration file path
        :param kwargs:
        """
        super(AggregateHistorian, self).__init__(**kwargs)
        _log.debug("In init of aggregate historian")
        # Instantiate variables
        config = utils.load_config(config_path)
        self.topic_id_map = None
        self.aggregate_topic_id_map = None
        self.volttron_table_defs = 'volttron_table_definitions'

        self.vip.config.set_default("config", config)
        self.vip.config.subscribe(self.configure, actions=["NEW", "UPDATE"],
                                  pattern="config")
        _log.debug("Done init of aggregate historian")

    def configure(self, config_name, action, config):
        """
        Converts aggregation time period into seconds, validates
        configuration values and calls the collect aggregate method for the
        first time

        :param config_name: name of the config entry in store. We only use
                            one config store entry with the default name config
        :param action: "NEW or "UPDATE" code treats both the same way
        :param config: configuration as json object
        """

        _log.debug("In configure of aggregate historian. current time"
                   "{} config is {}".format(datetime.utcnow(), config))

        if not config or not isinstance(config, dict):
            raise ValueError("Configuration should be a valid json")

        # 1. Check connection to db instantiate db functions class
        connection = config.get('connection', None)
        assert connection is not None
        database_type = connection.get('type', None)
        assert database_type is not None
        params = connection.get('params', None)
        assert params is not None

        self.topic_id_map, name_map = self.get_topic_map()
        self.agg_topic_id_map = self.get_agg_topic_map()
        _log.debug("In start of aggregate historian. "
                   "After loading topic and aggregate topic maps")

        if not config.get("aggregations"):
            _log.debug("End of onstart method - current time{}".format(
                datetime.utcnow()))
            return

        for agg_group in config['aggregations']:
            # 1. Validate and normalize aggregation period and
            # initialize use_calendar_periods flag
            agg_time_period = \
                AggregateHistorian.normalize_aggregation_time_period(
                    agg_group['aggregation_period'])
            use_calendar_periods = agg_group.get('use_calendar_time_periods',
                                                 False)

            # 2. Validate aggregation details in under points and update
            # aggregate_topics and aggregate_meta tables
            self._init_agg_group(agg_group, agg_time_period)

            # 3. Call parent method to set up periodic aggregation
            # collection calls
            if agg_group.get('utc_collection_start_time'):
                utc_collection_start_time = datetime.strptime(
                    agg_group.get('utc_collection_start_time'),
                    '%Y-%m-%dT%H:%M:%S.%f').replace(tzinfo=pytz.utc)
            else:
                utc_collection_start_time = datetime.utcnow().replace(
                    tzinfo=pytz.utc)
            self.collect_aggregate_data(
                utc_collection_start_time,
                agg_time_period,
                use_calendar_periods,
                agg_group['points'])
        _log.debug("End of onstart method - current time{}".format(
            datetime.utcnow()))

    def _init_agg_group(self, agg_group, agg_time_period):
        if 'points' not in agg_group:
            raise ValueError('Invalid configuration must have points')
        for data in agg_group['points']:
            topic_names = data.get('topic_names')
            topic_pattern = data.get('topic_name_pattern')
            if topic_names is None and topic_pattern is None:
                raise ValueError(
                    "Please provide a valid topic_name or "
                    "topic_name_pattern for aggregation_period {}".format(
                        agg_group['aggregation_period']))

            # Validate aggregation_type
            agg_type = data.get('aggregation_type', None)
            if not self.is_supported_aggregation(agg_type):
                raise ValueError("Invalid aggregation type {}"
                                 .format(data['aggregation_type']))
            agg_type = agg_type.lower()
            # Validate min count
            if data.get('min_count', 0) < 0:
                raise ValueError("Invalid min_count ({}). min_count "
                                 "should be "
                                 "an integer grater than 0".
                                 format(data['min_count']))

            # Validated topic name or pattern and populate topic_ids
            _log.debug("topic names {}".format(topic_names))
            topic_ids = []
            if topic_names is not None:
                for name in topic_names:
                    if not self.topic_id_map.get(name.lower(), None):
                        raise ValueError("Invalid topic_name {}".format(
                            name))
                    else:
                        topic_ids.append(self.topic_id_map[name.lower()])
                        _log.debug("topic_ids is {}".format(topic_ids))
                data['topic_ids'] = list(set(topic_ids))
            else:
                # Find if the topic_name patterns result in any topics
                # at all. If it does log them as info
                topic_map = self.vip.rpc.call(
                    PLATFORM_HISTORIAN,
                    "get_topics_by_pattern",
                    topic_pattern=topic_pattern).get()
                if topic_map is None or len(topic_map) == 0:
                    raise ValueError(
                        "Please provide a valid topic_name or "
                        "topic_name_pattern for aggregation_period {}. "
                        "The given topic_name_pattern({}) does not "
                        "match any existing topic names".format(
                            agg_group['aggregation_period'],
                            topic_pattern))

                _log.info("topic_names matching the given pattern {} "
                          ":\n {}".format(topic_pattern, list(topic_map.keys())))
                data['topic_ids'] = list(topic_map.values())

            # Aggregating across multiple points. Check if unique topic
            # name was given for this.
            _log.debug("topic pattern is {} and topic_ids is {}".format(
                topic_pattern, data['topic_ids']))
            topic_meta = topic_pattern
            if topic_pattern is None:
                topic_meta = tuple(topic_names)
            if topic_pattern or len(data['topic_ids']) > 1:
                if not data.get('aggregation_topic_name'):
                    raise ValueError(
                        "Please provide a valid aggregation_topic_name "
                        "when aggregating across multiple points. Update "
                        "aggregation_topic_name for aggregation_period:{} "
                        "and topics:{}".format(
                            agg_group['aggregation_period'],
                            topic_meta))

            else:
                if not data.get('aggregation_topic_name'):
                    data['aggregation_topic_name'] = topic_names[0]

            # Create data structure for storing aggregate data
            # table/collection. Pass additional parameters so that
            # topics and metadata table can be updated
            topic_meta = {'configured_topics': topic_meta}
            _log.debug("agg_map key is ({}, {},{})".format(
                data['aggregation_topic_name'].lower(),
                agg_type,
                agg_time_period))
            agg_id = self.agg_topic_id_map.get(
                (data['aggregation_topic_name'].lower(), agg_type,
                 agg_time_period),
                None)
            if agg_id:
                _log.debug(
                    "Found aggregate updating existing rows for id {} "
                    " name {} meta {}".format(agg_id,
                                              data['aggregation_topic_name'],
                                              topic_meta))
                self.update_aggregate_metadata(agg_id,
                                               data['aggregation_topic_name'],
                                               topic_meta)
            else:
                _log.debug(
                    "Inserting new record into aggregate_topics name {} "
                    "meta {}".format(data['aggregation_topic_name'],
                                     topic_meta))
                agg_id = self.initialize_aggregate_store(
                    data['aggregation_topic_name'],
                    data['aggregation_type'],
                    agg_time_period,
                    topic_meta)
                _log.debug("After insert aggregate_id is {}".format(agg_id))
                self.agg_topic_id_map[(data['aggregation_topic_name'].lower(),
                                       agg_type, agg_time_period)] = agg_id
            _log.debug("End of loop in init_agg_group. ids {}".format(
                data['topic_ids']))

    def collect_aggregate_data(self, collection_time, agg_time_period,
                               use_calendar_periods, points):

        """
        Method that does the collection and computation of aggregate data based
        on raw date in historian's data table. This method is called
        for the first time when a agent is configured with a new
        configuration or when the config in config store is updated. After the
        collection of aggregate data, this methods schedules itself to be
        called after a specific period of time. The time interval is
        calculated by
        :py:meth:`compute_next_collection_time() <AggregateHistorian.compute_next_collection_time>`
        This method in turn calls the platform historian's
        - :py:method:`get_topics_by_pattern()` <BaseHistorian.get_topics_by_pattern>

        and the following methods implemented by child classes:

        - :py:meth:`collect_aggregate() <AggregateHistorian.collect_aggregate>`
        - :py:meth:`insert_aggregate() <AggregateHistorian.insert_aggregate>`

        :param collection_time:  time of aggregation collection
        :param param agg_time_period: time agg_time_period for which data
                                      needs to be collected and aggregated
        :param param use_calendar_periods: flag that indicates if time
                                           agg_time_period should be aligned
                                           to calendar times
        :param param points: list of points for which aggregate data needs
                             to be collected. Each element in the list is a
                             dictionary containing
                             topic_names/topic_name_pattern,
                             aggregation_type(ex. sum, avg etc.), and
                             min_count(minimum number of raw data to be
                             present within the given time agg_time_period
                             for the aggregate to be computed. If
                             count is less than minimum no aggregate is
                             computed for that agg_time_period)
        """

        _log.debug(
            "In collect_aggregate_data: Time agg_time_period passed as arg  "
            "{} use_calendar={}".format(agg_time_period, use_calendar_periods))
        _log.debug("points passed as arg  {} ".format(points))

        start_time, end_time = \
            AggregateHistorian.compute_aggregation_time_slice(
                collection_time, agg_time_period, use_calendar_periods)
        try:
            _log.debug(
                "After  compute agg_time_period = {} start_time {} end_time "
                "{} ".format(agg_time_period, start_time, end_time))
            schedule_next = True
            for data in points:
                _log.debug("data in loop {}".format(data))
                topic_ids = data.get('topic_ids', None)
                _log.debug("topic ids configured {} ".format(topic_ids))
                topic_pattern = data.get('topic_name_pattern', None)

                aggregate_topic_id = \
                    self.agg_topic_id_map.get(
                        (data['aggregation_topic_name'].lower(),
                         data['aggregation_type'].lower(),
                         agg_time_period))
                if not aggregate_topic_id:
                    _log.warn("Name:{} Type: {} Aggregation Period: {}    --"
                              "No such aggregate topic found. This could have happened if the "
                              "configuration of the agent changed after the last schedule for data collection"
                              " Stopping collection for the outdated configuration".format(
                        data['aggregation_topic_name'].lower(),
                        data['aggregation_type'].lower(),
                        agg_time_period))
                    schedule_next = False
                    break  # break out of for loop and move to finally block

                if topic_pattern:
                    # Find topic ids that match the pattern at runtime
                    topic_map = self.vip.rpc.call(
                        PLATFORM_HISTORIAN,
                        "get_topics_by_pattern",
                        topic_pattern=topic_pattern).get()
                    _log.debug("Found topics for pattern {}".format(topic_map))
                    if topic_map:
                        topic_ids = list(topic_map.values())
                        _log.debug("topic ids loaded {} ".format(topic_ids))
                    else:
                        _log.warn(
                            "Skipping recording of aggregate data for {topic} "
                            "between {start_time} and {end_time} as ".format(
                                topic=topic_pattern,
                                start_time=start_time,
                                end_time=end_time))
                        return

                agg_value, count = self.collect_aggregate(
                    topic_ids,
                    data['aggregation_type'],
                    start_time,
                    end_time)
                if count == 0:
                    _log.warn(
                        "No records found for topic {topic} between "
                        "{start_time} and {end_time}".format(
                            topic=topic_pattern if topic_pattern else
                            data['topic_names'],
                            start_time=start_time,
                            end_time=end_time))
                elif count < data.get('min_count', 0):
                    _log.warn(
                        "Skipping recording of aggregate data for {topic} "
                        "between {start_time} and {end_time} as number of "
                        "records is less than minimum allowed("
                        "{count})".format(
                            topic=topic_pattern if topic_pattern
                            else data['topic_names'],
                            start_time=start_time,
                            end_time=end_time,
                            count=data.get('min_count', 0)))
                else:
                    _log.debug("data is {} aggg_time_period is {}".format(data, agg_time_period))
                    _log.debug(" topic id map {}".format(self.agg_topic_id_map))
                    self.insert_aggregate(aggregate_topic_id,
                                          data['aggregation_type'],
                                          agg_time_period,
                                          end_time,
                                          agg_value,
                                          topic_ids)

        finally:
            if schedule_next:
                collection_time = AggregateHistorian.compute_next_collection_time(
                    collection_time, agg_time_period, use_calendar_periods)
                _log.debug(
                    "Scheduling next collection at {}".format(collection_time))
                event = self.core.schedule(collection_time,
                                           self.collect_aggregate_data,
                                           collection_time,
                                           agg_time_period,
                                           use_calendar_periods,
                                           points)
                _log.debug("After Scheduling next collection.{}".format(event))

    @abstractmethod
    def get_topic_map(self):
        """
        Query the topics table and create a map of topic name to topic id.
        This should be done as part of init

        :return: Returns a list of topic_map containing {topic_name.lower():id}
        """
        pass

    @abstractmethod
    def get_agg_topic_map(self):
        """
        Query the aggregate_topics table and create a map of
        (topic name, aggregation type, aggregation time period) to
        topic id. This should be done as part of init

        :return: Returns a list of topic_map containing
        ::

            {(agg_topic_name.lower(), agg_type, agg_time_period) :id}

        """
        pass

    @abstractmethod
    def initialize_aggregate_store(self, aggregation_topic_name, agg_type,
                                   agg_time_period, topics_meta):
        """
        Create the data structure (table or collection) that is going to store
        the aggregate data for the give aggregation type and aggregation
        time period

        :param aggregation_topic_name: Unique topic name for this
                                       aggregation. If aggregation is done
                                       over multiple points it is a
                                       unique name given by user, else it is
                                       same as topic_name for which
                                       aggregation is done
        :param agg_type: The type of aggregation. For example, avg, sum etc.
        :param agg_time_period: The time period of aggregation
        :param topics_meta: String that represents the list of topics across
                            which this aggregation is computed. It could be
                            topic name pattern or list of topics. This
                            information should go into metadata table
        :return: Return a aggregation_topic_id after inserting
                 aggregation_topic_name into topics table

        """

    @abstractmethod
    def update_aggregate_metadata(self, agg_id, aggregation_topic_name,
                                  topic_meta):
        """
        Update aggregation_topic_name and topic_meta data for the given
        agg_id.

        :param agg_id: Aggregation topic id for which update should be done
        :param aggregation_topic_name: New aggregation_topic_name
        :param topic_meta: new topic metadata
        """

    @abstractmethod
    def collect_aggregate(self, topic_ids, agg_type, start_time, end_time):
        """
        Collect the aggregate data by querying the historian's data store

        :param topic_ids: list of topic ids for which aggregation should be
                          performed.
        :param agg_type: type of aggregation
        :param start_time: start time for query (inclusive)
        :param end_time:  end time for query (exclusive)
        :return: a tuple of (aggregated value, count of record over which
        this aggregation was computed)
        """
        pass

    @abstractmethod
    def insert_aggregate(self, agg_topic_id, agg_type, agg_time_period,
                         end_time, value, topic_ids):
        """
        Insert aggregate data collected for a specific  time period into
        database. Data is inserted into <agg_type>_<period> table

        :param agg_topic_id: If len(topic_ids) is 1. This would be the same
                             as the topic_ids[0]. Else this id corresponds to
                             the unique topic name given by user for this
                             aggregation across multiple points.
        :param agg_type: type of aggregation
        :param agg_time_period: The time period of aggregation
        :param end_time: end time used for query records that got aggregated
        :param topic_ids: topic ids for which aggregation was computed
        :param value: aggregation result
        """
        pass

    def is_supported_aggregation(self, agg_type):
        """
        Checks if the given aggregation is supported by the historian's
        data store

        :param agg_type: The type of aggregation to be computed
        :return: True is supported False otherwise
        """
        if agg_type:
            return agg_type.upper() in [x.upper() for x in
                                        self.get_aggregation_list()]
        else:
            return False

    @RPC.export
    def get_supported_aggregations(self):
        return self.get_aggregation_list()

    @abstractmethod
    def get_aggregation_list(self):
        """
        Returns a list of supported aggregations

        :return: list of supported aggregations
        """
        pass

    # Utility methods
    @staticmethod
    def normalize_aggregation_time_period(time_period):
        """
        Validates and normalizes aggregation time period. For example,
        if aggregation time period is given as 48h it will get converted
        into 2d

        :param time_period: time period string to be validated and normalized
        :return: normalized time period
        """
        try:
            time_period = time_period.strip()
            period = int(time_period[:-1])
        except ValueError:
            raise ValueError(
                "Aggregation period {} provided is invalid. Please "
                "specify an integer followed by m/h/d/w/M "
                "(minutes, hours, days, weeks".format(time_period))

        unit = time_period[-1:]

        if unit not in ['m', 'h', 'd', 'w', 'M']:
            raise ValueError(
                "Invalid unit {} provided for aggregation time "
                "period {}. Valid time periods are m,h,d,w,"
                "or M (minutes, hours, days, weeks, months".format(
                    unit, time_period))
        if unit == 'm':
            if period >= 60 and period % 60 == 0:
                period //= 60
                unit = 'h'
        if unit == 'h':
            if period >= 24 and period % 24 == 0:
                period //= 24
                unit = 'd'
        if unit == 'd':
            if period >= 7 and period % 7 == 0:
                period //= 7
                unit = 'w'

        return str(period) + unit

    @staticmethod
    def compute_next_collection_time(collection_time, agg_period,
                                     use_calendar_periods):
        """
        compute the next collection time based on current time in utc and
        aggregation time period.

        :param collection_time: time of aggregate collection
        :param agg_period: period string from AggregateHistorian config
        :param use_calendar_periods: boolean to say if aggregate period
                                     should be based on calendar periods.
                                     For example: Week = Sunday to Saturday,
                                     Hourly average would be 1AM= 2AM, 2AM-3AM
                                     etc.
        :return: next collection time in utc

        """
        period_int = int(agg_period[:-1])
        unit = agg_period[-1:]
        if unit == 'm':
            return collection_time + timedelta(minutes=period_int)
        elif unit == 'h':
            return collection_time + timedelta(hours=period_int)
        elif unit == 'd':
            return collection_time + timedelta(days=period_int)
        elif unit == 'w':
            return collection_time + timedelta(weeks=period_int)
        elif unit == 'M':
            if use_calendar_periods:
                # collect more frequently than 30 days so that
                # we don't miss collecting January's data in case we
                # start collecting on say Jan 31
                period_int *= 15
                return collection_time + timedelta(days=period_int)
            else:
                period_int *= 30
                return collection_time + timedelta(days=period_int)

    @staticmethod
    def compute_aggregation_time_slice(collection_time, agg_period,
                                       use_calender_time_periods):
        """
        Computes the start and end time for querying the historians data table
        for computing aggregates. Start and end time depend on whether the time
        periods should align to calendar time periods. For example a daily
        average could be computed for data collected between 12am to 11.59am of
        a specific date or data between (collection_time - 24 hours) and
        current_time. Setting use_calendar_time_periods to true results in
        former.

        :param collection_time: Time of aggregation collection
        :param agg_period: time period of the aggregation
        :param use_calender_time_periods: boolean to indicate if the time
                                          period should align to the calendar
                                          time periods
        :return: start and end time of aggregation. start time is inclusive
        and end time is not.
        """
        end_time = collection_time
        period_int = int(agg_period[:-1])
        unit = agg_period[-1:]

        if unit == 'm':
            start_time = end_time - timedelta(minutes=period_int)
        elif unit == 'h':
            start_time = end_time - timedelta(hours=period_int)
        elif unit == 'd':
            start_time = end_time - timedelta(days=period_int)
        elif unit == 'w':
            start_time = end_time - timedelta(weeks=period_int)
        elif unit == 'M':
            start_time = end_time - timedelta(days=30 * period_int)
        else:
            raise ValueError(
                "Invalid unit {} provided for aggregation_period. "
                "Unit should be m/h/d/w/M".format(unit))

        if use_calender_time_periods:
            if unit == 'm':
                start_time = start_time.replace(second=0,
                                                microsecond=0)
                end_time = end_time.replace(second=0,
                                            microsecond=0)
            if unit == 'h':
                start_time = start_time.replace(minute=0,
                                                second=0,
                                                microsecond=0)
                end_time = end_time.replace(minute=0,
                                            second=0,
                                            microsecond=0)
            elif unit == 'd':
                start_time = start_time.replace(hour=0,
                                                minute=0,
                                                second=0,
                                                microsecond=0)
                end_time = end_time.replace(hour=0,
                                            minute=0,
                                            second=0,
                                            microsecond=0)
            elif unit == 'w':

                day_idx = end_time.weekday()
                # weekday index starts on Monday, so Mon=0, Tue=1 etc.
                if day_idx != 6:
                    # If it is not a sunday move to last sunday
                    end_time = end_time - timedelta(days=day_idx + 1)

                end_time = end_time.replace(hour=0,
                                            minute=0,
                                            second=0,
                                            microsecond=0)
                start_time = end_time - timedelta(weeks=period_int)

            elif unit == 'M':
                end_time = end_time.replace(day=1,
                                            hour=0,
                                            minute=0,
                                            second=0,
                                            microsecond=0)
                # get last day of previous month
                end_time = end_time - timedelta(days=1)

                # move to first day of previous month
                start_time = copy.copy(end_time).replace(day=1,
                                                         hour=0,
                                                         minute=0,
                                                         second=0,
                                                         microsecond=0)

        return start_time, end_time
