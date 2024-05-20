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
        self.configured = False
        self.last_std_dev_time = get_aware_utc_now()

        self.default_config = {
            "file_path": "volttron.log",
            "analysis_interval_sec": 60,
            "publish_topic": "platform/log_statistics",
            "historian_topic": "analysis/log_statistics",
            "unit": "bytes"
        }
        if config_path:
            self.default_config.update(utils.load_config(config_path))
        self.vip.config.set_default("config", self.default_config)
        self.vip.config.subscribe(self.configure_main, actions=["NEW", "UPDATE"], pattern="config")

    def configure_main(self, config_name, action, contents):
        config = self.default_config.copy()
        config.update(contents)
        self.configured = True
        if action == "NEW" or "UPDATE":
            self.reset_parameters(config)
            _log.info("Starting " + self.__class__.__name__ + " agent")
            self.publish_analysis()

    def reset_parameters(self, config=None):
        self.analysis_interval_sec = config["analysis_interval_sec"]
        self.file_path = config["file_path"]
        self.publish_topic = config["publish_topic"]
        self.historian_topic = config["historian_topic"]
        self.unit = config["unit"]
        self.size_delta_list = []
        self.file_start_size = None
        self.prev_file_size = None
        self._scheduled_event = None
        if self.configured:
            self.publish_analysis()

    def publish_analysis(self):
        """
        Publishes file's size increment in previous time interval (60 minutes) with timestamp.
        Also publishes standard deviation of file's hourly size differences every 24 hour.
        """
        if not hasattr(self, '_scheduled_event'):
            # The settings haven't been initialized, so skip the rest of the method
            return

        if self._scheduled_event is not None:
            self._scheduled_event.cancel()

        if self.prev_file_size is None:
            self.prev_file_size = self.get_file_size()
            _log.debug(f"init_file_size = {self.convert_bytes(self.prev_file_size, self.unit)} {self.unit}")
        else:
            # read file size
            curr_file_size = self.get_file_size()

            # calculate size delta
            size_delta = curr_file_size - self.prev_file_size
            size_delta = self.convert_bytes(size_delta, self.unit)

            self.prev_file_size = curr_file_size

            self.size_delta_list.append(size_delta)

            headers = {'Date': datetime.datetime.utcnow().isoformat() + 'Z'}

            publish_message = {'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
                               'log_size_delta': size_delta}
            historian_message = [{
                "log_size_delta ": size_delta
            }, {
                "log_size_delta ": {
                    'units': f'{self.unit}',
                    'tz': 'UTC',
                    'type': 'float'
                }
            }]

            now = get_aware_utc_now()
            hours_since_last_std_dev = (now - self.last_std_dev_time).total_seconds() / 3600

            if hours_since_last_std_dev >= 24:
                if self.size_delta_list:  # make sure it has something in it
                    if len(self.size_delta_list) >= 2:  # make sure it has more than two items
                        mean = statistics.mean(self.size_delta_list)
                        standard_deviation = statistics.stdev(self.size_delta_list)

                        publish_message['log_mean'] = mean
                        print(f"Calculated mean: {mean}")
                        publish_message['log_std_dev'] = standard_deviation

                        historian_message[0]['log_mean'] = mean
                        historian_message[0]['log_std_dev'] = standard_deviation

                        historian_message[1]['log_mean'] = {'units': f'{self.unit}', 'tz': 'UTC', 'type': 'float'}
                        historian_message[1]['log_std_dev'] = {'units': f'{self.unit}', 'tz': 'UTC',
                                                               'type': 'float'}

                    else:
                        _log.info("Not enough data points to calculate standard deviation")

                else:
                    _log.info("Not enough data points to calculate mean and standard deviation")

                # Reset time
                self.last_std_dev_time = now

                self.size_delta_list = []

                _log.debug(f'publishing message {historian_message}'
                           f' with header {headers}'
                           f' on historian topic {self.historian_topic}')
                self.vip.pubsub.publish(peer="pubsub",
                                        topic=self.historian_topic,
                                        headers=headers,
                                        message=historian_message)

            _log.debug(f'publishing message {publish_message} {self.unit} on topic {self.publish_topic}')
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

    def convert_bytes(self, size, unit):
        """
        Converts size from bytes to the specified unit
        """
        unit = unit.lower()
        if unit == 'kb':
            return size / 1024
        elif unit == 'mb':
            return size / 1024 ** 2
        elif unit == 'gb':
            return size / 1024 ** 3
        return size

def main(argv=sys.argv):
    """
    Main method called by the platform.
    """
    utils.vip_main(LogStatisticsAgent, identity='platform.log_statistics')

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
