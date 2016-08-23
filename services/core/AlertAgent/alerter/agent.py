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

from volttron.platform.vip.agent import Agent, Core
from volttron.platform.agent import utils
from volttron.platform.messaging.health import Status, STATUS_BAD

utils.setup_logging()
_log = logging.getLogger(__name__)

__version__ = '0.1'


class AlertAgent(Agent):
    def __init__(self, config_path, **kwargs):
        super(AlertAgent, self).__init__(**kwargs)
        config = utils.load_config(config_path)
        self.wait_time = {}
        self.topic_ttl = {}

        for topic, seconds in config.iteritems():
            self.wait_time[topic] = seconds
            self.topic_ttl[topic] = seconds
            _log.debug("Expecting {} every {} seconds"
                       .format(topic, seconds))

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        for device in self.wait_time.iterkeys():
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=device,
                                      callback=self.reset_time)

    def reset_time(self, peer, sender, bus, topic, headers, message):
        try:
            self.topic_ttl[topic] = self.wait_time[topic]
            _log.debug("Resetting timeout for {}".format(topic))
        except KeyError:
            pass

    @Core.periodic(1)
    def decrement_ttl(self):
        for topic in self.wait_time.iterkeys():
            self.topic_ttl[topic] -= 1
            if self.topic_ttl[topic] <= 0:
                self.send_alert(topic)

    def send_alert(self, device):
        alert_key = "Timeout:{}".format(device)
        context = "{} not published within time limit".format(device)
        status = Status.build(STATUS_BAD, context=context)
        self.vip.health.send_alert(alert_key, status)


def main():
    utils.vip_main(AlertAgent)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
