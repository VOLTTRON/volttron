#!/usr/bin/env bash

if [ ! -e "./volttron/platform" ]; then
    echo "Please execute from root of volttron repository."
    exit 0
fi

export HIST="services/core/SQLHistorian"
export HIST_CONFIG="$HIST/config.sqlite.platform.historian"
SCRIPTS_CORE="./scripts/core"

$SCRIPTS_CORE/start_historian.sh $1

