.. _VOLTTRON-MessageBusRefactor:

====================
Message Bus Refactor
====================

Refactoring of the existing message bus became necessary as we needed to reduce long term costs of
maintenance, enhancement and support of the message bus. It made sense to move to a more widely used,
industry accepted messaging library such as RabbitMQ that has many of the features that we need already
built in.

  1. It has many different messaging patterns and routing topologies.
  2. It offers flexibility in deployment and supports large scale deployment
  3. It has well-developed SSL based authentication plugin.

The goal of the message bus refactor task is to
  1. Maintain essential features of current message bus and minimize transition cost
  2. Leverage an existing and growing community dedicated to the further development of RabbitMQ
  3. Move services provided currently by VOLTTRON agents to services natively provided by RabbitMQ
  4. Decrease VOLTTRON development time spent on supporting message bus which is now a commodity technology
  5. Address concerns from community about ZeroMQ.


.. toctree::

   rabbitmq-overview
   message-bus-plugin
   rabbitmq-refactor
   agent-communication-rabbitmq
   rabbitmq-ssl-auth
