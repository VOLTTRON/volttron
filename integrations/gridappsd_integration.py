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
from exceptions import ImportError, RuntimeError

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
from volttron.platform import jsonapi
from copy import deepcopy

_log = logging.getLogger(__name__)
__version__ = '1.0'


class GridAPPSDSimIntegration(BaseSimIntegration):
    """
    The class is responsible for integration with GridAPPSD co-simulation platform
    """
    def __init__(self, config, pubsub):
        super(GridAPPSDSimIntegration, self).__init__(config)
        self.pubsub = weakref.ref(pubsub)
        self.fed = None
        self._work_callback = None
        self._simulation_started = False
        self._simulation_complete = False
        self._simulation_delta = None
        self._simulation_length = None
        self.current_time = 0
        self.inputs = []
        self.outputs = {}
        self.endpoints = {}
        self.current_values = {}

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
        self._work_callback = callback


    def start_simulation(self):
        """
        This is a blocking call until the all the federates get connected to HELICS broker
        :return:
        """

        _log.debug("Spawning simulation loop to HELICS events")
        gevent.spawn(self._sim_loop)
        # Allow the spawned greenlet to run.
        gevent.sleep(0.1)


    def _sim_loop(self):
        """
        Continuous loop to get registered input values from HELICS and feed it to user callback
        :return:
        """


    def publish_to_simulation(self, topic, message):
        """
        Publish message on HELICS bus
        :param topic: HELICS publication key
        :param message: message
        :return:
        """


    def _publish_based_on_type(self, output):
        """
        Publish message based on type
        :param output:
        :return:
        """


    def _get_input_based_on_type(self, in_put):
        """
        Get input based on type
        :param in_put:
        :return:
        """

    def make_time_request(self, time_request=None):
        """
        Request for next time step. Granted time maybe lower than the requested time
        :param time_request:
        :return:
        """


    def pause_simulation(self):
        pass

    def resume_simulation(self):
        pass

    def is_sim_installed(self):
        return HAS_GAPPSD


    def stop_simulation(self):
        """
        Disconnect the federate from helics core and close the library
        :return:
        """


