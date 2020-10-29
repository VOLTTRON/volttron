.. _Multi-Platform-Deployment:

=========================
Multi-Platform Connection
=========================

There are multiple ways to establish connection between external
VOLTTRON platforms. Given that VOLTTRON now supports ZeroMq and RabbitMQ
type of message bus with each using different type authentication mechanism,
the number of different ways that agents can connect to external
platforms has significantly increased. Various multi-platform deployment
scenarios will be covered in this section.

#. Agents can directly connect to external platforms to send and receive messages.
   Forward historian, Data Mover agents fall under this category. The deployment steps
   for forward historian is described in :ref:`Forward Historian Deployment <Forward-Historian-Deployment>`
   and data mover historian in :ref:`DataMover Historian Deployment <DataMover-Historian-Deployment>`

#. The platforms maintain the connection with other platforms and agents can send
   to and receive messages from external platforms without having to establish
   connection directly. The deployment steps
   is described in :ref:`Multi Platform Router Deployment <Multi-Platform-Router-Deployment>`

#. RabbitMQ has ready made plugins such as shovel and federation to connect to
   external brokers. This feature is leveraged to make connections to external platforms. This is described in
   :ref:`Multi Platform RabbitMQ Deployment <Multi-platform-RabbitMQ-Deployment>`

#. A web based admin interface to authenticate multiple instances (ZeroMq or RabbitMQ)
   wanting to connect to single central instance is now available. The deployment steps
   is described in :ref:`Multi Platform Multi-Bus Deployment <Multi-Platform-Multi-Bus>`

#. VOLTTRON Central is a platform management web application that allows
   platforms to communicate and to be managed from a centralized server. The deployment steps
   is described in :ref:`VOLTTRON Central Demo <Device-Configuration-in-VOLTTRON-Central>`


Assumptions
===========

- `Data Collector` is the deployment box that has the drivers and is collecting data from devices which will be
  forwarded to a `VOLTTRON Central`.
- `Volttron Central (VC)` is the deployment box that has the historian which will save data from all Data Collectors to
  the central database.
- `VOLTTRON_HOME` is assumed to the default on both boxes (`/home/<user>/.volttron`).

.. note::

     ``VOLTTRON_HOME`` is the directory used by the platform for managing state and configuration of the platform and
     agents installed locally on the platform.  Auth keys, certificates, the configuration store, etc. are stored in
     this directory by the platform.

.. toctree::

    forward-historian-deployment
    datamover-historian-deployment
    multi-platform-router
    multi-platform-rabbitmq-deployment
    multi-platform-multi-bus
    volttron-central-deployment
