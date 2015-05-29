#!/usr/bin/env bash

if [ $1 == "-h" ]
then
  echo "./install_agent.sh <path to agent directory> <config path> <tag>"
  echo ""
  echo "install an agent on a volttron platform depending on VOLTTRON."
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
  echo "VOLTTRON_HOME UNSET setting to v1_home: $VOLTTRON_HOME"; 
fi

WHEEL=$(volttron-pkg package $1 | awk -F": " '{ print $2 }')

if [ ! -e "$WHEEL" ]
then
  echo "$WHEEL doesn't exist"
  exit 0
fi

volttron-pkg configure "$WHEEL" "$2"

volttron-ctl install "$3=$WHEEL"




