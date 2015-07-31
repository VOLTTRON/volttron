#!/usr/bin/env bash

export VOLTTRON_HOME=$HOME/.volttron

START="volttron-ctl start"

if [ ! -e "./Agents" ]; then
    echo "Please execute from root of volttron repository."
    exit 0
fi


# This is the directory that contains the scripts
HIST_TEST_DIR=`dirname $0`
HIST="Agents/SQLHistorianAgent"
HIST_TAG="hist"

SCRIPTS="./scripts"
$SCRIPTS/remove_agent.sh $HIST_TAG

if [ "$1" = "full" ]
then
    $HIST_TEST_DIR/start-platform.sh
fi

SCRIPTS="./scripts"
PACK="$SCRIPTS/pack_install.sh"

echo $PACK $HIST $HIST/config.mysql.platform.historian $HIST_TAG
# Install and start HIST.
$PACK $HIST $HIST/config.mysql.platform.historian $HIST_TAG
$START --tag $HIST_TAG

