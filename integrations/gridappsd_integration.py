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

try:
    from gridappsd import GridAPPSD
    HAS_GAPPSD = True
except ImportError:
    HAS_GAPPSD = False
    RuntimeError('GridAPPSD must be installed before running this script ')

import os
import logging
import gevent
import weakref
from volttron.platform.agent.base_simulation_integration.base_sim_integration import BaseSimIntegration

# tm: added for run_simulation workaround
from gridappsd.simulation import Simulation
from .gridappsd_docker import docker_up, docker_down
from gridappsd import topics as t

_log = logging.getLogger(__name__)
__version__ = '1.0'


class GridAPPSDSimIntegration(BaseSimIntegration):
    """
    The class is responsible for integration with GridAPPSD co-simulation platform
    """
    def __init__(self, config, pubsub):
        super(GridAPPSDSimIntegration, self).__init__(config)
        self._work_callback = None
        self._simulation_started = False
        self._simulation_complete = False
        self._simulation_delta = None
        self._simulation_length = None
        self.current_time = 0
        self.current_values = {}
        self.gridappsd = None
        self.sim = None
        self.event_callbacks = {}
        self.topic_callbacks = {}
        self.sim_id = None

    def register_inputs(self, config=None, callback=None):
        """
        Register configuration parameters with HELICS. The config parameters may include
        but not limited to:
        1. Name of the federate
        2. simulation length
        2. Type of core to use (zmq/tcp/udp etc)
        3. list (and type) of subscriptions
        4. list (and type) of publications
        5. broker address (if not default)
        :param config: config parameters
        :param callback: Register agent callback method
        :return:
        """
        self.config = config
        self._work_callback = callback

    def register_event_callbacks(self, callbacks={}):
        _log.debug("Registering for event callbacks")
        self.event_callbacks = callbacks

    def register_topic_callbacks(self, callbacks={}):
        topic_callbacks = callbacks

    def start_simulation(self):
        """
        This is a blocking call until the all the federates get connected to HELICS broker
        :return:
        """
        _log.debug("Docker up!")
        #docker_up(None)
        _log.debug('Containers started')
        self.gridappsd = GridAPPSD(override_threading=self.receiver_thread)

        _log.debug('Gridappsd connected')
        # Register event callbacks - on measurement, on timestep, on finish
        _log.debug(f"connection config is: {self.config}")
        self.sim = Simulation(self.gridappsd, self.config)
        _log.debug('Gridappsd adding onstart callback')

        self.sim.add_onstart_callback(self.sim_on_start)
        for name, cb in self.event_callbacks.items():
            if name == 'MEASUREMENT':
                _log.debug('Gridappsd adding measurement callback')
                self.sim.add_onmesurement_callback(cb)
            elif name == 'TIMESTEP':
                _log.debug('Gridappsd adding timestep callback')
                self.sim.add_ontimestep_callback(cb)
            elif name == 'FINISH':
                _log.debug('Gridappsd adding finish callback')
                self.sim.add_oncomplete_callback(cb)

        # Register/Subscribe for simulation topics
        for topic, cb in self.topic_callbacks:
            _log.debug('Gridappsd subscribing to topics callback')
            self.gridappsd.subscribe(topic, cb)

    def sim_on_start(self, sim):
        _log.debug(f"GridAppsD simulation id: {sim.simulation_id}")
        self.sim_id = sim.simulation_id

    def receiver_thread(self, arg):
        self._receiver_thread = gevent.threading.Thread(group=None, target=arg)
        self._receiver_thread.daemon = True  # Don't let thread prevent termination
        self._receiver_thread.start()
        _log.debug('Gridappsd receiver_thread started!')
        return self._receiver_thread

    def publish_to_simulation(self, topic, message):
        """
        Publish message on HELICS bus
        :param topic: HELICS publication key
        :param message: message
        :return:
        """
        self.gridappsd.send(self._test_topic, "foo bar")

    def pause_simulation(self, timeout):
        self.sim.pause()

    def resume_simulation(self):
        self.sim.resume()

    def is_sim_installed(self):
        return HAS_GAPPSD

    def stop_simulation(self):
        """
        Disconnect the federate from helics core and close the library
        :return:
        """
        _log.debug('Disconnect GridAppsd')
        self.gridappsd.disconnect()
        #docker_down()
        _log.debug('Containers stopped')

