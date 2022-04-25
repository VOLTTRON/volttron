.. _BACnet-Auto-Configuration:

=========================
BACnet Auto-Configuration
=========================

Included with the platform are two scripts for finding and configuring BACnet devices.  These scripts are located in
`scripts/bacnet`.  `bacnet_scan.py` will scan the network for devices.  `grab_bacnet_config.py` creates a CSV file
for the BACnet driver that can be used as a starting point for creating your own register configuration.

Both scripts are configured with the file `BACpypes.ini`.


Configuring the Utilities
-------------------------

While running both scripts create a temporary virtual BACnet device using the `bacpypes` library.  The virtual
device must be configured properly in order to work.  This configuration is stored in `scripts/bacnet/BACpypes.ini`
and will be read automatically when the utility is run.

.. note::

    The only value that (usually) needs to be changed is the **address** field.

.. warning::

    This is the address bound to the port on the machine you are running the script from, **NOT A TARGET DEVICE**

This value should be set to the IP address of the network interface used to communicate with the remote device.  If
there is more than one network interface you must use the address of the interface connected to the network that can
reach the device.

In Linux you can usually get the addresses bound to all interfaces by running ``ifconfig`` from the command line.

If a different outgoing port other than the default 47808 must be used, it can be specified as part of the address in
the form:

::

    <ADDRESS>:<PORT>
    
In some cases, the netmask of the network will be needed for proper configuration.  This can be done following this
format:

::

    <ADDRESS>/<NETMASK>:<PORT>
    
where ``<NETMASK>`` is the netmask length. The most common value is 24. See
http://www.computerhope.com/jargon/n/netmask.htm

In some cases, you may also need to specify a different device ID by changing the value of `objectIdentifier` so the
virtual BACnet device does not conflict with any devices on the network.  `objectIdentifier` defaults to 599.


Sample BACpypes.ini
^^^^^^^^^^^^^^^^^^^

.. code-block:: console

    [BACpypes]
    objectName: Betelgeuse
    address: 10.0.2.15/24
    objectIdentifier: 599
    maxApduLengthAccepted: 1024
    segmentationSupported: segmentedBoth
    vendorIdentifier: 15


Scanning for BACnet Devices
---------------------------

If the addresses for BACnet devices are unknown they can be discovered using the `bacnet_scan.py` utility.

To run the utility simply execute the following command:

.. code-block:: bash

    python bacnet_scan.py
    
and expect output similar to this:

.. code-block:: console

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
^^^^^^^^^^^^^^

The address where the device can be reached is listed on the `Device Address` line.  The BACnet device ID is listed on
the `Device Id` line.  The remaining lines are informational and not needed to configure the BACnet driver.

For the first example, the IP address ``192.168.1.42`` can be used to reach the device.  The second device is behind a
BACnet router and can be reached at ``1002:11``. See :ref:`BACnet router addressing <BACnet-Router-Addressing>`.


BACNet Scan Options
^^^^^^^^^^^^^^^^^^^

    - ``--address ADDRESS``:  Send the WhoIs request only to a specific address. Useful as a way to ping devices on a
      network that blocks broadcast traffic.
    - ``--range LOW/HIGH``:  Specify the device ID range for the results. Useful for filtering.
    - ``--timeout SECONDS``:  Specify how long to wait for responses to the original broadcast. This defaults to 5 which
      should be sufficient for most networks.
    - ``--csv-out CSV_OUT``:  Write the discovered devices to a CSV file. This can be used as inout for
      ``grab_multiple_configs.py``. See :ref:`Scraping Multiple Devices <Scraping-Multiple-BACnet-Devices>`.


Automatically Generating a BACnet Registry Configuration File
-------------------------------------------------------------

A CSV registry configuration file for the BACnet driver can be generated with the  ``grab_bacnet_config.py`` script.

.. warning::

    This configuration will need to be edited before it can be used!

The utility is invoked with the command:

.. code-block:: bash

    python grab_bacnet_config.py <device id>
    
This will query the device with the matching device ID for configuration information and print the resulting CSV file to
the console.

In order to save the configuration to a file use the ``--registry-out-file`` option to specify the output file name.

Optionally the ``--address`` option can be used to specify the address of the target. In some cases, this is needed to
help establish a route to the device.


Output and Assumptions
^^^^^^^^^^^^^^^^^^^^^^

* Attempts at determining if a point is writable proved too unreliable.  Therefore all points are considered to be
  read-only in the output.

* The only property for which a point is setup for an object is `presentValue`.

* By default, the `Volttron Point Name` is set to the value of the `name` property of the BACnet object on the
  device.  In most cases this name is vague.  No attempt is made at choosing a better name.  A duplicate of
  `Volttron Point Name` column called `Reference Point Name` is created to so that once `Volttron Point Name` is
  changed a reference remains to the actual BACnet device object name.

* Meta data from the objects on the device is used to attempt to put useful info in the  `Units`, `Unit Details`,
  and ``Notes`` columns.  Information such as the range of valid values, defaults, the resolution or sensor input, and
  enumeration or state names are scraped from the device.

With a few exceptions "Units" is pulled from the object's "units" property and given the name used by the `bacpypes`
library to describe it. If a value in the **Units** column takes the form

