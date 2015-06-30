# bring in the vars that are to be available for this script
. vars.sh

echo "Starting platform 1: $V1_HOME"
VOLTTRON_HOME=$V1_HOME volttron -vv -l $V1_HOME/volttron.log --vip-address=tcp://127.0.0.2:8081&
echo "Starting platform 2: $V2_HOME"
VOLTTRON_HOME=$V2_HOME volttron -vv -l $V2_HOME/volttron.log --vip-address=tcp://127.0.0.1:8081&

echo "Making volttron central on $V1_HOME"
VOLTTRON_HOME=$V1_HOME ../pack_install.sh ../../Agents/VolttronCentralAgent/ \
./volttron-central-config volttroncentral

echo "START volttron central"
VOLTTRON_HOME=$V1_HOME volttron-ctl start --tag volttroncentral

echo "Make platform1 on $V1_HOME"
VOLTTRON_HOME=$V1_HOME ../pack_install.sh ../../Agents/PlatformAgent/ \
./platform-config1 platformagent

echo "Start make-platform1"
VOLTTRON_HOME=$V1_HOME volttron-ctl start --tag platformagent

echo "Make platform2 on $V2_HOME"
VOLTTRON_HOME=$V2_HOME ../pack_install.sh ../../Agents/PlatformAgent/ \
./platform-config2 platformagent

echo "START platform agent 2"
VOLTTRON_HOME=$V2_HOME volttron-ctl start --tag platformagent

