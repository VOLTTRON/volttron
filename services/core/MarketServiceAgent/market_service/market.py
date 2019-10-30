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

ACCEPT_RESERVATIONS = 'market_accept_resevations'
ACCEPT_RESERVATIONS_HAS_FORMED = 'market_accept_resevations_market_has_formed'
ACCEPT_ALL_OFFERS = 'market_accept_all_offers'
ACCEPT_BUY_OFFERS = 'market_accept_buy_offers'
ACCEPT_SELL_OFFERS = 'market_accept_sell_offers'
MARKET_DONE = 'market_done'

import logging
from transitions import Machine
from volttron.platform.agent import utils
from market_service.offer_manager import OfferManager
from market_service.reservation_manager import ReservationManager
from volttron.platform.agent.base_market_agent.error_codes import NOT_FORMED, SHORT_OFFERS, BAD_STATE, NO_INTERSECT
from volttron.platform.agent.base_market_agent.buy_sell import BUYER, SELLER
from volttron.platform.messaging.topics import MARKET_AGGREGATE, MARKET_CLEAR, MARKET_ERROR, MARKET_RECORD

_tlog = logging.getLogger('transitions.core')
_tlog.setLevel(logging.WARNING)
_log = logging.getLogger(__name__)
utils.setup_logging()

class MarketFailureError(Exception):
    """Base class for exceptions in this module."""
    def __init__(self, market_name, market_state, object_type):
        super(MarketFailureError, self).__init__('The market {} is not accepting {} '
                                                 'at this time. The state is {}.'.format(market_name,
                                                 object_type, market_state))


