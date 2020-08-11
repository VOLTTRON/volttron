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



from ctypes import *
from datetime import datetime
import logging
import sys
import os

from volttron.platform.vip.agent import Agent, Core, PubSub, compat
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod
from volttron.platform.scheduling import periodic

__docformat__ = 'reStructuredText'
__version__ = '1.0'

"""This example agent calls functions from a shared object via
the ctypes module. The shared object must be built with make before
installing.
"""

utils.setup_logging()
_log = logging.getLogger(__name__)

PUBLISH_PERIOD = 1

class CAgent(Agent):
    def __init__(self, config_path, **kwargs):
        super(CAgent, self).__init__(**kwargs)

        so_filename = __file__.rsplit('/', 1)[0] + '/' + 'libfoo.so'

        cdll.LoadLibrary(so_filename)
        self.shared_object = CDLL(so_filename)

        self.get_water_temperature = self.shared_object.get_water_temperature
        self.get_water_temperature.restype = c_float

    @Core.schedule(periodic(PUBLISH_PERIOD))
    def publish_water_temperature(self):
        """Call the function from the shared object.
        """
        wt = self.get_water_temperature()
        _log.debug(wt)
        self.vip.pubsub.publish('pubsub', 'device/WATER_TEMP=' + str(wt))

def main():
    utils.vip_main(CAgent, version=__version__)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
