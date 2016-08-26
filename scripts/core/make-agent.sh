if [ -z "$VOLTTRON_HOME" ]; then
  VOLTTRON_HOME=$HOME/.volttron
  echo "VOLTTRON_HOME UNSET setting to $VOLTTRON_HOME";
fi

echo "VOLTTRON_HOME=$VOLTTRON_HOME"

# Requrie the TAG variable to be set.
if [ -z "$TAG" ]; then
  echo "The agent tag must be set.";
  exit 0
fi


COMMAND_ARGS=""

if [ ! -z "$VIP_ADDRESS" ]; then
  COMMAND_ARGS="$COMMAND_ARGS --vip-address $VIP_ADDRESS"
  echo "Using VIP_ADDRESS: $VIP_ADDRESS";


else
#Default to the ipc socket
  VIP_ADDRESS="ipc://@$VOLTTRON_HOME/run/vip.socket"
  COMMAND_ARGS="$COMMAND_ARGS --vip-address $VIP_ADDRESS"
  echo "Using VIP_ADDRESS: $VIP_ADDRESS";

fi

COMMAND="volttron-ctl"

START="$COMMAND start --tag $TAG $COMMAND_ARGS"
STOP="$COMMAND stop --tag $TAG $COMMAND_ARGS"
REMOVE="$COMMAND remove --tag $TAG $COMMAND_ARGS"
ENABLE="$COMMAND enable --tag $TAG $COMMAND_ARGS"
DISABLE="$COMMAND disable --tag $TAG $COMMAND_ARGS"



if [ ! -e "./volttron/platform" ]; then
    echo "Please execute from root of volttron repository."
    exit 0
fi

#export VOLTTRON_HOME=$VOLTTRON_HOME
# Require the SOURCE variable to be set to the agent directory
if [ -z "$SOURCE" ]; then
  echo "SOURCE variable must be set to the Agent directory.";
  exit 0
fi

# Require the CONFIG variable to be set to a config file
if [ -z "$CONFIG" ]; then
  echo "CONFIG variable must be set to the Agent config file.";
  exit 0
fi


# Attempt to remove the agent by the tag.
SCRIPTS_CORE="./scripts/core"
#$SCRIPTS_CORE/remove_agent.sh $TAG

#TODO: put this into a script on its own

$STOP
$DISABLE
$REMOVE

# For packaging of scripts us pack_install
PACK="$SCRIPTS_CORE/pack_install.sh"

echo $PACK $SOURCE $CONFIG $TAG
# Install and start HIST.
$PACK $SOURCE $CONFIG $TAG

echo "$START"
$START

if [ "$1" = "enable" ]
then
    $ENABLE
fi
