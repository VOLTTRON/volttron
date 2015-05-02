# bring in the vars that are to be available for this script
. demo-vars.sh

./demo-setup.sh
echo "Starting platform 1: $V1_HOME"
VOLTTRON_HOME=$V1_HOME volttron -vv&
echo "Starting platform 2: $V2_HOME"
VOLTTRON_HOME=$V2_HOME volttron -vv&
echo "Starting platform 3: $V3_HOME"
VOLTTRON_HOME=$V3_HOME volttron -vv&
echo "START make-management"
VOLTTRON_HOME=$V1_HOME ./make-volttroncentral
echo "START make-platform1"
VOLTTRON_HOME=$V1_HOME ./make-platform1
echo "START make-platform2"
VOLTTRON_HOME=$V2_HOME ./make-platform2
echo "START make-platform3"
VOLTTRON_HOME=$V3_HOME ./make-platform3
echo "START make hello2"
VOLTTRON_HOME=$V2_HOME ./make-hello2
echo "START platform manager"
VOLTTRON_HOME=$V1_HOME volttron-ctl start --tag manageragent
echo "START platform agent 2"
VOLTTRON_HOME=$V2_HOME volttron-ctl start --tag platformagent
echo "START platform agent 3"
VOLTTRON_HOME=$V3_HOME volttron-ctl start --tag platformagent
