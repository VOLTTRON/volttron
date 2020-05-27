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

1. Install python. Suggested 3.6.

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

Assumptions
~~~~~~~~~~~

-  Device driver agent is already developed

Installation:
~~~~~~~~~~~~~

1. Install VOLTTRON on a VM or different system than the one
   running Matlab.

    Follow link: http://volttron.readthedocs.io/en/develop/install.html

2. Add subtree volttron-applications under volttron/applications by using
   the following command:

.. code-block:: console

    git subtree add --prefix applications https://github.com/VOLTTRON/volttron-applications.git develop --squash

Configuration
~~~~~~~~~~~~~

1. Copy example configuration file `applications/pnnl/DrivenMatlabAgent/config_waterheater` to `volltron/config`.

2. Change config\_url and data\_url in the new config file to the
   ipaddress of machine running Matlab. Keep the same port numbers.

3. Change campus, building and unit (device) name in the config file.

4. Open example.m and change following line:

.. code-block:: matlab

   matlab_result = '{"commands":{"Zone1":[["temperature",27]],"Zone2":[["temperature",28]]}}';

Change it to include correct device name and point names in the format:

.. code-block:: matlab

   '{"commands":{"device1":[["point1",value1]],"device2":[["point2",value2]]}}';

Steps to test integration:
~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Start VOLTTRON

2. Run Actuator

3. Run device driver agent

4. Run DrivenMatlabAgent with the new config file

5. Run example.m in Matlab

Now whenever the device driver publishes the state of devices listed in the
config file of DrivenMatlabAgent, DrivenMatlabAgent will send it to Matlab
application and receive commands to send to devices.

Resources
---------

http://www.mathworks.com/help/matlab/getting-started_buik_wp-3.html

.. |Architecture| image:: files/matlab-archi.png
   :width: 4.62464in
   :height: 2.99070in
