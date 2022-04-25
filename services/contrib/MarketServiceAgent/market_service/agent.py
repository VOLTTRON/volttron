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

"""
.. _market-service-agent:

The Market Service Agent is used to allow agents to use transactive markets
to implement transactive control strategies.  The Market Service Agent provides
an implementation of double blind auction markets that can be used by multiple agents.

Agents that want to use the Market Service Agent inherit from the :ref:`base MarketAgent<Developing-Market-Agents>`.
The base MarketAgent handles all of the communication between the agent and the MarketServiceAgent.

MarketServiceAgent Configuration
================================

    "market_period"
        The time allowed for a market cycle in seconds. After this amount of time the market starts again.
        Defaults to 300.
    "reservation_delay"
        The time delay between the start of a market cycle and the start of gathering market reservations
         in seconds. Defaults to 0.
    "offer_delay"
        The time delay between the start of gathering market reservations and the start of gathering market bids/offers
         in seconds. Defaults to 120.
    "verbose_logging"
        If True this enables verbose logging.  If False, there is little or no logging.
        Defaults to True.


Sample configuration file
-------------------------

.. code-block:: python

    {
        "market_period": 300,
        "reservation_delay": 0,
        "offer_delay": 120,
        "verbose_logging": True
    }

"""

__docformat__ = 'reStructuredText'

import logging
import sys
import gevent

from transitions import Machine
from volttron.platform.agent.known_identities import PLATFORM_MARKET_SERVICE
from volttron.platform.agent import utils
from volttron.platform.messaging.topics import MARKET_RESERVE, MARKET_BID
from volttron.platform.vip.agent import Agent, Core, RPC
from volttron.platform.agent.base_market_agent.poly_line_factory import PolyLineFactory

from .market_list import MarketList
from .market_participant import MarketParticipant
from .director import Director

_tlog = logging.getLogger('transitions.core')
_tlog.setLevel(logging.WARNING)
_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "1.0"

INITIAL_WAIT = 'service_initial_wait'
COLLECT_RESERVATIONS = 'service_collect_reservations'
COLLECT_OFFERS = 'service_collect_offers'
NO_MARKETS = 'service_has_no_markets'


