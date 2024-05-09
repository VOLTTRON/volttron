# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
# }}}

import datetime
import logging
import os
import sys
import statistics

from volttron.platform.vip.agent import Agent, Core
from volttron.platform.agent import utils
from volttron.platform.agent.utils import get_aware_utc_now

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '1.0'


def log_statistics(config_path, **kwargs):
    """
    Load the LogStatisticsAgent agent configuration and returns and instance
    of the agent created using that configuration.
    :param config_path: Path to a configuration file.
    :type config_path: str
    :returns: LogStatisticsAgent agent instance
    :rtype: LogStatisticsAgent agent
    """
    config = utils.load_config(config_path)
    return LogStatisticsAgent(config, **kwargs)


class LogStatisticsAgent(Agent):
    """
    LogStatisticsAgent reads volttron.log file size every hour, compute the size delta from previous hour and publish
    the difference with timestamp. It also publishes standard deviation every 24 hours.
    :param config: Configuration dict
    :type config: dict
    Example configuration:
    .. code-block:: python
        {
        "file_path" : "/home/volttron/volttron.log",
        "analysis_interval_sec" : 60,
        "publish_topic" : "platform/log_statistics",
        "historian_topic" : "analysis/log_statistics"
        }
    """

    def __init__(self, config, **kwargs):
        super(LogStatisticsAgent, self).__init__(**kwargs)
        self.analysis_interval_sec = config["analysis_interval_sec"]
        self.file_path = config["file_path"]
        self.publish_topic = config["publish_topic"]
        self.historian_topic = config["historian_topic"]
        self.size_delta_list = []
        self.file_start_size = None
        self.prev_file_size = None
        self._scheduled_event = None

    @Core.receiver('onstart')
    def starting(self, sender, **kwargs):
        _log.info("Starting " + self.__class__.__name__ + " agent")
        self.publish_analysis()

    def publish_analysis(self):
        """
        Publishes file's size increment in previous time interval (60 minutes) with timestamp.
        Also publishes standard deviation of file's hourly size differences every 24 hour.
        """
        if self._scheduled_event is not None:
            self._scheduled_event.cancel()

        if self.prev_file_size is None:
            self.prev_file_size = self.get_file_size()
            _log.debug("init_file_size = {}".format(self.prev_file_size))
        else:
            # read file size
            curr_file_size = self.get_file_size()

            # calculate size delta
            size_delta = curr_file_size - self.prev_file_size
            self.prev_file_size = curr_file_size

            self.size_delta_list.append(size_delta)

            headers = {'Date': datetime.datetime.utcnow().isoformat() + 'Z'}

            publish_message = {'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
                               'log_size_delta': size_delta}
            historian_message = [{"log_size_delta ": size_delta},
                                 {"log_size_delta ": {'units': 'bytes', 'tz': 'UTC', 'type': 'float'}}]

            if len(self.size_delta_list) == 24:
                standard_deviation = statistics.stdev(self.size_delta_list)
                publish_message['log_std_dev'] = standard_deviation
                historian_message[0]['log_std_dev'] = standard_deviation
                historian_message[1]['log_std_dev'] = {'units': 'bytes', 'tz': 'UTC', 'type': 'float'}

                _log.debug('publishing message {} with header {} on historian topic {}'
                           .format(historian_message, headers, self.historian_topic))
                self.vip.pubsub.publish(peer="pubsub", topic=self.historian_topic, headers=headers,
                                        message=historian_message)

                self.size_delta_list = []

            _log.debug('publishing message {} on topic {}'.format(publish_message, self.publish_topic))
            self.vip.pubsub.publish(peer="pubsub", topic=self.publish_topic, message=publish_message)

        _log.debug('Scheduling next periodic call')
        now = get_aware_utc_now()
        next_update_time = now + datetime.timedelta(seconds=self.analysis_interval_sec)

        self._scheduled_event = self.core.schedule(next_update_time, self.publish_analysis)

    def get_file_size(self):
        try:
            return os.path.getsize(self.file_path)
        except OSError as e:
            _log.error(e)


def main(argv=sys.argv):
    """
    Main method called by the platform.
    """
    utils.vip_main(log_statistics, identity='platform.logstatisticsagent')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
