# FNCS Example Agent

This is an example agent using the fncs subsystem built into volttron.

## FNCS Versions

FNCS must use the same version of ZMQ that volttron does in order for the two applications to be compatible.  The version of ZMQ used in volttron is 4.1.5.  This can be downloaded from 
https://archive.org/download/zeromq_4.1.5/zeromq-4.1.5.tar.gz.  The most current version
of CZMQ that can be used with this version of ZMQ is version 3.0.2.  You can download this from
https://archive.org/download/zeromq_czmq_3.0.2/czmq-3.0.2.tar.gz.

Follow the fncs installation from https://github.com/FNCS/fncs substituding the above urls for 
ZMQ and CZMQ respectively.

Also, fncs must be installed into the python environment.  This can be done by the following steps:

1. Activate a volttron environment shell
1. cd to the <FNCS SRC>/python directory
1. Run python setup.py sdist
1. Run pip install dist/fncs-2.0.1.tar.gz


## Running the agent.

Make sure to export the variable LD_LIBRARY_PATH to the fncs_installation/lib folder before
starting any agent.

## FNCS Agent Configuration

You can specify the configuration in either json or yaml format.  The yaml format is specified
below. 

```` yml

# Optional federate_name (defaults to vip identity)
federate_name: federate1
# Optional broker_location (defaults to tcp://localhost:5570
broker_location: tcp://localhost:5570
# Optional time_delta (defaults to 1s)
time_delta: 1s
# Optional sim_lenthg (defaults to 60s)
sim_length: 60s
# Optional stop_agent_when_sim_complete default False
stop_agent_when_sim_complete: True

# Required topic_mapping
topic_mapping:
  # fncs key
  a:
    # fncs_topic to be subscribed to
    fncs_topic: devices/abcd
    volttron_topic: fncs/abc
  b:
    fncs_topic: alpha/betagama

````

## FNCS example federate1

In an activated volttron environment, export LD_LIBRARY_PATH equal to fncs_install/lib.  This is
the only requirement in order for fncs to be located within the environment.  The following
commands will install the agent to a volttron instance.  If the fncs_broker is running
and this is the last federate to be launched, the code should start publishing on fncs to 
devices/abcd (on volttron fncs/abc will be available as well.).

````bash

    (volttron)osboxes@osboxes ~/git/volttron $ export LD_LIBRARY_PATH=<fncs_install>/lib
    (volttron)osboxes@osboxes ~/git/volttron $ python scripts/install-agent.py -s examples/FNCS \
        -c examples/FNCS/federate1.yml -i federate1_test --force --start   

````

