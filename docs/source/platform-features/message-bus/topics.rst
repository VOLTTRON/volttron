.. _Messaging-Topics:

====================
Messaging and Topics
====================


Introduction
============

Agents in |VOLTTRON| communicate with each other using a publish/subscribe mechanism built on the Zero MQ or RabbitMQ
Python libraries.  This allows for great flexibility as topics can be created dynamically and the messages sent can be
any format as long as the sender and receiver understand it.  An agent with data to share publishes to a topic, then
any agents interested in that data subscribe to that topic.

While this flexibility is powerful, it also could also lead to confusion if some standard is not followed.  The current
conventions for communicating in the VOLTTRON are:

-  Topics and subtopics follow the format: ``topic/subtopic/subtopic``
-  Subscribers can subscribe to any and all levels. Subscriptions to `topic` will include messages for the base topic
   and all subtopics.  Subscriptions to ``topic/subtopic1`` will only receive messages for that subtopic and any
   children subtopics. Subscriptions to empty string ("") will receive ALL messages. This is not recommended.

Agents should set the `From` header.  This will allow agents to filter on the `To` message sent back.


Topics
======

- **alerts** - Base topic for alerts published by agents and subsystems, such as agent health alerts
- **analysis** - Base topic for analytics being used with building data
- **config** - Base topic for managing agent configuration
- **datalogger** - Base topic for agents wishing to record time series data
- **devices** - Base topic for data being published by drivers
- **devices/actuators** - Base topic used  by actuator agent for all device control actions and response
- **heartbeat** - Topic for publishing periodic "heartbeat" or "keep-alive"
- **market** - Base topics for market agent communication
- **record** - Base topic for agents to record data in an arbitrary format
- **weather** - Base topic for polling publishes of weather service agents

.. note::

   Other more specific topics may exist for specific agents or purposes.  Please review the documentation for the
   specific feature for more information.

.. |VOLTTRON| unicode:: VOLTTRON U+2122
