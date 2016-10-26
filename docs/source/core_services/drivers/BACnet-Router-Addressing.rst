.. _BACnet-Router-Addressing:
========================
BACnet Router Addressing
========================

The underlying library that Volttron uses for BACnet supports IP to
MS/TP routers. Devices behind the router use a Remote Station address in
the form

::

    <network>:<address>

where **<network>** is the configured network ID of the router and **<address>**
is the address of the device behind the router.

For example to access the device at **<address>** 12 for a router configured
for **<network>** 1002 can be accessed with this address:

::

    1002:12

**<network>** must be number from 0 to 65534 and **<address>** must be a number
from 0 to 255.

This type of address can be used anywhere an address is required in 
configuration of the Volttron BACnet driver.

Caveats
-------

VOLTTRON uses a UDP broadcast mechanism to establish the route to the device. 
If the route cannot be established it will fall back to a UDP broadcast for
all communication with the device. 
If the IP network where the router is connected blocks UDP
broadcast traffic then these addresses will not work. 
