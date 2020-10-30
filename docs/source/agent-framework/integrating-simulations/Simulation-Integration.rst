 .. _Simulation-Integration:

=====================================
Integrating With Simulation Platforms
=====================================
An agent wanting to integrate with a simulation platform has to create an object of concrete simulation integration class (HELICSSimIntegration).
This is best described with an example agent. The example agent will interface with HELICS co-simulation platform. For
more info about HELICS, please refer to https://helics.readthedocs.io/en/latest/installation/linux.html.

.. code-block:: python

    class HelicsExample(Agent):
        """
        HelicsExampleAgent demonstrates how VOLTTRON agent can interact with HELICS simulation environment
        """
        def __init__(self, config, **kwargs):
            super(HelicsExample, self).__init__(enable_store=False, **kwargs)
                self.config = config
                self.helics_sim = HELICSSimIntegration(config, self.vip.pubsub)


.. _Register-Simulation:

Register With Simulation Platform
---------------------------------
The agent has to first load the configuration file containing parameters such as connection address, simulation duration, input and
output topics etc., and register with simulation platform. The concrete simulation object will then register the agent with simulation
platform (in this case, HELICS) using appropriate APIs. The registration steps include connecting to the simulation platform, passing the
input and outputs topics to the simulation etc. In addition to that, the agent has to provide a callback method in order for
the concrete simulation object to pass the messages received from the simulation to the agent. The best place to call the register_inputs API is
within the onstart method of the agent.

.. code-block:: python

    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        """
        Register config parameters with HELICS.
        Start HELICS simulation.
        """
        # Register inputs with HELICS and provide callback method to receive messages from simulation
        try:
            self.helics_sim.register_inputs(self.config, self.do_work)
        except ValueError as ex:
            _log.error("Unable to register inputs with HELICS: {}".format(ex))
            self.core.stop()
            return

Start the Simulation Platform
-----------------------------
After registering with the simulation platform, the agent can go ahead and start the simulation.

.. code-block:: python

    # Register inputs with HELICS and provide callback method to receive messages from simulation
    try:
        self.helics_sim.start_simulation()
    except ValueError as ex:
        _log.error("Unable to register inputs with HELICS: {}".format(ex))
        self.core.stop()
        return

Receive outputs from the simulation
-----------------------------------
The concrete simulation object spawns a continuous loop that waits for any incoming messages (subscription messages) from the
simulation platform. On receiving a message, it passes the message to the callback method registered by the agent during the
register with simulation step <Register-Simulation>`_. The agent can now choose to work on the incoming message based on it's use case.
The agent can also choose to publish some message back to the simulation at this point of time as shown in below example. This is
totally optional and is based on agent's usecase.
At the end of the callback method, the agent needs to make time request to the simulation, so that it can advance forward in
simulation. Please note, this is a necessary step for HELICS co-simulation integration as the HELICS broker waits for time
requests from all it's federates before advancing the simulation. If no time request is made, the broker blocks the simulation.


.. code-block:: python

    def do_work(self):
        """
        Perform application specific work here using HELICS messages
        :return:
        """
        current_values = self.helics_sim.current_values
        _log.debug("Doing work: {}".format(self.core.identity))
        _log.debug("Current set of values from HELICS: {}".format(current_values))
        # Do something with HELICS messages
        # agent specific work!!!

        for pub in self.publications:
            key = pub['sim_topic']
            # Check if VOLTTRON topic has been configured. If no, publish dummy value for the HELICS
            # publication key
            volttron_topic = pub.get('volttron_topic', None)
            if volttron_topic is None:
                value = 90.5
                global_flag = pub.get('global', False)
                # If global flag is False, prepend federate name to the key
                if not global_flag:
                    key = "{fed}/{key}".format(fed=self._federate_name, key=key)
                    value = 67.90
                self.helics_sim.publish_to_simulation(key, value)

        self.helics_sim.make_time_request()

Publish to the simulation
-------------------------
The agent can publish messages to the simulation using publish_to_simulation API. The code snippet iterates over all the publication keys (topics)
and uses publish_to_simulation API to publish a dummy value of 67.90 for every publication key.

.. code-block:: python

    for pub in self.publications:
        key = pub['sim_topic']
        value = 67.90
        self.helics_sim.publish_to_simulation(key, value)

Advance the simulation
----------------------
With some simulation platforms such as HELICS, the federate can make explicit time request to advance in time by certain
number of time steps. There will be a global time keeper (in this case HELICS broker) which will be responsible for maintaining
time within the simulation. In the time request mode, each federate has to request for time advancement after it has
completed it's work. The global time keeper grants the lowest time among all time requests. All the federates receive
the granted time and advance forward in simulation time together in a synchronized manner. Please note, the granted time
may not be the same as the requested time by the agent.

Typically, the best place to make the time request is in the callback method provided to the simulation integration object.

.. code-block:: python

    self.helics_sim.make_time_request()

Pause the simulation
--------------------
Some simulation platforms such as GridAPPS-D have the capability to pause the simulation. The agent can make use of
this functionality by calling the appropriate wrapper API exposed by the concrete simulation class. In case of HELICS,
we do not have capability of pause/resume simulation, so calling pause_simulation() API will result in no operation.

.. code-block:: python

    self.helics_sim.pause_simulation()

Resume the simulation
---------------------
If the simulation platform provides the pause simulation functionality then it will also provide capability to resume
the simulation. The agent can call resume_simulation API to resume the simulation. In case of HELICS, we do not have the
capability of pause/resume simulation, so calling resume_simulation() API will result in no operation.

.. code-block:: python

    self.helics_sim.resume_simulation()

Stop the simulation
-------------------
The agent can stop the simulation at any point of point. In the case of HELICSSimIntegration object, it will disconnect
the federate from the HELICS core and close the library. Generally, it is a good practice to call the stop_simulation API
within the onstop() method of the agent. In this way, the agent stops the simulation before exiting the process.

.. code-block:: python

    @Core.receiver("onstop")
    def onstop(self, sender, **kwargs):
        """
        This method is called when the Agent is about to shutdown, but before it
        disconnects from the message bus.
        """
        self.helics_sim.stop_simulation()

