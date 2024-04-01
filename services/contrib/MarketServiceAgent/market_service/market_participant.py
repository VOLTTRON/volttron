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

from volttron.platform.agent.base_market_agent.buy_sell import BUYER, SELLER


class MarketParticipant:
    def __init__(self, buyer_seller, identity):
        self.buyer_seller = buyer_seller
        self.identity = identity
        if not self.is_buyer() and not self.is_seller():
            raise ValueError('expected either %s or %s, but got %s instead.' % (BUYER, SELLER, buyer_seller))

    def is_buyer(self):
        return self.buyer_seller == BUYER

    def is_seller(self):
        return self.buyer_seller == SELLER
