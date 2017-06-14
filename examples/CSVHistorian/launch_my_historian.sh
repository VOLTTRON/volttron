#!/usr/bin/env bash
#Useful for debugging as running this way will dump driver logging data directly to the console.
if [ -z "$VOLTTRON_HOME" ]; then
    export VOLTTRON_HOME=~/.volttron
fi
export AGENT_CONFIG=config
python -m csv_historian.historian

