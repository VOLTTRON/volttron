.. _BACnet-Auto-Configuration:

===================================================
Automatically Generating BACnet Configuration Files
===================================================

Included with the platform are two scripts for finding and configuring BACnet devices. 
These scripts are located in ``scripts/bacnet``. ``bacnet_scan.py`` will scan
the network for devices. ``grab_bacnet_config.py`` creates a CSV file for 
the BACnet driver that can be used as a starting point for creating
your own register configuration.

Both scripts are configured with the file ``BACpypes.ini``. 

Configuring the Utilities
-------------------------

While running both scripts create a temporary virtual BACnet device 
using the ``bacpypes`` library. The virtual
device must be configured properly in order to work. This
configuration is stored in ``scripts/bacnet/BACpypes.ini`` and will be
read automatically when the utility is run. 

The only value that (usually) needs to be changed is the **address** field.
**This address bound to the port on the machine you are running the script from, NOT
A TARGET DEVICE! ** This value should be set to the IP address of the
network interface used to communicate with the remote device. If there
is more than one network interface the address of the interface
connected to a network that can reach the device must be used.

In Linux you can usually get the addresses bound to all interfaces by running
``ifconfig`` from the command line.

If a different outgoing port other than the default 47808 must be used
the it can be specified as part of the address in the form

    ``<ADDRESS>:<PORT>``
    
In some cases the netmask of the network will be needed for proper configuration.
This can be done following this format

    ``<ADDRESS>/<NETMASK>:<PORT>``
    
where ``<NETMASK>`` is the netmask length. The most commmon value is 24. See http://www.computerhope.com/jargon/n/netmask.htm

In some cases you may also need to specify a different device ID by 
changing the value of **objectIdentifier** so the virtual BACnet device does
not conflict with any devices on the network. **objectIdentifier**
defaults to 599.

Sample BACpypes.ini
*******************

::

    [BACpypes]
    objectName: Betelgeuse
    address: 10.0.2.15/24
    objectIdentifier: 599
    maxApduLengthAccepted: 1024
    segmentationSupported: segmentedBoth
    vendorIdentifier: 15

Scanning for BACnet Devices
---------------------------

If the addresses for BACnet devices are unknown they can be discovered
using the ``bacnet_scan.py`` utility. 

To run the utility simply execute the following command:

    ``python bacnet_scan.py``
    
and expect output similar to this:

::

    Device Address        = <Address 192.168.1.42>
    Device Id             = 699
    maxAPDULengthAccepted = 1024
    segmentationSupported = segmentedBoth
    vendorID              = 15

    Device Address        = <RemoteStation 1002:11>
    Device Id             = 540011
    maxAPDULengthAccepted = 480
    segmentationSupported = segmentedBoth
    vendorID              = 5
    
Reading Output
**************

The address where the device can be reached is listed on the **Device Address** line.
The BACnet device ID is listed on the **Device Id** line.
The remaining lines are informational and not needed to configure the BACnet driver.

For the first example the IP address ``192.168.1.42`` can be used to reach
the device. The second device is behind a BACnet router and can be
reached at ``1002:11``. See RouterAddressing Remote Station addressing.

Options
-------

    - ``--address ADDRESS`` Send the who is request only to a specific address. Useful as a way to ping devices on a network that blocks broadcast traffic.
    - ``--range LOW HIGH`` Specify the device ID range for the results. Useful for filtering.
    - ``--timeout SECONDS`` Specify how long to wait for responses to the original broadcast. This defaults to 5 which should be sufficient for most networks.
    
Automatically Generating a BACnet Registry Configuration File
-------------------------------------------------------------

A CSV registry configuration file for the BACnet driver can be generated with the 
``grab_bacnet_config.py`` script. **This configuration will need to be edited 
before it can be used.**

The utility is invoked with the command:

    ``python grab_bacnet_config.py <device id>``
    
This will query the device with the matching device ID for configuration 
information and print the resulting CSV file to the console.

.. note:: Previous to VOLTTRON 3.5 ``grab_bacnet_config.py`` took the device address as an argument instead of the device ID.

In order to save the configuration to a file use the ``--file`` option to sepcify the
output file name.

Optionally the ``--address`` option can be used to specify the address of the target. In some cases this is needed to help
establish a route to the device.

Output and Assumptions
**********************

Attempts at determining if a point is writable proved too unreliable.
Therefore all points are considered to be read only in the output.

The only property for which a point is setup for an object is
**presentValue**. 

By default the **Volttron Point Name** is set to the value of the **name**
property of the BACnet object on the device. In most cases this name is vague.
No attempt is made at divining a better name. A
duplicate of "Volttron Point Name" solumn called "Reference Point Name" is created to so that
once "Volttron Point Name" is changed a reference remains to the actual
BACnet device object name.

