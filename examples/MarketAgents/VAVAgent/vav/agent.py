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

import sys
import logging
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.agent.base_market_agent import MarketAgent
from volttron.platform.agent.base_market_agent.poly_line import PolyLine
from volttron.platform.agent.base_market_agent.point import Point
from volttron.platform.agent.base_market_agent.error_codes import NOT_FORMED, SHORT_OFFERS, BAD_STATE, NO_INTERSECT
from volttron.platform.agent.base_market_agent.buy_sell import BUYER
from pnnl.models.firstorderzone import FirstOrderZone
import numpy as np

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.01"

def vav_agent(config_path, **kwargs):
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
    x0= config.get('x0', 0)
    x1= config.get('x1', 0)
    x2= config.get('x2', 0)
    x3= config.get('x3', 0)
    x4= config.get('x4', 0)
    c0= config.get('c0', 0)
    c1= config.get('c1', 0)
    c2= config.get('c2', 0)
    c3= config.get('c3', 0)
    c4= config.get('c4', 0)	
    tMinAdj= config.get('tMin', 0)
    tMaxAdj= config.get('tMax', 0)
    mDotMin= config.get('mDotMin', 0)
    mDotMax= config.get('mDotMax', 0)
    tIn= config.get('tIn', 0)
    nonResponsive= config.get('nonResponsive', False)	
    agent_name= config.get('agent_name')
    subscribing_topic= config.get('subscribing_topic')	
    verbose_logging= config.get('verbose_logging', True)
    return VAVAgent(market_name,agent_name,x0,x1,x2,x3,x4,c0,c1,c2,c3,c4,tMinAdj,tMaxAdj,mDotMin,mDotMax,tIn,nonResponsive,verbose_logging,subscribing_topic, **kwargs)


