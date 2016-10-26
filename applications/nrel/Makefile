
all: radiothermostatrelay  API_test_radiothermostatrelay cea2045relay API_test_cea2045relay schouse_controller vtime_now

radiothermostatrelay:
		volttron-ctl remove --force --tag radiothermostatrelay
		volttron-pkg package $(AGENTS_HOME)/RadioThermostatRelayAgent/
		volttron-pkg configure $(VOLTTRON_HOME)/packaged/radiothermostatrelayagent-3.0-py2-none-any.whl $(AGENTS_HOME)/RadioThermostatRelayAgent/config
		volttron-ctl install radiothermostatrelay=$(VOLTTRON_HOME)/packaged/radiothermostatrelayagent-3.0-py2-none-any.whl

API_test_radiothermostatrelay:
		volttron-ctl remove --force --tag API_test_radiothermostatrelay
		volttron-pkg package $(AGENTS_HOME)/RadioThermostatRelayAgent/
		volttron-pkg configure $(VOLTTRON_HOME)/packaged/radiothermostatrelayagent-3.0-py2-none-any.whl $(AGENTS_HOME)/RadioThermostatRelayAgent/config_api_test
		volttron-ctl install API_test_radiothermostatrelay=$(VOLTTRON_HOME)/packaged/radiothermostatrelayagent-3.0-py2-none-any.whl

cea2045relay:
		volttron-ctl remove --force --tag cea2045relay
		volttron-pkg package $(AGENTS_HOME)/CEA2045RelayAgent/
		volttron-pkg configure $(VOLTTRON_HOME)/packaged/cea2045relayagent-3.0-py2-none-any.whl $(AGENTS_HOME)/CEA2045RelayAgent/config
		volttron-ctl install cea2045relay=$(VOLTTRON_HOME)/packaged/cea2045relayagent-3.0-py2-none-any.whl

schouse_controller:
		volttron-ctl remove --force --tag schouse_controller
		volttron-pkg package $(AGENTS_HOME)/SC_HouseAgent/
		volttron-pkg configure $(VOLTTRON_HOME)/packaged/schouseagent-3.0-py2-none-any.whl $(AGENTS_HOME)/SC_HouseAgent/config
		volttron-ctl install schouse_controller=$(VOLTTRON_HOME)/packaged/schouseagent-3.0-py2-none-any.whl


API_test_cea2045relay:
		volttron-ctl remove --force --tag API_test_cea2045relay
		volttron-pkg package $(AGENTS_HOME)/CEA2045RelayAgent/
		volttron-pkg configure $(VOLTTRON_HOME)/packaged/cea2045relayagent-3.0-py2-none-any.whl $(AGENTS_HOME)/CEA2045RelayAgent/config_api_test
		volttron-ctl install API_test_cea2045relay=$(VOLTTRON_HOME)/packaged/cea2045relayagent-3.0-py2-none-any.whl


vtime_now:
	volttron-ctl remove --force --tag vtime_now
	volttron-pkg package $(AGENTS_HOME)/VolttimeAgent
	volttron-pkg configure $(VOLTTRON_HOME)/packaged/volttimeagent-3.0-py2-none-any.whl $(AGENTS_HOME)/VolttimeAgent/config
	volttron-ctl install vtime_now=$(VOLTTRON_HOME)/packaged/volttimeagent-3.0-py2-none-any.whl
