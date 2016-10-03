.. _VOLTTRON-Config:
VOLTTRON Config
===============

The new volttron-cfg commands allows for the easy configuration of a VOLTTRON platform. This includes
setting up the platform configuration, historian, VOLTTRON Central UI, and platform agent.

example volttron-cfg output:

Is this instance discoverable (Y/N)? [N] y

What is the external ipv4 address for this instance? [127.0.0.1]: 
What is the vip port this instance? [22916] 

What is the port for discovery? [8080] 

Which IP addresses are allowed to discover this instance? [/127.*/] 

Is this instance a volttron central (Y/N)? [N] y

Should volttron central autostart(Y/N)? [Y] 

Include volttron central platform agent on volttron central? [Y]

Should platform agent autostart(Y/N)? [Y] 

Should install sqlite platform historian? [N]y

Should historian agent autostart(Y/N)? [Y] 
