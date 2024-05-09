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
from volttron.platform.agent.base_market_agent.buy_sell import BUYER
from volttron.platform.agent.base_market_agent.poly_line import PolyLine
from volttron.platform.agent.base_market_agent.poly_line_factory import PolyLineFactory

_log = logging.getLogger(__name__)
utils.setup_logging()


class OfferManager:

    def __init__(self):
        self._buy_offers = []
        self._sell_offers = []
        self.increment = 100

    def make_offer(self, buyer_seller, curve):
        if (buyer_seller == BUYER):
            self._buy_offers.append(curve)
        else:
            self._sell_offers.append(curve)

    def aggregate_curves(self, buyer_seller):
        if (buyer_seller == BUYER):
            curve = self._aggregate(self._buy_offers)
        else:
            curve = self._aggregate(self._sell_offers)
        return curve

    def _aggregate(self, collection):
#        curve = PolyLineFactory.combine(collection, self.increment)
        curve = PolyLineFactory.combine_withoutincrement(collection)
        return curve

    def settle(self):
        enough_buys = len(self._buy_offers) > 0
        enough_sells = len(self._sell_offers) > 0
        if enough_buys:
            demand_curve = self._aggregate(self._buy_offers)
        else:
            _log.debug("There are no buy offers.")
        if enough_sells:
            supply_curve = self._aggregate(self._sell_offers)
        else:
            _log.debug("There are no sell offers.")

        if enough_buys and enough_sells:
            intersection = PolyLine.intersection(demand_curve, supply_curve)
        else:
            intersection = None, None, {}

        quantity = intersection[0]
        price = intersection[1]
        aux = PolyLine.compare(demand_curve, supply_curve)

        return quantity, price, aux

    def buyer_count(self):
        return len(self._buy_offers)

    def seller_count(self):
        return len(self._sell_offers)
