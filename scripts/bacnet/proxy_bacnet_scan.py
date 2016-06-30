# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2015, Battelle Memorial Institute
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
#}}}

import sys
import argparse
from csv import DictWriter

import logging
import argparse

import gevent
import os
from volttron.platform.vip.agent import Agent, PubSub
from volttron.platform.messaging import topics
from volttron.platform.agent import utils


from pprint import pprint

utils.setup_logging()
_log = logging.getLogger(__name__)

if "VOLTTRON_HOME" not in os.environ:
    os.environ["VOLTTRON_HOME"] = '`/.volttron'

class BACnetInteraction(Agent):
    def __init__(self, callback, *args):
        super(BACnetInteraction, self).__init__(*args)
        self.callbacks = {}
    def send_iam(self, low_device_id=None, high_device_id=None, address=None):
        self.vip.rpc.call("platform.bacnet_proxy", "who_is",
                           low_device_id=low_device_id,
                           high_device_id=high_device_id,
                           target_address=address).get(timeout=5.0)

    @PubSub.subscribe('pubsub', topics.BACNET_I_AM)
    def iam_handler(self, peer, sender, bus,  topic, headers, message):
        pprint(message)

agent = BACnetInteraction("bacnet_interaction")
gevent.spawn(agent.core.run).join(0)

"""
Simple utility to scrape device registers and write them to a configuration file.
"""



def main():
    # parse the command line arguments
    arg_parser = argparse.ArgumentParser(description=__doc__)

    arg_parser.add_argument("--address",
                            help="Target only device(s) at <address> for request")


    arg_parser.add_argument("--range", type=int, nargs=2, metavar=('LOW', 'HIGH'),
                            help="Lower and upper limit on device ID in results")

    arg_parser.add_argument("--timeout", type=int, metavar=('SECONDS'),
                            help="Time, in seconds, to wait for responses. Default: %(default)s",
                            default=5)
    
    args = arg_parser.parse_args()

    _log.debug("initialization")
    _log.debug("    - args: %r", args)


    _log.debug("starting build")

    kwargs = {'address': args.address}

    if args.range is not None:
        kwargs['low_device_id'] = int(args.range[0])
        kwargs['high_device_id'] = int(args.range[1])

    agent.send_iam(**kwargs)

    gevent.sleep(args.timeout)
        
try:
    main()
except Exception, e:
    _log.exception("an error has occurred: %s", e)
finally:
    _log.debug("finally")
    

    

