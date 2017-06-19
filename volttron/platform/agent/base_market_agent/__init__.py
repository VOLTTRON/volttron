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

import logging

from volttron.platform.agent.known_identities import PLATFORM_MARKET_SERVICE
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Core, PubSub
from volttron.platform.vip.agent import Agent
from volttron.platform.messaging.topics import MARKET_RESERVE, MARKET_BID, MARKET_CLEAR, MARKET_AGGREGATE, MARKET_ERROR
from volttron.platform.agent.base_market_agent.market_registration import MarketRegistration

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.01"


class MarketAgent(Agent):
    def __init__(self, **kwargs):
        super(MarketAgent, self).__init__(**kwargs)
        _log.debug("vip_identity: " + self.core.identity)
        self.registrations = []

    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        pass

    @PubSub.subscribe('pubsub', MARKET_RESERVE)
    def match_reservation(self, peer, sender, bus, topic, headers, message):
        for registration in self.registrations:
            timestamp = message[0]
            wants_reservation = registration.request_reservations(timestamp)
            if wants_reservation:
                self.vip.rpc.call(PLATFORM_MARKET_SERVICE, 'reserve_market',
                                  registration.market_name, registration.buyer_seller)

    @PubSub.subscribe('pubsub', MARKET_BID)
    def match_make_offer(self, peer, sender, bus, topic, headers, message):
        for registration in self.registrations:
            timestamp = message[0]
            registration.request_offers(timestamp)

    @PubSub.subscribe('pubsub', MARKET_CLEAR)
    def match_clear_price(self, peer, sender, bus, topic, headers, message):
        for registration in self.registrations:
            timestamp = message[0]
            price = message[1]
            quantity = message[2]
            registration.request_clear_price(timestamp, price, quantity)

    @PubSub.subscribe('pubsub', MARKET_AGGREGATE)
    def match_make_offer(self, peer, sender, bus, topic, headers, message):
        for registration in self.registrations:
            timestamp = message[0]
            aggregate_curve = message[1]
            registration.report_aggregate(timestamp, aggregate_curve)

    @PubSub.subscribe('pubsub', MARKET_ERROR)
    def match_make_offer(self, peer, sender, bus, topic, headers, message):
        for registration in self.registrations:
            timestamp = message[0]
            error_message = message[1]
            registration.report_error(timestamp, error_message)

    def join_market (self, market_name, buyer_seller, reservation_callback,
                     offer_callback, aggregate_callback, price_callback, error_callback):
        registration = MarketRegistration(market_name, buyer_seller,
                                          reservation_callback, offer_callback,
                                          aggregate_callback, price_callback, error_callback)
        self.registrations.append(registration)

