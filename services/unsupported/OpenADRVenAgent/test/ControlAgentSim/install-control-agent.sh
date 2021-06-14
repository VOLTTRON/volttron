cd $VOLTTRON_ROOT
export VIP_SOCKET="ipc://$VOLTTRON_HOME/run/vip.socket"
python scripts/install-agent.py \
    -s $VOLTTRON_ROOT/services/core/OpenADRVenAgent/test/ControlAgentSim \
    -i control_agent_sim \
    -c $VOLTTRON_ROOT/services/core/OpenADRVenAgent/test/ControlAgentSim/controlagentsim.config \
    -t control_agent_sim \
    -f