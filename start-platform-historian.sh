#!/usr/bin/env bash

export VOLTTRON_HOME=$HOME/.volttron

START="volttron-ctl start"
STOP="volttron-ctl stop"
DEL="volttron-ctl remove"
CLEAR="volttron-ctl clear"

HIST="Agents/SQLHistorianAgent"
HIST_TAG="hist"

# Delete the historian before executing the "full" script
$STOP --tag $HIST_TAG
$DEL --tag $HIST_TAG

if [ "$1" = "full" ]
then
    ./start-platform.sh
fi

SCRIPTS="volttron/scripts"
PACK="$SCRIPTS/pack_install.sh"

# Install and start HIST.
$PACK $HIST $HIST/config $HIST_TAG
$START --tag $HIST_TAG

