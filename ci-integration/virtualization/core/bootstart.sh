#! /usr/bin/env bash

# Uncomment if we are going to pre-setup the platform before
# running any of the environment.
#if [ -z /startup/setup-platform.py ]; then
#    echo "/startup/setup-platform.py does not exist.  The docker image must be corrupted"
#    exit 1
#fi

echo "Right before setup-platform.py is called I am calling printenv"
printenv
pip list
pip install --user wheel==0.30
#python /startup/setup-platform.py
PID=$?
echo "PID WAS $PID"
if [ "$PID" == "0" ]; then
    volttron -vv
fi


