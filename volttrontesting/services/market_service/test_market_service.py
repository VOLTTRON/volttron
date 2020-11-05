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
Pytest test cases for testing market service agent.
"""

from datetime import datetime
import gevent
import pytest

try:
    from volttron.platform.agent import utils
    from volttron.platform.agent.base_market_agent import MarketAgent
    from volttron.platform.agent.base_market_agent.poly_line import PolyLine
    from volttron.platform.agent.base_market_agent.point import Point
    from volttron.platform.agent.base_market_agent.buy_sell import BUYER, SELLER
except ImportError:
    pytest.skip("Market service requirements not installed.", allow_module_level=True)

STANDARD_GET_TIMEOUT = 5
BASE_DELAY = 6
LONG_DELAY = BASE_DELAY * 3


class _config_test_agent(MarketAgent):
    def __init__(self, identity, **kwargs):
        super(_config_test_agent, self).__init__(**kwargs)
        self.test_agent_name = identity
        self.reset_results()
        self.wants_reservation = True
        print_message("Starting {}".format(self.test_agent_name))

    def reset_results(self):
        print_message("reseting results in {}".format(self.test_agent_name))
        self.reservation_callback_results = []
        self.offer_callback_results = []
        self.aggregate_callback_results = []
        self.price_callback_results = []
        self.error_callback_results = []

    def join_market_as_simple_seller(self, market_name):
        print_message("join_market_as_simple_seller in {}".format(self.test_agent_name))
        self.join_market(market_name, SELLER, self.reservation_callback, self.offer_callback, None, self.price_callback, self.error_callback)

    def join_market_as_simple_buyer(self, market_name):
        print_message("join_market_as_simple_buyer in {}".format(self.test_agent_name))
        self.join_market(market_name, BUYER, self.reservation_callback, self.offer_callback, None, None, self.error_callback)

    def reservation_callback(self, timestamp, market_name, buyer_seller):
        print_message("reservation_callback in {}".format(self.test_agent_name))
        self.reservation_callback_results.append((timestamp, market_name, buyer_seller, self.wants_reservation))
        return self.wants_reservation

    def offer_callback(self, timestamp, market_name, buyer_seller):
        print_message("offer_callback in {}".format(self.test_agent_name))
        curve = None
        if self.has_reservation:
            if buyer_seller == BUYER:
                curve = self.create_demand_curve()
            else:
                curve = self.create_supply_curve()
        self.offer_callback_results.append((timestamp, market_name, buyer_seller, curve))
        if self.has_reservation:
            self.make_offer(market_name, buyer_seller, curve)

    def create_supply_curve(self):
        supply_curve = PolyLine()
        price = 100
        quantity = 0
        supply_curve.add(Point(price,quantity))
        price = 100
        quantity = 1000
        supply_curve.add(Point(price,quantity))
        return supply_curve

    def create_demand_curve(self):
        demand_curve = PolyLine()
        price = 0
        quantity = 1000
        demand_curve.add(Point(price, quantity))
        price = 1000
        quantity = 0
        demand_curve.add(Point(price, quantity))
        return demand_curve

    def aggregate_callback(self, timestamp, market_name, buyer_seller, curve):
        print_message("aggregate_callback in {}".format(self.test_agent_name))
        self.aggregate_callback_results.append((timestamp, market_name, buyer_seller, curve))

    def price_callback(self, timestamp, market_name, buyer_seller, price, quantity):
        print_message("price_callback in {}".format(self.test_agent_name))
        self.price_callback_results.append((timestamp, market_name, buyer_seller, price, quantity))
        self.has_reservation = False

    def error_callback(self, timestamp, market_name, buyer_seller, error_message):
        print_message("error_callback error message: {} in {}".format(self.test_agent_name))
        self.error_callback_results.append((timestamp, market_name, buyer_seller, error_message))
        self.has_reservation = False


def print_message(message):
    print("{0}: {1}".format(_get_time(), message))

def _get_time():
    now = datetime.now()
    now_string = str(now)
    return now_string


@pytest.fixture(scope="module")
def _module_config_test_service(request, volttron_instance):
    # Start the market service agent
    market_service_uuid = volttron_instance.install_agent(
        agent_dir="services/core/MarketServiceAgent",
        config_file={
            'market_period': LONG_DELAY,
            'reservation_delay': 0,
            'offer_delay': BASE_DELAY,
            'clear_delay': BASE_DELAY
        },
        start=True)
    print_message("market service agent id: {}".format(market_service_uuid))
    yield market_service_uuid
    print_message("In market service agent teardown method of module")
    volttron_instance.stop_agent(market_service_uuid)


@pytest.fixture(scope="function")
def _function_config_test_seller(request, volttron_instance, _module_config_test_service):
    seller_agent = volttron_instance.build_agent(identity='config_test_seller', agent_class=_config_test_agent)
    gevent.sleep(0.5)
    yield seller_agent
    seller_agent.core.stop(timeout=STANDARD_GET_TIMEOUT)

@pytest.fixture(scope="function")
def _function_config_test_buyer(request, volttron_instance, _module_config_test_service):
    buyer_agent = volttron_instance.build_agent(identity='config_test_buyer', agent_class=_config_test_agent)
    gevent.sleep(0.5)
    yield buyer_agent
    buyer_agent.core.stop(timeout=STANDARD_GET_TIMEOUT)


@pytest.mark.market
@pytest.mark.skip("needs to be fixed as the _config_seller and _config_buyer don't have has_reservation properties")
def test_simple_market_reservations(_function_config_test_seller, _function_config_test_buyer):
    seller_agent = _function_config_test_seller
    buyer_agent = _function_config_test_buyer
    market_name = 'electricity'
    seller_agent.join_market_as_simple_seller(market_name)
    buyer_agent.join_market_as_simple_buyer(market_name)
    gevent.sleep(LONG_DELAY)
    assert len(seller_agent.reservation_callback_results) >= 1, "expected that the seller got a reservation callback"
    assert len(buyer_agent.reservation_callback_results) >= 1, "expected that the buyer got a reservation callback"

@pytest.mark.market
@pytest.mark.skip("needs to be fixed as the _config_seller and _config_buyer don't have has_reservation properties")
def test_simple_market_offers(_function_config_test_seller, _function_config_test_buyer):
    seller_agent = _function_config_test_seller
    buyer_agent = _function_config_test_buyer
    market_name = 'electricity'
    seller_agent.join_market_as_simple_seller(market_name)
    buyer_agent.join_market_as_simple_buyer(market_name)
    gevent.sleep(LONG_DELAY)
    assert len(seller_agent.offer_callback_results) >= 1, "expected that the seller got an offer callback"
    assert len(buyer_agent.offer_callback_results) >= 1, "expected that the buyer got an offer callback"

@pytest.mark.market
@pytest.mark.skip("needs to be fixed as the _config_seller and _config_buyer don't have has_reservation properties")
def test_simple_market_prices(_function_config_test_seller, _function_config_test_buyer):
    seller_agent = _function_config_test_seller
    buyer_agent = _function_config_test_buyer
    market_name = 'electricity'
    seller_agent.join_market_as_simple_seller(market_name)
    buyer_agent.join_market_as_simple_buyer(market_name)
    gevent.sleep(LONG_DELAY)
    assert len(seller_agent.price_callback_results) >= 1, "expected that the seller got a price callback"
    assert len(buyer_agent.price_callback_results) >= 1, "expected that the buyer got a price callback"

@pytest.mark.market
@pytest.mark.skip("needs to be fixed as the _config_seller and _config_buyer don't have has_reservation properties")
def test_simple_market_errors(_function_config_test_seller, _function_config_test_buyer):
    seller_agent = _function_config_test_seller
    buyer_agent = _function_config_test_buyer
    market_name = 'electricity'
    seller_agent.join_market_as_simple_seller(market_name)
    buyer_agent.join_market_as_simple_buyer(market_name)
    gevent.sleep(LONG_DELAY)
    assert len(seller_agent.error_callback_results) == 0, "expected that the seller got no error callbacks"
    assert len(buyer_agent.error_callback_results) == 0, "expected that the buyer got no error callbacks"

