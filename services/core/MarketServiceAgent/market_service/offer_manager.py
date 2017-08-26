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

from volttron.platform.agent.base_market_agent.buy_sell import BUYER
from volttron.platform.agent.base_market_agent.poly_line import PolyLine
from volttron.platform.agent.base_market_agent.poly_line_factory import PolyLineFactory

class OfferManager(object):

    def __init__(self):
        self._buy_offers = []
        self._sell_offers = []
        self.increment = 100

    def make_offer(self, buyer_seller, curve):
        if (buyer_seller == BUYER):
            self._buy_offers.append(curve)
        else:
            self._sell_offers.append(curve)

    def aggregate_curves(self, buyer_seller):
        if (buyer_seller == BUYER):
            curve = self._aggregate(self._buy_offers)
        else:
            curve = self._aggregate(self._sell_offers)
        return curve

    def _aggregate(self, collection):
        curve = PolyLineFactory.combine(collection, self.increment)
        return curve

    def settle(self):
        error_message = ""
        enough_buys = len(self._buy_offers) > 0
        enough_sells = len(self._sell_offers) > 0
        if enough_buys:
            demand_curve = self._aggregate(self._buy_offers)
        else:
            error_message += "There are no buy offers."
        if enough_sells:
            supply_curve = self._aggregate(self._sell_offers)
        else:
            error_message += "There are no sell offers."

        if enough_buys and enough_sells:
            intersection = PolyLine.intersection(demand_curve, supply_curve)
        else:
            intersection = None

        if intersection is not None:
            price = intersection[1]
            quantity = intersection[0]
        else:
            price = None
            quantity = None

        return quantity, price, error_message

    def buyer_count(self):
        return len(self._buy_offers)

    def seller_count(self):
        return len(self._sell_offers)

