#!/usr/bin/env bash

# Error out when an error occurs.
set -e

if [ ! -e "./applications" ]; then
    echo "Please execute from root of volttron repository."
    exit 0
fi

# VOLTTRON_HOME directories that are used in the scripts
export V1_HOME=/tmp/v1home
export V2_HOME=/tmp/v2home
export V3_HOME=/tmp/v3home

# This is the directory that this script is actually being run from i.e.
# management-service-demo.
export DEMO_DIR=`dirname $0`
export SCRIPTS_CORE="./scripts/core"

# Checks whether or not all of the environment variables for the demo script
# are set up before continuing.  This block of code should be copied to all
# of the scripts that are going to be executed from the demo script.
$DEMO_DIR/check-config.sh

# Do initialization of VOLTTRON_HOME
$DEMO_DIR/demo-setup.sh

# Start install and start volttron instances and start the platform agents with
# volttron-central on one instance of volttron and platform agent on all
# of the instances of volttron.
$DEMO_DIR/start-platforms.sh

# Start historians on each of the different platforms
$DEMO_DIR/make-platform-historians.sh

echo "START make-hello1"
#VOLTTRON_HOME=$V1_HOME ./make-hello1
echo "START make-hello2"
#VOLTTRON_HOME=$V2_HOME ./make-hello2

#./make-platform-historians

echo "Launching browser"
#x-www-browser http://localhost:8080 &

