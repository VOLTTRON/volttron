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


__docformat__ = 'reStructuredText'

from gevent.monkey import patch_all
patch_all()

import gevent
import stomp
import logging
import sys
from gridappsd import topics as t
import yaml
from volttron.platform.messaging import headers as headers_mod
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC
from integrations.gridappsd_integration import GridAPPSDSimIntegration

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"


def gridappsd_example(config_path, **kwargs):
    """Parses the Agent configuration and returns an instance of
    the agent created using that configuration.

    :param config_path: Path to a configuration file.

    :type config_path: str
    :returns: GridappsdExample
    :rtype: GridappsdExample
    """
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}
    _log.debug("CONFIG: {}".format(config))
    if not config:
        _log.info("Using Agent defaults for starting configuration.")

    return GridappsdExample(config, **kwargs)


class GridappsdExample(Agent):
    """
    GridappsdExampleAgent demonstrates how VOLTTRON agent can interact with
    Gridappsd simulation environment
    """

    def __init__(self, config, **kwargs):
        super(GridappsdExample, self).__init__(enable_store=False, **kwargs)
        _log.debug("vip_identity: " + self.core.identity)
        self.config = config
        self.Gridappsd_sim = GridAPPSDSimIntegration(config, self.vip.pubsub)
        self.volttron_subscriptions = None
        self.sim_complete = False
        self.rcvd_measurement = False
        self.rcvd_first_measurement = 0
        self.are_we_paused = False
        self.sim_complete = True
        self.sim_running = False

    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        """
        Subscribe to VOLTTRON topics on VOLTTRON message bus.
        Register config parameters with Gridappsd.
        Start Gridappsd simulation.
        """
        # subscribe to the VOLTTRON topics if given.
        if self.volttron_subscriptions is not None:
            for sub in self.volttron_subscriptions:
                _log.info('Subscribing to {}'.format(sub))
                self.vip.pubsub.subscribe(peer='pubsub',
                                          prefix=sub,
                                          callback=self.on_receive_publisher_message)

        # Exit if GridAPPSD isn't installed in the current environment.
        if not self.Gridappsd_sim.is_sim_installed():
            _log.error("GridAPPSD module is unavailable please add it to the python environment.")
            self.core.stop()
            return

        try:
            # Register events with GridAPPSD
            # There are 4 event callbacks that GridAPPSD provides to monitor the status
            # - onstart, ontimestep, onmesurement, oncomplete
            # This example shows how to register with GridAPPSD simulation to get
            # event notifications
            event_callbacks = {'MEASUREMENT': self.onmeasurement,
                               "TIMESTEP": self.ontimestep,
                               "FINISH": self.onfinishsimulation}
            self.Gridappsd_sim.register_event_callbacks(event_callbacks)

            # Register the config file with GridAPPS-D
            self.Gridappsd_sim.register_inputs(self.config, self.do_work)
            # Start the simulation
            self.Gridappsd_sim.start_simulation()

            # Waiting for simulation to start
            i = 1
            while not self.Gridappsd_sim.sim_id and i < 20:
                _log.debug(f"waiting for simulation to start {i}")
                gevent.sleep(1)
                i += 1

            # Subscribe to GridAPPSD log messages
            if self.Gridappsd_sim.sim_id:
                self.Gridappsd_sim.gridappsd.subscribe(
                    t.simulation_log_topic(self.Gridappsd_sim.sim_id),
                    self.on_message)
                self.sim_running = True
            else:
                self.sim_running = False
                _log.debug("Simulation did not start")
        except stomp.exception.NotConnectedException as ex:
            _log.error("Unable to connect to GridAPPSD: {}".format(ex))
            _log.error("Exiting!!")
            self.core.stop()
        except ValueError as ex:
            _log.error("Unable to register inputs with GridAPPSD: {}".format(ex))
            self.core.stop()
            return

    def do_work(self):
        """
        Dummy callback for GridAPPS-D sim
        Unused
        :return:
        """
        pass
        
    def on_receive_publisher_message(self, peer, sender, bus, topic, headers, message):
        """
        Subscribe to publisher publications and change the data accordingly 
        """                 
        # Update controller data 
        val = message[0]
        # Do something with message

    @Core.receiver("onstop")
    def onstop(self, sender, **kwargs):
        """
        This method is called when the Agent is about to shutdown.
        Disconnect from GridAPPSD simulation
        """
        if self.sim_running:
            self.Gridappsd_sim.stop_simulation()

    def onmeasurement(self, sim, timestep, measurements):
        """
        Callback method to receive measurements
        :param sim: simulation object
        :param timestep: time step
        :param measurements: measurement value
        :return:
        """
        _log.info('Measurement received at %s', timestep)

        if not self.are_we_paused and not self.rcvd_first_measurement:
            _log.debug("Pausing sim now")
            self.Gridappsd_sim.pause_simulation()
            self.are_we_paused = True
            _log.debug(f"ARWEPAUSED {self.are_we_paused}")
            # Setting up so if we get another measurement while we
            # are paused we know it
            self.rcvd_measurement = False
            # Resume simulation after 30 sec
            self.core.spawn_later(30, self.resume_gridappsd_simulation)

        if not self.rcvd_measurement:
            print(f"A measurement {measurements} happened at {timestep}")
            data = {"data": measurements}

            headers = {
                headers_mod.DATE: utils.format_timestamp(utils.get_aware_utc_now()),
                headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.JSON
            }
            # Publishing measurement on VOLTTRON message bus
            self.vip.pubsub.publish(peer='pubsub',
                                    topic='gridappsd/measurement',
                                    message=data,
                                    headers=headers)
            self.rcvd_measurement = True
        else:
            self.rcvd_measurement = True
        self.rcvd_first_measurement = True

    def ontimestep(self, sim, timestep):
        """
        Event callback for timestep change
        :param sim:
        :param timestep:
        :return:
        """
        _log.debug("Timestamp: {}".format(timestep))

    def onfinishsimulation(self, sim):
        """
        Event callback to get notified when simulation has completed
        :param sim:
        :return:
        """
        self.sim_complete = True
        _log.info('Simulation Complete')

    def resume_gridappsd_simulation(self):
        """
        Resume simulation if paused
        :return:
        """
        if self.are_we_paused:
            _log.debug('Resuming simulation')
            self.Gridappsd_sim.resume_simulation()
            _log.debug('Resumed simulation')
            self.are_we_paused = False

    def on_message(self, headers, message):
        """
        Callback method to receive GridAPPSD log messages
        :param headers: headers
        :param message: log message
        :return:
        """
        try:
            _log.debug("Received GridAPPSD log message: {}".format(message))
            json_msg = yaml.safe_load(str(message))

            if "PAUSED" in json_msg["processStatus"]:
                _log.debug("GridAPPSD simulation has paused!!")

            if "resume" in json_msg["logMessage"]:
                _log.debug("GridAPPSD simulation has resumed!!")

        except Exception as e:
            message_str = "An error occurred while trying to translate the  message received" + str(e)


def main():
    """Main method called to start the agent."""
    utils.vip_main(gridappsd_example, version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
