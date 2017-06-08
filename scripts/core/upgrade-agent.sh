#!/usr/bin/env bash

if [ -z "$VOLTTRON_HOME" ]; then
  export VOLTTRON_HOME=$HOME/.volttron
  echo "VOLTTRON_HOME UNSET using default $VOLTTRON_HOME";
fi

echo "VOLTTRON_HOME=$VOLTTRON_HOME"

# Require the TAG variable to be set.
if [ -z "$TAG" ]; then
  echo "The TAG environmental variable must be set.";
  exit 0
fi

# Require the AGENT_VIP_IDENTITY variable to be set.
if [ -z "$AGENT_VIP_IDENTITY" ]; then
  echo "The AGENT_VIP_IDENTITY variable must be set.";
  exit 0
fi


COMMAND_ARGS=""

if [ ! -z "$VIP_ADDRESS" ]; then
  COMMAND_ARGS="$COMMAND_ARGS --vip-address $VIP_ADDRESS"
else
  # Default to the ipc socket
  VIP_ADDRESS="ipc://@$VOLTTRON_HOME/run/vip.socket"
  COMMAND_ARGS="$COMMAND_ARGS --vip-address $VIP_ADDRESS"
fi

echo "Using VIP_ADDRESS: $VIP_ADDRESS";

COMMAND="volttron-ctl"

START="$COMMAND start --tag $TAG $COMMAND_ARGS"
ENABLE="$COMMAND enable --tag $TAG $COMMAND_ARGS"

if [ ! -e "./volttron/platform" ]; then
    echo "Please execute from root of volttron repository."
    exit 0
fi

# Require the SOURCE variable to be set to the agent directory
if [ -z "$SOURCE" ]; then
  echo "SOURCE variable must be set to the Agent directory.";
  exit 0
fi

# Require the CONFIG variable to be set to a config file
if [ -z "$CONFIG" ]; then
  echo "CONFIG variable must be set to the Agent config file.";
  exit 0
fi

# Attempt to package the wheel file.
WHEEL=$(volttron-pkg package $SOURCE | awk -F"Package created at: " '{ print $2 }')

#Remove newlines
WHEEL=${WHEEL//$'\n'/}

if [ ! -e "$WHEEL" ]; then
  echo "Unable to build wheel file"
  echo "$WHEEL"
  echo "There maybe an issue with the code."
  exit 0
fi

volttron-pkg configure "$WHEEL" "$CONFIG"

volttron-ctl upgrade "$AGENT_VIP_IDENTITY" "$WHEEL" --tag="$TAG"

if [ -z "$NO_START" ]; then
  echo "Starting agent! $START"
  $START
fi

if [ "$1" = "enable" ]
then
    $ENABLE
fi
