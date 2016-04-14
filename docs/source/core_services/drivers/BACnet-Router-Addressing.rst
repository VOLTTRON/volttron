BACnet MS/TP to IP router
=====

Router Addressing
-----------------

The underlying library that Volttron uses for Bacnet supports IP to
MS/TP routers. Devices behind the router use a Remote Station address in
the form

::

    <network>:<address>

where "network" is the configured network ID of the router and "address"
is the address of the device behind the router.

For example to access the device at address 12 for a router configured
for network 1002 can be accessed with this address:

::

    1002:12

"network" must be number from 0 to 65534 and "address" must be a number
from 0 to 255.

This type of address can be used anywhere an address is required either
in configuration of the Volttron BACnet driver or scraping the
configuration.

For example, to scrape a device behind a router at 1024:5 you would use
a command line like this

::

    python grab_bacnet_config.py 1024:5 1024.5.csv

to write the configuration out to the file "1024.5.csv".

Caveats
~~~~~~~

BACnet uses a IP broadcast mechanism to communicate using these kind of
addresses. If the IP network where the router is connected blocks
broadcast traffic then these addresses will not work. (Nothing could
communicate with the router anyway, but that is a separate issue.)
