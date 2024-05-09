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

from volttron.platform.agent import utils
from .market import Market

_log = logging.getLogger(__name__)
utils.setup_logging()


class NoSuchMarketError(Exception):
    """Base class for exceptions in this module."""
    pass


class MarketList:
    def __init__(self, publish = None, verbose_logging = True):
        self.markets = {}
        self.publish = publish
        self.verbose_logging = verbose_logging

    def make_reservation(self, market_name, participant):
        if self.has_market(market_name):
            market = self.markets[market_name]
            market.make_reservation(participant)
        else:
            market = Market(market_name, participant, self.publish, self.verbose_logging)
            self.markets[market_name] = market

    def make_offer(self, market_name, participant, curve):
        market = self.get_market(market_name)
        market.make_offer(participant, curve)

    def clear_reservations(self):
        self.markets.clear()

    def collect_offers(self):
        for market in list(self.markets.values()):
            market.collect_offers()

    def get_market(self, market_name):
        if self.has_market(market_name):
            market = self.markets[market_name]
        else:
            raise NoSuchMarketError('Market %s does not exist.' % market_name)
        return market

    def has_market(self, market_name):
        return market_name in self.markets

    def has_market_formed(self, market_name):
        market_has_formed = False
        if self.has_market(market_name):
            market = self.markets[market_name]
            market_has_formed = market.has_market_formed()
        return market_has_formed

    def send_market_failure_errors(self):
        for market in list(self.markets.values()):
            # We have already sent unformed market failures
           if market.has_market_formed():
               # If the market has not cleared trying to clear it will send an error.
               if not market.is_market_done():
                   market.clear_market()

    def market_count(self):
        return len(self.markets)

    def unformed_market_list(self):
        _list = []
        for market in list(self.markets.values()):
            if not market.has_market_formed():
                _list.append(market.market_name)
        return _list
