# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this market_list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this market_list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
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
    assert market_list.has_market('no_market') == False


@pytest.mark.market
def test_market_participants_has_market():
    market_list = MarketList()
    market_name = 'test_market'
    seller_participant = MarketParticipant(SELLER, 'agent_id')
    market_list.make_reservation(market_name, seller_participant)
    assert market_list.has_market(market_name) == True


@pytest.mark.market
def test_market_participants_market_not_formed_no_market():
    market_list = MarketList()
    market_name = 'test_market'
    assert market_list.has_market_formed(market_name) == False


@pytest.mark.market
def test_market_participants_market_not_formed_one_seller():
    market_list = MarketList()
    market_name = 'test_market'
    seller_participant = MarketParticipant(SELLER, 'agent_id')
    market_list.make_reservation(market_name, seller_participant)
    assert market_list.has_market_formed(market_name) == False


@pytest.mark.market
def test_market_participants_market_bad_seller_argument():
    market_list = MarketList()
    market_name = 'test_market'
    with pytest.raises(ValueError) as error_info:
        bad_participant = MarketParticipant('bob is cool', 'agent_id')
        market_list.make_reservation(market_name, bad_participant)
    assert 'bob is cool' in error_info.value.message


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

