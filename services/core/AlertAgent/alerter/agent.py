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
# }}}

import logging
from datetime import datetime

from volttron.platform.vip.agent import Agent, Core, RPC
from volttron.platform.agent import utils
from volttron.platform.messaging.health import Status, STATUS_BAD
from volttron.platform.agent.known_identities import PLATFORM_ALERTER

utils.setup_logging()
_log = logging.getLogger(__name__)

__version__ = '0.3'


class AlertAgent(Agent):
    def __init__(self, config_path, **kwargs):
        super(AlertAgent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
        self.wait_time = {}
        self.topic_ttl = {}
        self.point_ttl = {}

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        config = self.config
        for topic in config.iterkeys():

            # Optional config option with a list of points that
            # might not be published.
            if type(config[topic]) is dict:
                point_config = config[topic]
                self.watch_device(topic,
                                  point_config["seconds"],
                                  point_config["points"])

            # Default config option
            else:
                timeout = config[topic]
                self.watch_topic(topic, timeout)

    @RPC.export
    def watch_topic(self, topic, timeout):
        """RPC method

        Listen for a topic to be published within a given
        number of seconds or send alerts.

        :param topic: Topic expected to be published.
        :type topic: str
        :param timeout: Seconds before an alert is sent.
        :type timeout: int
        """
        self.wait_time[topic] = timeout
        self.topic_ttl[topic] = timeout
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix=topic,
                                  callback=self.reset_time)
        _log.info("Expecting {} every {} seconds"
                   .format(topic, timeout))

    @RPC.export
    def watch_device(self, topic, timeout, points):
        """RPC method
        
        Watch a device's ALL topic and expect points. This
        method calls the watch topic method so both methods
        don't need to be called.

        :param topic: Topic expected to be published.
        :type topic: str
        :param timeout: Seconds before an alert is sent.
        :type timeout: int
        :param points: Points to expect in the publish message.
        :type points: [str]
        """
        self.point_ttl[topic] = {}

        for p in points:
            self.point_ttl[topic][p] = timeout

        self.watch_topic(topic, timeout)

    @RPC.export
    def ignore_topic(self, topic):
        """RPC method

        Remove a topic from agent's watch list. Alerts will no
        longer be sent if a topic stops being published.

        :param topic: Topic to remove from the watch list.
        :type topic: str
        """
        _log.info("Removing topic {} from watchlist".format(topic))

        self.vip.pubsub.unsubscribe(peer='pubsub',
                                    prefix=topic,
                                    callback=self.reset_time)
        self.point_ttl.pop(topic, None)
        self.topic_ttl.pop(topic, None)
        self.wait_time.pop(topic, None)

    def reset_time(self, peer, sender, bus, topic, headers, message):
        if topic not in self.wait_time:
            found = False
            # if topic isn't in wait time we need to figure out the
            # prefix topic so that we can determine the wait time
            for x in self.wait_time:
                # TODO: order the wait_time topics so furthest down the tree wins.
                if topic.startswith(x):
                    topic = x
                    found = True
                    break
            if not found:
                _log.debug("No configured topic prefix for topic {}".format(
                    topic)
                )
                return

        _log.debug("Resetting timeout for {}".format(topic))

        # Reset the standard topic timeout
        self.topic_ttl[topic] = self.wait_time[topic]

        # Reset timeouts on volatile points
        if topic in self.point_ttl:
            received_points = set(message[0].keys())
            expected_points = self.point_ttl[topic].keys()
            for point in expected_points:
                if point in received_points:
                    self.point_ttl[topic][point] = self.wait_time[topic]

    @Core.periodic(1)
    def decrement_ttl(self):
        for topic in self.wait_time.iterkeys():

            # Send an alert if a topic hasn't been seen
            self.topic_ttl[topic] -= 1
            if self.topic_ttl[topic] <= 0:
                self.send_alert(topic)
                self.topic_ttl[topic] = self.wait_time[topic]



            # Send an alert if a point hasn't been seen
            try:
                points = self.point_ttl[topic].keys()
                for p in points:
                    self.point_ttl[topic][p] -= 1
                    if self.point_ttl[topic][p] <= 0:
                        self.send_alert(topic, p)
                        self.point_ttl[topic][p] = self.wait_time[topic]
            except KeyError:
                pass

    def send_alert(self, device, point=None):
        if point is not None:
            alert_key = "Timeout:{}({})".format(device, point)
            context = "{}({}) not published within time limit".format(device, point)
        else:
            alert_key = "Timeout:{}".format(device)
            context = "{} not published within time limit".format(device)

        status = Status.build(STATUS_BAD, context=context)
        self.vip.health.send_alert(alert_key, status)


def main():
    utils.vip_main(AlertAgent, identity=PLATFORM_ALERTER)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
