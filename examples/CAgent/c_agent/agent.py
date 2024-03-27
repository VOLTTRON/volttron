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


from ctypes import CDLL, cdll, c_float
from datetime import datetime
import logging
import os
import sys

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
