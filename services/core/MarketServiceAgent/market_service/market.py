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
ACCEPT_RESERVATIONS_HAS_FORMED = 'accept_resevations_market_has_formed'
ACCEPT_OFFERS = 'accept_offers'
ACCEPT_BUY_OFFERS = 'accept_buy_offers'
ACCEPT_SELL_OFFERS = 'accept_sell_offers'
WAIT_FOR_CLEAR = 'wait_for_clear'
WAIT_FOR_RESERVATIONS = 'wait_for_reservations'

import logging
from volttron.platform.agent import utils
from market_service.offer_manager import OfferManager
from market_service.reservation_manager import ReservationManager
from volttron.platform.agent.base_market_agent.buy_sell import BUYER, SELLER

_log = logging.getLogger(__name__)
utils.setup_logging()

class MarketFailureError(StandardError):
    """Base class for exceptions in this module."""
    def __init__(self, market_name, market_state, object_type):
        super(MarketFailureError, self).__init__('The market {} is not accepting {} '
                                                 'at this time. The state is {}.'.format(market_name,
                                                 object_type, market_state))


class Market(object):

    def __init__(self, market_name, participant):
        self.reservations = ReservationManager()
        self.offers = OfferManager()
        self.market_name = market_name
        self.set_initial_state(ACCEPT_RESERVATIONS)
        self.make_reservation(participant)

    def make_reservation(self, participant):
        if self.market_state != ACCEPT_RESERVATIONS:
            raise MarketFailureError(self.market_name, self.market_state, 'reservations')

        self.reservations.make_reservation(participant)
        if self.has_market_formed():
            self.change_state(ACCEPT_RESERVATIONS_HAS_FORMED)


    def make_offer(self, participant, curve):
        if self.market_state not in [ACCEPT_OFFERS, ACCEPT_BUY_OFFERS, ACCEPT_SELL_OFFERS]:
            raise MarketFailureError(self.market_name, self.market_state, 'offers')


        aggregate_curve = None
        self.reservations.take_reservation(participant)
        self.offers.make_offer(participant.buyer_seller, curve)
        if self.all_satisfied(participant.buyer_seller):
            self.change_state(self._next_offer_state(participant))
            aggregate_curve = self.offers.aggregate_curves(participant.buyer_seller)
        return aggregate_curve

    def collect_offers(self):
        if self.market_state == ACCEPT_RESERVATIONS_HAS_FORMED:
            self.change_state(ACCEPT_OFFERS)
        elif self.market_state == ACCEPT_RESERVATIONS:
            self.change_state(WAIT_FOR_RESERVATIONS)
        else:
            self.log_market_failure('Programming error in Market class. State of {} and collect offers signal arrived. This represents a logic error.'.format(self.market_state))
            self.change_state(WAIT_FOR_RESERVATIONS)

    def clear_market(self):
        price = None
        quantity = None
        error_message = None
        if (self.market_state in [ACCEPT_OFFERS, ACCEPT_BUY_OFFERS, ACCEPT_SELL_OFFERS]):
            error_message = 'The market {} failed to recieve all the expected offers. The state is {}.'.format(self.market_name, self.market_state)
        elif (self.market_state != WAIT_FOR_CLEAR):
            error_message = 'Programming error in Market class. State of {} and clear market signal arrived. This represents a logic error.'.format(self.market_state)
        else:
            if not self.has_market_formed():
                error_message = 'The market {} has not received a buy and a sell reservation.'.format(self.market_name)
            else:
                self.change_state(WAIT_FOR_RESERVATIONS)
                quantity, price = self.offers.settle()
                if price is None:
                    error_message = "Error: The supply and demand curves do not intersect. The market {} failed to clear.".format(self.market_name)

        _log.debug("Clearing price for Market: {} Price: {} Qty: {} Error: {}".format(self.market_name, price, quantity, error_message))
        return [quantity, price, error_message]

    def reject_reservation(self, participant):
        self.log_market_failure('The market {} is not accepting reservations at this time. The state is {}.'.format(self.market_name, self.market_state))

    def reject_offer(self, participant):
        self.log_market_failure('The market {} is not accepting offers at this time. The state is {}.'.format(self.market_name, self.market_state))

    def has_market_formed(self):
        return self.reservations.has_market_formed()

    def _next_offer_state(self, participant):
        if self.market_state == ACCEPT_OFFERS:
            next_state = ACCEPT_BUY_OFFERS if participant.is_buyer else ACCEPT_SELL_OFFERS
        elif self.market_state == ACCEPT_BUY_OFFERS and participant.is_seller:
            next_state = WAIT_FOR_CLEAR
        elif self.market_state == ACCEPT_SELL_OFFERS and participant.is_buyer:
            next_state = WAIT_FOR_CLEAR
        else:
            self.log_market_failure('Programming error in Market class. State of {} and completed {} offers. This represents a logic error.'.format(self.market_state, participant.buyer_seller))
        return next_state

    def log_market_failure(self, message):
        _log.debug(message)
        raise MarketFailureError(message)

    def set_initial_state(self, new_state):
        message = "Market {} is entering its state: {}.".format(self.market_name, new_state)
        self.log_andChange_state(message, new_state)

    def log_andChange_state(self, message, new_state):
        _log.debug(message)
        self.market_state = new_state

    def change_state(self, new_state):
        if (self.market_name != new_state):
            message = "Market {} is changing state from state: {} to state: {}.".format(self.market_name, self.market_state, new_state)
            self.log_andChange_state(message, new_state)

    def all_satisfied(self, buyer_seller):
        are_satisfied = False
        if (buyer_seller == BUYER):
            are_satisfied = self.reservations.buyer_count() == self.offers.buyer_count()
        if (buyer_seller == SELLER):
            are_satisfied = self.reservations.seller_count() == self.offers.seller_count()
        return are_satisfied

