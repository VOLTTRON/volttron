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

from __future__ import absolute_import

import logging
import sys

from volttron.platform.messaging.health import STATUS_GOOD
from volttron.platform.vip.agent import Agent, Core, PubSub
from volttron.platform.agent import utils

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '3.2'
DEFAULT_MESSAGE = 'Listener Message'
DEFAULT_AGENTID = "listener"
DEFAULT_HEARTBEAT_PERIOD = 5


class ListenerAgent(Agent):
    """Listens to everything and publishes a heartbeat according to the
    heartbeat period specified in the settings module.
    """

    def __init__(self, config_path, **kwargs):
        super(ListenerAgent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
        self._agent_id = self.config.get('agentid', DEFAULT_AGENTID)
        self._message = self.config.get('message', DEFAULT_MESSAGE)
        self._heartbeat_period = self.config.get('heartbeat_period',
                                                 DEFAULT_HEARTBEAT_PERIOD)
        try:
            self._heartbeat_period = int(self._heartbeat_period)
        except:
            _log.warn('Invalid heartbeat period specified setting to default')
            self._heartbeat_period = DEFAULT_HEARTBEAT_PERIOD
        log_level = self.config.get('log-level', 'INFO')
        if log_level == 'ERROR':
            self._logfn = _log.error
        elif log_level == 'WARN':
            self._logfn = _log.warn
        elif log_level == 'DEBUG':
            self._logfn = _log.debug
        else:
            self._logfn = _log.info

    @Core.receiver('onsetup')
    def onsetup(self, sender, **kwargs):
        # Demonstrate accessing a value from the config file
        _log.info(self.config.get('message', DEFAULT_MESSAGE))
        self._agent_id = self.config.get('agentid')

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        _log.debug("VERSION IS: {}".format(self.core.version()))
        if self._heartbeat_period != 0:
            self.vip.heartbeat.start_with_period(self._heartbeat_period)
            self.vip.health.set_status(STATUS_GOOD, self._message)

    @PubSub.subscribe('pubsub', '')
    def on_match(self, peer, sender, bus, topic, headers, message):
        """Use match_all to receive all messages and print them out."""

        # Define an int register count on fake-driver csv config, increase the count by one each time it get called
        update_val = self.test('fake-campus/fake-building/fake-device', 'Count')
        print(update_val)

        # Define the modbus_test driver for master_driver agent, do set point for all registers
        self.set_point('modbus_test', 'BigUShort', 1234)
        self.set_point('modbus_test', 'BigUInt', 141141)
        self.set_point('modbus_test', 'BigULong', 9999999)
        self.set_point('modbus_test', 'BigShort', -1000)
        self.set_point('modbus_test', 'BigInt', -20000)
        self.set_point('modbus_test', 'BigFloat', -100.3345)
        self.set_point('modbus_test', 'BigLong', -898989)
        self.set_point('modbus_test', 'LittleUShort', 1234)
        self.set_point('modbus_test', 'LittleUInt', 141141)
        self.set_point('modbus_test', 'LittleULong', 9999999)
        self.set_point('modbus_test', 'LittleShort', -1000)
        self.set_point('modbus_test', 'LittleInt', -20000)
        self.set_point('modbus_test', 'LittleFloat', -100.3345)
        self.set_point('modbus_test', 'LittleLong', -898989)
        print ('MODBUS TEST', self.scrape_all('modbus_test'))

        # Define watts_on_1 (slave id 1) and watts_on_2 (slave id 2) for master_driver agent, do scrape_all
        print ('SLAVE ID 1', self.scrape_all('watts_on_1'))
        print ('SLAVE ID 2', self.scrape_all('watts_on_2'))

        # Define modbus_tk_test driver for master_driver agent, do set point, get point, and scrape_all
        print self.set_point('modbus_tk_test', 'unsigned short', 1234)
        print self.get_point('modbus_tk_test', 'unsigned short')
        print self.scrape_all('modbus_tk_test')


    def get_config(self, driver_name):
        return self.vip.rpc.call('platform.driver', 'config', driver_name).get()

    def get_point(self, driver_name, point_name):
        return self.vip.rpc.call('platform.driver', 'get_point', driver_name, point_name).get()

    def set_point(self, driver_name, point_name, point_value):
        return self.vip.rpc.call('platform.driver', 'set_point', driver_name, point_name, point_value).get()

    def scrape_all(self, driver_name):
        return self.vip.rpc.call('platform.driver', 'scrape_all', driver_name).get()

    def test(self, driver_name, point_name):
        point_value = self.get_point(driver_name, point_name)
        self.set_point(driver_name, point_name, (point_value + 1) % 1000)
        return self.scrape_all(driver_name)


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(ListenerAgent, version=__version__)
    except Exception as e:
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())