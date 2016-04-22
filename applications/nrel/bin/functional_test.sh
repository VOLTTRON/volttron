
rm volttron.log
rm status.log

volttron -vv -l volttron.log &
volttron-ctl start --tag API_test_cea2045relay
volttron-ctl start --tag API_test_radiothermostatrelay
volttron-ctl start --tag schouse_controller
volttron-ctl start --tag vtime_now

volttron-ctl status >> status.log

test_result=`grep -o "running" status.log | wc -l`
export test_result
sleep 300

volttron-ctl shutdown
ps -fe | grep volttron | awk '{print $2}' | xargs kill -9
ps -fe | grep python | awk '{print $2}' | xargs kill -9

if [ $test_result = 4 ]; then
   echo "Functional Test: Passed"
else
   echo "Functional Test: Failed"
fi
