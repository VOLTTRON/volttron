./demo-setup.sh
./start-platforms.sh
VOLTTRON_HOME=~/v1home ./make-management
VOLTTRON_HOME=~/v1home ./make-platform1
VOLTTRON_HOME=~/v2home ./make-platform2
VOLTTRON_HOME=~/v1home ./make-hello1
VOLTTRON_HOME=~/v2home ./make-hello2

VOLTTRON_HOME=~/v1home volttron-ctl start --tag manageragent
VOLTTRON_HOME=~/v1home volttron-ctl start --tag platformagent
VOLTTRON_HOME=~/v2home volttron-ctl start --tag platformagent


x-www-browser http://localhost:8080

