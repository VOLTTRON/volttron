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

import pytest

try:
    from volttron.platform.agent.base_market_agent.market_registration import MarketRegistration
    from volttron.platform.agent.base_market_agent.buy_sell import BUYER, SELLER
    from volttron.platform.agent.utils import get_aware_utc_now
    from volttron.platform.agent.base_market_agent.point import Point
    from volttron.platform.agent.base_market_agent.poly_line import PolyLine
except ImportError:
    pytest.skip("Market service requirements not installed.", allow_module_level=True)

@pytest.mark.market
def test_market_registration_no_reservation_callback():
    agent = MockAgent()
    registration = MarketRegistration('test_market', SELLER, None, null_callback, None, None, None)
    registration.request_reservations(get_time, agent)
    assert agent.reservation_made == True

@pytest.mark.market
def test_market_registration_true_reservation_callback():
    agent = MockAgent()
    registration = MarketRegistration('test_market', SELLER, wants_registration_true_callback, null_callback, None, None, None)
    registration.request_reservations(get_time, agent)
    assert agent.reservation_made == True

@pytest.mark.market
def test_market_registration_false_reservation_callback():
    agent = MockAgent()
    registration = MarketRegistration('test_market', SELLER, wants_registration_false_callback, null_callback, None, None, None)
    registration.request_reservations(get_time, agent)
    assert agent.reservation_made == False

@pytest.mark.market
def test_market_registration_no_offer_no_aggregate_no_price_callback():
    with pytest.raises(TypeError) as error_info:
        MarketRegistration('test_market', SELLER, None, None, None, None, None)
    assert 'You must provide either an offer, aggregate, or price callback.' in error_info.value.message

@pytest.mark.market
def test_market_registration_offer_callback():
    agent = MockAgent()
    registration = MarketRegistration('test_market', SELLER, None, agent.make_offer_callback, None, None, None)
    registration2 = MarketRegistration('test_market', BUYER, None, null_callback, None, None, None)
    registration.request_reservations(get_time, agent)
    registration.request_offers(get_time)
    assert agent.offer_made == True

def wants_registration_true_callback(*unused):
    return True

def wants_registration_false_callback(*unused):
    return False

def null_callback(*unused):
    pass

def get_time():
    now = get_aware_utc_now()
    return now

class MockAgent(object):
    def __init__(self):
        self.reservation_made = False
        self.offer_made = False
        self.has_reservation = False

    def make_reservation(self, market_name, buyer_seller):
        self.reservation_made = True
        self.has_reservation = True
        return self.has_reservation

    def make_offer(self, market_name, buyer_seller, curve):
        self.offer_made = True
        error_message = None
        result = (self.offer_made, error_message)
        return result

    def make_offer_callback(self, *unused):
        self.offer_made = True