class VAVAgent(MarketAgent, FirstOrderZone):
    """
    The SampleElectricMeterAgent serves as a sample of an electric meter that
    sells electricity for a single building at a fixed price.
    """
    def __init__(self, market_name,agent_name,x0,x1,x2,x3,x4,c0,c1,c2,c3,c4,tMinAdj,tMaxAdj,mDotMin,mDotMax,tIn,nonResponsive,verbose_logging,subscribing_topic, **kwargs):
        super(VAVAgent, self).__init__(verbose_logging, **kwargs)
        self.market_name = market_name
        self.agent_name = agent_name		
        self.x0 = x0
        self.x1 = x1
        self.x2 = x2
        self.x3 = x3
        self.x4 = x4
        self.c0 = c0
        self.c1 = c1
        self.c2 = c2
        self.c3 = c3
        self.c4 = c4
        self.tMinAdj=tMinAdj
        self.tMaxAdj=tMaxAdj
        self.tNomAdj=tIn
        self.tIn=tIn
        self.mDotMin=mDotMin
        self.mDotMax=mDotMax
        self.nonResponsive = nonResponsive
        self.iniState()
        self.subscribing_topic=subscribing_topic
        self.join_market(self.market_name, BUYER, None, self.offer_callback, None, self.price_callback, self.error_callback)
		
    @Core.receiver('onstart')
    def setup(self, sender, **kwargs):
        _log.debug('Subscribing to '+self.subscribing_topic)
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix=self.subscribing_topic,
                                  callback=self.updateState)
		
    def offer_callback(self, timestamp, market_name, buyer_seller):
        self.make_offer(market_name, buyer_seller, self.create_demand_curve())

    def create_demand_curve(self):
        self.demand_curve = PolyLine()		
        pMin = 10
        pMax = 100
        qMin = abs(self.getQMin())
        qMax = abs(self.getQMax())
        if (self.hvacAvail > 0):
            self.demand_curve.add(Point(price=max(pMin, pMax),quantity=min(qMin, qMax)))
            self.demand_curve.add(Point(price=min(pMin, pMax),quantity=max(qMin, qMax)))
        else:
            self.demand_curve.add(Point(price=max(pMin, pMax), quantity=0))
            self.demand_curve.add(Point(price=min(pMin, pMax),quantity=0))
        return self.demand_curve

    def iniState(self):
        self.hvacAvail = 1
        self.tSupHvac = 12.78
        self.tOut =32
        self.mDot = 1.0
        self.tSup = 12.78
        self.standby = 0
        self.occupied = 0
        self.tSet=22
        self.tDel=0.5
        self.tEase=0.25	
        self.qHvacSens = self.mDot*1006.*(self.tSup-self.tNomAdj)		
        self.qMin = min(0, self.mDotMin*1006.*(self.tSupHvac-self.tNomAdj))
        self.qMax = min(0, self.mDotMax*1006.*(self.tSupHvac-self.tNomAdj))
        self.pClear = None
        
		
    def updateState(self, peer, sender, bus, topic, headers, message):
	    '''Subscribe to device data from message bus
	    '''
	    _log.debug('Received one new dataset')
	    info = message[0].copy()
	    self.hvacAvail = info['SupplyFanStatus']
	    self.tSupHvac = info['DischargeAirTemperature']
	    self.tOut == info['OutdoorAirTemperature']
	    self.mDot = info['VAV'+self.agent_name+'_ZoneAirFlow']
	    self.tSup = info['VAV'+self.agent_name+'_ZoneDischargeAirTemperature']
	    self.tIn = info['VAV'+self.agent_name+'_ZoneTemperature']
	    self.qHvacSens = self.mDot*1006.*(self.tSup-self.tIn)		
	    self.qMin = min(0, self.mDotMin*1006.*(self.tSupHvac-self.tIn))
	    self.qMax = min(0, self.mDotMax*1006.*(self.tSupHvac-self.tIn))

    def updateTSet(self):
        if self.pClear is not None and not self.nonResponsive and self.hvacAvail:
            self.qClear = self.clamp(-self.demand_curve.y(self.pClear), self.qMax, self.qMin)
            self.tSet = self.clamp(self.getT(self.qClear), self.tMinAdj, self.tMaxAdj)
        else:
            self.tSet = self.clamp(self.ease(self.tNomAdj, self.tSet, self.tEase), self.tMinAdj, self.tMaxAdj)
            self.qClear = self.clamp(self.getQ(self.tSet), self.qMax, self.qMin)
        if self.qClear is None:
            self.qClear = 0.

		
    def getQMin(self):
        t = self.clamp(self.tSet+self.tDel, self.tMinAdj, self.tMaxAdj)
        q = self.clamp(self.getQ(t), self.qMax, self.qMin)
        return q


    def getQMax(self):
        t = self.clamp(self.tSet-self.tDel, self.tMinAdj, self.tMaxAdj)
        q = self.clamp(self.getQ(t), self.qMax, self.qMin)
        return q

    def clamp(self, value, x1, x2):
        minValue = min(x1, x2)
        maxValue = max(x1, x2)
        return min(max(value, minValue), maxValue)		
						
    def price_callback(self, timestamp, market_name, buyer_seller, price, quantity):
        _log.debug("the price is {}".format(price))
        self.pClear=price
        self.updateTSet()
        _log.debug("the new set point is {}".format(self.tSet))
        _log.debug("the set point is {}".format(self.subscribing_topic.replace('all','')+'VAV'+self.agent_name+'/ZoneCoolingTemperatureSetPoint'))
        self.vip.rpc.call('platform.actuator','set_point', self.agent_name,self.subscribing_topic.replace('all','')+'VAV'+self.agent_name+'/ZoneCoolingTemperatureSetPoint',self.tSet).get(timeout=5)
		
    def error_callback(self, timestamp, market_name, buyer_seller, error_code, error_message, aux):
        if error_code == NO_INTERSECT:
		      self.vip.rpc.call('platform.actuator','set_point', self.agent_name,self.subscribing_topic.replace('all','')+'VAV'+self.agent_name+'/ZoneCoolingTemperatureSetPoint',self.tNomAdj).get(timeout=5)
		
		
		

    def ease(self, target, current, limit):
        return current - np.sign(current-target)*min(abs(current-target), abs(limit))		
		
		
		

def main():
    """Main method called to start the agent."""
    utils.vip_main(vav_agent, version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
