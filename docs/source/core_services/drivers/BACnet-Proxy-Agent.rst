BACnet Proxy Agent
======

Introduction
------------

Communication with BACnet device on a network happens via a single
virtual BACnet device. Previous versions of Volttron used one virtual
device per device on the network. This only worked in a limited number
of circumstances. (This problem is fixed in the legacy sMap drivers in
Volttron 3.0 only) In the new driver architecture we have a separate
agent specifically for communicating with BACnet devices and managing
the virtual BACnet device.

Configuration
-------------

The agent configuration sets up the virtual BACnet device.

::

    {
        "vip_identity": "platform.bacnet_proxy",
        "device_address": "10.0.2.15",
        "max_apdu_length": 1024,
        "object_id": 599,
        "object_name": "Volttron BACnet driver",
        "vendor_id": 15,
        "segmentation_supported": "segmentedBoth"
    }

-  **vip\_identity** - The VIP identity of the agent. Defaults to
   "platform.bacnet\_proxy". This should only be changed if multiple
   Proxies need to be run for communication with multiple BACnet
   networks. See below.

BACnet device settings
~~~~~~~~~~~~~~~~~~~~~~

-  **device\_address** - Address bound to the network port over which
   BACnet communication will happen on the computer running VOLTTRON.
   This is NOT the address of any target device. See notes about device
   addressing below.

These settings determine the capabilities of the virtual BACnet device.
BACnet communication happens at the lowest common denominator between
two devices. For instance if the BACnet proxy supports segmentation and
the target device does not communication will happen without
segmentation support and will be subject to those limitations.
Consequently there is little reason to change the default settings
outside of the max\_apdu\_length (the default is not the largest
possible value).

-  **max\_apdu\_length** - (From bacpypes documentation) BACnet works on
   lots of different types of networks, from high speed Ethernet to
   “slower” and “cheaper” ARCNET or MS/TP (a serial bus protocol used
   for a field bus defined by BACnet). For devices to exchange messages
   they have to know the maximum size message the device can handle.
   (End BACpypes docs)

| This setting determines the largest APDU accepted by the BACnet
virtual device.
| Valid options are 50, 128, 206, 480, 1024, and 1476. Defaults to
1024.(Optional)

-  **object\_id** - ID of the Device object of the virtual bacnet
   device. Defaults to 599. (Optional)
-  **object\_name** - Name of the object. Defaults to "Volttron BACnet
   driver". (Optional)
-  **vendor\_id** - Vendor ID of the virtual bacnet device. Defaults to
   15. (Optional)
-  **segmentation\_supported** - (From bacpypes documentation) A vast
   majority of BACnet communications traffic fits in one message, but
   there can be times when larger messages are convinient and more
   efficient. Segmentation allows larger messages to be broken up into
   segemnts and spliced back together. It is not unusual for “low power”
   field equipment to not support segmentation. (End BACpypes docs)

Possible setting are segmentedBoth (default), segmentedTransmit,
segmentedReceive, or noSegmentation (Optional)

Device addressing
-----------------

In some cases it will be needed to specify the subnet mask of the
virtual device or a different port number to listen on. The full format
of the address is ADDRESS/SUBNET\_MASK:PORT. For instance if you need to
specify a subnet mask of 255.255.255.0 and the IP address bound to the
network port is 192.168.1.2 you would use the address

::

    192.168.1.2/24

If your BACnet network is on a different port (47809) besides the
default (47808) you would use the address

::

    192.168.1.2:47809

If you need to do both

192.168.1.2/24:47809

Communicating with multiple BACnet networks
-------------------------------------------

| If two BACnet devices are connected to different ports they are
considered to be on different BACnet networks. In order to communicate
with both devices you will need to run one BACnet Proxy Agent per
network.
| Each proxy will need to be bound to different ports appropriate to
each BACnet network and will need a different VIP identity specified.
When configuring drivers you will need to specify which proxy to use by
specifying the VIP identity.

For example a proxy connected to the default BACnet network

::

    {
        "vip_identity": "platform.bacnet_proxy_1",
        "device_address": "192.168.1.2/24"
    }

and another on port 47809

::

    {
        "vip_identity": "platform.bacnet_proxy_2",
        "device_address": "192.168.1.2/24:47809"
    }

a device one the first network

::

    {
        "driver_config": {"device_address": "1002:12",
                          "proxy_address": "platform.bacnet_proxy_1" },
        "campus": "campus",
        "building": "building",
        "unit": "bacnet1",
        "driver_type": "bacnet",
        "registry_config":"/home/kyle/configs/bacnet.csv",
        "interval": 60,
        "timezone": "UTC",
        "heart_beat_point": "Heartbeat"
    }

and a device on the second network

::

    {
        "driver_config": {"device_address": "12000:5",
                          "proxy_address": "platform.bacnet_proxy_2" },
        "campus": "campus",
        "building": "building",
        "unit": "bacnet2",
        "driver_type": "bacnet",
        "registry_config":"/home/kyle/configs/bacnet.csv",
        "interval": 60,
        "timezone": "UTC",
        "heart_beat_point": "Heartbeat"
    }

Notice that both configs use the same registry configuration
(/home/kyle/configs/bacnet.csv). This is perfectly fine as long as the
registry configuration is appropriate for both devices.
