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

import sys
import logging
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.agent.base_market_agent import MarketAgent
from volttron.platform.agent.base_market_agent.poly_line import PolyLine
from volttron.platform.agent.base_market_agent.point import Point
from volttron.platform.agent.base_market_agent.buy_sell import BUYER
from pnnl.models.firstorderzone import FirstOrderZone

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
    except StandardError:
        config = {}

    if not config:
        _log.info("Using defaults for starting configuration.")

    market_name = config.get('market_name', 'electric')
    x0= config.get('x0', 0)
    x1= config.get('x1', 0)
    x2= config.get('x2', 0)
    x3= config.get('x3', 0)
    x4= config.get('x4', 0)
    agent_name= config.get('agent_name')		
    return VAVAgent(market_name,agent_name,x0,x1,x2,x3,x4, **kwargs)


	
	

class VAVAgent(MarketAgent, FirstOrderZone):
    """
    The SampleElectricMeterAgent serves as a sample of an electric meter that
    sells electricity for a single building at a fixed price.
    """
    def __init__(self, market_name,agent_name,x0,x1,x2,x3,x4, **kwargs):
        super(VAVAgent, self).__init__(**kwargs)
        self.iniState()
        self.market_name = market_name
        self.agent_name = agent_name		
        self.x0 = x0
        self.x1 = x1
        self.x2 = x2
        self.x3 = x3
        self.x4 = x4
        self.subscribing_topic='devices/CAMPUS/BUILDING1/AHU1/all'
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
        demand_curve = PolyLine()		
        pMin = 10
        pMax = 100
        qMin = abs(self.getQMin())
        qMax = abs(self.getQMax())
        if (self.hvacAvail > 0):
            demand_curve.add(Point(price=max(pMin, pMax),quantity=min(qMin, qMax)))
            demand_curve.add(Point(price=min(pMin, pMax),quantity=max(qMin, qMax)))
        else:
            demand_curve.add(Point(price=max(pMin, pMax), quantity=0.0))
            demand_curve.add(Point(price=min(pMin, pMax),quantity=0.0))
        return demand_curve

    def iniState(self):
        self.hvacAvail = 1
        self.tSupHvac = 12.78
        self.tOut =32
        self.mDot = 1.0
        self.tSup = 12.78
        self.tIn = 22
        self.standby = 0
        self.occupied = 0
        self.tSet=22
        self.tDel=0.5
        self.tMinAdj=21
        self.tMaxAdj=23
        self.mDotMin=0.3
        self.mDotMax=1		
        self.qHvacSens = self.mDot*1006.*(self.tSup-self.tIn)		
        self.qMin = min(0, self.mDotMin*1006.*(self.tSupHvac-self.tIn))
        self.qMax = min(0, self.mDotMax*1006.*(self.tSupHvac-self.tIn))

		
    def updateState(self, peer, sender, bus, topic, headers, message):
	    '''Subscribe to device data from message bus
	    '''
	    _log.debug('Received one new dataset')
	    info = {}
	    for key, value in message[0].items():
                  info[key.lower()] = value
	    self.hvacAvail = info['SupplyFanStatus']
	    self.tSupHvac = info['DischargeAirTemperature']
	    self.tOut == info['OutdoorAirTemperature']
	    self.mDot = info[self.agent_name+'_ZoneAirFlow']
	    self.tSup = info[self.agent_name+'_ZoneDischargeAirTemperature']
	    self.tIn = info[self.agent_name+'_ZoneTemperature']
	    self.qHvacSens = self.mDot*1006.*(self.tSup-self.tIn)		
	    self.qMin = min(0, self.mDotMin*1006.*(self.tSupHvac-self.tIn))
	    self.qMax = min(0, self.mDotMax*1006.*(self.tSupHvac-self.tIn))
		
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
        _log.debug("Report cleared price for Market: {} {}, Message: {}".format(market_name, buyer_seller, price, quantity))

    def error_callback(self, timestamp, market_name, buyer_seller, error_message):
        _log.debug("Report error for Market: {} {}, Message: {}".format(market_name, buyer_seller, error_message))


def main():
    """Main method called to start the agent."""
    utils.vip_main(vav_agent, version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
