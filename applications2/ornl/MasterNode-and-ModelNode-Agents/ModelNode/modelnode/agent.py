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
import time
import json
import random
import uuid

import gevent
from zmq.utils import jsonapi

from volttron.platform.vip.agent import *
from volttron.platform.agent.base_historian import BaseHistorian
from volttron.platform.agent import utils
from volttron.platform.messaging import topics, headers as headers_mod

utils.setup_logging()
Log = logging.getLogger(__name__)

def enum(**enums):
    return type('Enum', (), enums)

class ModelNode(Agent):
    def __init__(self, config_path, **kwargs):
        super(ModelNode, self).__init__(**kwargs)
        self.Config = utils.load_config(config_path)
        self.AgentStatesEnum = enum(
            OFF = 0,
            HEATING_STAGE_ONE =  6,
            HEATING_STAGE_TWO =  3,
            COOLING_STAGE_ONE = -3,
            COOLING_STAGE_TWO = -6
        )
        self.initTimeStamp = time.time()

    @Core.receiver('onsetup')
    def setup(self, sender, **kwargs):
        self.agentID  = str(uuid.uuid4())
        self.setPoint = self.Config["setPoint"]
        self.modelNodePlatform = self.Config["modelnodeplatform"]

        # generate initial room temperature +- 2 degrees from setpoint
        self.x0  = self.setPoint + numpy.random.randn()
        # set initial state
        # Note that for the purposes of this experiment, only the cooling condition is used.
        if self.x0 > self.setPoint:
            self.u0 = -3
            self.SetCool(self.AgentStatesEnum.COOLING_STAGE_ONE)
        else:
            self.u0 = 0
            self.SetOff()

        
    @Core.receiver('onstart')
    def startup(self, sender, **kwargs):
        self.RegisterWithMasterNode()

    def RegisterWithMasterNode(self):
        msg = {}
        msg['ID'] = self.agentID
        msg['xref'] = self.setPoint
        msg['x0'] = self.x0
        msg['platform'] = self.modelNodePlatform

        headers = {headers_mod.FROM: self.agentID}
#         headers[headers_mod.CONTENT_TYPE] = headers_mod.CONTENT_TYPE.JSON
#         self.publish( topics.BUILDING_SEND(campus='ORNL', building='masternode',
#                                            topic='modelnode/register'),
#                       headers, json.dumps(msg) )
#         
        self.vip.pubsub.publish(
            'pubsub', topic='modelnode/register', headers=headers, message=msg)

    def SetOff(self):
        self.agentState = self.AgentStatesEnum.OFF


    def SetCool(self, stage):
        if stage == self.AgentStatesEnum.COOLING_STAGE_ONE:
            self.agentState = self.AgentStatesEnum.COOLING_STAGE_ONE
        elif stage == self.AgentStatesEnum.COOLING_STAGE_TWO:
            self.agentState = self.AgentStatesEnum.COOLING_STAGE_TWO
        else:
            Log.error(self, "Invalid cooling command/argument")
            

    def SetHeat(self, stage):
        if stage == self.AgentStatesEnum.HEATING_STAGE_ONE:
            self.agentState = self.AgentStatesEnum.HEATING_STAGE_ONE
        elif stage == self.AgentStatesEnum.HEATING_STAGE_TWO:
            self.agentState = self.AgentStatesEnum.HEATING_STAGE_TWO
        else:
            Log.error(self, "Invalid heating command/argument")

    # every 2 minutes??
    @Core.periodic(120)
    def HeartBeat(self):
        msg = {}
        msg['ID'] = self.agentID
        msg['xref'] = self.setPoint
        # Ideally, this will contain current temperature of the bldg/zone
        # In this experiment, the Master Node calculates this solving the ODE
        headers = {headers_mod.FROM: self.agentID}
#         headers[headers_mod.CONTENT_TYPE] = headers_mod.CONTENT_TYPE.JSON
#         self.publish( topics.BUILDING_SEND(campus='ORNL', building='masternode',
#                                             topic='modelnode/channels'),
#                       headers, json.dumps(msg) )

        self.vip.pubsub.publish(
            'pubsub', topic='modelnode/channels', headers=headers, message=msg)


    @PubSub.subscribe('pubsub',"masternode/command")
    def ProcessIncomingMessage(self, peer, sender, bus,  topic, headers, message):
        msg = message
        if msg['ID'] == self.agentID:
            value = msg['action']
            if value == 0:
                self.SetOff()
                Log.info("OFF")
            elif value == -3:
                self.SetCool(self.AgentStatesEnum.COOLING_STAGE_ONE)
                Log.info("COOL STAGE 1")
            elif value == -6:
                self.SetCool(self.AgentStatesEnum.COOLING_STAGE_TWO)
                Log.info("COOL STAGE 2")
            else:
                Log.error("Invalid command received")
            # Note that the heating condition is not considered here

def main(argv=sys.argv):
    try:
        utils.vip_main(ModelNode)
    except Exception as e:
        Log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass


