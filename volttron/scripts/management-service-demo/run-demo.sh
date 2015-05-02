. demo-vars.sh

./demo-setup.sh

echo "START start-platforms"
VOLTTRON_HOME=$V1_HOME volttron -vv&
echo "Starting platform 2"
VOLTTRON_HOME=$V2_HOME volttron -vv&
echo "Starting platform 3"
VOLTTRON_HOME=$V3_HOME volttron -vv&
echo "START make-volttroncentral"
VOLTTRON_HOME=$V1_HOME ./make-volttroncentral
echo "START make-platform1"
VOLTTRON_HOME=$V1_HOME ./make-platform1
echo "START make-platform2"
VOLTTRON_HOME=$V2_HOME ./make-platform2
echo "START make-platform3"
VOLTTRON_HOME=$V3_HOME ./make-platform3
echo "START make-hello1"
VOLTTRON_HOME=$V1_HOME ./make-hello1
echo "START make-hello2"
VOLTTRON_HOME=$V2_HOME ./make-hello2

echo "starting platform manager"
VOLTTRON_HOME=$V1_HOME volttron-ctl start --tag manageragent
echo "starting platform agent 1"
VOLTTRON_HOME=$V1_HOME volttron-ctl start --tag platformagent
echo "starting platform agent 2"
VOLTTRON_HOME=$V2_HOME volttron-ctl start --tag platformagent
echo "starting platform agent 3"
VOLTTRON_HOME=$V3_HOME volttron-ctl start --tag platformagent


echo "Launching browser"
x-www-browser http://localhost:8080 &

