#!/usr/bin/env bash

VOLTTRON_ROOT=$HOME/repos/volttron-rabbitmq

cmd = "$VOLTTRON_ROOT/scripts/install-agent.py"

python $cmd -s "$VOLTTRON_ROOT/examples/RemoteListener" \
    -i "remote.agent"
