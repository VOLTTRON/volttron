# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
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
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}
import gevent
import random
import sys
import logging
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.agent.base_market_agent import MarketAgent
from volttron.platform.agent.base_market_agent.poly_line import PolyLine
from volttron.platform.agent.base_market_agent.point import Point
from volttron.platform.agent.base_market_agent.buy_sell import BUYER
from pnnl.models.firstorderzone import FirstOrderZone
import numpy as np

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"

def light_agent(config_path, **kwargs):
    """Parses the Electric Meter Agent configuration and returns an instance of
    the agent created using that configuation.

    :param config_path: Path to a configuation file.

    :type config_path: str
    :returns: Market Service Agent
    :rtype: MarketServiceAgent
    """   
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}

    if not config:
        _log.info("Using defaults for starting configuration.")

    market_name = config.get('market_name')
    k= config.get('k', 0)
    qmax= float(config.get('Pmax', 0))
    Pabsnom= float(config.get('Pabsnom', 0))        
    nonResponsive= config.get('nonResponsive', False)    
    agent_name= config.get('agent_name')
    subscribing_topic= config.get('subscribing_topic', '')
    verbose_logging= config.get('verbose_logging', True)
    return LightAgent(market_name,agent_name,k,qmax,Pabsnom,nonResponsive,verbose_logging,subscribing_topic, **kwargs)


class LightAgent(MarketAgent, FirstOrderZone):
    """
    The SampleElectricMeterAgent serves as a sample of an electric meter that
    sells electricity for a single building at a fixed price.
    """
    def __init__(self, market_name,agent_name,k,qmax,Pabsnom,nonResponsive,verbose_logging,subscribing_topic, **kwargs):
        super(LightAgent, self).__init__(verbose_logging, **kwargs)
        self.market_name = market_name
        self.agent_name = agent_name        
        self.k = k
        self.qmax = qmax
        self.Pabsnom=Pabsnom        
        self.nonResponsive = nonResponsive
        self.iniState()
        self.subscribing_topic=subscribing_topic
        self.join_market(self.market_name, BUYER, None, self.offer_callback, None, self.price_callback, self.error_callback)

    @Core.receiver('onstart')
    def setup(self, sender, **kwargs):
        _log.debug('Subscribing to '+'devices/CAMPUS/BUILDING1/AHU1/all')
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix='devices/CAMPUS/BUILDING1/AHU1/all',
                                  callback=self.updateState)

    def offer_callback(self, timestamp, market_name, buyer_seller):
        result,message=self.make_offer(market_name, buyer_seller, self.create_demand_curve())
        _log.debug("results of the make offer {}".format(result))
        if not result:
            _log.debug("the new lightingt (maintain{}".format(self.qMax))
            gevent.sleep(random.random())
            self.vip.rpc.call('platform.actuator','set_point', self.agent_name,self.subscribing_topic+'/'+self.agent_name,round(self.qNorm,2)).get(timeout=6)

    def create_demand_curve(self):
        self.demand_curve = PolyLine()
        pMin = 10
        pMax = 100

        if (self.hvacAvail > 0):
            self.demand_curve.add(Point(price=min(pMin, pMax),quantity=max(self.qMin, self.qMax)*self.Pabsnom))
            self.demand_curve.add(Point(price=max(pMin, pMax),quantity=min(self.qMin, self.qMax)*self.Pabsnom))
        else:
            self.demand_curve.add(Point(price=max(pMin, pMax), quantity=0))
            self.demand_curve.add(Point(price=min(pMin, pMax),quantity=0))
        return self.demand_curve

    def iniState(self):
        self.hvacAvail = 1
        self.pClear = None
        self.qMin = 0.7
        self.qMax = self.qmax
        self.qNorm=self.qMax
        self.qClear=self.qNorm
 

    def updateState(self, peer, sender, bus, topic, headers, message):
        '''Subscribe to device data from message bus
        '''
        _log.debug('Received one new dataset')
        info = message[0].copy()
        self.hvacAvail = info['SupplyFanStatus']
        if (self.hvacAvail > 0):
              self.qNorm=self.qMax  
        else:
              self.qNorm=0


    def updateSet(self):
        if self.pClear is not None and not self.nonResponsive and self.hvacAvail:
            self.qClear = self.clamp(self.demand_curve.x(self.pClear), self.qMax, self.qMin)
        else:
            self.qClear = 0
#        if self.qClear is None:
#            self.qClear = 0.

    def clamp(self, value, x1, x2):
        minValue = min(x1, x2)
        maxValue = max(x1, x2)
        return min(max(value, minValue), maxValue)        
                        
    def price_callback(self, timestamp, market_name, buyer_seller, price, quantity):
        _log.debug("the price is {}".format(price))
        self.pClear=price
        if self.pClear is not None: 
            self.updateSet()
            _log.debug("the new lightingt is {}".format(self.qClear))
            gevent.sleep(random.random())
            self.vip.rpc.call('platform.actuator','set_point', self.agent_name,self.subscribing_topic+'/'+self.agent_name,round(self.qClear,2)).get(timeout=5)


    def error_callback(self, timestamp, market_name, buyer_seller,  error_code, error_message, aux):
        _log.debug("the new lightingt is {}".format(self.qNorm))
        self.vip.rpc.call('platform.actuator','set_point', self.agent_name,self.subscribing_topic+'/'+self.agent_name,round(self.qNorm,2)).get(timeout=5)
        

    def ease(self, target, current, limit):
        return current - np.sign(current-target)*min(abs(current-target), abs(limit))        


def main():
    """Main method called to start the agent."""
    utils.vip_main(light_agent, version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
