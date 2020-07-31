.. _RMQ-Multi-Platform-Setup:

Multi-Platform Deployment With RabbitMQ Message bus
===================================================

In ZeroMQ based VOLTTRON, if multiple instances needed to be connected together
and be able to send or receive messages to/from remote instances we would do it
in few different ways.

1. Write an agent that would connect to remote instance directly and publish/subscribe to messages or
   perform RPC communication directly. This is described in
   :ref:`Agent connection to remote volttron instance <Connecting_to_remote_RMQ>`


2. Use special agents such as forwarder/data puller agents to forward/receive
   messages to/from remote instances. This can be achieved using RabbitMQ's shovel plugin and is described at
   :ref:`Using Shovel Plug-in<shovel-plugin>`


3. Configure vip address of all remote instances that an instance has to connect to
   in it's $VOLTTRON_HOME/external_discovery.json and let the router module in each instance
   manage the connection and take care of the message routing for us.
   This is the most seamless way to do multi-platform communication. This can be achieved using RabbitMQ's federation
   plugin. Setup for this is described at :ref:`Using Federation Plug-in<federation-plugin>`

