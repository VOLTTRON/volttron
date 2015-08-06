#!/usr/bin/env bash

# Error out when an error occurs.
set -e

if [ ! -e "./applications" ]; then
    echo "Please execute from root of volttron repository."
    exit 0
fi

# VOLTTRON_HOME directories that are used in the scripts
V1_HOME=/tmp/v1home
V2_HOME=/tmp/v2home
V3_HOME=/tmp/v3home

# This is the directory that this script is actually being run from i.e.
# management-service-demo.
DEMO_DIR=`dirname $0`

echo "Shutting down platform 1"
VOLTTRON_HOME=$V1_HOME volttron-ctl shutdown --platform &> /dev/null
echo "Shutting down platform 2"
VOLTTRON_HOME=$V2_HOME volttron-ctl shutdown --platform &> /dev/null
echo "Shutting down platform 3"
VOLTTRON_HOME=$V3_HOME volttron-ctl shutdown --platform &> /dev/null 


