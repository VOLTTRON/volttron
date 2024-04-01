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

import pytest
try:
    from volttron.platform.agent.base_market_agent.point import Point
    from volttron.platform.agent.base_market_agent.poly_line import PolyLine
    from volttron.platform.agent.base_market_agent.buy_sell import BUYER, SELLER
    from market_service.offer_manager import OfferManager
except ImportError:
    pytest.skip("Market service requirements not installed.", allow_module_level=True)


@pytest.mark.market
def test_offer_settle_no_intersection():
    demand1 = create_demand_curve()
    demand2 = create_demand_curve()
    offer_manager = OfferManager()
    offer_manager.make_offer(BUYER, demand1)
    offer_manager.make_offer(SELLER, demand2)
    quantity, price, aux = offer_manager.settle()
    assert len(aux) == 4

def create_demand_curve():
    demand_curve = PolyLine()
    price = 0
    quantity = 1000
    demand_curve.add(Point(price, quantity))
    price = 1000
    quantity = 0
    demand_curve.add(Point(price, quantity))
    return demand_curve
