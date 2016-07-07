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
from abc import abstractmethod
from datetime import datetime, timedelta

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
        self._agent_id = self.config['agentid']
        self.topic_id_map = None

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
        Converts aggrgation time period into seconds and setups periodic
        call to collect_aggregate_data method
        @param sender:
        @param kwargs:
        @return:
        """
        self.topic_id_map, name_map = self.get_topic_map()
        for agg_group in self.config['aggregations']:

            # 1. Validate and normalize aggregation period and
            # initialize use_calendar_periods flag
            agg_time_period = self.format_aggregation_time_period(
                agg_group['aggregation_period'])
            use_calendar_periods = agg_group.get('use_calendar_time_periods',
                                                 False)
            # 2. Validate aggregation details in config
            for data in agg_group['points']:
                if data['topic_name'] is None or self.topic_id_map[data[
                    'topic_name'].lower()] is None:
                    raise ValueError("Invalid topic name " + data[
                        'topic_name'])
                if not self.is_supported_aggregation(data['aggregation_type']):
                    raise ValueError("Invalid aggregation type {}"
                                     .format(data['aggregation_type']))
                if data.get('min_count', 0) < 0:
                    raise ValueError("Invalid min_count ({}). min_count "
                                     "should be "
                                     "an integer grater than 0".
                                     format(data['min_count']))
                self.create_aggregate_store(data['aggregation_type'],
                                            agg_time_period)
            # 3. Call parent method to set up periodic aggregation
            # collection calls
            frequency = self.compute_aggregation_frequency_seconds(
                agg_time_period,
                use_calendar_periods)
            self.core.periodic(frequency,
                               self._collect_aggregate_data,
                               [agg_time_period, use_calendar_periods,
                                agg_group['points']]
                               )


    def _collect_aggregate_data(self, *args):
        """
        Method that does the collection and computation of aggregate data based
        on raw date in historian's data table. This method is called
        periodically when you call setup_periodic_data_collection.
        @param args: List containing [aggregation_period, use_calendar_periods,
        points ] where
         1. aggregation_period = time period for which data needs to be
        collected and aggregated
         2. use_calendar_periods = flag that indicates if time period should be
        aligned to calendar times
         3. points = list of points for which aggregate data needs to be
         collected. Each element in the list is a dictionary containing
         topic_name, aggregation_type(ex. sum, avg etc.), and min_count(
         minimum number of raw data to be present within the given time
         period for the aggregate to be computed. If count is less
         than minimum no aggregate is computed for that time period)
        """

        period = args[0]
        use_calendar = args[1]
        points = args[2]

        _log.debug("Time period passed as arg  {} ".format(period))

        end_time, start_time = self.compute_aggregation_timeslice(
            period, use_calendar)

        _log.debug("After  compute period = {} start_time {} end_time {} ".
                   format(period, start_time, end_time))
        for data in points:
            topic_id = self.topic_id_map[data['topic_name'].lower()]
            agg_value, count = self.collect_aggregate(
                topic_id,
                data['aggregation_type'],
                start_time,
                end_time)
            if count == 0:
                _log.warn("No records found for topic {topic} "
                          "between {start_time} and {end_time}".
                          format(topic=data['topic_name'],
                                 start_time=start_time,
                                 end_time=end_time))
            elif count < data.get('min_count', 0):
                _log.warn(
                    "Skipping recording of aggregate data for {topic} "
                    "between {start_time} and {end_time} as number of "
                    "records is less than minimum allowed("
                    "{count})".format(topic=data['topic_name'],
                                      start_time=start_time,
                                      end_time=end_time,
                                      count=data.get('min_count', 0)))
            else:
                self.insert_aggregate(data['aggregation_type'],
                                      period,
                                      end_time,
                                      topic_id,
                                      agg_value)

    @abstractmethod
    def get_topic_map(self):
        """
        Query the topics table and create a map of topic name to topic id.
        This should be done as part of init
        @return:
        """
        pass

    @abstractmethod
    def create_aggregate_store(self, param, agg_time_period):
        pass

    @abstractmethod
    def collect_aggregate(self, topic_id, agg_type, start_time, end_time):
        pass

    @abstractmethod
    def insert_aggregate(self, agg_type, period, end_time, topic_id, value):
        pass

    @abstractmethod
    def is_supported_aggregation(self,agg_type):
        pass

    # Utility methods

    def format_aggregation_time_period(self, time_period):
        """
        Validates and normalizes aggregation time period. For example,
        if aggregation time period is given as 48h it will get converted
        into 2d
        @param time_period: time period string to be validated and normalized
        @return: normalized time period
        """
        try:
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
                "or M (minutes, hours, days, weeks, months".format(unit,
                                                                   time_period))
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

    def compute_aggregation_frequency_seconds(self, agg_period,
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

    def compute_aggregation_timeslice(self, agg_period,
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

