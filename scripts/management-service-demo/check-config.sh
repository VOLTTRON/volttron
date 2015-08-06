#!/usr/bin/env bash
MISSING=0

if [ -z $DEMO_DIR ]; then
  echo "Missing DEMO_DIR in the environment."
  MISSING=100
fi

if [ -z $SCRIPTS_CORE ]; then
  echo "Missing SCRIPTS_CORE in the environment."
  MISSING=100
fi

if [ -z $V1_HOME ]; then
  echo "Missing V1_HOME in the environment."
  MISSING=100
fi

if [ -z $V2_HOME ]; then
  echo "Missing V2_HOME in the environment."
  MISSING=100
fi

if [ -z $V3_HOME ]; then
  echo "Missing V3_HOME in the environment."
  MISSING=100
fi

exit $MISSING
