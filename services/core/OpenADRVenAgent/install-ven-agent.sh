cd $VOLTTRON_ROOT
export VIP_SOCKET="ipc://$VOLTTRON_HOME/run/vip.socket"
python scripts/install-agent.py \
    -s $VOLTTRON_ROOT/services/core/OpenADRVenAgent \
    -i venagent \
    -c $VOLTTRON_ROOT/services/core/OpenADRVenAgent/openadrven.config \
    -t venagent \
    -f