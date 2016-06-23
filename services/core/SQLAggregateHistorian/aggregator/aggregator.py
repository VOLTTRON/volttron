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
import sys

from volttron.platform.agent import utils
from volttron.platform.agent.base_aggregate_historian import AggregateHistorian
from volttron.platform.aggregation_utils import aggregation_utils
from volttron.platform.dbutils import sqlutils
from volttron.platform.vip.agent import Core

_log = logging.getLogger(__name__)
__version__ = '1.0'


class SQLAggregateHistorian(AggregateHistorian):
    """
    Agent to aggregate data in historian based on a specific time period.
    Different instance of this agent is needed to interact with different
    type of historians.
    """

    def __init__(self, config_path, **kwargs):
        """
        Validate configuration, create connection to platform historian, create
        aggregate tables if necessary and set up a periodic call to
        aggregate data
        :param config_path: configuration file path
        :param kwargs:
        """
        super(SQLAggregateHistorian, self).__init__(config_path, **kwargs)

        # 1. Check connection to db instantiate db functions class
        connection = self.config.get('connection', None)
        assert connection is not None
        database_type = connection.get('type', None)
        assert database_type is not None
        params = connection.get('params', None)
        assert params is not None

        dbfuncts_class = sqlutils.get_dbfuncts_class(database_type)
        tables_def = sqlutils.get_table_def(self.config)
        self.dbfuncts = dbfuncts_class(connection['params'], tables_def)

        # 2. load topic name and topic id.
        self.topic_id_map, name_map = self.dbfuncts.get_topic_map()

    @Core.receiver('onstart')
    def _on_start(self, sender, **kwargs):
        for agg_group in self.config['aggregations']:

            # 1. Validate and normalize aggregation period and
            # initialize use_calendar_periods flag
            agg_time_period = aggregation_utils.format_aggregation_time_period(
                agg_group['aggregation_period'])
            use_calendar_periods = agg_group.get('use_calendar_time_periods',
                                                 False)
            # 2. Validate aggregation details in config
            for data in agg_group['points']:
                if data['topic_name'] is None or self.topic_id_map[data[
                        'topic_name'].lower()] is None:
                    raise ValueError("Invalid topic name " + data[
                        'topic_name'])
                if data['aggregation_type'].upper() not in ['AVG', 'MIN',
                                                            'MAX',
                                                            'COUNT', 'SUM']:
                    raise ValueError("Invalid aggregation type {}"
                                     .format(data['aggregation_type']))
                if data.get('min_count', 0) < 0:
                    raise ValueError("Invalid min_count ({}). min_count "
                                     "should be "
                                     "an integer grater than 0".
                                     format(data['min_count']))
                self.dbfuncts.create_aggregate_store(data['aggregation_type'],
                                                     agg_time_period)
            # 3. Call parent method to set up periodic aggregation
            # collection calls
            self.setup_periodic_data_collection(agg_time_period,
                                                use_calendar_periods,
                                                agg_group['points'])

    def collect_aggregate_data(self, *args):
        period = args[0]
        use_calendar = args[1]
        points = args[2]

        _log.debug("Time period passed as arg  {} ".format(period))

        end_time, start_time = aggregation_utils.compute_aggregation_timeslice(
            period, use_calendar)

        _log.debug("After  compute period = {} start_time {} end_time {} ".
                   format(period, start_time, end_time))
        for data in points:
            topic_id = self.topic_id_map[data['topic_name'].lower()]
            agg, count = self.dbfuncts.collect_aggregate(
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
                _log.warn("Skipping recording of aggregate data for {topic} "
                          "between {start_time} and {end_time} as number of "
                          "records is less than minimum allowed("
                          "{count})".format(topic=data['topic_name'],
                                            start_time=start_time,
                                            end_time=end_time,
                                            count=data.get('min_count', 0)))
            else:
                self.dbfuncts.insert_aggregate(data['aggregation_type'],
                                               period,
                                               end_time,
                                               topic_id,
                                               agg)


def main(argv=sys.argv):
    """Main method called by the eggsecutable."""
    try:
        utils.vip_main(SQLAggregateHistorian)
    except Exception as e:
        _log.exception('unhandled exception' + e.message)


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
