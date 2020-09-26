Master Driver Configuration Examples
====================================

This directory contains a complete set of example configurations for the master driver agent. 

All configurations have been used with real devices on a test network. Most files will have to be adapted
to your network and devices.

The included ``master-driver.agent`` loads all the drivers in this folder.

BACnet
------

- ``bacnet1.config`` and ``bacnet2.config`` - Driver configurations.
- ``bacnet.csv`` - Register configuration. This file can be automatically generated for a device with ``scripts/bacnet/grab_bacnet_config.py``.

MODBUS
------

- ``modbus.config`` - Driver configuration.
- ``catalyst371.csv`` - Register configuration for a TWT Catalyst 371.

Fake Devices
------------

- ``fake.config`` - Driver configuration.
- ``fake.csv`` - Register configuration for a fake device.
