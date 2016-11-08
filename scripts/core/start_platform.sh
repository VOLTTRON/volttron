#!/usr/bin/env bash

set -e

# This script has the ability to start a volttron central and/or platform agent
# with customizable configuration files.
#
# Environmental variables 
#   VOLTTRON_HOME 
#     If not set will be defaulted to $HOME/.volttron
#
#   VC_CONFIG (if no arguments or vc argument is passed)  
#     If not set will be set to ./services/core/VottronCentral/config
#
#   PLATFORM_CONFIG  (if no arguments or platform argument is passed)
#     If not set will be set to ./services/core/Platform/config
#
# Command Line Arguments
#   platform - If present the platform agent will be deleted and reinstalled
#   vc       - If present the volttron central agent will be deleted and reinstalled
#
#   If no arguments are specified then both the platform and volttron central
#   agents will be deleted and reinstalled.
#
# Outcome
#   If volttron central agent is successfully started one should be able to 
#   access it at http://localhost:8080 and see the web interface.

if [ ! -e "./volttron/platform" ]; then
    echo "Please execute from root of volttron repository."
    exit 0
fi

if [ -z $VOLTTRON_HOME ]
then
  echo "VOLTTRON_HOME not set setting to $HOME/.volttron"
  export VOLTTRON_HOME=$HOME/.volttron
else
  echo "VOLTTRON_HOME is $VOLTTRON_HOME"
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
    #echo "VC_CONFIG set to $VC/config"
    VC_CONFIG=$VC/config
  fi
  echo "VC_CONFIG is $VC_CONFIG"
  echo "Starting Volttron Central with tag $VC_TAG"
  $PACK $VC "$VC_CONFIG" $VC_TAG
  $START --tag $VC_TAG
fi

if [ "$START_PLATFORM" == 1 ];
then
  $STOP --tag $PLATFORM_TAG
  $DEL -f --tag $PLATFORM_TAG
  if [ -z $PLATFORM_CONFIG ]; then
    #echo "PLATFORM_CONFIG set to $PLATFORM/config"
    PLATFORM_CONFIG=$PLATFORM/config
  fi
  echo "PLATFORM_CONFIG is $PLATFORM_CONFIG"
  echo "Starting Platform agent with tag $PLATFORM_TAG"  
  $PACK $PLATFORM "$PLATFORM_CONFIG" $PLATFORM_TAG
  $START --tag $PLATFORM_TAG
fi

$CLEAR
