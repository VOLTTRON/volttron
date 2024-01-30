.. _MQTT-Historian:

==============
MQTT Historian
==============

Overview
========

The MQTT Historian agent publishes data to an MQTT broker.  The ``mqttlistener.py`` script will connect to the broker
and print all messages.

.. note::
   The MQTT Historian is located within the **core** directory. ::

      services/core/MQTTHistorian/


Dependencies
============
The Paho MQTT library from Eclipse is needed for the agent and can be installed with:

.. code-block:: bash

    pip install paho-mqtt


The Mosquitto MQTT broker may be useful for testing and can be installed with

.. code-block:: bash

    apt-get install mosquitto
