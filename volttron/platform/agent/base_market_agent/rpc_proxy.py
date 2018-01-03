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
import gevent

from volttron.platform.agent import utils
from volttron.platform.agent.known_identities import PLATFORM_MARKET_SERVICE
from volttron.platform.jsonrpc import RemoteError

_log = logging.getLogger(__name__)
utils.setup_logging()

class RpcProxy(object):
    """
    The purpose of the RpcProxy is to allow the MarketRegistration to make
    RPC calls on the agent that subclasses of the agent can't see and therefore
    can't make.
    """
    def __init__(self, rpc_call, verbose_logging = True):
        """
        The initalization needs the rpc_call method to grant access to the RPC calls needed to
        communicate with the marketService.
        :param rpc_call: The MarketAgent owns this object.
        """
        self.rpc_call = rpc_call
        self.verbose_logging = verbose_logging

    def make_reservation(self, market_name, buyer_seller):
        """
        This call makes a reservation with the MarketService.  This allows the agent to submit a bid and receive
        a cleared market price.

        :param market_name: The name of the market commodity.

        :param buyer_seller: A string indicating whether the agent is buying from or selling to the market.
        The agent shall use the pre-defined strings provided.
        """
        try:
            self.rpc_call(PLATFORM_MARKET_SERVICE, 'make_reservation', market_name, buyer_seller).get(timeout=5.0)
            has_reservation = True
        except RemoteError as e:
            has_reservation = False
        except gevent.Timeout as e:
            has_reservation = False
        return has_reservation

    def make_offer(self, market_name, buyer_seller, curve):
        """
        This call makes an offer with the MarketService.

        :param market_name: The name of the market commodity.

        :param buyer_seller: A string indicating whether the agent is buying from or selling to the market.
        The agent shall use the pre-defined strings provided.

        :param curve: The demand curve for buyers or the supply curve for sellers.
        """
        try:
            self.rpc_call(PLATFORM_MARKET_SERVICE, 'make_offer', market_name, buyer_seller,
                              curve.tuppleize()).get(timeout=5.0)
            result = (True, None)
            if self.verbose_logging:
                _log.debug("Market: {} {} has made an offer Curve: {}".format(market_name,
                                                                                       buyer_seller,
                                                                                       curve.points))
        except RemoteError as e:
            result = (False, e.message)
            _log.info(
                "Market: {} {} has had an offer rejected because {}".format(market_name, buyer_seller, e.message))
        except gevent.Timeout as e:
            result = (False, e.message)
            _log.info("Market: {} {} has had an offer rejected because {}".format(market_name, buyer_seller, e.message))
        return result


