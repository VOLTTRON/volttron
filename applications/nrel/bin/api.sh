
rm volttron.log
rm status.log

volttron -vv -l volttron.log &
volttron-ctl start --tag API_test_cea2045relay
volttron-ctl start --tag API_test_radiothermostatrelay
volttron-ctl start --tag schouse_controller
volttron-ctl start --tag vtime_now

volttron-ctl status 
