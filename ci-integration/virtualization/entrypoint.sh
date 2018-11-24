#!/bin/bash

# Add local user
# Either use the LOCAL_USER_ID if passed in at runtime or
# fallback
set -e
USER_ID=${LOCAL_USER_ID:-9001}

# echo "Starting with UID : $USER_ID VOLTTRON_USER_HOME is $VOLTTRON_USER_HOME"

id -u volttron

if [ $(id -u volttron > /dev/null 2>&1; echo $?) == 1 ]; then
  echo "Adding new user with UID $USER_ID"
  useradd --shell /bin/bash -u $USER_ID -o -c "" -m volttron
else
  usermod -u $USER_ID volttron
fi

export HOME=${VOLTTRON_USER_HOME}

# Only need to change
if [ -z "${VOLTTRON_USER_HOME}" ]; then
  chown volttron.volttron -R ${VOLTTRON_USER_HOME}
fi

cd ${VOLTTRON_ROOT}

# if [ ! -f "platform_config.yml" ]; then
#   echo "File not found at $VOLTTRON_USER_HOME/platform_config.yml";
#   echo "mount or copy file into child container."
#   exit 1;
# fi

if [ ! -n "$@" ]; then
  echo "Please provide a command to run (e.g. /bin/bash, volttron -vv)";
  exit 1;
else
  # echo "now Executing $@";
  export PATH="/code/volttron/env/bin:$PATH";
  echo $PATH;
  exec /usr/local/bin/gosu volttron "$@";
fi
