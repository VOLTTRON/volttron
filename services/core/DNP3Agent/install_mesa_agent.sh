#/bin/sh
# This script assumes that $VOLTTRON_ROOT is the directory where VOLTTRON source code is loaded from github.

export DNP3_ROOT=$VOLTTRON_ROOT/services/core/DNP3Agent

# Install the agent that resides in the dnp3.mesa subdirectory
export AGENT_MODULE=dnp3.mesa.agent

cd $VOLTTRON_ROOT

python scripts/install-agent.py -s $DNP3_ROOT -i mesaagent -c $DNP3_ROOT/mesaagent.config -t mesaagent -f

# Convert function YAML to JSON
cd $DNP3_ROOT
python dnp3/mesa/conversion.py < dnp3/mesa/mesa_functions.yaml > dnp3/mesa/mesa_functions.config

# Put the agent's point definitions and function definitions in the config store.
cd $VOLTTRON_ROOT
vctl config store mesaagent mesa_points.config $DNP3_ROOT/dnp3/mesa_points.config
vctl config store mesaagent mesa_functions.config $DNP3_ROOT/dnp3/mesa/mesa_functions.config

echo
echo Stored point and function configurations in config store...
vctl config list mesaagent
echo
