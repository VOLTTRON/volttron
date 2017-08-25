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
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
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

from volttron.platform.agent import utils
from volttron.platform.messaging.topics import MARKET_AGGREGATE, MARKET_CLEAR, MARKET_ERROR
from market_service.market import Market

class NoSuchMarketError(StandardError):
    """Base class for exceptions in this module."""
    pass

class MarketList(object):
    def __init__(self, publish = None):
        self.markets = {}
        self.publish = publish

    def make_reservation(self, market_name, participant):
        if self.has_market(market_name):
            market = self.markets[market_name]
            market.make_reservation(participant)
        else:
            market = Market(market_name, participant)
            self.markets[market_name] = market

    def make_offer(self, market_name, participant, curve):
        market = self.get_market(market_name)
        aggregate_curve = market.make_offer(participant, curve)
        if aggregate_curve is not None:
            timestamp = self._get_time()
            timestamp_string = utils.format_timestamp(timestamp)
            self.publish(peer='pubsub',
                                topic=MARKET_AGGREGATE,
                                message=[timestamp_string, aggregate_curve.tuppleize()])

    def clear_reservations(self):
        self.markets.clear()

    def collect_offers(self):
        for market in self.markets.itervalues():
            market.collect_offers()

    def clear_market(self, timestamp):
        timestamp_string = utils.format_timestamp(timestamp)
        for market in self.markets.itervalues():
            cleared_quantity, cleared_price, error_message = market.clear_market()
            if cleared_price is not None and cleared_quantity is not None:
                self.publish(peer='pubsub',
                             topic=MARKET_CLEAR,
                             message=[timestamp_string, cleared_quantity, cleared_price])
            elif error_message is not None:
                self.publish(peer='pubsub',
                             topic=MARKET_ERROR,
                             message=[timestamp_string, error_message])

    def get_market(self, market_name):
        if self.has_market(market_name):
            market = self.markets[market_name]
        else:
            raise NoSuchMarketError('Market %s does not exist.' % market_name)
        return market

    def has_market(self, market_name):
        return self.markets.has_key(market_name)

    def has_market_formed(self, market_name):
        market_has_formed = False
        if self.has_market(market_name):
            market = self.markets[market_name]
            market_has_formed = market.has_market_formed()
        return market_has_formed

    def market_count(self):
        return len(self.markets)

    def unformed_market_list(self):
        list = []
        for market in self.markets.itervalues():
           if not market.has_market_formed:
               list << market.market_name
        return list

    def _get_time(self):
        now = utils.get_aware_utc_now()
        return now

