.. C Driver and C Test Agent:

==========
C Driver
==========

The C Driver is an example implementation of an interface that
allows the platform driver to transparently call C code.

In order to run this driver, put the cdriver.py file into the platform driver's
interfaces directory, then configure the platform driver normally using the
included test_cdriver.config configuration file (see the 
[Driver Framework overview](https://volttron.readthedocs.io/en/main/driver-framework/drivers-overview.html) 
and the [Driver Development overview](https://volttron.readthedocs.io/en/main/driver-framework/drivers-overview.html) 
for a more in-depth explanation of the driver framework, including configuration
, directory structure, etc.) To see csv driver publishes, start the platform
driver and listener agents.

=====================
C Test Agent
=====================

This example agent calls functions from a shared object.

To use this agent as-is, install it as normal with the provided configuration
file ("config" in the agent's directory)

This agent is not intended for any kind of production use, and it may require
additional adaptation based on the testing needs of a given driver. This agent
may be used as an example for interacting with a shared C object, and serve
as a jumping-off point for other simple test agents.
