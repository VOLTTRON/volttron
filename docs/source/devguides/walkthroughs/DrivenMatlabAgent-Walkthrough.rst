.. _MatLabBridge:

MatLab Integration
==================


Overview:
---------

Matlab-VOLTTRON integration allows Matlab applications to receive
data from devices and send control commands to change points on
those devices.

DrivenMatlabAgent in VOLTTRON allows this interaction by using ZeroMQ
sockets to communicate with the Matlab application.

Data Flow Architecture:
~~~~~~~~~~~~~~~~~~~~~~~

|Architecture|


Installation steps for system running Matlab:
---------------------------------------------

1. Install python. Suggested 3.4. Other supported versions are 2.7, 3.3.

2. Install pyzmq (tested with version 15.2.0)
   Follow steps at: https://github.com/zeromq/pyzmq

3. Install Matlab (tested with R2015b)

4. Start Matlab and set the python path.
   In the Matlab command window set the python path with `pyversion`:

.. code-block:: console

   >> pyversion python.exe

5. To test that the python path has been set correctly type following in
   the Matlab command window. Matlab shoud print the python path with version
   information.

.. code-block:: console

   >> pyversion

6. To test that the pyzmq library is installed correctly and is accessible
   from python inside Matlab, type the following in Matlab command window
   and it should show pyzmq version installed.

.. code-block:: console

   >> py.zmq.pyzmq_version()

7. Copy `example.m` from `volttron/examples/ExampleMatlabApplication/matlab`
   to your desired folder.

Run and test Matlab VOLTTRON Integration:
-----------------------------------------

Installation:
~~~~~~~~~~~~~

1. Install VOLTTRON on a VM or different system than the one
   running Matlab.

    Follow link: http://volttron.readthedocs.io/en/develop/install.html

2. Add subtree volttron-applications under volttron/applications by using
   the following command:

.. code-block:: console

    git subtree add --prefix applications https://github.com/VOLTTRON/volttron-applications.git develop --squash

Install Dependencies
~~~~~~~~~~~~~~~~~~~~

To test the interaction between matlab driven agent and matlab code you would
 need the following agents running

1. Actuator Agent

Run the following command to install and start Actuator agent if you don't
already have it running

.. code-block:: console

   python scripts/install-agent.py  -s services/core/ActuatorAgent

2. Run master driver and configure it to publish device data.

   The easiest way to do this for testing is to use the volttron-cfg command.
    This command needs to be run when volttron instance is not running.
    It can install master driver and sets up a fake device. Code snippet below
    shows an example run of the volttron-cfg command. Say "Y" to the prompt to
    install a master driver and a fake device,
    fake-campus/fake-building/fake-device.

.. code-block:: console

   (volttron)[velo@osboxes myvolttron]$ ./stop-volttron
   Shutting down VOLTTRON
   (volttron)[velo@osboxes myvolttron]$ volttron-cfg

   Your VOLTTRON_HOME currently set to: /home/velo/volttron_test

   Is this the volttron you are attempting to setup?  [Y]: y
   What is the external instance ipv4 address? [tcp://127.0.0.1]:
   What is the instance port for the vip address? [22916]:
   Is this instance a volttron central? [N]: N
   Will this instance be controlled by volttron central? [Y]: N
   Would you like to install a platform historian? [N]: N
   Would you like to install a master driver? [N]: Y
   Configuring /home/velo/workspace/myvolttron/services/core/MasterDriverAgent
   Install a fake device on the master driver? [N]: Y
   Should agent autostart? [N]:
   Would you like to install a listener agent? [N]: Y
   Configuring examples/ListenerAgent
   Should agent autostart? [N]: N
   Finished configuration

3. Start volttron.

Configuration
~~~~~~~~~~~~~
1. Create a config directory in your volttron source directory if one doesn't
   already exist

2. Copy example configuration file
   `applications/pnnl/DrivenMatlabAgent/config_waterheater` to `volltron/config`.

3. Change config\_url and data\_url in the new config file to the
   ipaddress of machine running Matlab. Keep the same port numbers.

4. Change campus, building and unit (device) name in the config file. If you
   used volttron-cfg command to configure a fake device it would be fake-campus,
   fake-building, and fake-device respectively

5. Update arguments, conversion_map, and unittype field to use the correct point name(s).
   Following is an example of config with a single point "temperature"

.. code-block:: python
   "arguments": {
        "temperature": "temperature",

        "config_url": "tcp://<ip address of machine running matlab>:5556",
        "data_url": "tcp://<ip address of machine running matlab>:5557",
        "recv_timeout": 50000
    },
    "conversion_map": {
        "temperature*": "float"
    },
    "unittype_map": {
        "temperature*": "Farenheit"
    }

5. Open example.m and change following line:

.. code-block:: matlab

   matlab_result = '{"commands":{"Zone1":[["temperature",27]],"Zone2":[["temperature",28]]}}';

Change it to include correct device name(instead of Zone1 and Zone2) and point
names(instead of "temperature") in the format:

.. code-block:: matlab

   '{"commands":{"device1":[["point1",value1]],"device2":[["point2",value2]]}}';

If you used volttron-cfg for setting up fake device then you can leave point
name as "temperature"

Steps to test integration:
~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Start VOLTTRON

2. Run Actuator

3. Run device driver agent

4. Install  DrivenMatlabAgent with the new config file

.. code-block:: console

   python scripts/install-agent.py  -s applications/pnnl/DrivenMatlabAgent -c config/config_waterheater

5. Run DrivenMatlabAgent

6. Run example.m in Matlab

Now whenever the device driver publishes the state of devices listed in the
config file of DrivenMatlabAgent, DrivenMatlabAgent will send it to Matlab
application and receive commands to send to devices.

Resources
---------

http://www.mathworks.com/help/matlab/getting-started_buik_wp-3.html

.. |Architecture| image:: files/matlab-archi.png
   :width: 4.62464in
   :height: 2.99070in