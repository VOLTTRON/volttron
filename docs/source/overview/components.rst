.. _components:

==========
Components
==========

The components of the Transactional Network are illustrated in the figure below. The Device Interface communicates to the HVAC Controller using Modbus. It periodically scrapes data off the controller and both pushes to the sMAP historian and publishes it to the Message Bus on a topic for each device. The Device Interface also responds to lock and control commands published on the requests topic. Agents must first request and receive a lock on a device for a certain time period. During this time, they have exclusive control of the device and may issues commands. The sMAP agent in the figure represents the Archiver Agent that allows agents to request data from sMAP over the Message Bus. The
Archiver Agent isolates agents from the details of the Historian and would allow the platform to use a different or multiple historian solutions (sMAP, a database, and a some other site).


|Overview of the VOLTTRON platform|

.. |Overview of the VOLTTRON platform| image:: files/overview.png
