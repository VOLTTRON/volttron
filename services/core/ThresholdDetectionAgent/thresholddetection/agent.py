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

import logging
import sys
import uuid

from volttron.platform.vip.agent import Agent, Core, PubSub, RPC, compat
from volttron.platform.agent import utils
from volttron.platform.messaging.health import Status, STATUS_BAD

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '3.5'


def thresholddetection_agent(config_path, **kwargs):
    """Load configuration for ThresholdDetectionAgent

    :param config_path: Path to a configuration file.

    :type config_path: str
    :returns: ThresholdDetectionAgent instance
    :rtype: ThresholdDetectionAgent
    """
    config = utils.load_config(config_path)
    vip_identity = 'platform.thresholddetection'
    kwargs.pop('identity', None)
    return ThresholdDetectionAgent(config, identity=vip_identity)


class ThresholdDetectionAgent(Agent):
    """
    Listen to topics and publish alerts when thresholds are passed.

    The agent's configuration specifies which topics to watch, the
    topic's threshold, and the message to send in an alert. Topics
    in the `watch_max` list trigger alerts when the published data
    are greater than the specified threshold. Topics in the
    `watch_min` list trigger alerts when the published data are
    less than the specified threshold. Non-numberic data will be
    ignored. Alerts are published to alert/TOPIC where TOPIC is the
    watched topic.

    Example configuration:

    .. code-block:: python

        {
          "watch_max": [
            {
              "topic": "datalogger/log/platform/cpu_percent",
              "threshold": 99,
              "message": "CPU ({topic}) exceeded {threshold} percent",
              "enabled": true
            }
          ]
          "watch_min": [
            {
              "topic": "some/temperature/topic",
              "threshold": 0,
              "message": "Temperature is below {threshold}",
              "enabled": true
            }
          ]
        }

    """
    def __init__(self, config, **kwargs):
        self.config = config
        super(ThresholdDetectionAgent, self).__init__(**kwargs)

    @Core.receiver('onstart')
    def start(self, sender, **kwargs):

        def is_number(x):
            try:
                float(x)
                return True
            except ValueError:
                return False

        def generate_callback(message, threshold, comparator):
            """generate callback function for pubsub.subscribe"""
            def callback(peer, sender, bus, topic, headers, data):
                if is_number(data):
                    if comparator(data, threshold):
                        alert_message = '{} ({} published {})\n'.format(
                            message, topic, data)
                        self.alert(alert_message, topic)
            return callback

        comparators = {'watch_max': lambda x, y: x > y,
                       'watch_min': lambda x, y: x < y}

        for key, comparator in comparators.iteritems():
            for item in self.config.get(key, []):
                if item.get('enabled', True):
                    # replaces keywords ({topic}, {threshold})
                    # with values in the message:
                    msg = item['message'].format(**item)
                    callback = generate_callback(
                        msg, item['threshold'], comparator)
                    self.vip.pubsub.subscribe(
                        'pubsub', item['topic'], callback)

    def alert(self, message, topic):
        """
        Raise alert for the given topic

        :param message: Message to include in alert
        :param topic: PUB/SUB topic that caused alert
        :type message: str
        :type topic: str
        """
        status = Status.build(STATUS_BAD, message)
        self.vip.health.send_alert(topic, status)


def main(argv=sys.argv):
    '''Main method called by the platform.'''
    utils.vip_main(thresholddetection_agent)

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
