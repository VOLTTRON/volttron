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

from volttron.platform.agent import utils
from volttron.platform.agent.base_aggregate_historian import AggregateHistorian
from volttron.platform.dbutils import sqlutils

_log = logging.getLogger(__name__)
__version__ = '1.0'


class SQLAggregateHistorian(AggregateHistorian):
    """
    Agent to aggregate data in historian based on a specific time period.
    This aggregate historian aggregates data collected by SQLHistorian.
    """

    def __init__(self, config_path, **kwargs):
        """
        Validate configuration, create connection to historian, create
        aggregate tables if necessary and set up a periodic call to
        aggregate data
        :param config_path: configuration file path
        :param kwargs:
        """
        self.dbfuncts_class = None
        super(SQLAggregateHistorian, self).__init__(config_path, **kwargs)

    def configure(self, config_name, action, config):
        if not config or not isinstance(config, dict):
            raise ValueError("Configuration should be a valid json")

        # 1. Check connection to db instantiate db functions class
        connection = config.get('connection', None)
        assert connection is not None
        database_type = connection.get('type', None)
        assert database_type is not None
        params = connection.get('params', None)
        assert params is not None

        class_name = sqlutils.get_dbfuncts_class(database_type)
        self.dbfuncts_class = class_name(connection['params'], None)
        self.dbfuncts_class.setup_aggregate_historian_tables(
            self.volttron_table_defs)
        super(SQLAggregateHistorian, self).configure(
            config_name, action, config)

    def get_topic_map(self):
        return self.dbfuncts_class.get_topic_map()

    def get_agg_topic_map(self):
        return self.dbfuncts_class.get_agg_topic_map()

    def find_topics_by_pattern(self, topic_pattern):
        return self.dbfuncts_class.find_topics_by_pattern(topic_pattern)

    def get_aggregation_list(self):
        if self.dbfuncts_class:
            return self.dbfuncts_class.get_aggregation_list()
        else:
            raise Exception("Please configure historian with a valid "
                            "configuration")


    def initialize_aggregate_store(self, aggregation_topic_name, agg_type,
                                   agg_time_period, topics_meta):
        _log.debug("aggregation_topic_name " + aggregation_topic_name)
        _log.debug("topics_meta {}".format(topics_meta))
        self.dbfuncts_class.create_aggregate_store(agg_type, agg_time_period)
        agg_id = self.dbfuncts_class.insert_agg_topic(aggregation_topic_name,
                                                      agg_type,
                                                      agg_time_period)
        self.dbfuncts_class.insert_agg_meta(agg_id[0], topics_meta)
        return agg_id[0]

    def update_aggregate_metadata(self, agg_id, aggregation_topic_name,
                                  topic_meta):
        _log.debug("aggregation_topic_name " + aggregation_topic_name)
        _log.debug("topic_meta {}".format(topic_meta))

        self.dbfuncts_class.update_agg_topic(agg_id, aggregation_topic_name)
        self.dbfuncts_class.insert_agg_meta(agg_id, topic_meta)

    def collect_aggregate(self, topic_ids, agg_type, start_time, end_time):
        return self.dbfuncts_class.collect_aggregate(
            topic_ids,
            agg_type,
            start_time,
            end_time)

    def insert_aggregate(self, topic_id, agg_type, period, end_time,
                         value, topic_ids):
        self.dbfuncts_class.insert_aggregate(topic_id,
                                             agg_type,
                                             period,
                                             end_time,
                                             value,
                                             topic_ids)


def main(argv=sys.argv):
    """Main method called by the eggsecutable."""
    try:
        utils.vip_main(SQLAggregateHistorian)
    except Exception as e:
        _log.exception('unhandled exception' + e.message)


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
