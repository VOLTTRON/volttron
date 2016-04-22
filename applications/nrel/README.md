##VOLTTRON in ESIF:

**Contributors:**

Deepthi Vaidhynathan, Xin Jin, Wesley Jones, Harry Sorensen - National Renewable Energy Laboratory  

**Agents:**

**CEA-2045:**

The CEA-2045 standard specifies a modular communications interface (MCI) to facilitate communications with residential devices for applications such as energy management. The MCI provides a standard interface for energy management signals and messages to reach devices. Typical devices include energy management controllers, appliances, sensors, and other consumer products. CEA-2045 standard is analogous to the USB standard for the computer electronics; any residential devices that is CEA-2045 compliant should be play-and-plug.

- This agent acts as a relay for CEA2045 compliant appliance, it translates controls from a controller and relays it to the appliance
- This agent can be configured to communicate with a real hardware or to a simulated object.
- For the purpose of API and Functional Test, you would use the simulated object
- To connect with a real device, specify the USB port and baud rate in the config file

```
config
**********************************************
{

"agentid": "CEA2045",
"message": "hello from CEA2045",
"device1_usb_port" : "/dev/cu.usbserial-A603Y394",
"device1_baud_rate" : 19200,
"device_type" : 1
}
**********************************************

config_api_test
**********************************************
{
"agentid": "CEA2045 - Test",
"message": "hello from CEA2045 test",
"device1_usb_port" : "None",
"device1_baud_rate" : 0,
"device_type" : 1
}
**********************************************
```



**Radio Thermostat:**

Implementing the most common functions.
Radio Thermostat Company of America, Wi-Fi USNAP Module API, Version 1.3, March 22, 2012. Available on http://lowpowerlab.com/downloads/RadioThermostat_CT50_Honeywell_Wifi_API_V1.3.pdf. Retrieved on April 6, 2016.

- This agent acts as a relay for a thermostat, it translates controls from a controller and relays it to the appliance
- This agent can be configured to communicate with a real hardware or to a simulated object.
- For the purpose of API and Functional Test, you would use the simulated object
- To connect with a real device specify the url in the config file

```
config
**********************************************
{
"agentid": "Thermostat",
"message": "hello from thermostat",
"url_address" : "http://10.10.47.12/tstat"
}
**********************************************

config_api_test
**********************************************
{
"agentid": "Thermostat Test",
"message": "hello from Thermostat test",
"url_address" : "Fake"
}
**********************************************
```


**SC_House-Agent:**

  - This is an example controller to which shows how to write control signals for the above two relays

**Volttime-Agent:**

  - This agent publishes the actual time on the bus, all agents subscribe to this, for synchronized execution



**Environment**
  - Activate the volttron environment and set VOLTTRON_HOME to point to your volttron home directory
  - set export AGENTS_HOME=`pwd`/agents (agents directory) - used by Makefile

**bin**
  - This directory contains scripts to start all agents
      - make all
      - . bin/api.sh
      - . bin/hardware.sh

**Makefile**
  - The Makefile is used to package and install all agents in the agents directory

**Unit-test for API**
  - The Thermostat and CEA2045 have API that are used to talk to the appliances.
  - There are unittest in those directories to test the APIs
  - ***To test  the CEA-2045 API:***
```
$cd agents/CEA2045RelayAgent/cea2045relay/
$export PYTHONPATH=./:$PYTHONPATH
$ nosetests API_test.py -v
Test emergency command ... ok
Test normal run ... ok
Test shed command ... ok

----------------------------------------------------------------------
Ran 3 tests in 0.001s

OK

```
  - ***To test  the Thermostat API:***
```
$cd agents/ThermostatRelayAgent/thermostatrelay/
$export PYTHONPATH=./:$PYTHONPATH
$ nosetests API_test.py -v
Test  mode() interface ... ok
Test  t_cool() interface ... ok
Test  t_heat() interface ... ok
Test the tstat() interface ... ok

----------------------------------------------------------------------
Ran 4 tests in 0.001s

OK

```