class MarketServiceAgent(Agent):
    states = [INITIAL_WAIT, COLLECT_RESERVATIONS, COLLECT_OFFERS, NO_MARKETS]
    transitions = [
        {'trigger': 'start_reservations', 'source': INITIAL_WAIT, 'dest': COLLECT_RESERVATIONS},
        {'trigger': 'start_offers_no_markets', 'source': COLLECT_RESERVATIONS, 'dest': NO_MARKETS},
        {'trigger': 'start_offers_has_markets', 'source': COLLECT_RESERVATIONS, 'dest': COLLECT_OFFERS},
        {'trigger': 'start_reservations', 'source': COLLECT_OFFERS, 'dest': COLLECT_RESERVATIONS},
        {'trigger': 'start_reservations', 'source': NO_MARKETS, 'dest': COLLECT_RESERVATIONS},
    ]

    def __init__(self, config_path, **kwargs):
        super(MarketServiceAgent, self).__init__(**kwargs)

        config = utils.load_config(config_path)
        self.agent_name = config.get('agent_name', 'MixMarketService')
        self.market_period = int(config.get('market_period', 300))
        self.reservation_delay = int(config.get('reservation_delay', 0))
        self.offer_delay = int(config.get('offer_delay', 120))
        self.verbose_logging = int(config.get('verbose_logging', True))
        self.director = None
        # This can be periodic or event_driven
        self.market_type = config.get("market_type", "event_driven")
        if self.market_type not in ["periodic", "event_driven"]:
            self.market_type = "event_driven"

        self.state_machine = Machine(model=self, states=MarketServiceAgent.states,
                                     transitions= MarketServiceAgent.transitions, initial=INITIAL_WAIT)
        self.market_list = MarketList(self.vip.pubsub.publish, self.verbose_logging)

    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        if self.market_type == "periodic":
            self.director = Director(self.market_period, self.reservation_delay, self.offer_delay)
            self.director.start(self)
        else:
            # Listen to the new_cycle signal
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix='mixmarket/start_new_cycle',
                                      callback=self.start_new_cycle)

    def start_new_cycle(self, peer, sender, bus, topic, headers, message):
        _log.debug("Trigger market period for Market agent.")
        gevent.sleep(self.reservation_delay)
        self.send_collect_reservations_request(utils.get_aware_utc_now())

        gevent.sleep(self.offer_delay)
        self.send_collect_offers_request(utils.get_aware_utc_now())

    def send_collect_reservations_request(self, timestamp):
        _log.debug("send_collect_reservations_request at {}".format(timestamp))
        self.start_reservations()
        self.market_list.send_market_failure_errors()
        self.market_list.clear_reservations()
        self.vip.pubsub.publish(peer='pubsub',
                                topic=MARKET_RESERVE,
                                message=utils.format_timestamp(timestamp))

    def send_collect_offers_request(self, timestamp):
        if self.has_any_markets():
            self.begin_collect_offers(timestamp)
        else:
            self.start_offers_no_markets()

    def begin_collect_offers(self, timestamp):
        _log.debug("send_collect_offers_request at {}".format(timestamp))
        self.start_offers_has_markets()
        self.market_list.collect_offers()
        unformed_markets = self.market_list.unformed_market_list()
        self.vip.pubsub.publish(peer='pubsub',
                                topic=MARKET_BID,
                                message=[utils.format_timestamp(timestamp), unformed_markets])

    @RPC.export
    def make_reservation(self, market_name, buyer_seller):
        import time
        start = time.time()

        identity = bytes(self.vip.rpc.context.vip_message.peer, "utf8")
        log_message = "Received {} reservation for market {} from agent {}".format(buyer_seller, market_name, identity)
        _log.debug(log_message)
        if self.state == COLLECT_RESERVATIONS:
            self.accept_reservation(buyer_seller, identity, market_name)
        else:
            self.reject_reservation(buyer_seller, identity, market_name)

        end = time.time()
        print(end - start)

    def accept_reservation(self, buyer_seller, identity, market_name):
        _log.info("Reservation on Market: {} {} made by {} was accepted.".format(market_name, buyer_seller, identity))
        participant = MarketParticipant(buyer_seller, identity)
        self.market_list.make_reservation(market_name, participant)

    def reject_reservation(self, buyer_seller, identity, market_name):
        _log.info("Reservation on Market: {} {} made by {} was rejected.".format(market_name, buyer_seller, identity))
        raise RuntimeError("Error: Market service not accepting reservations at this time.")

    @RPC.export
    def make_offer(self, market_name, buyer_seller, offer):
        identity = bytes(self.vip.rpc.context.vip_message.peer, "utf8")
        log_message = "Received {} offer for market {} from agent {}".format(buyer_seller, market_name, identity)
        _log.debug(log_message)
        if self.state == COLLECT_OFFERS:
            self.accept_offer(buyer_seller, identity, market_name, offer)
        else:
            self.reject_offer(buyer_seller, identity, market_name, offer)

    def accept_offer(self, buyer_seller, identity, market_name, offer):
        _log.info("Offer on Market: {} {} made by {} was accepted.".format(market_name, buyer_seller, identity))
        participant = MarketParticipant(buyer_seller, identity)
        curve = PolyLineFactory.fromTupples(offer)
        self.market_list.make_offer(market_name, participant, curve)

    def reject_offer(self, buyer_seller, identity, market_name, offer):
        _log.info("Offer on Market: {} {} made by {} was rejected.".format(market_name, buyer_seller, identity))
        raise RuntimeError("Error: Market service not accepting offers at this time.")

    def has_any_markets(self):
        unformed_markets = self.market_list.unformed_market_list()
        return len(unformed_markets) < self.market_list.market_count()


def main():
    """Main method called to start the agent."""
    utils.vip_main(MarketServiceAgent,
                   identity=PLATFORM_MARKET_SERVICE,
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
