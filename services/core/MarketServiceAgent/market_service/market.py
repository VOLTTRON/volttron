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

ACCEPT_RESERVATIONS = 'accept_resevations'
ACCEPT_OFFERS = 'accept_offers'
ACCEPT_BUY_OFFERS = 'accept_buy_offers'
ACCEPT_SELL_OFFERS = 'accept_sell_offers'
WAIT_FOR_CLEAR = 'wait_for_clear'
WAIT_FOR_RESERVATIONS = 'wait_for_reservations'

from market_service.offer_manager import OfferManager
from market_service.reservation_manager import ReservationManager
from volttron.platform.agent.base_market_agent.buy_sell import BUYER, SELLER

class MarketFailureError(StandardError):
    """Base class for exceptions in this module."""
    def __init__(self, market_name, market_state, object_type):
        super(MarketFailureError, self).__init__('The market %s is not accepting %s '
                                                 'at this time. The state is %s.' % market_name,
                                                 object_type, market_state)


class Market(object):

    def __init__(self, market_name, participant):
        self.reservations = ReservationManager()
        self.offers = OfferManager()
        self.market_name = market_name
        self.market_state = ACCEPT_RESERVATIONS
        self.make_reservation(participant)

    def make_reservation(self, participant):
        if self.market_state != ACCEPT_RESERVATIONS:
            raise MarketFailureError(self.market_name, self.market_state, 'reservations')

        self.reservations.make_reservation(participant)

    def make_offer(self, participant, curve):
        if self.market_state not in [ACCEPT_OFFERS, ACCEPT_BUY_OFFERS, ACCEPT_SELL_OFFERS]:
            raise MarketFailureError(self.market_name, self.market_state, 'offers')


        aggregate_curve = None
        self.reservations.take_reservation(participant)
        self.offers.make_offer(participant.buyer_seller, curve)
        if self.reservations.all_satisfied(participant.buyer_seller):
            self.market_state = self.next_offer_state(participant.buyer_seller)
            aggregate_curve = self.offers.aggregate_curves(participant.buyer_seller)
        return aggregate_curve

    def collect_offers(self):
        self.market_state = ACCEPT_OFFERS

    def clear_market(self):
        cleared_price = None
        error_message = None
        if (self.market_state in [ACCEPT_OFFERS, ACCEPT_BUY_OFFERS, ACCEPT_SELL_OFFERS]):
            error_message = 'The market %s failed to recieve all the expected offers. The state is %s.' % \
                            self.market_name, self.market_state
        elif (self.market_state != WAIT_FOR_CLEAR):
            error_message = 'Programming error in Market class. State of $s and clear market signal arrived. ' \
                            'This represents a logic error.', self.market_state
        else:
            if not self.has_market_formed():
                error_message = 'The market %s has not received a buy and a sell reservation.' % self.market_name
            else:
                self.market_state = WAIT_FOR_RESERVATIONS
                cleared_price = self.offers.settle()

        return [cleared_price, error_message]

    def reject_reservation(self, participant):
        raise MarketFailureError('The market %s is not accepting reservations at this time. The state is %s.' %
                                 self.market_name, self.market_state)

    def reject_offer(self, participant):
        raise MarketFailureError('The market %s is not accepting offers at this time. The state is %s.' %
                                 self.market_name, self.market_state)

    def has_market_formed(self):
        return self.reservations.has_market_formed()

    def next_offer_state(self, buyer_seller):
        if self.market_state == ACCEPT_OFFERS:
            next_state = ACCEPT_BUY_OFFERS if buyer_seller == BUYER else ACCEPT_SELL_OFFERS
        elif self.market_state == ACCEPT_BUY_OFFERS and buyer_seller == SELLER:
            next_state = WAIT_FOR_CLEAR
        elif self.market_state == ACCEPT_SELL_OFFERS and buyer_seller == BUYER:
            next_state = WAIT_FOR_CLEAR
        else:
            raise MarketFailureError('Programming error in Market class. State of $s and completed %s offers. '
                                     'This represents a logic error.', self.market_state, buyer_seller)
        return next_state
