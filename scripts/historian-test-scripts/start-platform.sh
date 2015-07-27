#!/usr/bin/env bash

# Starts a volttron central and platform agent.  The platform agent will
# tagged plat and the volttron central agent will be  tagged vc.
#
# After execting this shell script one should be able to browse to
# http://localhost:8080 and see the web interface.

export VOLTTRON_HOME=$HOME/.volttron

if [ ! -e "./Agents" ]; then
    echo "Please execute from root of volttron repository."
    exit 0
fi

echo "Starting the vc platform and platform agent on the default volttron home."
SCRIPTS="volttron/scripts"
PACK="$SCRIPTS/pack_install.sh"

VC="Agents/VolttronCentralAgent"
VC_TAG="vc"
PLATFORM="Agents/PlatformAgent"
PLATFORM_TAG="plat"

START="volttron-ctl start"
STOP="volttron-ctl stop"
DEL="volttron-ctl remove"
CLEAR="volttron-ctl clear"

$STOP --tag $PLATFORM_TAG $VC_TAG
$DEL --tag $PLATFORM_TAG $VC_TAG

# Install and start VC.
$PACK $VC $VC/config $VC_TAG
$START --tag $VC_TAG

# Install and start platform.
$PACK $PLATFORM "$PLATFORM/config-devvm" $PLATFORM_TAG
$START --tag $PLATFORM_TAG

$CLEAR
