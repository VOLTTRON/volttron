Scanning for BACnet Devices
---------------------------

If the addresses for BACnet devices are unknown they can be discovered
using the bacnet\_scan utility. This program is found in the
volttron/drivers folder along with the [BacnetDriver BACnet driver] and
the [AutoBacnetConfigGeneration grab\_bacnet\_config] utility.

The bacnet\_scan utility uses the same configuration file (BACpypes.ini)
as grab\_bacnet\_config. See AutoBacnetConfigGeneration for setting that
up.

To run the utility simply execute the following command:

::

    python bacnet_scan.py

and expect output similar to this:

::

    Device Address        = <Address 192.168.1.42>
    iAmDeviceIdentifier   = ('device', 699)
    maxAPDULengthAccepted = 1024
    segmentationSupported = segmentedBoth
    vendorID              = 15

    Device Address        = <RemoteStation 1002:11>
    iAmDeviceIdentifier   = ('device', 540011)
    maxAPDULengthAccepted = 480
    segmentationSupported = segmentedBoth
    vendorID              = 5

Reading Output
~~~~~~~~~~~~~~

The address where the device can be reached is listed in the first line.
The remaining lines are informational and not needed to configure BACnet
properly.

For the first example the IP address 192.168.1.42 can be used to reach
the device. The second device is behind a BACnet router and can be
reached at 1002:11. See [RouterAddressing Remote Station addressing].

Options
~~~~~~~

-  | --address
   | 

   -  Send the who is request only to a specific address. Useful as a
      way to ping devices on a network that blocks broadcast traffic.

-  --range - Specify the device ID range for the results. Useful for
   filtering.
-  --timeout - Specify how long to wait for responses to the original
   broadcast. This defaults to 5 which should be sufficient for most
   networks.