class Market(object):
    states = [ACCEPT_RESERVATIONS, ACCEPT_RESERVATIONS_HAS_FORMED, ACCEPT_ALL_OFFERS, ACCEPT_BUY_OFFERS, ACCEPT_SELL_OFFERS, MARKET_DONE]
    transitions = [
        {'trigger': 'receive_reservation', 'source': ACCEPT_RESERVATIONS, 'dest': ACCEPT_RESERVATIONS},
        {'trigger': 'market_forms', 'source': ACCEPT_RESERVATIONS, 'dest': ACCEPT_RESERVATIONS_HAS_FORMED},
        {'trigger': 'start_offers', 'source': ACCEPT_RESERVATIONS, 'dest': MARKET_DONE},
        {'trigger': 'receive_buy_offer', 'source': ACCEPT_RESERVATIONS, 'dest': MARKET_DONE},
        {'trigger': 'receive_sell_offer', 'source': ACCEPT_RESERVATIONS, 'dest': MARKET_DONE},

        {'trigger': 'receive_reservation', 'source': ACCEPT_RESERVATIONS_HAS_FORMED, 'dest': ACCEPT_RESERVATIONS_HAS_FORMED},
        {'trigger': 'start_offers', 'source': ACCEPT_RESERVATIONS_HAS_FORMED, 'dest': ACCEPT_ALL_OFFERS},
        {'trigger': 'receive_buy_offer', 'source': ACCEPT_RESERVATIONS_HAS_FORMED, 'dest': MARKET_DONE},
        {'trigger': 'receive_sell_offer', 'source': ACCEPT_RESERVATIONS_HAS_FORMED, 'dest': MARKET_DONE},

        {'trigger': 'receive_reservation', 'source': ACCEPT_ALL_OFFERS, 'dest': ACCEPT_ALL_OFFERS},
        {'trigger': 'receive_sell_offer', 'source': ACCEPT_ALL_OFFERS, 'dest': ACCEPT_ALL_OFFERS},
        {'trigger': 'receive_buy_offer', 'source': ACCEPT_ALL_OFFERS, 'dest': ACCEPT_ALL_OFFERS},
        {'trigger': 'last_sell_offer', 'source': ACCEPT_ALL_OFFERS, 'dest': ACCEPT_BUY_OFFERS},
        {'trigger': 'last_buy_offer', 'source': ACCEPT_ALL_OFFERS, 'dest': ACCEPT_SELL_OFFERS},

        {'trigger': 'receive_reservation', 'source': ACCEPT_BUY_OFFERS, 'dest': ACCEPT_BUY_OFFERS},
        {'trigger': 'receive_sell_offer', 'source': ACCEPT_BUY_OFFERS, 'dest': ACCEPT_BUY_OFFERS},
        {'trigger': 'receive_buy_offer', 'source': ACCEPT_BUY_OFFERS, 'dest': ACCEPT_BUY_OFFERS},
        {'trigger': 'last_buy_offer', 'source': ACCEPT_BUY_OFFERS, 'dest': MARKET_DONE},

        {'trigger': 'receive_reservation', 'source': ACCEPT_SELL_OFFERS, 'dest': ACCEPT_SELL_OFFERS},
        {'trigger': 'receive_sell_offer', 'source': ACCEPT_SELL_OFFERS, 'dest': ACCEPT_SELL_OFFERS},
        {'trigger': 'receive_buy_offer', 'source': ACCEPT_SELL_OFFERS, 'dest': ACCEPT_SELL_OFFERS},
        {'trigger': 'last_sell_offer', 'source': ACCEPT_SELL_OFFERS, 'dest': MARKET_DONE},

        {'trigger': 'receive_reservation', 'source': MARKET_DONE, 'dest': MARKET_DONE},
        {'trigger': 'receive_sell_offer', 'source': MARKET_DONE, 'dest': MARKET_DONE},
        {'trigger': 'receive_buy_offer', 'source': MARKET_DONE, 'dest': MARKET_DONE},
    ]

    def __init__(self, market_name, participant, publish, verbose_logging = True):
        self.reservations = ReservationManager()
        self.offers = OfferManager()
        self.market_name = market_name
        self.publish = publish
        self.verbose_logging = verbose_logging
        _log.debug("Initializing Market: {} {} verbose logging is {}.".format(self.market_name,
                   participant.buyer_seller, self.verbose_logging))
        self.state_machine = Machine(model=self, states=Market.states,
                                     transitions= Market.transitions, initial=ACCEPT_RESERVATIONS)
        self.make_reservation(participant)

    def make_reservation(self, participant):
        if self.verbose_logging:
            _log.debug("Make reservation Market: {} {} entered in state {}".format(self.market_name,
                                                                                   participant.buyer_seller,
                                                                                   self.state))
        self.receive_reservation()
        market_already_formed = self.has_market_formed()
        if self.state not in [ACCEPT_RESERVATIONS, ACCEPT_RESERVATIONS_HAS_FORMED]:
            raise MarketFailureError(self.market_name, self.state, 'reservations')
        self.reservations.make_reservation(participant)
        if self.verbose_logging:
            if participant.buyer_seller == BUYER:
                reservation_count = self.reservations.buyer_count()
            else:
                reservation_count = self.reservations.seller_count()
            _log.debug("Make reservation Market: {} {} now has {} reservations.".format(self.market_name,
                       participant.buyer_seller, reservation_count))
        if not market_already_formed and self.has_market_formed():
            self.market_forms()
        if self.verbose_logging:
            _log.debug("Make reservation Market: {} {} exited in state {}".format(self.market_name,
                                                                                  participant.buyer_seller,
                                                                                  self.state))


    def make_offer(self, participant, curve):
        if self.verbose_logging:
            _log.debug("Make offer Market: {} {} entered in state {}".format(self.market_name,
                                                                             participant.buyer_seller,
                                                                             self.state))
        if (participant.buyer_seller == SELLER):
            self.receive_sell_offer()
        else:
            self.receive_buy_offer()
        if self.state not in [ACCEPT_ALL_OFFERS, ACCEPT_BUY_OFFERS, ACCEPT_SELL_OFFERS]:
            raise MarketFailureError(self.market_name, self.state, 'offers')
        self.reservations.take_reservation(participant)
        if self.verbose_logging:
            if participant.buyer_seller == BUYER:
                offer_count = self.offers.buyer_count()
            else:
                offer_count = self.reservations.seller_count()
            _log.debug("Make offer Market: {} {} now has {} offers. Curve: {}".format(self.market_name,
                       participant.buyer_seller, offer_count, curve.tuppleize()))
        self.offers.make_offer(participant.buyer_seller, curve)
        if self.all_satisfied(participant.buyer_seller):
            if (participant.buyer_seller == SELLER):
                self.last_sell_offer()
            else:
                self.last_buy_offer()
            aggregate_curve = self.offers.aggregate_curves(participant.buyer_seller)
            if self.verbose_logging:
                _log.debug("Report aggregate Market: {} {} Curve: {}".format(self.market_name,
                           participant.buyer_seller, aggregate_curve.tuppleize()))
            if aggregate_curve is not None:
                timestamp = self._get_time()
                timestamp_string = utils.format_timestamp(timestamp)
                self.publish(peer='pubsub',
                             topic=MARKET_AGGREGATE,
                             message=[timestamp_string, self.market_name,
                                      participant.buyer_seller, aggregate_curve.tuppleize()])
            if self.is_market_done():
                self.clear_market()
        if self.verbose_logging:
            _log.debug("Make offer Market: {} {} exited in state {}".format(self.market_name,
                                                                             participant.buyer_seller,
                                                                             self.state))

    def collect_offers(self):
        self.start_offers()

    def clear_market(self):
        price = None
        quantity = None
        error_code = None
        error_message = None
        aux = {}
        if (self.state in [ACCEPT_ALL_OFFERS, ACCEPT_BUY_OFFERS, ACCEPT_SELL_OFFERS]):
            error_code = SHORT_OFFERS
            error_message = 'The market {} failed to recieve all the expected offers. The state is {}.'.format(self.market_name, self.state)
        elif (self.state != MARKET_DONE):
            error_code = BAD_STATE
            error_message = 'Programming error in Market class. State of {} and clear market signal arrived. This represents a logic error.'.format(self.state)
        else:
            if not self.has_market_formed():
                error_code = NOT_FORMED
                error_message = 'The market {} has not received a buy and a sell reservation.'.format(self.market_name)
            else:
                quantity, price, aux = self.offers.settle()
                if price is None:
                    error_code = NO_INTERSECT
                    error_message = "Error: The supply and demand curves do not intersect. The market {} failed to clear.".format(self.market_name)
        _log.info("Clearing price for Market: {} Price: {} Qty: {}".format(self.market_name, price, quantity))
        timestamp = self._get_time()
        timestamp_string = utils.format_timestamp(timestamp)
        self.publish(peer='pubsub',
                     topic=MARKET_CLEAR,
                     message=[timestamp_string, self.market_name, quantity, price])
        self.publish(peer='pubsub',
                     topic=MARKET_RECORD,
                     message=[timestamp_string, self.market_name, quantity, price])
        if error_message is not None:
            self.publish(peer='pubsub',
                         topic=MARKET_ERROR,
                         message=[timestamp_string, self.market_name, error_code, error_message, aux])

    def has_market_formed(self):
        return self.reservations.has_market_formed()

    def log_market_failure(self, message):
        _log.debug(message)
        raise MarketFailureError(message)

    def all_satisfied(self, buyer_seller):
        are_satisfied = False
        if (buyer_seller == BUYER):
            are_satisfied = self.reservations.buyer_count() == self.offers.buyer_count()
        if (buyer_seller == SELLER):
            are_satisfied = self.reservations.seller_count() == self.offers.seller_count()
        return are_satisfied

    def _get_time(self):
        now = utils.get_aware_utc_now()
        return now

