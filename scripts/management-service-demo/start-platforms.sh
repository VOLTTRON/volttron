#!/usr/bin/env bash

set -e

# Make sure that DEMO_DIR is set before continuing setup.
if [ -z $DEMO_DIR ]; then
  echo "Missing DEMO_DIR in the environment."
  exit 100
fi

$DEMO_DIR/check-config.sh

echo "Starting platform 1: $V1_HOME"
VOLTTRON_HOME=$V1_HOME volttron -vv -l $V1_HOME/volttron.log&
echo "Starting platform 2: $V2_HOME"
VOLTTRON_HOME=$V2_HOME volttron -vv -l $V2_HOME/volttron.log&
echo "Starting platform 3: $V3_HOME"
VOLTTRON_HOME=$V3_HOME volttron -vv -l $V3_HOME/volttron.log&

echo 'Starting vc and platform 1'
VOLTTRON_HOME=$V1_HOME \
VC_CONFIG=$DEMO_DIR/volttron-central-config \
PLATFORM_CONFIG=$DEMO_DIR/platform-config1 \
  $SCRIPTS_CORE/start_platform.sh

echo 'Starting platform 2'
VOLTTRON_HOME=$V2_HOME \
PLATFORM_CONFIG=$DEMO_DIR/platform-config2 \
  $SCRIPTS_CORE/start_platform.sh platform
  
echo 'Starting platform 3'
VOLTTRON_HOME=$V3_HOME \
PLATFORM_CONFIG=$DEMO_DIR/platform-config3 \
  $SCRIPTS_CORE/start_platform.sh platform

  

