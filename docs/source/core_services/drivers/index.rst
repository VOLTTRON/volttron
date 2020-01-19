.. _VOLTTRON-Driver-Framework:
=========================
VOLTTRON Driver Framework
=========================

All Voltton drivers are implemented through the Master Driver Agent and are technically sub-agents 
running in the same process as the Master Driver Agent. Each of these driver sub-agents is responsible 
for creating an interface to a single device. Creating that interface is facilitated by an instance of 
an interface class. There are a variety of interface classes included. The most commonly used interfaces
are BACnet and Modbus.

.. toctree::
    :glob:
    :maxdepth: 2

    *

    driver_configuration/index