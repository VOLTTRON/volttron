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

from volttron.platform.agent import utils
from volttron.platform.aggregation_utils import aggregation_utils
from volttron.platform.vip.agent import Agent

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
        self.config = utils.load_config(config_path)
        self._agent_id = self.config['agentid']

    def setup_periodic_data_collection(self, aggregation_period,
                                       use_calendar_periods,
                                       points):
        """
        Converts aggrgation time period into seconds and setups periodic
        call to collect_aggregate_data method
        @param aggregation_period:  aggregation time period
        @param use_calendar_periods: should aggregation time slices be
        aligned to calendar time period.
        @param points: List of points for which data should be collected.
        Each element in the list is a dictionary containing topic_name,
        aggregation_type(ex. sum, avg etc.), and min_count(minimum number of
        raw data to be present within the given time period for the
        aggregate to be computed
        """
        frequency = \
            aggregation_utils.compute_aggregation_frequency_seconds(
                aggregation_period,
                use_calendar_periods)
        self.core.periodic(frequency,
                           self.collect_aggregate_data,
                           [aggregation_period, use_calendar_periods, points]
                           )

    @abstractmethod
    def collect_aggregate_data(self, *args):
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
