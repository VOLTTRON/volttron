# -*- coding: utf-8 -*-
# {{{
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

import time
import helics as h
import logging
import argparse
import random

logger = logging.getLogger(__name__)


def destroy_federate(fed):
    """
    fed: federate to destroy
    """
    h.helicsFederateFinalize(fed)
    h.helicsFederateFree(fed)
    h.helicsCloseLibrary()


def federate_example(config_path):
    # Registering  federate from json

    try:
        fed = h.helicsCreateCombinationFederateFromConfig(config_path)
    except h._helics.HelicsException as exc:
        print("Exception occured".format(exc))
        exit(-1)
    federate_name = h.helicsFederateGetName(fed)
    print(federate_name)
    endpoint_count = h.helicsFederateGetEndpointCount(fed)
    subkeys_count = h.helicsFederateGetInputCount(fed)
    pubkeys_count = h.helicsFederateGetPublicationCount(fed)

    # Reference to Publications and Subscription form index
    endid = {}
    subid = {}
    pubid = {}
    for i in range(0,endpoint_count):
        endid["m{}".format(i)] = h.helicsFederateGetEndpointByIndex(fed, i)
        end_name = h.helicsEndpointGetName(endid["m{}".format(i)])
        logger.info( 'Registered Endpoint ---> {}'.format(end_name))

    for i in range(0, subkeys_count):
        idx = h.helicsFederateGetInputByIndex(fed, i)
        subid["m{}".format(i)] = idx
        status = h.helicsInputSetDefaultComplex(subid["m{}".format(i)], 0, 0)
        sub_key = h.helicsSubscriptionGetKey(idx)
        logger.info( 'Registered Subscription ---> {}'.format(sub_key))

    for i in range(0, pubkeys_count):
        idx = h.helicsFederateGetPublicationByIndex(fed, i)
        pubid["m{}".format(i)] = idx
        pub_key = h.helicsPublicationGetKey(idx)
        logger.info( 'Registered Publications ---> {}'.format(pub_key))

    print('###############################################################################################')
    print('########################   Entering Execution Mode  ##########################################')
    # Entering Execution Mode
    h.helicsFederateEnterExecutingMode(fed)
    print('###############################################################################################')

    hours = 0.1
    total_inteval = int(60 * 60 * hours)
    grantedtime = -1
    update_interval = 1 # 5*60
    k = 0
    data ={}
    time.sleep(5)
    time_sim = []
    real = 0
    for t in range(0, total_inteval, update_interval):
        while grantedtime < t:
            grantedtime = h.helicsFederateRequestTime (fed, t)
        time.sleep(0.1)
        print('########################   Time interval {}  ##########################################'.format(t))
        print('########################   Publishing to topics  ######################################')
        real = real + 1
        for i in range(0, pubkeys_count):
            idx = pubid["m{}".format(i)]
            h.helicsPublicationPublishComplex(idx, real*i, 78)

        print( '########################   Get input from subscribed topics  #########################')
        for i in range(0, subkeys_count):
            idx = subid["m{}".format(i)]
            value = h.helicsInputGetDouble(idx)
            key = h.helicsSubscriptionGetKey(idx)
            print("Value for key: {} is {}".format(key, value))

        print('########################   Get from Endpoint  #########################################')
        idx = endid["m{}".format(0)]
        while h.helicsEndpointHasMessage(idx):            
            msg = h.helicsEndpointGetMessage(idx)
            end_name = h.helicsEndpointGetName(idx)
            print("Value from endpoint name: {} is {}".format(end_name, msg.data))

        print('########################   Send to VOLTTRON Endpoint  #################################')
        for i in range(0, endpoint_count):
            idx = endid["m{}".format(i)]
            value = i + random.randint(1, 101) + 89.7
            end_name = h.helicsEndpointGetName(idx)
            print("Sending Value:{0} for endpoint: {1}".format(value, end_name))
            h.helicsEndpointSendEventRaw(idx, '', str(value), t)
            end_name = h.helicsEndpointGetName(idx)

    logger.info("Destroying federate")
    destroy_federate(fed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('config_path',
                        help='path of the config file')
    args = parser.parse_args()
    try:
        federate_example(args.config_path)
    except KeyboardInterrupt:
        logger.info("Exiting due to keyboard interrupt")
