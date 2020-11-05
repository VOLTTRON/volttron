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

import logging

from volttron.platform.agent import utils
from .market import Market

_log = logging.getLogger(__name__)
utils.setup_logging()


class NoSuchMarketError(Exception):
    """Base class for exceptions in this module."""
    pass


class MarketList(object):
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
