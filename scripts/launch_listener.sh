#!/usr/bin/env bash
# Manually launch the listener agent. Useful for debugging as running this way will dump driver logging data directly to the console.
pushd ../examples/ListenerAgent
if [ -z "$VOLTTRON_HOME" ]; then
    export VOLTTRON_HOME=~/.volttron
fi
export AGENT_CONFIG=config
python -m listener.agent
popd

