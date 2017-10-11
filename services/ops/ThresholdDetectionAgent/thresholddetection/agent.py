# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2017, Battelle Memorial Institute
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

import logging
import sys
import uuid

from volttron.platform.vip.agent import Agent, Core, PubSub, RPC, compat
from volttron.platform.agent import utils
from volttron.platform.messaging.health import Status, STATUS_BAD

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '3.7'


def thresholddetection_agent(config_path, **kwargs):
    """Load configuration for ThresholdDetectionAgent

    :param config_path: Path to a configuration file.

    :type config_path: str
    :returns: ThresholdDetectionAgent instance
    :rtype: ThresholdDetectionAgent
    """
    config = utils.load_config(config_path)
    return ThresholdDetectionAgent(config, **kwargs)


class ThresholdDetectionAgent(Agent):
    """
    Listen to topics and publish alerts when thresholds are passed.

    The agent's configuration specifies which topics to watch, the
    topic's threshold, and the message to send in an alert. Topics
    can specify a maximum and minimum threshold. Non-numberic data
    will be ignored.

    Example configuration:

    .. code-block:: python

        {
            "datalogger/log/platfor/cpu_percent": {
                "threshold_max": 99,
            },
            "some/temperature/topic": {
                "threshold_min": 0,
            },
            "devices/some/device/topic/all": {
                "some_point": {
                    "threshold_max": 42,
                    "threshold_min": 0
                }
            }
        }

    """
    def __init__(self, config, **kwargs):
        super(ThresholdDetectionAgent, self).__init__(**kwargs)
        self.config_topics = {}

        self.vip.config.set_default("config", config)
        self.vip.config.subscribe(self._config_add, actions="NEW", pattern="config")
        self.vip.config.subscribe(self._config_del, actions="DELETE", pattern="config")
        self.vip.config.subscribe(self._config_mod, actions="UPDATE", pattern="config")

    def _config_add(self, config_name, action, contents):
        """
        Configstore callback

        Subscribes to configured topics with customized callbacks
        """
        self.config_topics[config_name] = set()
        for topic, values in contents.iteritems():
            self.config_topics[config_name].add(topic)
            _log.info("Subscribing to {}".format(topic))

            if topic.startswith("devices/") and topic.endswith("/all"):
                self._create_device_subscription(topic, values)
            else:
                self._create_standard_subscription(topic, values)

    def _create_device_subscription(self, topic, device_points):
        """
        Subscribe to points in a device's all publish and alert if
        values are out of range

        :param topic: All topic from a device scrape
        :type topic: str

        :param device_points: Dictionary of points to thresholds
        :type device_points: dict
        """
        for point, values in device_points.iteritems():
            threshold_max = values.get('threshold_max')
            threshold_min = values.get('threshold_min')

            def callback(peer, sender, bus, topic, headers, message):
                data = message[0].get(point)

                try:
                    float(data)
                except ValueError:
                    return

                if threshold_max is not None and data > threshold_max:
                    self._alert(topic, threshold_max, data, point=point)
                elif threshold_min is not None and data < threshold_min:
                    self._alert(topic, threshold_min, data, point=point)

            self.vip.pubsub.subscribe('pubsub', topic, callback)

    def _create_standard_subscription(self, topic, values):
        """
        Subscribe to a topic and alert if its message is out of range

        :param topic: All topic from a device scrape
        :type topic: str

        :param device_points: Dictionary of points to thresholds
        :type device_points: dict
        """
        threshold_max = values.get('threshold_max')
        threshold_min = values.get('threshold_min')

        def callback(peer, sender, bus, topic, headers, data):
            try:
                float(data)
            except ValueError:
                return

            if threshold_max is not None and data > threshold_max:
                self._alert(topic, threshold_max, data)
            elif threshold_min is not None and data < threshold_min:
                self._alert(topic, threshold_min, data)

        self.vip.pubsub.subscribe('pubsub', topic, callback)

    def _config_del(self, config_name, action, contents):
        """
        Configstore callback

        Unsubscribes from topics in a deleted configuration.
        """
        topics = self.config_topics.pop(config_name)
        for t in topics:
            _log.info("Unsubscribing from {}".format(t))
            self.vip.pubsub.unsubscribe(peer='pubsub',
                                        prefix=t,
                                        callback=None).get()

    def _config_mod(self, *args):
        """
        Configstore callback

        Unsubscribes and resubscribes to updated configuration.
        """
        self._config_del(*args)
        self._config_add(*args)

    def _alert(self, topic, threshold, data, point=''):
        """
        Raise alert for the given topic.

        :param topic: Topic that has published some threshold-exceeding value.
        :type topic: str

        :param threshold: Value that has been exceeded. Used in alert message.
        :type threshold: float

        :param data: Value that is out of range. Used in alert message.
        :type data: float

        :param point: Optional point name. Used in alert message.
        :type point: str
        """
        if point:
            point = '({})'.format(point)

        if threshold < data:
            custom = "above"
        else:
            custom = "below"

        message = "{topic}{point} value ({data})" \
                  "is {custom} acceptable limit ({threshold})"

        message = message.format(topic=topic,
                                 point=point,
                                 data=data,
                                 custom=custom,
                                 threshold=threshold)

        status = Status.build(STATUS_BAD, message)
        self.vip.health.send_alert(topic, status)


def main(argv=sys.argv):
    """Main method called by the platform."""
    utils.vip_main(thresholddetection_agent,
                   identity='platform.thresholddetection', 
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
