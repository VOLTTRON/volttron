.. _CSV Driver and Driver Test Agent:

==========
CSV Driver
==========

This example driver writes data to "registers" as lines in a CSV file. This
driver is an example driver for development purposes only.

In order to run this driver, put the csvdriver.py file into the platform driver's
interfaces directory, then configure the platform driver normally using the
included csv_driver.config configuration file and csv_registers.csv registry
configuration file (see devguides > walkthroughs > Driver-Creation-Walkthrough
for a more in-depth explanation of the driver framework, including configuration
, directory structure, etc.) To see csv driver publishes, start the master
driver and listener agents.

=====================
CSV Driver Test Agent
=====================

This example agent was developed to test the basic functionality of the CSV
example driver. This agent performs 2 functions:

    1. The driver subscribes to an all publish for a configured device topic.
    When the publish occurs, a callback is called which logs a message
    indicating that the publish has occurred and been read by the agent. This is
    useful for ensuring that the regular scrape_all publishes are working.
    2. The driver will periodically create a schedule request for the actuator
    for the next 10 seconds on the "device", then request that the actuator set
    a point on the device. This serves the purpose of ensuring that the set
    point function works, as well as demonstrating state changes for the device
    during scrape_all.

To use this agent as-is, install it as normal with the provided configuration
file ("config" in the agent's directory), install an actuator agent instance
(minimal or no configuration is necessary in the easiest case), and install a
listener agent instance. If the driver code file is in the platform driver's
interfaces directory the user should see publishes via the listener agent and
logging from this agent which indicates that the driver is functioning (some
values in the scrape_all publish should oscillate to demonstrate that the driver
is working).

This agent is not intended for any kind of production use, and it may require
additional adaptation based on the testing needs of a given driver. This agent
may be used as an example for interacting with an actuator agent, and serve
as a jumping-off point for other simple test agents.
