# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
# }}}

import logging
import gevent

from volttron.platform.agent import utils
from volttron.platform.agent.base_market_agent.error_codes import NOT_FORMED
from volttron.platform.agent.base_market_agent.market_registration import MarketRegistration

_log = logging.getLogger(__name__)
utils.setup_logging()

GREENLET_ENABLED = False


class RegistrationManager:
    """
    The ReservationManager manages a list of MarketReservations for the MarketAgents.
    This class exists to hide the features of the underlying collection that are not relevant to
    managing market reservations.
    """
    def __init__(self, rpc_proxy):
        """
        The initalization needs the agent to grant access to the RPC calls needed to
        communicate with the marketService.
        :param rpc_proxy: The MarketAgents that owns this object.
        """
        self.registrations = []
        self.rpc_proxy = rpc_proxy

    def make_registration(self, market_name, buyer_seller, reservation_callback, offer_callback,
                          aggregate_callback, price_callback, error_callback):
        registration = MarketRegistration(market_name, buyer_seller, reservation_callback, offer_callback,
                                          aggregate_callback, price_callback, error_callback)
        self.registrations.append(registration)

    def make_offer(self, market_name, buyer_seller, curve):
        result = False
        error_message = "Market: {} {} was not found in the local list of markets".format(market_name, buyer_seller)
        for registration in self.registrations:
            if registration.market_name == market_name:
                result, error_message = registration.make_offer(buyer_seller, curve, self.rpc_proxy)
        return result, error_message

    def request_reservations(self, timestamp):
        greenlets = []
        _log.debug("Registration manager request_reservations")
        for registration in self.registrations:
            if GREENLET_ENABLED:
                event = gevent.spawn(registration.request_reservations, timestamp, self.rpc_proxy)
                greenlets.append(event)
            else:
                registration.request_reservations(timestamp, self.rpc_proxy)
        gevent.joinall(greenlets)
        _log.debug("After request reserverations!")

    def request_offers(self, timestamp, unformed_markets):
        greenlets = []
        _log.debug("Registration manager request_offers")
        for registration in self.registrations:
            if registration.market_name not in unformed_markets:
                if GREENLET_ENABLED:
                    event = gevent.spawn(registration.request_offers, timestamp)
                    greenlets.append(event)
                else:
                    registration.request_offers(timestamp)
            else:
                error_message = 'The market {} has not received a buy and a sell reservation.'.format(registration.market_name)
                registration.report_error(timestamp, NOT_FORMED, error_message, {})
        gevent.joinall(greenlets)
        _log.debug("After request offers!")

    def report_clear_price(self, timestamp, market_name, price, quantity):
        for registration in self.registrations:
            if registration.market_name == market_name:
                registration.report_clear_price(timestamp, price, quantity)

    def report_aggregate(self, timestamp, market_name, buyer_seller, aggregate_curve):
        for registration in self.registrations:
            if registration.market_name == market_name:
                registration.report_aggregate(timestamp, buyer_seller, aggregate_curve)

    def report_error(self, timestamp, market_name, error_code, error_message, aux):
        for registration in self.registrations:
            if registration.market_name == market_name:
                registration.report_error(timestamp, error_code, error_message, aux)
