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
    from gridappsd.simulation import Simulation
    from gridappsd import topics as t
    import stomp
    HAS_GAPPSD = True
except ImportError:
    HAS_GAPPSD = False
    RuntimeError('GridAPPSD must be installed before running this script ')

import os
import logging
import gevent
import weakref

from volttron.platform.agent.base_simulation_integration.base_sim_integration import BaseSimIntegration

_log = logging.getLogger(__name__)
__version__ = '1.0'


class GridAPPSDSimIntegration(BaseSimIntegration):
    """
    The class is responsible for integration with GridAPPSD co-simulation platform.
    It provides integration support to register configuration, start, stop, publish,
    receive messages, pause and resume simulation
    """
    def __init__(self, config, pubsub):
        super(GridAPPSDSimIntegration, self).__init__(config)
        self._work_callback = None
        self.config = config
        self.gridappsd = None
        self.sim = None
        self.event_callbacks = {}
        self.topic_callbacks = {}
        self.sim_id = None

    def register_inputs(self, config=None, callback=None):
        """
        Register configuration parameters with GridAppsD.
        The config parameters may include but not limited to:
        - power_system_config
        - application_config
        - simulation_config
        - test_config
        - service_configs
        : Register agent callback method
        :return:
        """
        self.config = config
        self._work_callback = callback

    def register_event_callbacks(self, callbacks={}):
        """
        Register for event callbacks for event notifications such as
        - on measurement change
        - on timestep change
        - on finish
        """
        _log.debug("Registering for event callbacks")
        self.event_callbacks = callbacks

    def register_topic_callbacks(self, callbacks={}):
        """
        Register for any simulation topic callbacks
        """
        _log.debug("Registering for topic callbacks")
        self.topic_callbacks = callbacks

    def start_simulation(self):
        """
        Simulation start activities involve:
        - Creating GridAppsD connection gevent thread
        - Registering for event callbacks (if specified)
        - Registering for topic callbacks if specified
        - Starting simulation based on the input config
        :return:
        """
        try:
            self.gridappsd = GridAPPSD(override_threading=self.receiver_thread)

            _log.debug('Gridappsd connected')

            _log.debug(f"connection config is: {self.config}")
            self.sim = Simulation(self.gridappsd, self.config)

            _log.debug('Gridappsd adding onstart callback')
            # Register for onstart callback to know if simulation has started
            self.sim.add_onstart_callback(self.sim_on_start)
            # Register event callbacks - on measurement, on timestep, on finish
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

            # Starting GridAppsD simulation
            self.sim.start_simulation()
            _log.debug(f"Gridappsd simulation id: {self.sim.simulation_id}")
        except stomp.exception.NotConnectedException as ex:
            _log.error("Unable to connect to GridAPPSD: {}".format(ex))
            raise ex

    def sim_on_start(self, sim):
        """
        Simulation on start callback to get notified when simulation starts
        """
        _log.debug(f"GridAppsD simulation id inside sim_on_start(): {sim.simulation_id}")
        self.sim_id = sim.simulation_id

    def receiver_thread(self, arg):
        """
        GridAPPSD connection thread
        """
        self._receiver_thread = gevent.threading.Thread(group=None, target=arg)
        self._receiver_thread.daemon = True  # Don't let thread prevent termination
        self._receiver_thread.start()
        _log.debug('Gridappsd receiver_thread started!')
        return self._receiver_thread

    def publish_to_simulation(self, topic, message):
        """
        Publish message to GridAppsD
        :param topic: GridAppsD publication topic
        :param message: message
        :return:
        """
        self.gridappsd.send(topic, message)

    def pause_simulation(self, timeout=None):
        """
        Pause the GridAppsD simulation
        """
        if timeout is None:
            self.sim.pause()
        else:
            self.sim.pause(timeout)

    def resume_simulation(self):
        """
        Resume the GridAppsD simulation
        """
        self.sim.resume()

    def is_sim_installed(self):
        """
        Flag to indicate if GridAppsD is installed
        """
        return HAS_GAPPSD

    def stop_simulation(self):
        """
        Stop the simulation if running and disconnect from GridAppsD server
        :return:
        """
        _log.debug('Stopping the simulation')
        try:
            if self.sim_id is not None:
                self.sim.stop()
            _log.debug('Disconnect GridAppsd')
            if self.gridappsd is not None:
                self.gridappsd.disconnect()
        except Exception:
            _log.error("Error stop GridAPPSD simulation")


