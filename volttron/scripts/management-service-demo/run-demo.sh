. demo-vars.sh

./demo-setup.sh
./start-platforms.sh
VOLTTRON_HOME=$V1_HOME ./make-management
VOLTTRON_HOME=$V1_HOME ./make-platform1
VOLTTRON_HOME=$V2_HOME ./make-platform2
VOLTTRON_HOME=$V3_HOME ./make-platform3
#VOLTTRON_HOME=$V1_HOME ./make-hello1
#VOLTTRON_HOME=$V2_HOME ./make-hello2

echo "starting platform manager"
VOLTTRON_HOME=$V1_HOME volttron-ctl start --tag manageragent
echo "starting platform agent 1"
VOLTTRON_HOME=$V1_HOME volttron-ctl start --tag platformagent
echo "starting platform agent 2"
VOLTTRON_HOME=~/v2home volttron-ctl start --tag platformagent

echo "Launching browser"
x-www-browser http://localhost:8080

