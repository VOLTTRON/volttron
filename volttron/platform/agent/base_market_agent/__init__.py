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

import logging

from volttron.platform.agent import utils
from volttron.platform.vip.agent import PubSub
from volttron.platform.vip.agent import Agent
from volttron.platform.messaging.topics import MARKET_RESERVE, MARKET_BID, MARKET_CLEAR, MARKET_AGGREGATE, MARKET_ERROR
from volttron.platform.agent.base_market_agent.registration_manager import RegistrationManager
from volttron.platform.agent.base_market_agent.poly_line_factory import PolyLineFactory
from volttron.platform.agent.base_market_agent.rpc_proxy import RpcProxy

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.01"


class MarketAgent(Agent):
    """
    The MarketAgents serves as the base class for any agent that wants to praticipate in
    an auction market.  By inheriting from this agent all the remote communication
    with the MarketService is handled and the sub-class can be unconcerned with those details.
    """
    def __init__(self, verbose_logging = True, **kwargs):
        super(MarketAgent, self).__init__(**kwargs)
        _log.debug("vip_identity: " + self.core.identity)
        rpc_proxy = RpcProxy(self.vip.rpc.call, verbose_logging)
        self.registrations = RegistrationManager(rpc_proxy)
        self.verbose_logging = verbose_logging

    @PubSub.subscribe('pubsub', MARKET_RESERVE)
    def match_reservation(self, peer, sender, bus, topic, headers, message):
        timestamp = utils.parse_timestamp_string(message[0])
        decoded_message = "Timestamp: {}".format(timestamp)
        self.log_event("match_reservation", peer, sender, bus, topic, headers, decoded_message)
        self.registrations.request_reservations(timestamp)


    @PubSub.subscribe('pubsub', MARKET_BID)
    def match_make_offer(self, peer, sender, bus, topic, headers, message):
        timestamp = utils.parse_timestamp_string(message[0])
        unformed_markets = message[1]
        decoded_message = "Timestamp: {}".format(timestamp)
        self.log_event("match_make_offer", peer, sender, bus, topic, headers, decoded_message)
        self.registrations.request_offers(timestamp, unformed_markets)

    @PubSub.subscribe('pubsub', MARKET_CLEAR)
    def match_report_clear_price(self, peer, sender, bus, topic, headers, message):
        timestamp = utils.parse_timestamp_string(message[0])
        market_name = message[1]
        quantity = message[2]
        price = message[3]
        decoded_message = "Timestamp: {} Market: {} Price: {} Quantity: {}".format(timestamp, market_name, price, quantity)
        self.log_event("match_report_clear_price", peer, sender, bus, topic, headers, decoded_message)
        self.registrations.report_clear_price(timestamp, market_name, price, quantity)

    @PubSub.subscribe('pubsub', MARKET_AGGREGATE)
    def match_report_aggregate(self, peer, sender, bus, topic, headers, message):
        timestamp = utils.parse_timestamp_string(message[0])
        market_name = message[1]
        buyer_seller = message[2]
        aggregate_curve_points = message[3]
        decoded_message = "Timestamp: {} Market: {} {} Curve: {}".format(timestamp, market_name, buyer_seller, aggregate_curve_points)
        self.log_event("match_report_aggregate", peer, sender, bus, topic, headers, decoded_message)
        aggregate_curve = PolyLineFactory.fromTupples(aggregate_curve_points)
        self.registrations.report_aggregate(timestamp, market_name, buyer_seller, aggregate_curve)

    @PubSub.subscribe('pubsub', MARKET_ERROR)
    def match_report_error(self, peer, sender, bus, topic, headers, message):
        timestamp = utils.parse_timestamp_string(message[0])
        market_name = message[1]
        error_code = message[2]
        error_message = message[3]
        aux = message[4]
        decoded_message = "Timestamp: {} Market: {} Code: {} Message: {}".format(timestamp, market_name, error_code, error_message)
        self.log_event("match_report_error", peer, sender, bus, topic, headers, decoded_message)
        self.registrations.report_error(timestamp, market_name, error_code, error_message, aux)

    def log_event(self, method_name, peer, sender, bus, topic, headers, decoded_message):
        if self.verbose_logging:
            _log.debug("{} Peer: {} Sender: {} Bus: {} Topic: {} Headers: {} Message: {}".format(method_name, peer, sender, bus, topic, headers, decoded_message))

    def join_market (self, market_name, buyer_seller, reservation_callback,
                     offer_callback, aggregate_callback, price_callback, error_callback):
        """
        This routine is called once to join a market as a buyer or a seller.
        The agent supplies call-back functions that the MarketAgents calls as the market process proceeds.

        :param market_name: The name of the market commodity.

        :param buyer_seller: A string indicating whether the agent is buying from or selling to the market.
        The agent shall use the pre-defined strings provided.

        :param reservation_callback: This callback is called at the beginning of each round of bidding and clearing.
        The agent can choose whether or not to participate in this round.
        If the agent wants to participate it returns true otherwise it returns false.
        If the agent does not specify a callback routine a reservation will be made for each round automatically.
        A market will only exist if there are reservations for at least one buyer and at least one seller.
        If the market fails to achieve the minimum participation the error callback will be called.

        :param offer_callback: If the agent has made a reservation for the market this routine is called.
        If the agent wishes to make an offer at this time the market agent computes either supply or demand curves
        as appropriate and offers them to the market service by calling the make offer method.
        For each market joined either an offer callback or an aggregate callback is required.
        You can’t supply both for any single market.

        :param aggregate_callback: When a market has received all its buy offers it calculates an aggregate
        demand curve.  When the market receives all of its sell offers it calculates an aggregate supply curve.
        This callback delivers the aggregate curve to the market agent whenever the appropriate curve
        becomes available.  If the market agent want to use this to make an offer it would do that using
        the make offer method.  For each market joined either an offer callback or an aggregate callback is required.
        You can’t supply both for any single market.

        :param price_callback: This callback is called when the market clears. The price callback is optional.

        :param error_callback: This callback is called at appropriate time points or when an error occurs.
        If a market fails to form this will be called at the offer time.
        If the market doesn’t receive all its offers this will be called at market clear time.
        If the market fails to clear this would be called at the next reservation time.
        This allows agents to respond at or near the normal time points.  The error callback is optional.
        """
        self.registrations.make_registration(market_name, buyer_seller,
                                          reservation_callback, offer_callback,
                                          aggregate_callback, price_callback, error_callback)

    def make_offer(self, market_name, buyer_seller, curve):
        """
        This call makes an offer with the MarketService.

        :param market_name: The name of the market commodity.

        :param buyer_seller: A string indicating whether the agent is buying from or selling to the market.
        The agent shall use the pre-defined strings provided.

        :param curve: The demand curve for buyers or the supply curve for sellers.
        """
        result = self.registrations.make_offer(market_name, buyer_seller, curve)
        return result