Meta data from the objects on the device is used to attempt to put
useful info in the  **Units** **Unit Details**, and **Notes** columns.
Information such as the range of valid values, defaults, the resolution
or sensor input, and enumeration or state names are scraped from the
device.

With a few exceptions "Units" is pulled from the object's "units"
property and given the name used by the bacpypes library to describe it.
If a value in the **Units** column takes the form

    ``UNKNOWN UNIT ENUM VALUE: <value>``

then the device is using a nonstandard value for the units on that
object.

Problems and Debugging
**********************

Typically the utility should run quickly and finish in a few seconds or
less. In our testing we have never seen a successful scrape take more
than 1 second. If the utility has not finished after about 3 seconds it
is probably having trouble communicating with the device and should be
stopped. Rerunning with debug output can help diagnose the problem.

To output debug messages to the console add the ``--debug`` switch to
the ``end`` of the command line arguments.

    ``python grab_bacnet_config.py <device ID> --file test.csv --debug``

On a successful run you will see output similar to this:

::

    DEBUG:<u>main</u>:initialization
    DEBUG:<u>main</u>:    - args: Namespace(address='10.0.2.20', buggers=False, debug=[], ini=<class 'bacpypes.consolelogging.ini'>, max_range_report=1e+20, out_file=<open file 'out.csv', mode 'wb' at 0x901b0d0>)
    DEBUG:<u>main</u>.SynchronousApplication:<u>init</u> (<bacpypes.app.LocalDeviceObject object at 0x901de6c>, '10.0.2.15')
    DEBUG:<u>main</u>:starting build
    DEBUG:<u>main</u>:pduSource = <Address 10.0.2.20>
    DEBUG:<u>main</u>:iAmDeviceIdentifier = ('device', 500)
    DEBUG:<u>main</u>:maxAPDULengthAccepted = 1024
    DEBUG:<u>main</u>:segmentationSupported = segmentedBoth
    DEBUG:<u>main</u>:vendorID = 5
    DEBUG:<u>main</u>:device_name = MS-NCE2560-0
    DEBUG:<u>main</u>:description = 
    DEBUG:<u>main</u>:objectCount = 32
    DEBUG:<u>main</u>:object name = 2400Stevens/FCB.Local Application.Room Real Temp 2
    DEBUG:<u>main</u>:  object type = analogInput
    DEBUG:<u>main</u>:  object index = 3000274
    DEBUG:<u>main</u>:  object units = degreesFahrenheit
    DEBUG:<u>main</u>:  object units details = -50.00 to 250.00
    DEBUG:<u>main</u>:  object notes = Resolution: 0.1
    DEBUG:<u>main</u>:object name = 2400Stevens/FCB.Local Application.Room Real Temp 1
    DEBUG:<u>main</u>:  object type = analogInput
    DEBUG:<u>main</u>:  object index = 3000275
    DEBUG:<u>main</u>:  object units = degreesFahrenheit
    DEBUG:<u>main</u>:  object units details = -50.00 to 250.00
    DEBUG:<u>main</u>:  object notes = Resolution: 0.1
    DEBUG:<u>main</u>:object name = 2400Stevens/FCB.Local Application.OSA
    DEBUG:<u>main</u>:  object type = analogInput
    DEBUG:<u>main</u>:  object index = 3000276
    DEBUG:<u>main</u>:  object units = degreesFahrenheit
    DEBUG:<u>main</u>:  object units details = -50.00 to 250.00
    DEBUG:<u>main</u>:  object notes = Resolution: 0.1
    ...

and will finish something like this:

::

    ...
    DEBUG:<u>main</u>:object name = 2400Stevens/FCB.Local Application.MOTOR1-C
    DEBUG:<u>main</u>:  object type = binaryOutput
    DEBUG:<u>main</u>:  object index = 3000263
    DEBUG:<u>main</u>:  object units = Enum
    DEBUG:<u>main</u>:  object units details = 0-1 (default 0)
    DEBUG:<u>main</u>:  object notes = BinaryPV: 0=inactive, 1=active
    DEBUG:<u>main</u>:finally

Typically if the BACnet device is unreachable for any reason (wrong IP,
network down/unreachable, wrong interface specified, device failure,
etc) the scraper will stall at this message:

::

    DEBUG:<u>main</u>:starting build

If you have not specified a valid interface in BACpypes.ini you will see
the following error with a stack trace:

::

    ERROR:<u>main</u>:an error has occurred: [Errno 99] Cannot assign requested address
    <Python stack trace cut>

