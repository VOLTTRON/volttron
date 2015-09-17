# This script provides a shortcut for issuing VOLTTRON commands when you have 
# setup an externally facing vip address, encryption, and authorization

#Modify these values for your deployment

if [ -z "$VOLTTRON_HOME" ]; then
  VOLTTRON_HOME=$HOME/.volttron
  echo "VOLTTRON_HOME UNSET setting to $VOLTTRON_HOME";
fi

echo "VOLTTRON_HOME=$VOLTTRON_HOME"

if [ -z "$VIP_ADDRESS" ]; then
  VIP_ADDRESS="ipc://@$VOLTTRON_HOME/run/vip.socket"
  COMMAND_ARGS="$COMMAND_ARGS --vip-address $VIP_ADDRESS"
  echo "Using VIP_ADDRESS: $VIP_ADDRESS";

fi



export VIP_ADDRESS="$VIP_ADDRESS"

volttron-ctl $1 --vip-address $VIP_ADDRESS

