#!/usr/bin/env bash

export VOLTTRON_HOME=$HOME/.volttron

START="volttron-ctl start"

if [ ! -e "./volttron/platform" ]; then
    echo "Please execute from root of volttron repository."
    exit 0
fi

if [ -z "$VOLTTRON_HOME" ]; then
  VOLTTRON_HOME=$HOME/.volttron
  echo "VOLTTRON_HOME UNSET setting to $VOLTTRON_HOME";
fi

# Require the HIST variable to be set to the agent directory
if [ -z "$HIST" ]; then
  echo "HIST variable must be set to the historian directory.";
  exit 0
fi

# Require the HIST_CONFIG variable to be set to a config file
if [ -z "$HIST_CONFIG" ]; then
  echo "HIST_CONFIG variable must be set to the historian config file.";
  exit 0
fi

# Allow the HIST_TAG variable to be set.
if [ -z "$HIST_TAG" ]; then
  echo "The historian tag will be hist.";
  HIST_TAG="hist"
fi

# Attempt to remove the agent by the tag.
SCRIPTS_CORE="./scripts/core"
$SCRIPTS_CORE/remove_agent.sh $HIST_TAG

# If we need to start the platform do so before the historian itself.
if [ "$1" = "full" ]
then
    $SCRIPTS_CORE/start_platform.sh
fi

# For packaging of scripts us pack_install
PACK="$SCRIPTS_CORE/pack_install.sh"

echo $PACK $HIST $HIST_CONFIG $HIST_TAG
# Install and start HIST.
$PACK $HIST $HIST_CONFIG $HIST_TAG
$START --tag $HIST_TAG

