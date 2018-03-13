DNP3Agent is a VOLTTRON agent that handles DNP3 outstation communications.

DNP3Agent models a DNP3 outstation, communicating with a DNP3 master.

For further information about this agent and DNP3 communications, please see the VOLTTRON
DNP3 specification, located in VOLTTRON readthedocs 
under http://volttron.readthedocs.io/en/develop/specifications/dnp3_agent.html.

pydnp3 must be installed in order to run DNP3Agent in VOLTTRON. As of right now, pydnp3 must be installed from
source. pydnp3 can be installed from a command-line shell as follows - please note that you must be in a
"volttron" virtual environment for the following commands:

    (volttron) $ git clone --recursive http://github.com/Kisensum/pydnp3
    (volttron) $ cd pydnp3
    (volttron) $ python setup.py install

DNP3Agent can be installed from a command-line shell as follows:

    (volttron) $ export VOLTTRON_ROOT=<your volttron install directory>
    (volttron) $ export DNP3_ROOT=$VOLTTRON_ROOT/services/core/DNP3Agent
    (volttron) $ cd $VOLTTRON_ROOT
    (volttron) $ python scripts/install-agent.py -s $DNP3_ROOT -i dnp3agent -c $DNP3_ROOT/dnp3agent.config -t dnp3agent -f
