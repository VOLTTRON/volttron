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
from volttron.platform.agent.base_market_agent.buy_sell import SELLER
# from pnnl.models.firstorderzone import FirstOrderZone

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.01"

def ahu_agent(config_path, **kwargs):
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
    air_market_name = config.get('market_name1', 'air')
    electric_market_name = config.get('market_name2', 'electric')
    agent_name= config.get('agent_name')		
    verbose_logging= config.get('verbose_logging', True)
    return AHUAgent(air_market_name,electric_market_name,agent_name, verbose_logging, **kwargs)

class AHUAgent(MarketAgent):
    """
    The SampleElectricMeterAgent serves as a sample of an electric meter that
    sells electricity for a single building at a fixed price.
    """
    def __init__(self, air_market_name, electric_market_name, agent_name, verbose_logging, **kwargs):
        super(AHUAgent, self).__init__(verbose_logging, **kwargs)
        self.ini_state()
        self.air_market_name = air_market_name
        self.electric_market_name = electric_market_name
        self.agent_name = agent_name
        self.subscribing_topic='devices/CAMPUS/BUILDING1/AHU1/all'
        self.join_market(self.air_market_name, SELLER, None, None, self.air_aggregate_callback, self.air_price_callback, self.error_callback)
        self.join_market(self.electric_market_name, BUYER, None, None, None, self.electric_price_callback, self.error_callback)
        self.hvacAvail = 0
		
    @Core.receiver('onstart')
    def setup(self, sender, **kwargs):
        _log.debug('Subscribing to '+self.subscribing_topic)
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix=self.subscribing_topic,
                                  callback=self.updateState)
								  
    def air_aggregate_callback(self, timestamp, market_name, buyer_seller, aggregate_air_demand):
        if buyer_seller == BUYER:
            electric_demand = self.create_electric_demand_curve(aggregate_air_demand)
            self.make_offer(self.electric_market_name, BUYER, electric_demand)
            _log.debug("Report make offer for Market: {} BuySell: {} Curve: {}".format(market_name,
                                                                                       buyer_seller,
                                                                                       electric_demand.points))

    def electric_price_callback(self, timestamp, market_name, buyer_seller, price, quantity):
        self.report_cleared_price(buyer_seller, market_name, price, quantity)
        air_supply_curve = self.create_air_supply_curve(price)
        self.make_offer(self.air_market_name, SELLER, air_supply_curve)
        _log.debug("Report make offer for Market: {} BuySell: {} Curve: {}".format(market_name,
                                                                                   buyer_seller,
                                                                                   air_supply_curve.points))

    def air_price_callback(self, timestamp, market_name, buyer_seller, price, quantity):
        self.report_cleared_price(buyer_seller, market_name, price, quantity)

    def report_cleared_price(self, buyer_seller, market_name, price, quantity):
        _log.debug(
            "Report cleared price for Market: {} BuySell: {} Price: {} Quantity: {}".format(market_name, buyer_seller, price, quantity))

    def error_callback(self, timestamp, market_name, buyer_seller, error_message):
        _log.debug("Report error for Market: {} {}, Message: {}".format(market_name, buyer_seller, error_message))

    def create_air_supply_curve(self, electric_price):
        supply_curve = PolyLine()
        price = 65
        quantity = 100000
        supply_curve.add(Point(price=price,quantity=quantity))
        price = 65
        quantity = -1*10000
        supply_curve.add(Point(price=price,quantity=quantity))
        return supply_curve
		
    def create_electric_demand_curve(self, aggregate_air_demand):
        _log.debug("Call the aggregated function") 
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
        return aggregate_air_demand

    def ini_state(self):
        pass

    def updateState(self, peer, sender, bus, topic, headers, message):
        '''Subscribe to device data from message bus
        '''
        _log.debug('Received one new dataset')
        info = {}
        for key, value in message[0].items():
            info[key.lower()] = value

    def getQMax(self):
        return 0

    def getQMin(self):
        return 0


def main():
    """Main method called to start the agent."""
    utils.vip_main(ahu_agent, version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
