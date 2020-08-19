.. _Testing-Driver-Scalability:

Scalability Planning
====================

Goals
-----

-  Determine the limits of the number of devices that can be interacted
   with via a single Volttron platform.
-  Determine how scaling out affects the rate at which devices are
   scraped. i.e. How long from the first device scrape to the last?
-  Determine the effects of socket throttling in the master driver on
   the performance of Modbus device scraping.
-  Measure total memory consumption of the Master Driver Agent at scale.
-  Measure how well the base history agent and one or more of the
   concrete agents handle a large amount of data.
-  Determine the volume of messages that can be achieved on the pubsub
   before the platform starts rejecting them.

Test framework
--------------

Test Devices
~~~~~~~~~~~~

Simple, command line configured virtual devices to test against in both
Modbus and BACnet flavors. Devices should create 10 points to read that
generate either random or easily predictable (but not necessarily
constant) data. Process should be completely self contained.

Test devices will be run on remote hosts from the Volttron test
deployment.

Launcher Script
~~~~~~~~~~~~~~~

-  The script will be configurable as to the number and type of devices
   to launch.
-  The script will be configurable as to the hosts to launch virtual
   devices on.
-  The script (probably a fabric script) will push out code for and
   launch one or more test devices on one or more machines for the
   platform to scrape.
-  The script will generate all of the master driver configuration files
   to launch the master driver.
-  The script may launch the master driver.
-  The script may launch any other agents used to measure performance.

Shutdown Script
~~~~~~~~~~~~~~~

-  The script (probably the same fabric script run with different
   options) will shutdown all virtual drivers on the network.
-  The script may shutdown the master driver.
-  The script may shutdown any related agents.

Performance Metrics Agent
~~~~~~~~~~~~~~~~~~~~~~~~~

This agent will track the publishes by the different drivers and
generate data in some form to indicate:

-  Total time for all devices to be scraped
-  Any devices that were not successfully scraped.
-  Performance of the message bus.

Additional Benefits
~~~~~~~~~~~~~~~~~~~

Most parts of a test bed run should be configurable. If a user wanted to
verify that the Master Driver worked, for instance, they could run the
test bed with only a few virtual device to confirm that the platform is
working correctly.

Running a simple test
~~~~~~~~~~~~~~~~~~~~~

| You will need 2 open terminals to run this test. (3 if you want to run
  the platform in it's own terminal)
| Checkout the feature/scalability branch.

Start the platform.

Go to the volttron/scripts/scalability-testing directory in two
different terminals. (Both with the environment activated)

In one terminal run:

::

    python config_builder.py --count=1500 --scalability-test --scalability-test-iterations=6 fake fake18.csv localhost

Change the path to fake.csv as needed.

(Optional) After it finishes run:

::

    ./launch_fake_historian.sh 

to start the null historian.

In a separate terminal run:

::

    ./launch_scalability_drivers.sh

to start the scalability test.

This will emulate the scraping of 1500 devices with 18 points each 6
times, log the timing, and quit.

Redirecting the driver log output to a file can help improve
performance. Testing should be done with and without the null historian.

Currently only the depth first all is published by drivers in this
branch. Uncomment the other publishes in driver.py to test out full
publishing. fake.csv has 18 points.

Optionally you can run two listener agents from the volttron/scripts
directory in two more terminals with the command:

::

    ./launch_listener.sh

and rerun the test to see the how it changes the performance.

Real Driver Benchmarking
------------------------

Scalability testing using actual MODBUS or BACnet drivers can be done
using the virtual device applications in the
scripts/scalability-testing/virtual-drivers/ directory. The
configuration of the master driver and launching of these virtual
devices on a target machine can be done automatically with fabric.

Setup
~~~~~

This requires two computers to run: One for the VOLTTRON platform to run
the tests on ("the platform") and a target machine to host the virtual
devices ("the target").

Target setup
^^^^^^^^^^^^

The target machine must have the VOLTTRON source with the
feature/scalability branch checked out and bootstrapped. Make a note of
the directory of the VOLTTRON code.

Platform setup
^^^^^^^^^^^^^^

With the VOLTTRON environment activated install fabric.

::

    pip install fabric

Edit the file scripts/scalability-testing/test\_settings.py as needed.

-  virtual\_device\_host (string) - Login name and IP address of the
   target machine. This is used to remotely start and stop virtual
   devices via ssh. `"volttron@10.0.0.1 <mailto:"volttron@10.0.0.1>`__"

-  device\_types - map of driver types to tuple of the device count and
   registry config to use for the virtual devices. Valid device types
   are "bacnet" and "modbus".

-  volttron\_install - location of volttron code on the target.

To configure the driver on the platform and launch the virtual devices
on the target run

::

    fab deploy_virtual_devices

When prompted enter the password for the target machine. Upon completion
virtual devices will be running on the target and configuration files
written for the master driver.

Launch Test
^^^^^^^^^^^

If your test includes virtual BACnet devices be sure to configure and
launch the BACnet Proxy before launching the scalability driver test.

(Optional)

::

    ./launch_fake_historian.sh 

to start the null historian.

In a separate terminal run:

::

    ./launch_scalability_drivers.sh

to start the scalability test.

To stop the virtual devices run

::

    fab stop_virtual_devices

and enter the user password when prompted.
