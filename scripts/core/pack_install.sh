#!/usr/bin/env bash

if [ $1 == "-h" ]
then
  echo "./pack_agent.sh <path to agent directory> <config path> <tag>"
  echo ""
  echo "Package and install an agent to a running instance of volttron."
  echo "If VOLTTRON_HOME is not set then uses \$HOME/.volttron as VOLTTRON_HOME"
  exit 0
fi

if [ ! -e "$1/setup.py" ]
then
  echo "Agent directory must have a setup.py in it."
  exit 0
fi

if [ ! -e "$2" ]
then
  echo "Invalid configuration file."
  exit 0
fi

if [ -z "$3" ]
then
  echo "Invalid tag name."
  exit 0
fi

if [ -z "$VOLTTRON_HOME" ]; then
  VOLTTRON_HOME=$HOME/.volttron
  echo "VOLTTRON_HOME UNSET setting to $VOLTTRON_HOME";
fi

echo "VOLTTRON_HOME=$VOLTTRON_HOME"

COMMAND_ARGS=""

if [ ! -z "$VIP_ADDRESS" ]; then
  COMMAND_ARGS="$COMMAND_ARGS --vip-address '$VIP_ADDRESS'"
  echo "Using VIP_ADDRESS: $VIP_ADDRESS";
fi


WHEEL=$(volttron-pkg package $1 | awk -F": " '{ print $2 }')

#Remove newlines
WHEEL=${WHEEL//$'\n'/}


if [ ! -e "$WHEEL" ]; then
  echo "$WHEEL doesn't exist"
  exit 0
fi

# Clear the old agents out.
VOLTTRON_HOME=$VOLTTRON_HOME volttron-ctl clear

VOLTTRON_HOME=$VOLTTRON_HOME volttron-pkg configure "$WHEEL" "$2"

if [ -z "$AGENT_VIP_IDENTITY" ]; then
    VOLTTRON_HOME=$VOLTTRON_HOME volttron-ctl $COMMAND_ARGS install "$WHEEL" --tag "$3"
else
    VOLTTRON_HOME=$VOLTTRON_HOME volttron-ctl $COMMAND_ARGS install "$WHEEL" --tag "$3" --vip-identity "$AGENT_VIP_IDENTITY"
fi

