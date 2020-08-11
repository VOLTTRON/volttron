#!/bin/bash

# Add local user
# Either use the LOCAL_USER_ID if passed in at runtime or
# fallback
set -e

# USER_ID="${LOCAL_USER_ID:?LOCAL_USER_ID must be set use -e LOCAL_USER_ID=\$UID -it <image> as an example}" # ${LOCAL_USER_ID:-2001}
USER_ID=1000

if [ -z ${USER_ID} ]; then
  echo "USER_ID NOT SET"
  echo "Please pass environmental variable LOCAL_USER_ID to the run command."
  echo "docker run -e LOCAL_USER_ID=\$UID -it <image> as an example."
  exit 1
fi

# The HOME directory is not setup in the docker context yet
# we need that to be setup before we call the main startup script.
export HOME=${VOLTTRON_USER_HOME}
# Add the pip user bin to the path since we aren't using the
# virtualenv environment in the distribution.
export PATH=$HOME/.local/bin:$PATH
VOLTTRON_UID_ORIGINAL=`id -u volttron`

if [ $VOLTTRON_UID_ORIGINAL != $USER_ID ]; then
  echo "Changing volttron USER_ID to match passed LOCAL_USER_ID ${USER_ID} "
  usermod -u $USER_ID volttron
fi
# echo "Exporting HOME"
# export HOME=${VOLTTRON_USER_HOME}

# # Only need to change
# if [ -z "${VOLTTRON_USER_HOME}" ]; then
#   echo "chown volttron.volttron -R $VOLTTRON_USER_HOME"
#   chown volttron.volttron -R ${VOLTTRON_USER_HOME}
# fi

# echo "cd to $VOLTTRON_USER_HOME"
# cd ${VOLTTRON_USER_HOME}

# # if [ ! -f "platform_config.yml" ]; then
# #   echo "File not found at $VOLTTRON_USER_HOME/platform_config.yml";
# #   echo "mount or copy file into child container."
# #   exit 1;
# # fi

# For tests that need to use Docker, we need to restart the virtual machine so that user added to 'docker' group, such as user 'volttron' can have privileges to run Docker.
# See step 3 of "Manage Docker as a non-root user" https://docs.docker.com/engine/install/linux-postinstall/
# However, rebooting a container results in a "System has not been booted with systemd as init system (PID 1)."
# Thus, in order to give Docker privileges to 'volttron' user, '/var/run/docker/sock' is modified to be readable, writable, and executable by all users.
# This is obviously a security risk, however, given that the container that uses this `entrypoint.sh` is ephemeral and used only for testing, the risk
# is minimal and more importantly allows successful level one integration testing on Travis CI.
chmod 777 /var/run/docker.sock


if [[ $# -lt 1 ]]; then
  echo "Please provide a command to run (e.g. /bin/bash, volttron -vv)";
  exit 1;
else
  echo "now Executing $@";
  #chroot --userspec volttron ${VOLTTRON_ROOT} "$@";
  exec gosu volttron "$@";
fi
