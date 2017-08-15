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
import sys

from volttron.platform.agent.known_identities import PLATFORM_MARKET_SERVICE
from volttron.platform.agent import utils
from volttron.platform.messaging.topics import MARKET_RESERVE, MARKET_BID, MARKET_ERROR
from volttron.platform.vip.agent import Agent, Core, RPC
from market_service.director import Director
from market_service.market_list import MarketList
from market_service.market_participant import MarketParticipant
from volttron.platform.agent.base_market_agent.poly_line_factory import PolyLineFactory

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.01"


def market_service_agent(config_path, **kwargs):
    """Parses the Market Service Agent configuration and returns an instance of
    the agent created using that configuation.

    :param config_path: Path to a configuation file.

    :type config_path: str
    :returns: Market Service Agent
    :rtype: MarketServiceAgent
    """
    _log.debug("Starting MarketServiceAgent")
    try:
        config = utils.load_config(config_path)
    except StandardError:
        config = {}

    if not config:
        _log.info("Using Market Service Agent defaults for starting configuration.")

    market_period = int(config.get('market_period', 300))
    reservation_delay = int(config.get('reservation_delay', 0))
    offer_delay = int(config.get('offer_delay', 120))
    clear_delay = int(config.get('clear_delay', 120))

    return MarketServiceAgent(market_period, reservation_delay, offer_delay, clear_delay, **kwargs)


class MarketServiceAgent(Agent):
    def __init__(self, market_period=300, reservation_delay=0, offer_delay=120, clear_delay=120, **kwargs):
        super(MarketServiceAgent, self).__init__(**kwargs)

        _log.debug("vip_identity: {0}".format(self.core.identity))
        _log.debug("market_period: {0}".format(market_period))
        _log.debug("reservation_delay: {0}".format(reservation_delay))
        _log.debug("offer_delay: {0}".format(offer_delay))
        _log.debug("clear_delay: {0}".format(clear_delay))

        self.director = Director(market_period, reservation_delay, offer_delay, clear_delay)

    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        self.market_list = MarketList(self.vip.pubsub.publish)
        self.director.start(self)

    def send_collect_reservations_request(self, timestamp):
        _log.debug("send_collect_reservations_request at {}".format(timestamp))
        self.market_list.clear_reservations()
        self.vip.pubsub.publish(peer='pubsub',
                                topic=MARKET_RESERVE,
                                message=utils.format_timestamp(timestamp))

    def send_collect_offers_request(self, timestamp):
        _log.debug("send_collect_offers_request at {}".format(timestamp))
        self.market_list.collect_offers()
        self._send_unformed_market_errors(timestamp)
        self.vip.pubsub.publish(peer='pubsub',
                                topic=MARKET_BID,
                                message=utils.format_timestamp(timestamp))

    def send_clear_request(self, timestamp):
        _log.debug("send_clear_request at {}".format(timestamp))
        self.market_list.clear_market(timestamp)

    @RPC.export
    def make_reservation(self, market_name, buyer_seller):
        identity = bytes(self.vip.rpc.context.vip_message.peer)
        log_message = "Received {0} reservation for market {1} from {2}".format(buyer_seller, market_name, identity)
        _log.debug(log_message)
        participant = MarketParticipant(buyer_seller, identity)
        self.market_list.make_reservation(market_name, participant)

    @RPC.export
    def make_offer(self, market_name, buyer_seller, offer):
        identity = bytes(self.vip.rpc.context.vip_message.peer)
        log_message = "Received {0} offer for market {1} from {2}".format(buyer_seller, market_name, identity)
        _log.debug(log_message)
        participant = MarketParticipant(buyer_seller, identity)
        curve = PolyLineFactory.fromTupples(offer)
        self.market_list.make_offer(market_name, participant, curve)

    def _send_unformed_market_errors(self, timestamp):
        unformed_markets = self.market_list.unformed_market_list()
        for market_name in unformed_markets:
            log_message = "Sent unformed market error for market {0}".format(market_name)
            _log.debug(log_message)
            self.vip.pubsub.publish(peer='pubsub',
                                    topic=MARKET_ERROR,
                                    message=[timestamp, 'Market %s did not form.'.format(market_name)])


def main():
    """Main method called to start the agent."""
    utils.vip_main(market_service_agent, identity=PLATFORM_MARKET_SERVICE,
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
