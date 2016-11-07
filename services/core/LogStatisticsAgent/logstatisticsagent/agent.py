# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

#}}}

import datetime
import logging
import os
import sys
import statistics

from volttron.platform.vip.agent import Agent, RPC, Core
from volttron.platform.agent import utils
from volttron.platform.agent.utils import get_aware_utc_now


utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '3.6'


def log_statistics(config_path, **kwargs):
    """Load the FileWatchPublisher agent configuration and returns and instance
        of the agent created using that configuration.

    :param config_path: Path to a configuration file.

    :type config_path: str
    :returns: LogStatisticsAgent agent instance
    :rtype: LogStatisticsAgent agent
    """
    config = utils.load_config(config_path)
    return LogStatisticsAgent(config, **kwargs)


class LogStatisticsAgent(Agent):
    """LogStatisticsAgent reads volttron.log file size every hour,
    compute the size delta from previous hour and publish the difference
    with timestamp. It also publishes standard deviation every 24 hours.


    :param config: Configuration dict
    :type config: dict

    Example configuration:

    .. code-block:: python

    {
        "analysis_interval" : 60
    }

    """
    def __init__(self, config, **kwargs):
        super(LogStatisticsAgent, self).__init__(**kwargs)
        self.analysis_interval = config["analysis_interval"]
        self.filepath = config["filepath"]
        self.topic = "platform/log/hourly_size_delta"
        self.size_delta_list = []
        self.file_start_size = None
        self.prev_file_size = None
        self._scheduled_event = None


    @Core.receiver('onstart')
    def starting(self, sender, **kwargs):
        _log.info("Starting "+self.__class__.__name__+" agent")
        self.publish_analysis()

    def publish_analysis(self):

        if self._scheduled_event is not None:
            self._scheduled_event.cancel()

        if self.prev_file_size is None:
            self.prev_file_size = self.get_file_size()
            _log.debug("init_file_size = {}".format(self.prev_file_size))
        else:
            # read file size
            curr_file_size = self.get_file_size()

            #calculate size delta
            size_delta = curr_file_size - self.prev_file_size
            self.prev_file_size = curr_file_size

            self.size_delta_list.append(size_delta)

            message = {'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
                       'size_delta' : size_delta}
            if len(self.size_delta_list) == 24:
                standard_deviation = statistics.stdev(self.size_delta_list)
                message['std_dev'] = standard_deviation
            _log.debug('publishing message {} on topic {}'.format(message, self.topic))
            self.vip.pubsub.publish(peer="pubsub", topic=self.topic,
                                    message=message)

        _log.debug('Scheduling next periodic call')
        now = get_aware_utc_now()
        next_update_time = now + datetime.timedelta(
            seconds=self.analysis_interval)

        self._scheduled_event = self.core.schedule(
            next_update_time, self.publish_analysis())

    def get_file_size(self):
        try:
            return os.path.getsize(self.filepath)
        except OSError as e:
            _log.error(e.message)

def main(argv=sys.argv):
    """Main method called by the platform."""
    utils.vip_main(log_statistics, identity='platform.logstatisticsagent')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass