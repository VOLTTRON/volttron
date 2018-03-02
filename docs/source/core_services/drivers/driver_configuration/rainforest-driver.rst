.. _Rainforest-Driver:
Rainforest Emu2 Driver Configuration
------------------------------------

The Emu2 is a device for connecting to and reading data from smart power meters.
We have an experimental driver to talk to this device. It requires cloning the
Rainforest Automation library which can be found
`here <https://github.com/rainforestautomation/Emu-Serial-API>`_.

.. note::

   The Emu Serial Api library has its own dependencies which should be installed
   with pip while the VOLTTRON environment is activated.

The Emu2 device interface is configured as follows. Set `emu_library_path`
to the location of the cloned library. `tty` should be set to the name of the
Emu2's character special file. One way to find this is to run `dmesg` before
and after plugging in the Emu2, and checking the new output.

.. code-block:: json

   {
       "driver_config": {
           "tty": "ttyACM0",
           "emu_library_path": "/home/volttron/Emu-Serial-Api"
       },
       "driver_type": "rainforestemu2",
       "interval": 30,
       "registry_config": "config://emu2.json",
       "timezone": "UTC"
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
