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

import pytest

try:
    from market_service.market_list import MarketList
    from market_service.market_participant import MarketParticipant
    from volttron.platform.agent.base_market_agent.buy_sell import BUYER, SELLER
except ImportError:
    pytest.skip("Market service requirements not installed.", allow_module_level=True)



@pytest.mark.market
def test_market_participants_no_market():
    market_list = MarketList()
    assert market_list.has_market('no_market') is False


@pytest.mark.market
def test_market_participants_has_market():
    market_list = MarketList()
    market_name = 'test_market'
    seller_participant = MarketParticipant(SELLER, 'agent_id')
    market_list.make_reservation(market_name, seller_participant)
    assert market_list.has_market(market_name) is True


@pytest.mark.market
def test_market_participants_market_not_formed_no_market():
    market_list = MarketList()
    market_name = 'test_market'
    assert market_list.has_market_formed(market_name) is False


@pytest.mark.market
def test_market_participants_market_not_formed_one_seller():
    market_list = MarketList()
    market_name = 'test_market'
    seller_participant = MarketParticipant(SELLER, 'agent_id')
    market_list.make_reservation(market_name, seller_participant)
    assert market_list.has_market_formed(market_name) is False


@pytest.mark.market
def test_market_participants_market_bad_seller_argument():
    market_list = MarketList()
    market_name = 'test_market'
    with pytest.raises(ValueError) as error_info:
        bad_participant = MarketParticipant('bob is cool', 'agent_id')
        market_list.make_reservation(market_name, bad_participant)
    assert 'bob is cool' in error_info.value.args[0]


@pytest.mark.market
def test_market_participants_market_not_formed_one_buyer():
    market_list = MarketList()
    market_name = 'test_market'
    buyer_participant = MarketParticipant(BUYER, 'agent_id')
    market_list.make_reservation(market_name, buyer_participant)
    assert market_list.has_market_formed(market_name) == False


@pytest.mark.market
def test_market_participants_market_formed_one_buyer_one_seller():
    market_list = MarketList()
    market_name = 'test_market'
    buyer_participant = MarketParticipant(BUYER, 'agent_id1')
    market_list.make_reservation(market_name, buyer_participant)
    seller_participant = MarketParticipant(SELLER, 'agent_id2')
    market_list.make_reservation(market_name, seller_participant)
    assert market_list.market_count() == 1
    assert market_list.has_market_formed(market_name) == True
    unformed_markets = market_list.unformed_market_list()
    assert len(unformed_markets) == 0


@pytest.mark.market
def test_market_unformed_market_list():
    market_list = MarketList()
    market_name1 = 'test_market1'
    market_name2 = 'test_market2'
    buyer_participant = MarketParticipant(BUYER, 'agent_id1')
    market_list.make_reservation(market_name1, buyer_participant)
    seller_participant = MarketParticipant(SELLER, 'agent_id2')
    market_list.make_reservation(market_name2, seller_participant)
    assert market_list.market_count() == 2
    unformed_markets = market_list.unformed_market_list()
    assert len(unformed_markets) > 0
