# HELICS Example Agent

This is an example agent that demonstrates how to integrate with HELICS co-simulation platform.

## HELICS installation
For installing setup in Ubuntu based systems, follow the steps described in 
https://helics.readthedocs.io/en/latest/installation/linux.html

## Install python bindings of HELICS

We need to also install python bindings of HELICS inside VOLTTRON environment. 
This can be done by the following steps:

1. Activate a VOLTTRON environment shell
    ````
    source env/bin/activate
    ````
2. VOLTTRON uses older version of pip3. Upgrade to latest pip version since HELICS needs it.
    ````
    pip install -U pip
    ````
3. Install python support for HELICS
    ````
    pip install helics
    ````

## HELICS Agent Configuration

You can specify the configuration in either json or yaml format.  The yaml format is specified
below. 

```` yml
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
    # - HELICS subscription topic,
    # - datatype
    # - publication topic for VOLTTRON (optional) to republish the
    #   message on VOLTTRON message bus
    # - additional/optional HELICS specific configuration
    - sim_topic: federate2/totalLoad
      volttron_topic: helics/abc
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

# Send/Receive messages directly to endpoints
endpoints:
    # List of endpoint configuration
    - name: federate1/EV6 # your endpoint (base prefix needs to be federate name, in our case it's "federate1")
      destination: federate2/EV6 # destination endpoint
      type: genmessage #message type
      global: true # global endpoint: true/false
    - name: federate1/EV5
      destination: federate2/EV5
      type: genmessage
      global: true

volttron_subscriptions:
    - feeder0_output/all

````

## Running HELICS Example agent

1. Start HELICS broker in new terminal. We will specify two federates - one for HELICS example agent and another for
separate python federate script.
    ````
    helics_broker -f 2
    ````
2. Start HELICS example agent in new terminal at the root of VOLTTRON source directory
    ````
    source env/bin/activate
    python scripts/install-agent.py -s examples/HELICS/ -c examples/HELICS/helics_federate1.yml -i hexample --start --force
    ````
3. In another terminal, start another python federate. At the root of VOLTTRON source directory.
    ````
    source env/bin/activate
    python examples/HELICS/helics_federate.py examples/HELICS/helics_federate2.json 
    ````

You will see that messages are being sent and received between the two federates

