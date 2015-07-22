#!/usr/bin/env bash

export VOLTTRON_HOME=$HOME/.volttron

if [ -z "$1" ]; then
    echo "please pass a tag to be removed from volttron"
    exit 0
fi

TAG="$1"
STOP="volttron-ctl stop"
DEL="volttron-ctl remove"
CLEAR="volttron-ctl clear"

$STOP --tag $TAG
$DEL --tag $TAG
$CLEAR