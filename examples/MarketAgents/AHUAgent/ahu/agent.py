# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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
from volttron.platform.agent.base_market_agent.buy_sell import BUYER
from volttron.platform.agent.base_market_agent.buy_sell import SELLER
from pnnl.models.ahuchiller import AhuChiller
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
    except Exception:
        config = {}

    if not config:
        _log.info("Using defaults for starting configuration.")
    air_market_name = config.get('market_name1', 'air')
    electric_market_name = config.get('market_name2', 'electric')
    agent_name= config.get('agent_name')
    subscribing_topic= config.get('subscribing_topic')
    c0= config.get('c0')
    c1= config.get('c1')
    c2= config.get('c2')
    c3= config.get('c3')
    COP= config.get('COP')	
    verbose_logging= config.get('verbose_logging', True)
    return AHUAgent(air_market_name,electric_market_name,agent_name,subscribing_topic,c0,c1,c2,c3,COP,verbose_logging, **kwargs)

class AHUAgent(MarketAgent, AhuChiller):
    """
    The SampleElectricMeterAgent serves as a sample of an electric meter that
    sells electricity for a single building at a fixed price.
    """
    def __init__(self, air_market_name, electric_market_name, agent_name,subscribing_topic,c0,c1,c2,c3,COP,verbose_logging, **kwargs):
        super(AHUAgent, self).__init__(verbose_logging, **kwargs)

        self.air_market_name = air_market_name
        self.electric_market_name = electric_market_name
        self.agent_name = agent_name
        self.subscribing_topic=subscribing_topic
        self.c0 = c0
        self.c1 = c1
        self.c2 = c2
        self.c3 = c3
        self.COP = COP
        self.join_market(self.air_market_name, SELLER, None, None, self.air_aggregate_callback, self.air_price_callback, self.error_callback)
        self.join_market(self.electric_market_name, BUYER, None, None, None, self.electric_price_callback, self.error_callback)
        self.hvacAvail = 0
        self.cpAir = 1006.
        self.c4 = 0.
        self.c5 = 0.
        self.staticPressure = 0.
        self.iniState()
        self.old_price = None
        self.old_quantity = None
		
    @Core.receiver('onstart')
    def setup(self, sender, **kwargs):
        _log.debug('Subscribing to '+self.subscribing_topic)
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix=self.subscribing_topic,
                                  callback=self.updateState)
								  
    def air_aggregate_callback(self, timestamp, market_name, buyer_seller, aggregate_air_demand):
        if buyer_seller == BUYER:
            electric_demand = self.create_electric_demand_curve(aggregate_air_demand)
            success, message = self.make_offer(self.electric_market_name, BUYER, electric_demand)
            if success:
                _log.debug("Report make offer for Market: {} {} Curve: {}".format(self.electric_market_name,
                                                                                  BUYER, electric_demand.points))
            else:
                # we aren't going to get a cleared price, so make an offer with the old price.
                self.make_air_market_offer()

    def electric_price_callback(self, timestamp, market_name, buyer_seller, price, quantity):
        self.report_cleared_price(buyer_seller, market_name, price, quantity)
        self.old_price = price
        self.old_quantity = quantity
        self.make_air_market_offer()

    def make_air_market_offer(self):
        # make an offer with the old price
        air_supply_curve = self.create_air_supply_curve(self.old_price, self.old_quantity)
        success, message = self.make_offer(self.air_market_name, SELLER, air_supply_curve)
        if success:
            _log.debug("Report make offer for Market: {} {} Curve: {}".format(self.air_market_name,
                                                                              SELLER, air_supply_curve.points))

    def air_price_callback(self, timestamp, market_name, buyer_seller, price, quantity):
        self.report_cleared_price(buyer_seller, market_name, price, quantity)

    def report_cleared_price(self, buyer_seller, market_name, price, quantity):
        _log.debug(
            "Report cleared price for Market: {} {} Price: {} Quantity: {}".format(market_name, buyer_seller, price, quantity))

    def error_callback(self, timestamp, market_name, buyer_seller, error_code, error_message, aux):
        _log.debug("Report error for Market: {} {}, Code: {}, Message: {}".format(market_name, buyer_seller, error_code, error_message))

    def create_air_supply_curve(self, electric_price, electric_quantity):
        supply_curve = PolyLine()
        price = 65
        quantity = 100000
        supply_curve.add(Point(price=price,quantity=quantity))
        price = 65
        quantity = 0 # negative quantities are not real -1*10000
        supply_curve.add(Point(price=price,quantity=quantity))
        return supply_curve
		
    def create_electric_demand_curve(self, aggregate_air_demand):
        curve = PolyLine()
        for point in aggregate_air_demand.points:
            curve.add(Point(price=point.y, quantity=self.calcTotalLoad(point.x)))
        self.buyBidCurve = curve
        _log.debug("Report aggregated curve : {}".format(curve.points))
        return curve

    def iniState(self):
        self.tAirReturn = 20.
        self.tAirSupply = 10.
        self.tAirMixed = 20.
        self.mDotAir=0
        self.pClear = None

    def updateState(self, peer, sender, bus, topic, headers, message):
        '''Subscribe to device data from message bus
        '''
        _log.debug('Received one new dataset')
        info = message[0].copy()
        tAirMixed= info['MixedAirTemperature']
        tAirReturn= info['ReturnAirTemperature']
        tAirSupply= info['DischargeAirTemperature']
        mDotAir= info['DischargeAirFlow']		



def main():
    """Main method called to start the agent."""
    utils.vip_main(ahu_agent, version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
