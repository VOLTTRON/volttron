# bring in the vars that are to be available for this script
. demo-vars.sh

./demo-setup.sh
echo "Starting platform 1: $V1_HOME"
VOLTTRON_HOME=$V1_HOME volttron -vv -l $V1_HOME/volttron.log&
echo "Starting platform 2: $V2_HOME"
VOLTTRON_HOME=$V2_HOME volttron -vv -l $V2_HOME/volttron.log&
echo "Starting platform 3: $V3_HOME"
VOLTTRON_HOME=$V3_HOME volttron -vv -l $V3_HOME/volttron.log&

echo "Make volttron central"
VOLTTRON_HOME=$V1_HOME ./make-volttroncentral
echo "START volttron central"
VOLTTRON_HOME=$V1_HOME volttron-ctl start --tag volttroncentral

echo "Make platform1"
VOLTTRON_HOME=$V1_HOME ./make-platform1
echo "Start make-platform1"
VOLTTRON_HOME=$V1_HOME volttron-ctl start --tag platformagent

echo "Make platform2"
VOLTTRON_HOME=$V2_HOME ./make-platform2
echo "START platform agent 2"
VOLTTRON_HOME=$V2_HOME volttron-ctl start --tag platformagent

echo "Make platform3"
VOLTTRON_HOME=$V3_HOME ./make-platform3
echo "START platform agent 3"
VOLTTRON_HOME=$V3_HOME volttron-ctl start --tag platformagent

