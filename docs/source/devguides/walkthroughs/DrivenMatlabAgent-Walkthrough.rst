=====================================================================================
How to integrate Matlab application with VOLTTRON to send control commands to devices
=====================================================================================

Overview:
=========

    Matlab-VOLTTRON integration allows Matlab application to receive
    data from devices and send control commands to change points on
    those devices.

    DrivenMatlabAgent in VOLTTRON allows this interaction by using zmq
    sockets to communicate with Matlab application.

Data Flow Architecture:
-------------

|Architecture|


Installation steps for system running Matlab:
=============================================

1. Install python. Suggested 3.4. Other supported versions 2.7, 3.3.

2. Install pyzmq (tested with version 15.2.0)

    Follow steps at: https://github.com/zeromq/pyzmq

1. Matlab (tested with R2015b)

2. Setup python path inside Matlab

   Open Matlab command window and set python path as:

   pyversion [*path/to]*/python.exe

3. To test if python path is setup correctly type following in Matlab
   command window and it should show python.exe path with version
   information.

    pyversion

1. To test if pyzmq library is installed correctly and is accessible
   from python inside Matlab, type following in Matlab command window
   and it should show pyzmq version installed.

   py.zmq.pyzmq\_version()

2. Copy example.m from volttron/examples/MatlabControlApplication to your desired folder.

Run and test Matlab VOLTTRON Integration:
=========================================

Assumptions
-----------

-  Device driver agent is already developed

Installation:
--------------

1. Install VOLTTRON on a VM or different system than the one
   running Matlab.

    Follow link: http://volttron.readthedocs.io/en/develop/install.html

2. Add subtree volttron-applications under volttron/applications by using following command:

    git subtree add --prefix applications https://github.com/VOLTTRON/volttron-applications.git develop --squash

Configuration
-------------

1. Copy example configuration file applications/pnnl/DrivenMatlabAgent/config\_waterheater to volltron/config.

2. Change config\_url and data\_url in the new config file to the
   ipaddress of machine running Matlab. Keep the same port numbers.

3. Change campus, building and unit (device) name in the config file.

4. Open example.m change following line :

   matlab\_result =
   '{"commands":{"Zone1":[["temperature",27]],"Zone2":[["temperature",28]]}}';

   Change it to include correct device name and point names in the
   format:

   '{"commands":{"device1":[["point1",value1]],"device2":[["point2",value2]]}}';

Steps to test integration:
---------------------------

1. Start VOLTTRON

2. Run Actuator

3. Run device driver agent

4. Run DrivenMatlabAgent with the new config file.

5. Run example.m

Now whenever device driver publish state of devices listed in config
file of DrivenMatlabAgent, DrivenMatlabAgent will send it to Matlab
application and receive commands to send to devices.

Resources
=========

http://www.mathworks.com/help/matlab/getting-started_buik_wp-3.html

.. |Architecture| image:: files/matlab-archi.png
   :width: 4.62464in
   :height: 2.99070in
