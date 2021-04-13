#!/usr/bin/env bash
# Manually launch the bacnet proxy agent. Useful for debugging as running this way will dump driver logging data directly to the console.
pushd ../services/core/BACnetProxy
if [ -z "$VOLTTRON_HOME" ]; then
    export VOLTTRON_HOME=~/.volttron
fi
export AGENT_CONFIG=config
python -m bacnet_proxy.agent
popd

