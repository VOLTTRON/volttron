## C Driver

The C Driver is an example implementation of an interface that
allows the platform driver to transparently call C code.

In order to run this driver, put the cdriver.py file into the platform driver's
interfaces directory (/services/core/PlatformDriverAgent/platform_driver/interfaces),
build the shared C object using the `make all` command (if not already done so), 
add the path to the shared C object to the test_cdriver.config configuration file, 
and then configure the platform driver normally using the test_cdriver.config configuration 
file (see [here](https://volttron.readthedocs.io/en/main/driver-framework/platform-driver/platform-driver.html#adding-device-configurations-to-the-configuration-store))
for instructions on configuring the platform driver). To see that the C driver publishes, 
start the platform driver, listener agent, and the C Agent described below, then view 
the volttron.log file to confirm the driver is running.

See the [Driver Framework overview](https://volttron.readthedocs.io/en/main/driver-framework/drivers-overview.html) 
and the [Driver Development overview](https://volttron.readthedocs.io/en/main/driver-framework/drivers-overview.html) 
for a more in-depth explanation of the driver framework, including configuration, 
directory structure, etc.

## C Test Agent

This example agent calls functions from a shared object.

To use this agent as-is, build the shared C object using the `make all` command 
(if not already done so) and then install it as normal with the provided configuration
file ("config" in the agent's directory). For more information on installing and
running agents, see the [Agent Control Commands](https://volttron.readthedocs.io/en/main/platform-features/control/agent-management-control.html).

This agent is not intended for any kind of production use, and it may require
additional adaptation based on the testing needs of a given driver. This agent
may be used as an example for interacting with a shared C object, and serve
as a jumping-off point for other simple test agents.
