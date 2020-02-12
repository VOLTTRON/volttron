 .. _Multi-Platform-PubSub:

===================================
Multi-Platform PubSub Communication
===================================

Multi-Platform pubsub communication allows an agent on one platform to subscribe to receive messages from another
platform without having to setup connection to the remote platform directly. The connection will be internally managed
by the VOLTTRON platform router module. Please refer here
:ref:`Multi-Platform Communication Setup <Multi-Platform-Communication>`) for more details regarding setting up of
Multi-Platform connections.

External Platform Message Subscription
**************************************


To subscribe for topics from remote platform, the subscriber agent has to add an additional input parameter -
``all_platforms`` to the pubsub subscribe method.

Here is an example,

.. code:: python

    self.vip.pubsub.subscribe('pubsub', 'foo', self.on_match, all_platforms=True)

There is no change in the publish method pf PubSub subsystem. If all the configurations are correct and the publisher
agent on the remote platform is publishing message to topic=``foo``, then the subscriber agent will start receiving
those messages.
