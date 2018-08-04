DNP3Agent and MesaAgent, either of which can be built from this directory,
are VOLTTRON agents that handle DNP3 communications.
They implement a DNP3 outstation, communicating with a DNP3 master.

For further information about these agents and DNP3 communications, please see the VOLTTRON
DNP3 and MESA specifications, located in VOLTTRON readthedocs 
under http://volttron.readthedocs.io/en/develop/specifications/dnp3_agent.html
and http://volttron.readthedocs.io/en/develop/specifications/mesa_agent.html.

These agents depend on the pydnp3 library, which must be installed in the VOLTTRON virtual environment:

    (volttron) $ pip install pydnp3

Installing MesaAgent
--------------------

MesaAgent implements MESA-ESS, an enhanced version of the DNP3 protocol.

MesaAgent can be installed by running the **install_mesa_agent.sh** 
command-line script as follows: 

    (volttron) $ export VOLTTRON_ROOT=<your volttron install directory>
    (volttron) $ source $VOLTTRON_ROOT/services/core/DNP3Agent/install_mesa_agent.sh

The **install_mesa_agent.sh** script installs the agent:

    (volttron) $ export DNP3_ROOT=$VOLTTRON_ROOT/services/core/DNP3Agent
    (volttron) $ export AGENT_MODULE=dnp3.mesa.agent
    (volttron) $ cd $VOLTTRON_ROOT
    (volttron) $ python scripts/install-agent.py -s $DNP3_ROOT -i mesaagent -c $DNP3_ROOT/mesaagent.config -t mesaagent -f

(Note that $AGENT_MODULE directs the installer to use agent
source code residing in the "dnp3/mesa" subdirectory.)

Then the script stores DNP3 point and MESA function definitions in the agent's config store:

    (volttron) $ cd $DNP3_ROOT
    (volttron) $ python dnp3/mesa/conversion.py < dnp3/mesa/mesa_functions.yaml > dnp3/mesa/mesa_functions.config
    (volttron) $ cd $VOLTTRON_ROOT
    (volttron) $ vctl config store mesaagent mesa_points.config $DNP3_ROOT/dnp3/mesa_points.config
    (volttron) $ vctl config store mesaagent mesa_functions.config $DNP3_ROOT/dnp3/mesa/mesa_functions.config

Regression tests can be run from a command-line shell as follows:

    (volttron) $ pytest services/core/DNP3Agent/tests/test_mesa_agent.py

Installing DNP3Agent
--------------------

DNP3Agent implements the basic DNP3 protocol.

DNP3Agent can be installed by running the **install_dnp3_agent.sh** 
command-line script as follows: 

    (volttron) $ export VOLTTRON_ROOT=<your volttron install directory>
    (volttron) $ source $VOLTTRON_ROOT/services/core/DNP3Agent/install_dnp3_agent.sh

The **install_dnp3_agent.sh** script installs the agent:

    (volttron) $ export DNP3_ROOT=$VOLTTRON_ROOT/services/core/DNP3Agent
    (volttron) $ export AGENT_MODULE=dnp3.agent
    (volttron) $ cd $VOLTTRON_ROOT
    (volttron) $ python scripts/install-agent.py -s $DNP3_ROOT -i dnp3agent -c $DNP3_ROOT/dnp3agent.config -t dnp3agent -f

(Note that $AGENT_MODULE directs the installer to use agent
source code residing in the "dnp3" directory.)

Then the script stores DNP3 point (but not MESA function) definitions in the agent's config store:

    (volttron) $ vctl config store dnp3agent mesa_points.config $DNP3_ROOT/dnp3/mesa_points.config

Regression tests can be run from a command-line shell as follows:

    (volttron) $ cd $VOLTTRON_ROOT
    (volttron) $ pytest services/core/DNP3Agent/tests/test_dnp3_agent.py
