# This script assumes that $VOLTTRON_ROOT is the directory where VOLTTRON source code is loaded from github.

export DNP3_ROOT=$VOLTTRON_ROOT/services/core/DNP3Agent

# Install the agent that resides in the dnp3 subdirectory
export AGENT_MODULE=dnp3.agent

cd $VOLTTRON_ROOT

python scripts/install-agent.py -s $DNP3_ROOT -i dnp3agent -c $DNP3_ROOT/dnp3agent.config -t dnp3agent -f

# Put the agent's point definitions in the config store.
cd $VOLTTRON_ROOT
vctl config store dnp3agent mesa_points.config $DNP3_ROOT/dnp3/mesa_points.config

echo
echo Stored point configurations in config store...
vctl config list dnp3agent
echo