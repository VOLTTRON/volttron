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
from volttron.platform import get_home

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '1.0'


def log_statistics(config_path: str, **kwargs):
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

    def __init__(self, config_path=None, **kwargs):
        super(LogStatisticsAgent, self).__init__(**kwargs)

        self.last_std_dev_time = get_aware_utc_now()

        self.default_config = {
            "file_path": f"volttron/volttron.log",
            "analysis_interval_sec": 60,
            "publish_topic": "platform/log_statistics",
            "historian_topic": "analysis/log_statistics"
        }
        self.vip.config.set_default("config", self.default_config)
        self.vip.config.subscribe(self.configure_main, actions=["NEW", "UPDATE"], pattern="config")

    def configure_main(self, config_name, action, contents):
        config = self.default_config.copy()
        config.update(contents)
        if action == "NEW" or "UPDATE":
            self.reset_parameters(config)

    def reset_parameters(self, config=None):
        self.analysis_interval_sec = config["analysis_interval_sec"]
        self.file_path = config["file_path"]
        self.publish_topic = config["publish_topic"]
        self.historian_topic = config["historian_topic"]
        self.size_delta_list = []
        self.file_start_size = None
        self.prev_file_size = None
        self._scheduled_event = None

        self.publish_analysis()

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

            publish_message = {'timestamp': datetime.datetime.utcnow().isoformat() + 'Z', 'log_size_delta': size_delta}
            historian_message = [{
                "log_size_delta ": size_delta
            }, {
                "log_size_delta ": {
                    'units': 'bytes',
                    'tz': 'UTC',
                    'type': 'float'
                }
            }]

            now = get_aware_utc_now()
            hours_since_last_std_dev = (now - self.last_std_dev_time).total_seconds() / 3600

            if hours_since_last_std_dev >= 24:
                if self.size_delta_list:    # make sure it has something in it
                    if len(self.size_delta_list) >= 2:    # make sure it has more than two items
                        mean = statistics.mean(self.size_delta_list)
                        standard_deviation = statistics.stdev(self.size_delta_list)

                        publish_message['log_mean'] = mean
                        print(f"Calculated mean: {mean}")
                        publish_message['log_std_dev'] = standard_deviation

                        historian_message[0]['log_mean'] = mean
                        historian_message[0]['log_std_dev'] = standard_deviation

                        historian_message[1]['log_mean'] = {'units': 'bytes', 'tz': 'UTC', 'type': 'float'}
                        historian_message[1]['log_std_dev'] = {'units': 'bytes', 'tz': 'UTC', 'type': 'float'}

                    else:
                        _log.info("Not enough data points to calculate standard deviation")

                else:
                    _log.info("Not enough data points to calculate mean and standard deviation")

                # Reset time
                self.last_std_dev_time = now

                self.size_delta_list = []

                _log.debug('publishing message {} with header {} on historian topic {}'.format(
                    historian_message, headers, self.historian_topic))
                self.vip.pubsub.publish(peer="pubsub",
                                        topic=self.historian_topic,
                                        headers=headers,
                                        message=historian_message)

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
    utils.vip_main(log_statistics, identity='platform.log_statistics')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
