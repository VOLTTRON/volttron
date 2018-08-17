# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
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

import sys
from csv import DictWriter

import logging
import argparse

from bacpypes.object import get_datatype
from bacpypes.primitivedata import (Enumerated, Unsigned, Boolean, Integer,
                                    Real, Double)
import gevent
from gevent.event import AsyncResult

from volttron.platform import get_address, get_home
from volttron.platform.agent import utils
from volttron.platform.agent.bacnet_proxy_reader import BACnetReader
from volttron.platform.keystore import KeyStore
from volttron.platform.messaging import topics
from volttron.platform.vip.agent import Agent, PubSub, errors
from volttron.platform.vip.agent.utils import build_agent
from volttron.platform.jsonrpc import RemoteError


utils.setup_logging()
_log = logging.getLogger(__name__)


def bacnet_response(context, results):
    """ Response function used as a callback.

    This function is used during the retrieval of bacnet responses.

    :param context:
    :param results:
    :return:
    """
    global config_writer
    _log.debug("Handling bacnet responses: RESULTS: {}".format(results))
    message = dict(results=results)
    if context is not None:
        message.update(context)
    # Handle the last return value of the bacnet_reader which signals the
    # end of the batch by forgetting it because there will be no results
    # for any of the cells.  We just check the 'Reference Point Name' here
    # however.
    if message['results'].get('Reference Point Name', None):
        config_writer.writerow(message['results'])


def main():
    global agent
    global config_writer
    # parse the command line arguments
    arg_parser = argparse.ArgumentParser(description=__doc__)

    arg_parser.add_argument("device_id", type=int,
                            help="Device ID of the target device" )

    arg_parser.add_argument("--address",
                            help="Address of target device, may be needed to help route initial request to device." )

    arg_parser.add_argument("--registry-out-file", type=argparse.FileType('wb'),
                            help="Output registry to CSV file",
                            default=sys.stdout )

    arg_parser.add_argument("--driver-out-file", type=argparse.FileType('wb'),
                            help="Output driver configuration to JSON file.",
                            default=sys.stdout)

    arg_parser.add_argument("--max-range-report", nargs='?', type=float,
                            help='Affects how very large numbers are reported in the "Unit Details" column of the output. '
                            'Does not affect driver behavior.',
                            default=1.0e+20 )

    arg_parser.add_argument("--proxy-id",
                            help="VIP IDENTITY of the BACnet proxy agent.",
                            default="platform.bacnet_proxy")

    args = arg_parser.parse_args()

    _log.debug("initialization")
    _log.debug("    - args: %r", args)

    key_store = KeyStore()
    config_writer = DictWriter(args.registry_out_file,
                              ('Reference Point Name',
                               'Volttron Point Name',
                               'Units',
                               'Unit Details',
                               'BACnet Object Type',
                               'Property',
                               'Writable',
                               'Index',
                               'Write Priority',
                               'Notes'))

    config_writer.writeheader()

    agent = build_agent(address=get_address(),
                        volttron_home=get_home(),
                        publickey=key_store.public,
                        secretkey=key_store.secret,
                        enable_store=False)

    bn = BACnetReader(agent.vip, args.proxy_id, bacnet_response)

    async_result = AsyncResult()

    try:
        bn.get_iam(args.device_id, async_result.set, args.address)
    except errors.Unreachable:
        msg = "No BACnet proxy Agent running on the platform with the " \
              "VIP IDENTITY {}".format(args.proxy_id)
        sys.exit(1)

    try:
        results = async_result.get(timeout=5.0)
    except gevent.Timeout:
        _log.error("No response from device id {}".format(args.device_id))
        sys.exit(1)

    if args.address and args.address != results["address"]:
        msg = "Inconsistent results from passed address " \
              "({}) and device address ({}) using results.".format(
            args.address, results["address"])
        _log.warning(msg)
        args.address = results["address"]
    elif results["address"]:
        args.address = results["address"]

    bn.read_device_properties(target_address=args.address,
                              device_id=args.device_id)

    agent.core.stop()


try:
    main()
except Exception, e:
    _log.exception("an error has occurred: %s", e)
finally:
    _log.debug("finally")




