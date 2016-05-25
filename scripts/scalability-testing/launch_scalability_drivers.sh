#!/usr/bin/env bash
# Manually launch the master driver agent using the configuration created by the config builder.
# Useful for debugging as running this way will dump driver logging data directly to the console.
pushd ../../services/core/MasterDriverAgent
if [ -z "$VOLTTRON_HOME" ]; then
    export VOLTTRON_HOME=~/.volttron
fi
export AGENT_CONFIG=../../../scripts/scalability-testing/configs/master-driver.agent
python -m master_driver.agent
popd

