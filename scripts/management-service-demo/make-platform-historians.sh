#!/usr/bin/env bash

set -e

# Make sure that DEMO_DIR is set before continuing setup.
if [ -z $DEMO_DIR ]; then
  echo "Missing DEMO_DIR in the environment."
  exit 100
fi

$DEMO_DIR/check-config.sh

echo 'Installing platform 1 historian'
VOLTTRON_HOME=$V1_HOME $SCRIPTS_CORE/pack_install.sh \
  services/core/SQLHistorian \
  $DEMO_DIR/platform-historian-config1 hist

VOLTTRON_HOME=$V1_HOME volttron-ctl start --tag hist

echo 'Installing platform 2 historian'
VOLTTRON_HOME=$V2_HOME $SCRIPTS_CORE/pack_install.sh \
  services/core/SQLHistorian \
  $DEMO_DIR/platform-historian-config2 hist

VOLTTRON_HOME=$V2_HOME volttron-ctl start --tag hist

echo 'Installing platform 3 historian'
VOLTTRON_HOME=$V3_HOME $SCRIPTS_CORE/pack_install.sh \
  services/core/SQLHistorian \
  $DEMO_DIR/platform-historian-config3 hist

VOLTTRON_HOME=$V3_HOME volttron-ctl start --tag hist
