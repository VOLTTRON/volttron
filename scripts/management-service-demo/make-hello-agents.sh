#!/usr/bin/env bash

set -e

# Make sure that DEMO_DIR is set before continuing setup.
if [ -z $DEMO_DIR ]; then
  echo "Missing DEMO_DIR in the environment."
  exit 100
fi

$DEMO_DIR/check-config.sh

VOLTTRON_HOME=$V1_HOME $SCRIPTS_CORE/pack_install.sh examples/HelloAgent \
  $DEMO_DIR/hello-config1 hello
  
VOLTTRON_HOME=$V2_HOME $SCRIPTS_CORE/pack_install.sh examples/HelloAgent \
  $DEMO_DIR/hello-config2 hello
