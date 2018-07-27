# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
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
    from market_service.market_participant import MarketParticipant
    from market_service.market import Market, ACCEPT_RESERVATIONS
    from volttron.platform.agent.base_market_agent.buy_sell import BUYER, SELLER
except ImportError:
    pytest.skip("Market service requirements not installed.", allow_module_level=True)

@pytest.mark.market
def test_market_state_create_name():
    market_name = 'test_market'
    market = build_test_machine(market_name, BUYER)
    assert market_name == market.market_name

def build_test_machine(market_name = 'test_market', buyer_seller = BUYER):
    participant = MarketParticipant(buyer_seller, 'agent_id')
    publisher = Publisher()
    market = Market(market_name, participant, publisher.publish)
    return market

@pytest.mark.market
def test_market_state_create_state():
    market = build_test_machine()
    assert market.state == ACCEPT_RESERVATIONS

@pytest.mark.market
def test_market_state_create_has_formed_false():
    market = build_test_machine()
    assert market.has_market_formed() == False

@pytest.mark.market
def test_market_state_create_has_formed_true():
    market_name = 'test_market'
    market = build_test_machine(market_name, BUYER)
    participant = MarketParticipant(SELLER, 'agent_id2')
    market.make_reservation(participant)
    assert market.has_market_formed()

class Publisher(object):
    def __init__(self):
        pass

    def publish(self, peer, topic, headers=None, message=None, bus=''):
        pass
