# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2015, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
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

#}}}

import logging
import sys
import uuid

from volttron.platform.vip.agent import Agent, Core, PubSub, RPC, compat
from volttron.platform.agent import utils


utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '3.5'


def anomalydetection_agent(config_path, **kwargs):
    config = utils.load_config(config_path)
    identity = config.get('identity', 'anomalydetection')
    kwargs.pop('identity', None)

    class AnomalyDetectionAgent(Agent):
        '''Listens to specified topics and publishes alerts when anomalies are
        detected.
        '''

        def __init__(self, **kwargs):
            super(AnomalyDetectionAgent, self).__init__(**kwargs)
            self._topics = {}

        @RPC.export
        def watch_max(self, prefix, max_value):
            alert_topic = '{}'.format(uuid.uuid4())

            def callback(peer, sender, bus, topic, headers, message):
                if message > max_value:
                    msg = 'Value from {} ({}) passed threshold ({})'.format(
                            topic, message, max_value)
                    self.vip.pubsub.publish('pubsub', alert_topic, message=msg)

            self.vip.pubsub.subscribe('pubsub', prefix, callback)
            return alert_topic

        @RPC.export
        def unwatch(self, alert_topic):
            self.vip.pubsub.unsubscribe('pubsub', alert_topic, callback=None)

    AnomalyDetectionAgent.__name__ = 'AnomalyDetectionAgent'
    return AnomalyDetectionAgent(identity=identity)


def main(argv=sys.argv):
    '''Main method called by the platform.'''
    utils.vip_main(anomalydetection_agent)

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
