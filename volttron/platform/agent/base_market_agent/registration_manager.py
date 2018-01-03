# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2017, Battelle Memorial Institute
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

from volttron.platform.agent import utils
from volttron.platform.agent.base_market_agent.error_codes import NOT_FORMED
from volttron.platform.agent.base_market_agent.market_registration import MarketRegistration

_log = logging.getLogger(__name__)
utils.setup_logging()

class RegistrationManager(object):
    """
    The ReservationManager manages a list of MarketReservations for the MarketAgents.
    This class exists to hide the features of the underlying collection that are not relevant to
    managing market reservations.
    """
    def __init__(self, rpc_proxy):
        """
        The initalization needs the agent to grant access to the RPC calls needed to
        communicate with the marketService.
        :param rpc_proxy: The MarketAgents that owns this object.
        """
        self.registrations = []
        self.rpc_proxy = rpc_proxy

    def make_registration(self, market_name, buyer_seller, reservation_callback, offer_callback,
                          aggregate_callback, price_callback, error_callback):
        registration = MarketRegistration(market_name, buyer_seller, reservation_callback, offer_callback,
                                          aggregate_callback, price_callback, error_callback)
        self.registrations.append(registration)

    def make_offer(self, market_name, buyer_seller, curve):
        result = False
        error_message = "Market: {} {} was not found in the local list of markets".format(market_name, buyer_seller)
        for registration in self.registrations:
            if (registration.market_name == market_name):
                result, error_message = registration.make_offer(buyer_seller, curve, self.rpc_proxy)
        return result, error_message

    def request_reservations(self, timestamp):
        for registration in self.registrations:
            registration.request_reservations(timestamp, self.rpc_proxy)

    def request_offers(self, timestamp, unformed_markets):
        for registration in self.registrations:
            if (registration.market_name not in unformed_markets):
                registration.request_offers(timestamp)
            else:
                error_message = 'The market {} has not received a buy and a sell reservation.'.format(registration.market_name)
                registration.report_error(timestamp, NOT_FORMED, error_message, {})

    def report_clear_price(self, timestamp, market_name, price, quantity):
        for registration in self.registrations:
            if (registration.market_name == market_name):
                registration.report_clear_price(timestamp, price, quantity)

    def report_aggregate(self, timestamp, market_name, buyer_seller, aggregate_curve):
        for registration in self.registrations:
            if (registration.market_name == market_name):
                registration.report_aggregate(timestamp, buyer_seller, aggregate_curve)

    def report_error(self, timestamp, market_name, error_code, error_message, aux):
        for registration in self.registrations:
            if (registration.market_name == market_name):
                registration.report_error(timestamp, error_code, error_message, aux)
