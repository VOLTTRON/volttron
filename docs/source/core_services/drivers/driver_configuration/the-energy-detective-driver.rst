.. _The-Energy-Detective-Driver:
The Energy Detective Meter Driver
------------------------------------

The TED-Pro is an energy monitoring system that can measure energy consumption
of multiple mains and supports submetering of individual circuits. 
This driver connects to a TED Pro Energy Control Center (ECC) and can collect
information from multiple Measuring Transmiting Units (MTUs) and Spyder submetering
devices connected to the ECC.
.. note::

   The Emu Serial Api library has its own dependencies which should be installed
   with pip while the VOLTTRON environment is activated.

The TED Pro device interface is configured as follows. You'll need the ip address
or hostname of the ECC on a network segment accessible from the Volttron instance, 
if configured to use a port other than 80, you can provide it as shown below,
following a colon after the host address. 

to the location of the cloned library. `tty` should be set to the name of the
Emu2's character special file. One way to find this is to run `dmesg` before
and after plugging in the Emu2, and checking the new output.

.. code-block:: json

    {
        "driver_type": "ted_meter", 
        "driver_config": {
            "username": "username", 
            "device_address": "192.168.1.100:8080", 
            "password": "password", 
            "scrape_spyder": true, 
            "track_totalizers": true
        }
    }

The registry config file referred to in the first configuration must be an array
of strings. This tells the interface which data points should be retrieved from
the device every interval. If the NetworkInfo point is omitted it will be
included automatically.

.. code-block:: json

   [
       "NetworkInfo",
       "InstantaneousDemand",
       "PriceCluster"
   ]
