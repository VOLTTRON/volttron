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
import os
import os.path as p

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


class MasterNode(Agent):
    def __init__(self, config_path, **kwargs):
        super(MasterNode, self).__init__(**kwargs)
        config = utils.load_config(config_path)
        self.model_nodes = []
        for address in config['model_node_addresses']:
            agent = Agent(address=address)
            event = gevent.event.Event()
            agent.core.onstart.connect(lambda *a, **kw: event.set(), event)
            gevent.spawn(agent.core.run)
            event.wait()
            self.model_nodes.append(agent)

        self.n_buildings = len(self.model_nodes)

        self.additionalInit = False

        self.iteration = 0
        self.registered_nodes = []
        self.Nsim = 144
        self.Reg = []
        self.x0 = []
        self.xref = []

        # values from state space model; after discretization
        self.Ad = 0.99984
        self.Bd = 0.2564993
        self.Cd = 0.0019237

        # read regulation signal and downsample to 10 mins
        # 150 steps is 10 mins in this file
        base_dir = p.abspath(p.dirname(__file__))
        numpy_file = p.join(base_dir, config['data_file'])
        sig = numpy.loadtxt(open(numpy_file,'rb'), delimiter=',', skiprows=1)
        for i in range(0, 21601, 150):
            self.Reg.append(sig[i, 0])

        # load outside air temp, u and d1 variables
        u_file = p.join(base_dir, config['u_file'])
        d1_file = p.join(base_dir, config['d1_file'])
        self.u = numpy.loadtxt(open(u_file, 'rb'), delimiter=',')
        self.d1 = numpy.loadtxt(open(d1_file, 'rb'), delimiter=',')

        # Scaling regulation signal to number of expected registered buildings
        self.Reg = numpy.multiply(self.n_buildings, self.Reg)

    @RPC.export
    def register_modelnode(self, message):
        ID = message['ID']
        x0 = message['x0']
        xref = message['xref']
        self.registered_nodes.append(ID)
        self.x0.append(x0)
        self.xref.append(xref)
        log.info( ' REGISTER REQUEST ::::::::::::::::::::::::::::::::: ' + ID )

    @Core.periodic(2)
    def RunControl(self):
        n_registered = len(self.registered_nodes)
        if n_registered != self.n_buildings:
            log.info('{} nodes registered, master configured for {}'.format(
                n_registered,
                self.n_buildings))
            return

        if not self.additionalInit:
            self.X = numpy.zeros((self.n_buildings, self.Nsim))
            self.X[:,0] = self.x0
            self.X_T = numpy.zeros((self.n_buildings, self.Nsim))
            self.X_T[:,0] = self.x0
            self.u0 = numpy.zeros(self.n_buildings)
            for j in range(0, self.n_buildings):
                if self.x0[j] > self.xref[j]:
                    self.u0[j] = StateEnum.COOLING_STAGE_ONE
                else:
                    self.u0[j] = StateEnum.OFF
            self.U = numpy.zeros((self.n_buildings, self.Nsim))
            self.U[:, 0] = self.u0

            self.additionalInit = True

        # control strategy
        log.info( 'ITERATION ::::::::::::::::::::::::::::::::: ' + str(self.iteration))
        i = self.iteration

        for j in range(0, self.n_buildings):
            #% ODE - state eqn
            self.X[j, i] = self.Ad * self.X_T[j, i - 1] + self.Bd * self.U[j, i - 1]

            #% ODE in state space format - measurement eq
            self.X_T[j, i] = self.X[j, i] + self.Cd * self.d1[i - 1]
            log.info('{} {} {}'.format(self.X.shape, self.X_T.shape, len(self.xref)))

            # decision for bldg j
            if self.X_T[j, i] >= self.xref[j] + 1:
                self.U[j, i] = StateEnum.COOLING_STAGE_ONE
            elif self.X_T[j, i] <= self.xref[j] - 0.5:
                self.U[j, i] = StateEnum.OFF
            else:
                # stay the same
                self.U[j, i] = self.U[j, i-1]

        # compute deviations frpm set pt and sort desc
        Dev = self.X_T[:,i] - self.xref[j]

        # Ordered by lowest temp difference
        OrderAsc = numpy.argsort(Dev)

        # reverse asc order to get desc order
        OrderDesc = OrderAsc[::-1]

        # no of buildings reqd to satisfy reg signal,
        # use prev step to get next step.
        # bcoz bldgs go up or down in 3 kw increments, divide by 3 to get no of bldgs
        ReqBld = int(abs(round(self.Reg[i-1] / 3.0)))
        log.info('No of required bldgs: {} ! = regulation need of: {}'.format(str(ReqBld),
                                                                              str(self.Reg[i-1])))

        count = 0
        if self.Reg[i-1] > 0:
            # increase power consumption starting with highest temp difference
            for k in range(0, self.n_buildings):
                if self.U[OrderDesc[k],i-1] == StateEnum.OFF:
                    self.U[OrderDesc[k],i] = StateEnum.COOLING_STAGE_ONE
                    count += 1
                elif self.U[OrderDesc[k],i-1] == StateEnum.COOLING_STAGE_ONE:
                    self.U[OrderDesc[k],i] = StateEnum.COOLING_STAGE_TWO
                    count += 1

                if count >= ReqBld:
                    break

        if self.Reg[i-1] < 0:
            # decrease power consumption, aka switch off equipment, starting with lowest temp difference for comfort
            for k in range(0, ReqBld):
                if self.U[OrderAsc[k], i-1] == StateEnum.COOLING_STAGE_ONE:
                    self.U[OrderAsc[k], i] = StateEnum.OFF
                    count += 1
                elif self.U[OrderAsc[k], i-1] == StateEnum.COOLING_STAGE_TWO:
                    self.U[OrderAsc[k], i] = StateEnum.COOLING_STAGE_ONE
                    count += 1

                if count >= ReqBld:
                    break

        for model in self.model_nodes:
            try:
                model.vip.rpc.call('modelnode', 'set_state', self.U[j, i]).get()
            except Exception as e:
                print e

        self.iteration += 1
        if self.iteration == self.Nsim:
            self.iteration = 0
            self.additionalInit = False


def main():
    utils.vip_main(MasterNode)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
