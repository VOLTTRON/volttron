# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of the United States Government. Neither the
# United States Government nor the United States Department of Energy, nor Battelle, nor any of their employees, nor any
# jurisdiction or organization that has cooperated in the development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product, process, or service by trade name,
# trademark, manufacturer, or otherwise does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or Battelle Memorial Institute. The views and opinions
# of authors expressed herein do not necessarily state or reflect those of the United States Government or any agency
# thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY under
# Contract DE-AC05-76RL01830
# }}}

from datetime import datetime
import os
import sys

import json
import gevent

from volttron.platform.messaging import headers as headers_mod
from volttron.platform.vip.agent import Agent, PubSub, Core
from volttron.platform.agent import utils

from settings import topic_prefixes_to_watch, heartbeat_period, agent_kwargs


class NodeRedSubscriber(Agent):

    def onmessage(self, peer, sender, bus, topic, headers, message):
        d = {'topic': topic,
             'headers': headers,
             'message': message}
        sys.stdout.write(json.dumps(d)+'\n')
        sys.stdout.flush()

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        for prefix in topic_prefixes_to_watch:
            self.vip.pubsub.subscribe(peer='pubsub', prefix=prefix, callback=self.onmessage).get(timeout=10)

    # Demonstrate periodic decorator and settings access
    @Core.periodic(heartbeat_period)
    def publish_heartbeat(self):
        now = datetime.utcnow().isoformat(' ') + 'Z'
        headers = {
            headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
            headers_mod.DATE: now,
        }
        result = self.vip.pubsub.publish('pubsub', 'heartbeat/NodeRedSubscriber', headers, now)
        result.get(timeout=10)


if  __name__ == '__main__':
    try:
        # If stdout is a pipe, re-open it line buffered
        if utils.isapipe(sys.stdout):
            # Hold a reference to the previous file object so it doesn't
            # get garbage collected and close the underlying descriptor.
            stdout = sys.stdout
            sys.stdout = os.fdopen(stdout.fileno(), 'w', 1)

        agent = NodeRedSubscriber(identity='NodeRedSubscriber', **agent_kwargs)
        task = gevent.spawn(agent.core.run)

        try:
            task.join()
        finally:
            task.kill()

    except KeyboardInterrupt:
        pass

