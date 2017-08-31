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

from transitions import Machine
from volttron.platform.agent import utils

_log = logging.getLogger(__name__)
utils.setup_logging()

REGISTRATION_WAIT = 'registration_wait'
OFFER_WAIT = 'registration_offer_wait'
AGGREGATE_WAIT = 'registration_aggregate_wait'
PRICE_WAIT = 'registration_price_wait'


class MarketRegistration(object):
    states = [REGISTRATION_WAIT, OFFER_WAIT, AGGREGATE_WAIT, PRICE_WAIT]
    transitions = [
        {'trigger': 'received_request_reservations', 'source': REGISTRATION_WAIT, 'dest': REGISTRATION_WAIT},
        {'trigger': 'success_reserve_with_offer', 'source': REGISTRATION_WAIT, 'dest': OFFER_WAIT},
        {'trigger': 'success_reserve_with_aggregate', 'source': REGISTRATION_WAIT, 'dest': AGGREGATE_WAIT},
        {'trigger': 'fail_reserve', 'source': REGISTRATION_WAIT, 'dest': REGISTRATION_WAIT},
        {'trigger': 'received_request_offers', 'source': REGISTRATION_WAIT, 'dest': REGISTRATION_WAIT},
        {'trigger': 'received_report_aggregate', 'source': REGISTRATION_WAIT, 'dest': REGISTRATION_WAIT},
        {'trigger': 'received_report_price', 'source': REGISTRATION_WAIT, 'dest': REGISTRATION_WAIT},

        {'trigger': 'received_request_reservations', 'source': OFFER_WAIT, 'dest': REGISTRATION_WAIT},
        {'trigger': 'received_request_offers', 'source': OFFER_WAIT, 'dest': OFFER_WAIT},
        {'trigger': 'success_offers', 'source': OFFER_WAIT, 'dest': PRICE_WAIT},
        {'trigger': 'fail_offers', 'source': OFFER_WAIT, 'dest': REGISTRATION_WAIT},
        {'trigger': 'received_report_aggregate', 'source': OFFER_WAIT, 'dest': OFFER_WAIT},
        {'trigger': 'received_report_price', 'source': OFFER_WAIT, 'dest': REGISTRATION_WAIT},

        {'trigger': 'received_request_reservations', 'source': AGGREGATE_WAIT, 'dest': REGISTRATION_WAIT},
        {'trigger': 'received_request_offers', 'source': AGGREGATE_WAIT, 'dest': AGGREGATE_WAIT},
        {'trigger': 'success_offers', 'source': AGGREGATE_WAIT, 'dest': PRICE_WAIT},
        {'trigger': 'received_report_aggregate', 'source': AGGREGATE_WAIT, 'dest': OFFER_WAIT},
        {'trigger': 'received_report_price', 'source': AGGREGATE_WAIT, 'dest': REGISTRATION_WAIT},

        {'trigger': 'received_request_reservations', 'source': PRICE_WAIT, 'dest': REGISTRATION_WAIT},
        {'trigger': 'received_request_offers', 'source': PRICE_WAIT, 'dest': REGISTRATION_WAIT},
        {'trigger': 'received_report_aggregate', 'source': PRICE_WAIT, 'dest': PRICE_WAIT},
        {'trigger': 'received_report_price', 'source': PRICE_WAIT, 'dest': REGISTRATION_WAIT},
        {'trigger': 'received_error_report', 'source': '*', 'dest': REGISTRATION_WAIT},
    ]

    def __init__(self, market_name, buyer_seller, reservation_callback, offer_callback,
                 aggregate_callback, price_callback, error_callback):
        self.market_name = market_name
        self.buyer_seller = buyer_seller
        self.reservation_callback = reservation_callback
        self.offer_callback = offer_callback
        self.aggregate_callback = aggregate_callback
        self.price_callback = price_callback
        self.error_callback = error_callback
        self.always_wants_reservation = self.reservation_callback == None
        self.has_reservation = False
        self.state_machine = Machine(model=self, states=MarketRegistration.states,
                                     transitions= MarketRegistration.transitions, initital=REGISTRATION_WAIT)
        self._validate_callbacks()

    def _validate_callbacks(self):
        if self.offer_callback is None and self.aggregate_callback is None:
            raise TypeError('You must provide either an offer callback or an aggregate callback.')
        if self.offer_callback is not None and self.aggregate_callback is not None:
            raise TypeError('You must only provide an offer callback or an aggregate callback, but not both.')

    def request_reservations(self, timestamp, agent):
        self.received_request_reservations()
        if self.is_registration_wait():
            self.has_reservation = False
            if self.reservation_callback is not None:
                wants_reservation_this_time = self.reservation_callback(timestamp, self.market_name, self.buyer_seller)
            else:
                wants_reservation_this_time = self.always_wants_reservation
            if wants_reservation_this_time:
                agent.make_reservation(self.market_name, self.buyer_seller)
                if agent.has_reservation:
                    self.has_reservation = agent.has_reservation
                    if (self.offer_callback is not None):
                        self.success_reserve_with_offer()
                    else:
                        self.success_reserve_with_aggregate()
                else:
                    self.fail_reserve()

    def request_offers(self, timestamp, agent):
        self.received_request_offers()
        if self.state_machine.state in [OFFER_WAIT, AGGREGATE_WAIT]:
            if self.state_machine.state == AGGREGATE_WAIT:
                return # ignore offers when waiting for an aggregate
            if self.has_reservation and self.offer_callback is not None:
                curve = self.offer_callback(timestamp, self.market_name, self.buyer_seller)
                if curve is not None:
                    offer_accepted, error_message = agent.make_offer(self.market_name, self.buyer_seller, curve)
                else:
                    offer_accepted = False
                    error_message = "the offer callback did not return a valid curve."
            self.check_offer_accepted(offer_accepted, error_message)

    def check_offer_accepted(self, offer_accepted, error_message):
        if offer_accepted:
            self.success_offer()
        else:
            self.fail_offer()

    def report_clear_price(self, timestamp, price, quantity):
        _log.debug("report_clear_price Timestamp: {} Price: {} Qty: {} Has Reservation: {}".format(timestamp, price, quantity, self.has_reservation))
        if self.state_machine.state != PRICE_WAIT and self.has_reservation and self.price_callback is not None:
            _log.debug("report_clear_price calling price_callback method for {} {} {} {}".format(self.market_name, self.buyer_seller, price, quantity))
            self.price_callback(timestamp, self.market_name, self.buyer_seller, price, quantity)
        self.has_reservation = False
        self.received_report_price()

    def report_aggregate(self, timestamp, aggregate_curve):
        entry_state = self.state_machine.state
        self.received_report_aggregate()
        if entry_state in [AGGREGATE_WAIT, OFFER_WAIT, PRICE_WAIT]:
            if entry_state == AGGREGATE_WAIT and self.has_reservation and self.aggregate_callback is not None:
                offer_accepted= self.aggregate_callback(timestamp, self.market_name, self.buyer_seller, aggregate_curve)
                if offer_accepted:
                    error_message = None
                else:
                    error_message = "aggregate_callback failed to get an offer accepted."
                self.check_offer_accepted(offer_accepted, error_message)

    def report_error(self, timestamp, error_message):
        if self.reportable_error(error_message):
            self.received_error_report()
        if self.error_callback is not None:
            self.error_callback(timestamp, self.market_name, self.buyer_seller, error_message)
        self.change_state(REGISTRATION_WAIT, "we got an error message")

    def reportable_error(self, error_message):
        # We need to decide what messages return us to the default start state.
        return False

