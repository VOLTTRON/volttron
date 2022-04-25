# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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

"""
This script watches a temp file for volttron_home to change.  When it changes, this
script will attempt to connect and execute peerlist on the platform after every
10th of a second.

Execute the following in an activated shell:

    python debugging_utils/peerlist-watcher.py

In another shell echo the volttron home to the proper file.


"""
import os
from pathlib import Path
from typing import Optional

import gevent

from volttron.platform.keystore import KeyStore
from volttron.platform.vip.agent import Agent
from volttron.platform.vip.agent.utils import build_agent


def get_volttron_home():
    if Path("/tmp/volttron_home.txt").exists():
        with open("/tmp/volttron_home.txt") as fp:
            return fp.read().strip()
    return None


def get_public_private_key(volttron_home):
    ks = KeyStore()
    return ks.public, ks.secret


volttron_home = get_volttron_home()
last_output = ""

agent: Optional[Agent] = None
while True:
    new_volttron_home = get_volttron_home()
    if new_volttron_home is not None and new_volttron_home != volttron_home:
        if agent:
            agent.core.stop()
            agent = None
        volttron_home = new_volttron_home

        os.environ['VOLTTRON_HOME'] = volttron_home
        public, secret = get_public_private_key(volttron_home)
        last_output = f"Attempting connection {volttron_home}"
        print(last_output)
        agent = build_agent(volttron_home=volttron_home,
                            identity="peer.finder",
                            publickey=public,
                            secretkey=secret,
                            serverkey=public)

    if agent:
        try:
            with gevent.Timeout(5):
                next_last_output = f"Peerlist: {agent.vip.peerlist().get()}"
                if next_last_output != last_output:
                    last_output = next_last_output
                    print(last_output)
        except gevent.Timeout:
            agent.core.stop()
            agent = None
    else:
        next_last_output = "waiting on file."
        if next_last_output != last_output:
            last_output = next_last_output
            print(last_output)

    gevent.sleep(0.1)

