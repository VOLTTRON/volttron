#!/usr/bin/env bash

export VOLTTRON_HOME=$HOME/.volttron

if [ ! -e "./Agents" ]; then
    echo "Please execute from root of volttron repository."
    exit 0
fi

START="volttron-ctl start"

AGENT="Agents/PlatformAgent"
CFG="$AGENT/config-devvm"
TAG="plat"

./scripts/remove_agent.sh $TAG
./scripts/pack_install.sh $AGENT $CFG $TAG
$START --tag $TAG
