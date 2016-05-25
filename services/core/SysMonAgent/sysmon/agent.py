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

#}}}

import logging
import sys

import psutil

from volttron.platform.vip.agent import Agent, RPC, Core
from volttron.platform.agent import utils


utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '3.5'


def sysmon_agent(config_path, **kwargs):
    """Load the SysMon Agent configuration and returns and instance
    of the agent created using that configuration.

    :param config_path: Path to a configuration file.

    :type config_path: str
    :returns: SysMonAgent instance
    :rtype: SysMonAgent
    """
    config = utils.load_config(config_path)
    vip_identity = 'platform.sysmon'
    # Use the identity 'platform.sysmon'. Pop the uuid off the kwargs.
    kwargs.pop('identity', None)
    return SysMonAgent(config, identity=vip_identity, **kwargs)


class SysMonAgent(Agent):
    """Monitor utilization of system resources (CPU, memory, disk)

    The percent usage of each system resource can be queried via
    RPC and they are published periodically to configured topics.

    :param config: Configuration dict
    :type config: dict

    Example configuration:

    .. code-block:: python

        {
            "base_topic": "datalogger/log/platform",
            "cpu_check_interval": 5,
            "memory_check_interval": 5,
            "disk_check_interval": 5,
            "disk_path": "/"
        }
    """
    def __init__(self, config, **kwargs):
        super(SysMonAgent, self).__init__(**kwargs)
        self.base_topic = config.pop('base_topic', 'datalogger/log/platform')
        self.cpu_check_interval = config.pop('cpu_check_interval', 5)
        self.memory_check_interval = config.pop('memory_check_interval', 5)
        self.disk_check_interval = config.pop('disk_check_interval', 5)
        self.disk_path = config.pop('disk_path', '/')
        for key in config:
            _log.warn('Ignoring unrecognized cofiguration parameter %s', key)

        self._pub_greenlets = []

    def _configure(self, config):
        self.base_topic = config.pop('base_topic', self.base_topic)
        self.cpu_check_interval = config.pop('cpu_check_interval',
                                             self.cpu_check_interval)
        self.memory_check_interval = config.pop('memory_check_interval',
                                                self.memory_check_interval)
        self.disk_check_interval = config.pop('disk_check_interval',
                                              self.disk_check_interval)
        self.disk_path = config.pop('disk_path', self.disk_path)
        for key in config:
            _log.warn('Ignoring unrecognized cofiguration parameter %s', key)

    @Core.receiver('onstart')
    def start(self, sender, **kwargs):
        """Set up periodic publishing of system resource data"""
        self._start_pub()

    def _periodic_pub(self, func, period, wait=0):
        """Periodically call func and publish its return value"""
        def pub_wrapper():
            data = func()
            topic = self.base_topic + '/' + func.__name__
            self.vip.pubsub.publish(peer='pubsub', topic=topic,
                                    message=data)
        greenlet = self.core.periodic(period, pub_wrapper, wait=wait)
        self._pub_greenlets.append(greenlet)

    @RPC.export
    def cpu_percent(self):
        """Return CPU usage percentage"""
        return psutil.cpu_percent()

    @RPC.export
    def memory_percent(self):
        """Return memory usage percentage"""
        return psutil.virtual_memory().percent

    @RPC.export
    def disk_percent(self):
        """Return usage of disk mounted at configured path"""
        return psutil.disk_usage(self.disk_path).percent

    @RPC.export
    def reconfigure(self, **kwargs):
        """Reconfigure the agent"""
        self._configure(kwargs)
        self._restart()

    def _restart(self):
        self._stop_pub()
        self._start_pub()

    def _start_pub(self):
        self._periodic_pub(self.cpu_percent, self.cpu_check_interval)
        self._periodic_pub(self.memory_percent, self.memory_check_interval)
        self._periodic_pub(self.disk_percent, self.disk_check_interval)

    def _stop_pub(self):
        for greenlet in self._pub_greenlets:
            greenlet.kill()
        self._pub_greenlets = []


def main(argv=sys.argv):
    """Main method called by the platform."""
    utils.vip_main(sysmon_agent)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
