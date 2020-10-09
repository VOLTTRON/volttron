 .. _Simulation-Integration-Configuration:

=======================================================
Configuration for Integrating With Simulation Platforms
=======================================================
Configurations for interfacing with simulation platforms will vary depending on the specifications of that platform but there may be few common configuration
options that we can group together as separate sections such as

* Config parameters that help us setup the simulation such as connection parameters (connection address), unique name for the participant, total simulation time
* List of topics for subscribing with simulation platform
* List of topics for publishing to the simulation platform
* List of topics subscribing with VOLTTRON message bus

We have grouped these four categories of configuration into four different sections - properties, inputs, outputs and volttron_subscriptions.
The simulation integration class will read these four sections and register with simulation platform appropriately. If an agent needs to
interface with EnergyPlus or HELICS using the simulation integration framework, then it will need to group the configurations into above four
sections.

**Note**

GridAPPS-D can run complex power system simulations using variety of simulators such as GridLAB-D, HELICS, MatPower etc.
So the configuration for GridAPPS-D cannot follow the above format. Because of this, the configuration for GridAPPSD is taken in the raw format and passed drectly to the GridAPPS-D simulation.

Example Configuration
---------------------------------
The configuration for interfacing with a simulation platform is described by using integration with HELICS as an example. Each participant in a
HELICS co-simulation environment is called a federate.

Below is an example HELICS config file.

.. code-block:: yaml

    # Config parameters for setting up HELICS federate
    properties:
        name: federate1 # unique name for the federate
        loglevel: 5 # log level
        coreType: zmq # core type
        timeDelta: 1.0 # time delta (defaults to 1s)
        uninterruptible: true
        simulation_length: 360 # simulation length in seconds (defaults to 360s)

    # configuration for subscribing to HELICS simulation
    outputs:
        # List of subscription information, typically contains
        # - subscription topic,
        # - datatype
        # - publication topic for VOLTTRON (optional) to republish the
        #   message on VOLTTRON message bus
        # - additional/optional simulation specific configuration
        - sim_topic: federate2/totalLoad
          volttron_topic: helics/abc
          type: complex
          required: true
        - sim_topic: federate2/charge_EV6
          volttron_topic: helics/ev6
          type: complex
          required: true

    # configuration for publishing to HELICS simulation
    inputs:
        # List of publication information, containing
        # - HELICS publication topic,
        # - datatype
        # - metadata associated with the topic (for example unit)
        # - subscription topic for VOLTTRON message bus (optional) which can then be
        #   republished on HELICS with HELICS publication topic
        # - additional/optional publication specific configuration
        - sim_topic: pub1 # HELICS publication key
          type: double    # datatype
          unit: m         # unit
          info: this is an information string for use by the application #additional info
          volttron_topic: pub1/all # topic to subscribe on VOLTTRON bus
          global: true
        - sim_topic: pub2
          type: double
          volttron_topic: pub2/all

    volttron_subscriptions:
        - feeder0_output/all


The properties section may contain the following.

* Unique name for the federate
* core type (for example, zmq, tcp, mpi)
* time step delta in seconds
* total simulation time etc

**Note**
The individual fields under this section may vary depending on whether the agent is interfacing with HELICS or EnergyPlus.

In the outputs section, list of subscriptions (if any) need to be provided. Each subscription will contain the following.

* subscription topic
* data type
* VOLTTRON topic to republish the message on VOLTTRON message bus (optional)
* required flag (optional)


In the outputs section, list of publications (if any) need to be provided. Each publication will contain the following.

* publication topic
* data type
* metadata asscoiated with the topic
* VOLTTRON topic to subscribe on the VOLTTRON message bus which will be republished on simulation bus (optional)
* additional information (optional)

In the volttron_subscriptions, list of topics need to be subscribed on VOLTTRON bus can be provided.
