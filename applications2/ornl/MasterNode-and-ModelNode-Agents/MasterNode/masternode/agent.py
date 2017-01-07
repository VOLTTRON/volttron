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
import os
import os.path as p
import time
import json

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

class MasterNode(Agent):
    def __init__(self, config_path, **kwargs):
        super(MasterNode, self).__init__(**kwargs)
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
        self.agentID = 'masternode'
#         super(MasterNode, self).setup()
        self.Bld = self.Config["numberOfBuildings"]
        self.modelNodes = []
        self.modelNodesPlatform = []
        self.x0 = []
        self.xref = []
        # values from state space model; after discretization
        self.Ad = 0.99984
        self.Bd = 0.2564993
        self.Cd = 0.0019237
        self.c = 1

        self.Nsim = 144

        print "DIRECTORY :::", os.path.abspath(os.curdir)
        base_dir = p.abspath(p.dirname(__file__))
        numpy_file = p.join(base_dir,self.Config['data_file'])
        u_file = p.join(base_dir,self.Config['u_file'])
        d1_file = p.join(base_dir,self.Config['d1_file'])
        # read regulation signal and downsample to 10 mins
        Sig = numpy.loadtxt(open(numpy_file,"rb"),delimiter=",",skiprows=1)

        # downsample, 150 steps is 10 mins in this file
        self.Reg = []
        for i in range(0, 21601, 150):
            self.Reg.append(Sig[i, 0])

        # load outside air temp, u and d1 variables
        self.u = numpy.loadtxt(open(u_file,"rb"),delimiter=",",skiprows=0)
        self.d1 = numpy.loadtxt(open(d1_file,"rb"),delimiter=",",skiprows=0)

        # Scaling regulation signal to number of expected registered buildings
        self.Reg = numpy.multiply(self.Bld, self.Reg)

        self.additionalInit = False

        self.i = 0


    @PubSub.subscribe('pubsub',"modelnode/register")
    def ProcessIncomingMessage(self, peer, sender, bus,  topic, headers, message):
        msg = message
        ID = msg['ID']
        x0 = msg['x0']
        xref = msg['xref']
        platform = msg['platform']
        self.modelNodes.append(ID)
        self.modelNodesPlatform.append(platform)
        self.x0.append(x0)
        self.xref.append(xref)
        Log.info( " REGISTER REQUEST ::::::::::::::::::::::::::::::::: " + ID )

    # every 10 mins
    @Core.periodic(2)
    def RunControl(self):
        if len(self.modelNodes) != self.Bld:
            Log.info("Number of buildings registered with Master node is "
                     + str(len(self.modelNodes)) + ", MasterNode configured for " + str(self.Bld) + " yet")
            return

        if not self.additionalInit:
            self.X = numpy.zeros((self.Bld, self.Nsim))
            self.X[:,0] = self.x0
            self.X_T = numpy.zeros((self.Bld, self.Nsim))
            self.X_T[:,0] = self.x0
            self.u0 = numpy.zeros(self.Bld)
            for j in range(0, self.Bld):
                if self.x0[j] > self.xref[j]:
                    self.u0[j] = self.AgentStatesEnum.COOLING_STAGE_ONE
                else:
                    self.u0[j] = self.AgentStatesEnum.OFF
            self.U = numpy.zeros((self.Bld, self.Nsim))
            self.U[:, 0] = self.u0

            self.additionalInit = True

        # control strategy
        #for i in range(1, self.Nsim): # had to make this p from p+1
        i = self.i
        Log.info( "ITERATION ::::::::::::::::::::::::::::::::: " + str(i) )

        for j in range(0, self.Bld):
            self.X[j, i] = self.Ad*self.X_T[j,i-1] + self.Bd*self.U[j,i-1]  #% ODE - state eqn
            self.X_T[j,i] = self.X[j,i] + self.Cd*self.d1[i-1]  #% ODE in state space format - measurement eq
            print i, j
            print self.X.shape, self.X_T.shape, len(self.xref)
            if self.X_T[j,i] >= self.xref[j] + 1:
                self.U[j,i] = self.AgentStatesEnum.COOLING_STAGE_ONE # % decision for bldg j
            elif self.X_T[j,i] <= self.xref[j] - 0.5:
                self.U[j,i] = self.AgentStatesEnum.OFF # % decision for bldg j
            else:
                self.U[j,i] = self.U[j,i-1] # % decision for bldg j; stay the same

        # compute deviations frpm set pt and sort desc
        Dev = self.X_T[:,i] - self.xref[j]
        # sort desc
        #Dev.sort()
        #Dev = Dev[::-1] # reverses the array to desc
        # insted of above 2 lines, use argsort bcoz we need the indices pointing to which buliding to commmand

        # Ordered by lowest temp difference
        OrderAsc = numpy.argsort(Dev)
        # reverse asc order to get desc order
        # ordered by highest temp ddiffrence
        OrderDesc = OrderAsc[::-1]

        # no of buildings reqd to satisfy reg signal,
        # use prev step to get next step.
        # bcoz bldgs go up or down in 3 kw increments, divide by 3 to get no of bldgs
        ReqBld = int(abs(round(self.Reg[i-1]/3.0)))
        Log.info("No of required bldgs: " +str(ReqBld) + " ! = regulation need of: " + str(self.Reg[i-1]))


        count = 0
        if self.Reg[i-1] > 0:
            # increase power consumption starting with highest temp difference
            for k in range(0, self.Bld):
                if self.U[OrderDesc[k],i-1] == self.AgentStatesEnum.OFF:
                    self.U[OrderDesc[k],i] = self.AgentStatesEnum.COOLING_STAGE_ONE
                    count = count + 1
                elif self.U[OrderDesc[k],i-1] == self.AgentStatesEnum.COOLING_STAGE_ONE:
                    self.U[OrderDesc[k],i] = self.AgentStatesEnum.COOLING_STAGE_TWO
                    count = count + 1
                if count >= ReqBld:
                    break

        if self.Reg[i-1] < 0:
            # decrease power consumption, aka switch off equipment, starting with lowest temp difference for comfort
            for k in range(0, ReqBld):
                if self.U[OrderAsc[k],i-1] == self.AgentStatesEnum.COOLING_STAGE_ONE:
                    self.U[OrderAsc[k],i] = self.AgentStatesEnum.OFF
                    count = count + 1
                elif self.U[OrderAsc[k],i-1] == self.AgentStatesEnum.COOLING_STAGE_TWO:
                    self.U[OrderAsc[k],i] = self.AgentStatesEnum.COOLING_STAGE_ONE
                    count = count + 1
                if count >= ReqBld:
                    break
        for j in range(0, self.Bld):
            msg = {}
            msg['ID'] = self.modelNodes[j]
            msg['action'] = self.U[j,i]
            headers = {headers_mod.FROM: self.agentID}
#             headers[headers_mod.CONTENT_TYPE] = headers_mod.CONTENT_TYPE.JSON
#             self.publish( topics.BUILDING_SEND(campus='ORNL', 
#                                                building=self.modelNodesPlatform[j], 
#                                                topic='masternode/command'),
#                       headers, json.dumps(msg) )
            self.vip.pubsub.publish(
            'pubsub', topic='masternode/command', headers=headers, message=msg)

        Log.info( numpy.array_str(self.U[:,i]) )
        self.i = self.i + 1
        if self.i == self.Nsim:
            self.i = 0
            self.additionalInit = False

def main(argv=sys.argv):
    try:
        utils.vip_main(MasterNode)
    except Exception as e:
        Log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
