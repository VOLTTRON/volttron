.. _Multi_Platform_Walkthrough:

RabbitMQ Multi Platform Walk-through
====================================

This guide describes the creation of three VOLTTRON instances on three virtual machines.  The use case
for this example is that we want to use the Forwarder to pass device data from two VOLTTRON instance to
a single "central" instance for storage.  For this document node will be used interchangeably with VOLTTRON
instance.

Node Setup
----------

For this example we will have two types of nodes; a data collector and a central node.  Each of the data
collectors will have different message buses (VOLTTRON supports both RabbitMQ and ZMQ).  The nodes will
be configured as in the following table.

.. csv-table:: Node Configuration
   :header: "", "Central", "Node-ZMQ", "Node-RMQ"
   :widths: 20, 15, 10, 10

   "Node Type", "Central", "Data Collector", "Data Collector"
   "Master Driver", "", "yes", "yes"
   "Forwarder", "", "yes", "yes"
   "SQL Historian", "yes", "", ""
   "Volttron Central", "yes", "", ""
   "Exposes RMQ Port", "yes", "", ""
   "Exposes ZMQ Port", "yes", "", ""
   "Exposes HTTPS Port", "yes", "", ""

The goal of this is to be able to see the data from Node-ZMQ and Node-RMQ in the Central SQL Historian and on
the trending charts of Volttron Central.

Virtual Machine Setup
---------------------

The first step in creating a VOLTTRON instance is to make sure the machine is ready for volttron.  Each machine
should have its hostname setup.  For this walkthrough the hostnames central, node-zmq and node-rmq will be used

For Central and Node-RMQ follow the instructions :ref:`Building-VOLTTRON#steps-for-rabbitmq`.  For Node-ZMQ use
:ref:`Building-VOLTTRON#steps-for-zmq`.

Instance Setup
--------------

The following conventions/assumtions are made for the rest of this document:

  - Commands should be run from the volttron root
  - VOLTTRON_HOME will use the default: $HOME/.volttron
  - Default vip port shall be used: 22916
  - HTTPS port shall be 8443
  - Replace central, node-zmq and node-rmq with your own hostnames.

The following will use vcfg (volttron-cfg) to configure the individual platforms.

Central Instance Setup
----------------------

..note:
  This instance must have been bootstrapped using --rabbitmq see :ref:`Building-VOLTTRON#steps-for-rabbitmq`.



Node-ZMQ Instance Setup
-----------------------

Central Instance Setup
----------------------