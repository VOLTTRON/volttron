#!/usr/bin/env bash

set -e

# Make sure that DEMO_DIR is set before continuing setup.
if [ -z $DEMO_DIR ]; then
  echo "Missing DEMO_DIR in the environment."
  exit 100
fi

# Checks whether or not all of the environment variables for the demo script
# are set up before continuing.  This block of code should be copied to all
# of the scripts that are going to be executed from the demo script.
$DEMO_DIR/check-config.sh

echo "(Re)creating Platform Directories:"
if [ -d "$V1_HOME" ]; then
  rm -rf $V1_HOME
fi

if [ -d "$V2_HOME" ]; then
  rm -rf $V2_HOME
fi

if [ -d "$V3_HOME" ]; then
  rm -rf $V3_HOME
fi

# We add the curve.key to not include encryption
# on tcp communication.
mkdir $V1_HOME
touch $V1_HOME/curve.key
mkdir $V2_HOME
touch $V2_HOME/curve.key
mkdir $V3_HOME
touch $V3_HOME/curve.key
