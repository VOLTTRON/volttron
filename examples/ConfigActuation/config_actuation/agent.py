# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.
#

# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization
# that has cooperated in the development of these materials, makes
# any warranty, express or implied, or assumes any legal liability
# or responsibility for the accuracy, completeness, or usefulness or
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does
# not necessarily constitute or imply its endorsement, recommendation,
# r favoring by the United States Government or any agency thereof,
# or Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

#}}}

import datetime
import logging
import os
import sys

from volttron.platform.vip.agent import Agent
from volttron.platform.agent import utils


utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.1'


class ConfigActuation(Agent):
    """
    This agent is used to demonstrate scheduling and acutation of devices
    when a configstore item is added or updated.

    .. note::

       An error is expected if the scheduled device does not exist.

    """

    def __init__(self, config_path, **kwargs):
        super(ConfigActuation, self).__init__(**kwargs)
        config = utils.load_config(config_path)

        self.vip.config.set_default("config", config)
        self.vip.config.subscribe(self.configure, actions=["NEW", "UPDATE"], pattern="config")

    def configure(self, config_name, action, contents):
        try:
            device = contents['device']
            point = contents['point']
            value = contents['value']
        except KeyError as e:
            _log.error("Missing config parameter: {}".format(e.message))
            return
        
        try:
            start = str(datetime.datetime.now())
            end = str(datetime.datetime.now() + datetime.timedelta(minutes=1))
            msg = [[device, start, end]]

            result = self.vip.rpc.call('platform.actuator',
                                       'request_new_schedule',
                                       'agent_id', # ignored by actuator
                                       'some task',
                                       'LOW',
                                       msg).get(timeout=10)
            _log.info("schedule result {}".format(result))
        except Exception as e:
            _log.warning("Could not contact actuator. Is it running?")
            print(e)
            return

        try:
            if result['result'] == 'SUCCESS':
                result = self.vip.rpc.call('platform.actuator',
                                           'set_point',
                                           'agent_id', # ignored by actuator
                                           os.path.join(device, point),
                                           value).get(timeout=10)
                _log.info("Set result {}".format(result))
        except Exception as e:
            _log.warning("Expected to fail since there is no real device to set")
            print(e)


def main(argv=sys.argv):
    utils.vip_main(ConfigActuation)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