.. code-block:: python

    UNKNOWN UNIT ENUM VALUE: <value>

then the device is using a nonstandard value for the units on that object.


.. _Scraping-Multiple-BACnet-Devices:

Scraping Multiple Devices
-------------------------

The `grab_multiple_configs.py` script will use the CSV output of `bacnet_scan.py` to automatically run
`grab_bacnet_config.py` on every device listed in the CSV file.

The output is put in two directories. `devices/` contains basic driver configurations for the scrapped devices.
`registry_configs/` contains the registry file generated by grab_bacnet_config.py.

`grab_multiple_configs.py` makes no assumptions about device names or topics, however the output is appropriate for
the `install_platform_driver_configs.py` script.


Grab Multiple Configs Options
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

    - ``--out-directory OUT_DIRECTORY`` Specify the output directory.
    - ``--use-proxy`` Use `proxy_grab_bacnet_config.py` to gather configuration data.
    - ``--proxy-id`` When using ``-use-proxy``, supply ``proxy-id`` with the VIP identity of a BACnet proxy agent.  This
      is useful for deployments with multiple BACnet proxies, such as on segmented networks, or in deployments
      communicating with multiple BACnet networks.


BACnet Proxy Alternative Scripts
--------------------------------

Both `grab_bacnet_config.py` and `bacnet_scan.py` have alternative versions called
`proxy_grab_bacnet_config.py` and `proxy_bacnet_scan.py` respectively.  These versions require that the
VOLTTRON platform is running and BACnet Proxy agent is running.  Both of these agents use the same command line
arguments as their independent counterparts.

.. warning::

    These versions of the BACnet scripts are intended as a proof of concept and have not been optimized for performance.
    `proxy_grab_bacnet_config.py` takes about 10 times longer to grab a configuration than `grab_bacnet_config.py`


Problems and Debugging
----------------------

* Both `grab_bacnet_config.py` and `bacnet_scan.py` creates a virtual device that open up a port for communication
  with devices.  If the BACnet Proxy is running on the VOLTTRON platform it will cause both of these scripts to fail at
  startup.  Stopping the BACnet Proxy will resolve the problem.

* Typically the utility should run quickly and finish in 30 seconds or less.  In our testing, we have never seen a
  successful scrape take more than 15 seconds on a very slow device with many points.  Many devices will scrape in less
  than 3 seconds.

* If the utility has not finished after about 60 seconds it is probably having trouble communicating with the device and
  should be stopped.  Rerunning with debug output can help diagnose the problem.

To output debug messages to the console add the ``--debug`` switch to the **end** of the command line arguments.

.. code-block:: bash

    python grab_bacnet_config.py <device ID> --out-file test.csv --debug

On a successful run you will see output similar to this:

.. code-block:: console

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
    DEBUG:<u>main</u>:object name = Building/FCB.Local Application.Room Real Temp 2
    DEBUG:<u>main</u>:  object type = analogInput
    DEBUG:<u>main</u>:  object index = 3000274
    DEBUG:<u>main</u>:  object units = degreesFahrenheit
    DEBUG:<u>main</u>:  object units details = -50.00 to 250.00
    DEBUG:<u>main</u>:  object notes = Resolution: 0.1
    DEBUG:<u>main</u>:object name = Building/FCB.Local Application.Room Real Temp 1
    DEBUG:<u>main</u>:  object type = analogInput
    DEBUG:<u>main</u>:  object index = 3000275
    DEBUG:<u>main</u>:  object units = degreesFahrenheit
    DEBUG:<u>main</u>:  object units details = -50.00 to 250.00
    DEBUG:<u>main</u>:  object notes = Resolution: 0.1
    DEBUG:<u>main</u>:object name = Building/FCB.Local Application.OSA
    DEBUG:<u>main</u>:  object type = analogInput
    DEBUG:<u>main</u>:  object index = 3000276
    DEBUG:<u>main</u>:  object units = degreesFahrenheit
    DEBUG:<u>main</u>:  object units details = -50.00 to 250.00
    DEBUG:<u>main</u>:  object notes = Resolution: 0.1
    ...

and will finish something like this:

.. code-block:: console

    ...
    DEBUG:<u>main</u>:object name = Building/FCB.Local Application.MOTOR1-C
    DEBUG:<u>main</u>:  object type = binaryOutput
    DEBUG:<u>main</u>:  object index = 3000263
    DEBUG:<u>main</u>:  object units = Enum
    DEBUG:<u>main</u>:  object units details = 0-1 (default 0)
    DEBUG:<u>main</u>:  object notes = BinaryPV: 0=inactive, 1=active
    DEBUG:<u>main</u>:finally

Typically if the BACnet device is unreachable for any reason (wrong IP, network down/unreachable, wrong interface
specified, device failure, etc) the scraper will stall at this message:

.. code-block:: console

    DEBUG:<u>main</u>:starting build

If you have not specified a valid interface in BACpypes.ini you will see the following error with a stack trace:

.. code-block:: console

    ERROR:<u>main</u>:an error has occurred: [Errno 99] Cannot assign requested address
    <Python stack trace cut>
