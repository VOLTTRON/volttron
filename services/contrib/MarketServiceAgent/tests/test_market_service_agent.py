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

import os
import json
import gevent
import pytest

from market_service.market_participant import MarketParticipant
from volttron.platform.agent.base_market_agent.buy_sell import BUYER
from volttron.platform.messaging.health import STATUS_GOOD
from volttron.platform import get_services_core

"""
Integration tests for Market Service Agent
"""


@pytest.mark.market
def test_default_config(volttron_instance):
    """
    Test the default configuration file included with the agent
    """
    publish_agent = volttron_instance.build_agent(identity="test_agent")
    gevent.sleep(1)

    config_path = os.path.join(get_services_core("MarketServiceAgent"), "config")
    with open(config_path, "r") as config_file:
        config_json = json.load(config_file)
    assert isinstance(config_json, dict)
    volttron_instance.install_agent(
        agent_dir=get_services_core("MarketServiceAgent"),
        config_file=config_json,
        start=True,
        vip_identity="health_test")
    assert publish_agent.vip.rpc.call("health_test", "health.get_status").get(timeout=10).get('status') == STATUS_GOOD

    # perform basic sanity check
    market_name = 'test_market'
    buyer_participant = MarketParticipant(BUYER, 'agent_id1')

    publish_agent.vip.rpc.call("health_test", "make_reservation", market_name, buyer_participant.buyer_seller)
