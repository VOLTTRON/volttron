Automatically generating a BACnet configuration file
----------------------------------------------------

Included with the sMap bacnet driver is a utility for automatically
scraping a starting configuration file for the driver. **This
configuration will need to be edited before it can be used.**

The utility is called grab\_bacnet\_config.py and is located in the
volttron/drivers directory.

Configuring the utility
~~~~~~~~~~~~~~~~~~~~~~~

The utility emulates a BACnet device using the bacpypes library. The
device must be configured properly in order to work. By default this
configuration is stored in volttron/drivers/BACpypes.ini and will be
read automatically when the utility is run. NOTE: This file is NOT used
for the configuration of the sMap driver.

The only value that (usually) needs to be changed is the address field.
**This address is for the machine you are running the script from, NOT
THE DEVICE BEING SCRAPED! The target device address is specified on the
command line.** This value should be set to the IP address of the
network interface used to communicate with the remote device. If there
is more than one network interface the address of the interface
connected to a network that can reach the device must be used.

If a different outgoing port other than the default 47808 must be used
the it can be specified as part of the address in the form

.. raw:: html

   <ADDRESS>

.

Sample BACpypes.ini
^^^^^^^^^^^^^^^^^^^

::

    [BACpypes]
    objectName: Betelgeuse
    address: 10.0.2.15 
    objectIdentifier: 599
    maxApduLengthAccepted: 1024
    segmentationSupported: segmentedBoth
    vendorIdentifier: 15

Invoking the Utility
~~~~~~~~~~~~~~~~~~~~

The utility is invoked with the command:

::

    python grab_bacnet_config.py <device address> <output file>

Working with a Router
~~~~~~~~~~~~~~~~~~~~~

See RouterAddressing

Output and Assumptions
~~~~~~~~~~~~~~~~~~~~~~

Attempts at determining if a point is writable proved too unreliable.
Therefore all points are considered to be read only in the output.

The only property for which a point is setup for an object is
"presentValue". Only cases where the data type of presentValue is
compatible with sMap is a point created.

By default the "PNNL Point Name" is set to the value of the "name"
property of the object. In most cases this name is vague and not
compatible with sMap. No attempt is made at divining a better name. A
duplicate of "PNNL Point Name" called "Point Name" is created to so that
once "PNNL Point Name" is changed a reference remains to the actual
device object name.

Meta data from the objects on the device is used to attempt to put
useful info in "Units", "Unit Details" (unused by sMap), and "Notes".
Information such as the range of valid values, defaults, the resolution
or sensor input, and enumeration or state names are scraped from the
device.

With a few exceptions "Units" is pulled from the object's "units"
property and given the name used by the bacpypes library to describe it.
If a value in the "Units" column takes the form

::

    UNKNOWN UNIT ENUM VALUE: <value>

then the device is using a nonstandard value for the units on that
object.

Problems and Debugging
~~~~~~~~~~~~~~~~~~~~~~

Typically the utility should run quickly and finish in a few seconds or
less. In our testing we have never seen a successful scrape take more
than 1 second. If the utility has not finished after about 3 seconds it
is probably having trouble communicating with the device and should be
stopped. Rerunning with debug output can help diagnose the problem.

To output debug messages to the console add the **--debug** switch to
the **end** of the command line arguments.

::

    python grab_bacnet_config.py <device IP> <output file> --debug

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

