#!/usr/bin/env bash

if [ ! -e "./volttron/platform" ]; then
    echo "Please execute from root of volttron repository."
    exit 0
fi

export HIST="services/core/OpenEISHistorian"
export HIST_CONFIG="$HIST/openeis.historian.config"
SCRIPTS_CORE="./scripts/core"

$SCRIPTS_CORE/start_historian.sh $1

