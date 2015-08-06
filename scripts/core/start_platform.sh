#!/usr/bin/env bash

set -e

# Starts a volttron central and platform agent.  The platform agent will
# tagged plat and the volttron central agent will be  tagged vc.
#
# After execting this shell script one should be able to browse to
# http://localhost:8080 and see the web interface.

if [ ! -e "./applications" ]; then
    echo "Please execute from root of volttron repository."
    exit 0
fi

if [ -z $VOLTTRON_HOME ]
then
  echo "VOLTTRON_HOME not set setting to $HOME/.volttron"
  export VOLTTRON_HOME=$HOME/.volttron
fi

# Default case 
START_VC=0
START_PLATFORM=0
for var in "$@"
do
  if [ "$var" == "vc" ]; then
    START_VC=1
  fi
  if [ "$var" == "platform" ]; then
    START_PLATFORM=1
  fi
done

if [ "$START_VC" == "0" ] &&  [ "$START_PLATFORM" == "0" ]; then
  START_VC=1
  START_PLATFORM=1
fi

SCRIPTS="./scripts/core"
PACK="$SCRIPTS/pack_install.sh"

VC="services/core/VolttronCentral"
VC_TAG="vc"
  
PLATFORM="services/core/Platform"
PLATFORM_TAG="plat"

START="volttron-ctl start"
STOP="volttron-ctl stop"
DEL="volttron-ctl remove"
CLEAR="volttron-ctl clear"

# Install and start VC.
if [ "$START_VC" == 1 ];
then
  $STOP --tag $VC_TAG
  $DEL -f --tag $VC_TAG
  if [ -z $VC_CONFIG ]; then
    echo "VC_CONFIG set to $VC/config"
    VC_CONFIG=$VC/config
  fi
  echo "Starting Volttron Central with tag $VC_TAG"
  $PACK $VC "$VC_CONFIG" $VC_TAG
  $START --tag $VC_TAG
fi

if [ "$START_PLATFORM" == 1 ];
then
  $STOP --tag $PLATFORM_TAG
  $DEL -f --tag $PLATFORM_TAG
  if [ -z $PLATFORM_CONFIG ]; then
    echo "PLATFORM_CONFIG set to $PLATFORM/config"
    PLATFORM_CONFIG=$PLATFORM/config
  fi
  echo "Starting Platform agent with tag $PLATFORM_TAG"  
  $PACK $PLATFORM "$PLATFORM_CONFIG" $PLATFORM_TAG
  $START --tag $PLATFORM_TAG
fi

$CLEAR
