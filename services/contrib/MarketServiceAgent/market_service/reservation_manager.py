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


class MarketReservationError(Exception):
    """Base class for exceptions in this module."""
    pass


class ReservationManager:

    def __init__(self):
        self._buy_reservations = {}
        self._sell_reservations = {}

    def make_reservation(self, participant):
        if participant.is_buyer():
            self._make_buy_reservation(participant.identity)
        else:
            self._make_sell_reservation(participant.identity)

    def _make_buy_reservation(self, owner):
        self._add_reservation(self._buy_reservations, owner, 'buy')

    def _add_reservation(self, collection, owner, type):
        if owner not in collection:
            collection[owner] = False
        else:
            message = 'Market participant {0} made more than a single {1} reservation.'.format(owner, type)
            raise MarketReservationError(message)

    def _make_sell_reservation(self, owner):
        self._add_reservation(self._sell_reservations, owner, 'sell')

    def take_reservation(self, participant):
        if participant.is_buyer():
            self._take_buy_reservation(participant.identity)
        else:
            self._take_sell_reservation(participant.identity)

    def _take_buy_reservation(self, owner):
        self._take_reservation(self._buy_reservations, owner, 'buy')

    def _take_sell_reservation(self, owner):
        self._take_reservation(self._sell_reservations, owner, 'sell')

    def _take_reservation(self, collection, owner, type):
        if owner in collection and not collection[owner]:
            collection[owner] = True
        else:
            message = 'Market participant {0} made no {1} reservation.'.format(owner, type)
            raise MarketReservationError(message)

    def has_market_formed(self):
        has_buyer  = len(self._buy_reservations) > 0
        has_seller = len(self._sell_reservations) > 0
        return has_buyer and has_seller

    def buyer_count(self):
        return len(self._buy_reservations)

    def seller_count(self):
        return len(self._sell_reservations)
