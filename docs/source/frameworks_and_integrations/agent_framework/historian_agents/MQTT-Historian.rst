.. _MQTT-Historian:

MQTT Historian
==============

Overview
--------
The MQTT Historian agent publishes data to an MQTT broker.

The mqttlistener.py script will connect to the broker and print
all messages.

Dependencies
------------
The Paho MQTT library from Eclipse is needed for the agent and can
be installed with:

::

    pip install paho-mqtt


The Mosquitto MQTT broker may be useful for testing and can be installed with

::

    apt-get install mosquitto
