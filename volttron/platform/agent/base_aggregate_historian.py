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
from datetime import datetime, timedelta

from abc import abstractmethod
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent
from volttron.platform.vip.agent import Core

_log = logging.getLogger(__name__)
__version__ = '1.0'


class AggregateHistorian(Agent):
    """
    Base agent to aggregate data in historian based on a specific time period.
    Different subclasses of this agent is needed to interact with different
    type of historians. Subclasses should
        1. Implement the collect_aggregate_data with logic to query the
        historian data table to collect and aggregate raw data and store it
        specific aggrgate tables/collections
        2. call setup_periodic_collection() method from its onstart method
        to set up periodic call to collect_aggregate_data()
    """

    def __init__(self, config_path, **kwargs):
        """
        Call super init class. Loads config file
        :param config_path: configuration file path
        :param kwargs:
        """
        super(AggregateHistorian, self).__init__(**kwargs)

        # Instantiate variables
        self.config = utils.load_config(config_path)
        self.topic_id_map = None
        self.aggregate_topic_id_map = None
        self.volttron_table_defs = 'volttron_table_definitions'

        # 1. Check connection to db instantiate db functions class
        connection = self.config.get('connection', None)
        assert connection is not None
        database_type = connection.get('type', None)
        assert database_type is not None
        params = connection.get('params', None)
        assert params is not None

    @Core.receiver('onstart')
    def _on_start(self, sender, **kwargs):
        """
        Converts aggregation time period into seconds, validates
        configuration values and setups periodic call to
        :py:meth:`AggregateHistorian._collect_aggregate_data` method
        @param sender:
        @param kwargs:
        @return:
        """
        self.topic_id_map, name_map = self.get_topic_map()
        self.agg_topic_id_map = self.get_agg_topic_map()

        for agg_group in self.config['aggregations']:
            # 1. Validate and normalize aggregation period and
            # initialize use_calendar_periods flag
            agg_time_period = \
                AggregateHistorian.format_aggregation_time_period(
                    agg_group['aggregation_period'])
            use_calendar_periods = agg_group.get('use_calendar_time_periods',
                                                 False)

            # 2. Validate aggregation details in under points and update
            # aggregate_topics and aggregate_meta tables
            self._init_agg_group(agg_group, agg_time_period)

            # 3. Call parent method to set up periodic aggregation
            # collection calls
            frequency = \
                AggregateHistorian.compute_aggregation_frequency_seconds(
                    agg_time_period,
                    use_calendar_periods)
            self.core.periodic(frequency,
                               self._collect_aggregate_data,
                               [agg_time_period, use_calendar_periods,
                                agg_group['points']]
                               )

    def _init_agg_group(self, agg_group, agg_time_period):
        if 'points' not in agg_group:
            raise ValueError('Invalid configuration must have points')
        for data in agg_group['points']:
            topic_names = data.get('topic_names', None)
            topic_pattern = data.get('topic_name_pattern', None)
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
                data['topic_ids'] = topic_ids
            else:
                # Find if the topic_name patterns result in any topics
                # at all. If it does log them as info
                topic_map = self.find_topics_by_pattern(topic_pattern)
                if topic_map is None or len(topic_map) == 0:
                    raise ValueError(
                        "Please provide a valid topic_name or "
                        "topic_name_pattern for aggregation_period {}. "
                        "The given topic_name_pattern({}) does not "
                        "match any existing topic names".format(
                            agg_group['aggregation_period'],
                            topic_pattern))

                _log.info("topic_names matching the given pattern {} "
                          ":\n {}".format(topic_pattern, topic_map.keys()))
                data['topic_ids'] = topic_map.values()

            # Aggregating across multiple points. Check if unique topic
            # name was given for this.
            _log.debug("topic pattern is {} and topic_ids is {}".format(
                topic_pattern, data['topic_ids']))
            topic_meta = topic_pattern
            if topic_pattern is None:
                topic_meta = topic_names
            if topic_pattern or len(data['topic_ids']) > 1:
                if not data.get('aggregation_topic_name', None):
                    raise ValueError(
                        "Please provide a valid aggregation_topic_name "
                        "when aggregating across multiple points. Update "
                        "aggregation_topic_name for aggregation_period:{} "
                        "and topics:{}".format(
                            agg_group['aggregation_period'],
                            topic_meta))

            else:
                data['aggregation_topic_name'] = topic_names[0]

            # Create data structure for storing aggregate data
            # table/collection. Pass additional parameters so that
            # topics and metadata table can be updated
            topic_meta = {'configured_topics': topic_meta}
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
                self.update_aggregate_store(agg_id,
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

    def _collect_aggregate_data(self, *args):
        """
        Method that does the collection and computation of aggregate data based
        on raw date in historian's data table. This method is called
        periodically when you call setup_periodic_data_collection.
        @param args: List containing [aggregation_period, use_calendar_periods,
        points ] where
         1. aggregation_period = time agg_time_period for which data needs
         to be
        collected and aggregated
         2. use_calendar_periods = flag that indicates if time
         agg_time_period should be
        aligned to calendar times
         3. points = list of points for which aggregate data needs to be
         collected. Each element in the list is a dictionary containing
         topic_names/topic_name_pattern, aggregation_type(ex. sum, avg etc.),
         and min_count(minimum number of raw data to be present within the
         given time agg_time_period for the aggregate to be computed. If
         count is less
         than minimum no aggregate is computed for that time agg_time_period)
        """

        agg_time_period = args[0]
        use_calendar = args[1]
        points = args[2]

        _log.debug(
            "Time agg_time_period passed as arg  {} ".format(agg_time_period))
        _log.debug("points passed as arg  {} ".format(points))

        end_time, start_time = \
            AggregateHistorian.compute_aggregation_timeslice(agg_time_period,
                                                             use_calendar)

        _log.debug(
            "After  compute agg_time_period = {} start_time {} end_time {} ".
            format(agg_time_period, start_time, end_time))
        for data in points:
            _log.debug("data in loop {}".format(data))
            topic_ids = data.get('topic_ids', None)
            _log.debug("topic ids configured {} ".format(topic_ids))
            topic_pattern = data.get('topic_name_pattern', None)
            if topic_pattern:
                # Find topic ids that match the pattern at runtime
                topic_map = self.find_topics_by_pattern(topic_pattern)
                _log.debug("Found topics for pattern {}".format(topic_map))
                if topic_map:
                    topic_ids = topic_map.values()
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
                _log.warn("No records found for topic {topic} "
                          "between {start_time} and {end_time}".
                          format(topic=data['topic_names'],
                                 start_time=start_time,
                                 end_time=end_time))
            elif count < data.get('min_count', 0):
                _log.warn(
                    "Skipping recording of aggregate data for {topic} "
                    "between {start_time} and {end_time} as number of "
                    "records is less than minimum allowed("
                    "{count})".format(topic=data['topic_names'],
                                      start_time=start_time,
                                      end_time=end_time,
                                      count=data.get('min_count', 0)))
            else:
                aggregate_topic_id = \
                    self.agg_topic_id_map[
                        data['aggregation_topic_name'].lower(),
                        data['aggregation_type'].lower(),
                        agg_time_period]
                _log.debug("agg_topic_id {} and topic ids sent to insert {} "
                           "".format(aggregate_topic_id, topic_ids))
                self.insert_aggregate(aggregate_topic_id,
                                      data['aggregation_type'],
                                      agg_time_period,
                                      end_time,
                                      agg_value,
                                      topic_ids)

    @abstractmethod
    def get_topic_map(self):
        """
        Query the topics table and create a map of topic name to topic id.
        This should be done as part of init
        @return: Returns a list of topic_map containing
        {topic_name.lower():id}
        """
        pass

    @abstractmethod
    def get_agg_topic_map(self):
        """
        Query the aggregate_topics table and create a map of
        (topic name, aggregation type, aggregation time period) to
        topic id.
        This should be done as part of init
        @return: Returns a list of topic_map containing
        {(agg_topic_name.lower(), agg_type, agg_time_period) :id}
        """
        pass

    @abstractmethod
    def find_topics_by_pattern(self, topic_pattern):
        """ Find the list of topics and its id for a given topic_pattern
        @return: returns list of dictionary object {topic_name.lower():id}"""

    @abstractmethod
    def initialize_aggregate_store(self, aggregation_topic_name, agg_type,
                                   agg_time_period, topics_meta):
        """
        Create the data structure (table or collection) that is going to store
        the aggregate data for the give aggregation type and aggregation
        time period
        @param aggregation_topic_name: Unique topic name for this
        aggregation. If aggregation is done over multiple points it is a
        unique name given by user, else it is same as topic_name for which
        aggregation is done
        @param agg_type: The type of aggregation. For example, avg, sum etc.
        @param agg_time_period: The time period of aggregation
        @param topics_meta: String that represents the list of topics across
        which this aggregation is computed. It could be topic name pattern
        or list of topics. This information should go into metadata table
        @:return - Return a aggregation_topic_id after inserting
        aggregation_topic_name into topics table
        """

    @abstractmethod
    def update_aggregate_store(self, agg_id, aggregation_topic_name,
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
        Collects the aggregate data by querying the historian's data store
        @param topic_ids: list of topic ids for which aggregation should be
        performed.
        @param agg_type: type of aggregation
        @param start_time: start time for query (inclusive)
        @param end_time:  end time for query (exclusive)
        @return: a tuple of (aggregated value, count of record over which
        this aggregation was computed)
        """
        pass

    @abstractmethod
    def insert_aggregate(self, agg_topic_id, agg_type, agg_time_period,
                         end_time, value, topic_ids):
        """
        @param agg_topic_id: If len(topic_ids) is 1. This would be the same
        as the topic_ids[0]. Else this id corresponds to the unique topic name
        given by user for this aggregation across multiple points.
        @param agg_type: type of aggregation
        @param agg_time_period: The time period of aggregation
        @param end_time: end time used for query records that got aggregated
        @param topic_ids: topic ids for which aggregation was computed
        @param value: aggregation result
        """
        pass

    @abstractmethod
    def is_supported_aggregation(self, agg_type):
        """
        Checks if the given aggregation is supported by the historian's
        data store
        @param agg_type: The type of aggregation to be computed
        @return: True is supported False otherwise
        """
        pass

    # Utility methods
    @staticmethod
    def format_aggregation_time_period(time_period):
        """
        Validates and normalizes aggregation time period. For example,
        if aggregation time period is given as 48h it will get converted
        into 2d
        @param time_period: time period string to be validated and normalized
        @return: normalized time period
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
                period /= 60
                unit = 'h'
        if unit == 'h':
            if period >= 24 and period % 24 == 0:
                period /= 24
                unit = 'd'
        if unit == 'd':
            if period >= 7 and period % 7 == 0:
                period /= 7
                unit = 'w'

        return str(period) + unit

    @staticmethod
    def compute_aggregation_frequency_seconds(agg_period,
                                              use_calendar_periods):
        """
        Return aggregate collection frequency in seconds. This can be used
        to call the aggregate collection method periodically using
        self.core.periodic()
        @param agg_period: period string from AggregateHistorian config
        @param use_calendar_periods: boolean to say if aggregate period
        should be
        based on calendar periods. For example: Week = Sunday to Saturday,
        Hourly average would be 1AM= 2AM, 2AM-3AM etc
        @return: collection frequency in seconds
        """
        period_int = int(agg_period[:-1])
        unit = agg_period[-1:]
        if unit == 'm':
            return period_int * 60
        elif unit == 'h':
            return period_int * 60 * 60
        elif unit == 'd':
            return period_int * 24 * 60 * 60
        elif unit == 'w':
            return period_int * 7 * 24 * 60 * 60
        elif unit == 'M':
            if use_calendar_periods:
                # collect more frequently than needed so that
                # we don't miss collecting February in case we
                # start collecting on say Jan 31
                return period_int * 15 * 24 * 60 * 60
            else:
                return period_int * 30 * 24 * 60 * 60

    @staticmethod
    def compute_aggregation_timeslice(agg_period,
                                      use_calender_time_periods):
        """
        Computes the start and end time for querying the historians data table
        for computing aggregates. Start and end time depend on whether the time
        periods should align to calendar time periods. For example a daily
        average could be computed for data collected between 12am to 11.59am of
        a specific date or data between (current_time - 24 hours) and
        current_time.
        Setting use_calendar_time_periods to true results in former.
        @param agg_period:
        @param use_calender_time_periods:
        @return:
        """
        current = datetime.utcnow()
        period_int = int(agg_period[:-1])
        unit = agg_period[-1:]
        end_time = current
        if unit == 'm':
            start_time = end_time - timedelta(minutes=period_int)
        elif unit == 'h':
            start_time = end_time - timedelta(hours=period_int)
        elif unit == 'd':
            start_time = end_time - timedelta(days=period_int)
        elif unit == 'w':
            start_time = end_time - timedelta(weeks=period_int)
        elif unit == 'M':
            start_time = end_time - timedelta(days=30)
        else:
            raise ValueError(
                "Invalid unit {} provided for aggregation_period. "
                "Unit should be m/h/d/w/M".format(unit))

        if use_calender_time_periods:
            if unit == 'h':
                start_time = start_time.replace(minute=0,
                                                second=0,
                                                microsecond=0)
                end_time = end_time.replace(minute=0,
                                            second=0,
                                            microsecond=0)
            elif unit == 'd' or unit == 'w':
                start_time = start_time.replace(hour=0,
                                                minute=0,
                                                second=0,
                                                microsecond=0)
                end_time = end_time.replace(hour=0,
                                            minute=0,
                                            second=0,
                                            microsecond=0)
            elif unit == 'M':
                end_time = current.replace(day=1,
                                           hour=0,
                                           minute=0,
                                           second=0,
                                           microsecond=0)
                # get last day of previous month
                start_time = end_time - timedelta(days=1)
                # move to first day of previous month
                start_time = start_time.replace(day=1,
                                                hour=0,
                                                minute=0,
                                                second=0,
                                                microsecond=0)

        return end_time, start_time
