#!/usr/bin/env bash
# Manually launch the platform driver agent. Useful for debugging as running this way will dump driver logging data directly to the console.
pushd ../services/core/PlatformDriverAgent
if [ -z "$VOLTTRON_HOME" ]; then
    export VOLTTRON_HOME=~/.volttron
fi
export AGENT_CONFIG=fake-platform-driver.agent
python -m platform_driver.agent
popd

