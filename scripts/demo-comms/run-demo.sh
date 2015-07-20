. vars.sh
. prepare.sh

./start-platforms.sh

#echo "START make-hello1"
#VOLTTRON_HOME=$V1_HOME ./make-hello1
#echo "START make-hello2"
#VOLTTRON_HOME=$V2_HOME ./make-hello2

#./make-platform-historians

echo "Launching browser"
x-www-browser http://localhost:8080 &

