# Copyright (c) 2014 Oak Ridge National Laboratory Permission is hereby granted, free of charge,
# to any person obtaining a copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sellcopies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.


import logging
import sys
import numpy
import json
import random
import uuid

import gevent
from zmq.utils import jsonapi

from volttron.platform.vip.agent import *
from volttron.platform.agent import utils
from volttron.platform.messaging import topics, headers as headers_mod

utils.setup_logging()
log = logging.getLogger(__name__)


class StateEnum(object):
    OFF = 0
    COOLING_STAGE_ONE = -3
    COOLING_STAGE_TWO = -6


class ModelNode(Agent):
    def __init__(self, config_path, **kwargs):
        super(ModelNode, self).__init__(**kwargs)
        config = utils.load_config(config_path)
        self.setPoint = config['setPoint']
        self.master_vip = config['master-vip-address']

    @Core.receiver('onsetup')
    def onsetup(self, sender, **kwargs):
        self.agentID  = str(uuid.uuid4())

        # generate initial room temperature +- 2 degrees from setpoint
        self.x0  = self.setPoint + numpy.random.randn()

        # set initial state
        # Note that for the purposes of this experiment, only the cooling condition is used.
        if self.x0 > self.setPoint:
            self._set_state(StateEnum.COOLING_STAGE_ONE)
        else:
            self._set_state(StateEnum.OFF)

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        message = {}
        message['ID'] = self.agentID
        message['xref'] = self.setPoint
        message['x0'] = self.x0

        agent = Agent(address=self.master_vip)
        event = gevent.event.Event()
        agent.core.onstart.connect(lambda *a, **kw: event.set(), event)
        gevent.spawn(agent.core.run)
        event.wait()

        agent.vip.rpc.call('masternode',
                        'register_modelnode',
                           message).get(timeout=2)

    def _set_state(self, state):
        self.agentState = state

    @RPC.export
    def set_state(self, value):
        if value == 0:
            self._set_state(StateEnum.OFF)
            log.info('OFF')
        elif value == -3:
            self._set_state(StateEnum.COOLING_STAGE_ONE)
            log.info('COOL STAGE 1')
        elif value == -6:
            self._set_state(StateEnum.COOLING_STAGE_TWO)
            log.info('COOL STAGE 2')
        else:
            log.error('Invalid command received')


def main():
    utils.vip_main(ModelNode)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
