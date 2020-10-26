.. _PubSub-Between-Remote-Platforms:

=============================================
PubSub Communication Between Remote Platforms
=============================================

This document describes pubsub communication between different platforms.  The goal of this specification is to improve
forward historians forwarding local PubSub messages to remote platforms.  Agents interested in receiving PubSub
messages from external platforms will not need to have a forward historian running on the source platform to forward
PubSub messages to the interested destination platforms;  The VIP router will now do all the work.  It shall use the
Routing Service to internally manage connections with external VOLTTRON platforms and use the PubSubService for the
actual inter-platform PubSub communication.

For future:

This specification will need to be extended to support PubSub communication between platforms that are
multiple hops away.  The VIP router of each platform shall need to maintain a routing table and use it to forward pubsub
messages to subscribed platforms that are multiple hops away.  The routing table shall contain shortest path to each
destination platform.


Functional Capabilities
=======================

1. Each VOLTTRON platform shall have a list of other VOLTTRON platforms that it has to connect to in a config file.

2. Routing Service of each platform connects to other platforms on startup.

3. The Routing Service in each platform is responsible for connecting to (and also initiating reconnection if required),
   monitoring and disconnecting from each external platform.  The function of the Routing Service is explained in detail
   in the Routing Service section.

4. Platform to platform PubSub communication shall be using VIP protocol with the subsystem frame set to "pubsub".

5. The PubSubService of each VOLTTRON platform shall maintain a list of local and external subscriptions.

6. Each VIP router sends its list of external subscriptions to other connected platforms in the following cases:

    a. On startup

    b. When a new subscription is added

    c. When an existing subscription is removed

    d. When a new platform gets connected

7. When a remote platform disconnection is detected, all stale subscriptions related to that platform shall be removed.

8. Whenever an agent publishes a message to a specific topic, the PubSubService on the local platform first checks the
   topic against its list of local subscriptions.  If a local subscription exists, it sends the publish message to
   corresponding local subscribers.

9. The PubSubService shall also check the topic against list of external subscriptions.  If an external subscription
   exists, it shall use the Routing Service to send the publish message to the corresponding external platform.

10. Whenever a router receives messages from other platform, it shall check the destination platform in the incoming
    message.

    a. If the destination platform is the local platform, it hand overs the publish message to the PubSubService which
       checks the topic against list of external subscriptions.  If an external subscription matches, the PubSubService
       forwards the message to all the local subscribers subscribed to that topic.

    b. If the destination platform is not the local platform, it discards the message.


Routing Service
---------------

1. The Routing Service shall maintain connection status (CONNECTING, CONNECTED, DISCONNECTED etc.) for each external
   platform.

2. In order to establish connection with an external VOLTTRON platform, the server key of the remote platform is needed.
   The Routing Service shall connect to an external platform once it obtains the server key for that platform from the
   KeyDiscoveryService.

3. The Routing Service shall exchange "hello"/"welcome" handshake messages with the newly connected remote platform to
   confirm the connection.  It shall use VIP protocol with the subsystem frame set to “routing_table” for the handshake
   messages.

4. Routing Service shall monitor the connection status and inform the PubSubService whenever a remote platform gets
   connected/disconnected.


For Future:

1. Each VIP router shall exchange its routing table with its connected platforms on startup and whenever a new platform
   gets connected or disconnected.

2. The router shall go through each entry in the routing table that it received from other platforms and calculate the
   shortest, most stable path to each remote platform.  It then sends the updated routing table to other platforms for
   adjustments in the forwarding paths (in their local routing table) if any.

3. Whenever a VIP router detects a new connection, it adds an entry into the routing table and sends updated routing
   table to its neighboring platforms.  Each router in the other platforms shall update and re-calculate the forwarding
   paths in its local routing table and forward to rest of the platforms.

4. Similarly, whenever a VIP router detects a remote platform disconnection, it deletes the entry in the routing table
   for that platform and forwards the routing table to other platforms to do the same.


KeyDiscovery Service
--------------------

1. Each platform tries to obtain the platform discovery information - platform name, VIP address and server key of
   remote VOLTTRON platforms through HTTP discovery service at startup.

2. If unsuccessful, it shall make regular attempts to obtain discovery information until successful.

3. The platform discovery information shall then be sent to the Routing Service using VIP protocol with subsystem
   frame set to "routing_table".


Messages for Routing Service
============================

Below are example messages that are applicable to the Routing Service.

* Message sent by KeyDiscovery Service containing the platform discovery information (platform name, VIP address and
  server key) of a remote platform

   ::

       +-+
       | |                                Empty recipient frame
       +-+----+
       | VIP1 |                           Signature frame
       +-+----+
       | |                                Empty user ID frame
       +-+----+
       | 0001 |                           Request ID, for example "0001"
       +---------------+
       | routing_table |                  Subsystem, "routing_table"
       +---------------+----------------+
       | normalmode_platform_connection | Type of operation, "normalmode_platform_connection"
       +--------------------------------+
       | platform discovery information |
       | of external platform           | platform name, VIP address and server key of external platform
       +--------------------------------+
       | platform name       | Remote platform for which the server key belongs to.
       +---------------------+


Handshake messages between two newly connected external VOLTTRON platform to confirm successful connection.

* Message from initiating platform

   ::

       +-+
       | |                     Empty recipient frame
       +-+----+
       | VIP1 |                Signature frame
       +-+----+
       | |                     Empty user ID frame
       +-+----+
       | 0001 |                Request ID, for example "0001"
       +--------------++
       | routing_table |       Subsystem, "routing_table"
       +---------------+
       | hello  |              Operation, "hello"
       +--------+
       | hello  |              Hello handshake request frame
       +--------+------+
       | platform name |       Platform initiating a "hello"
       +---------------+


* Reply message from the destination platform

   ::

       +-+
       | |                     Empty recipient frame
       +-+----+
       | VIP1 |                Signature frame
       +-+----+
       | |                     Empty user ID frame
       +-+----+
       | 0001 |                Request ID, for example "0001"
       +--------------++
       | routing_table |       Subsystem, "routing_table"
       +--------+------+
       | hello  |              Operation, "hello"
       +--------++
       | welcome |             Welcome handshake reply frame
       +---------+-----+
       | platform name |       Platform sending reply to "hello"
       +---------------+

Messages for PubSub communication
=================================

The VIP routers of each platform shall send PubSub messages between platforms using VIP protocol message semantics.
Below is an example of external subscription list message sent by VOLTTRON platform `V1` router to VOLTTRON platform
`V2`.

::

    +-+
    | |                 Empty recipient frame
    +-+----+
    | VIP1 |            Signature frame
    +-+---------+
    |V1 user id |       Empty user ID frame
    +-+---------+
    | 0001 |            Request ID, for example "0001"
    +-------++
    | pubsub |          Subsystem, "pubsub"
    +-------------+-+
    | external_list |   Operation, "external_list" in this case
    +---------------+
    | List of       |
    | subscriptions |   Subscriptions dictionary consisting of VOLTTRON platform id and list of topics as
    +---------------+   key - value pairings, for example: { "V1": ["devices/rtu3"]}


This shows an example of an external publish message sent by the router of VOLTTRON platform `V2` to VOLTTRON platform
`V1`.

::


    +-+
    | |                     Empty recipient frame
    +-+----+
    | VIP1 |                Signature frame
    +-+---------+
    |V1 user id |           Empty user ID frame
    +-+---------+
    | 0001 |                Request ID, for example "0001"
    +-------++
    | pubsub |              Subsystem, "pubsub"
    +------------------+
    | external_publish |    Operation, "external_publish" in this case
    +------------------+
    | topic            |    Message topic
    +------------------+
    | publish message  |    Actual publish message frame
    +------------------+


API
===


Methods for Routing Service
---------------------------

- *external_route( )* - This method receives message frames from external platforms, checks the subsystem frame and
  redirects to appropriate subsystem (routing table, pubsub) handler. It shall run within a separate thread and get
  executed whenever there is a new incoming message from other platforms.
- *setup( )* - This method initiates socket connections with all the external VOLTTRON platforms configured in the config
  file. It also starts monitor thread to monitor connections with external platforms.
- *handle_subsystem( frames )* - Routing Service subsytem handler to handle serverkey message from KeyDiscoveryService and
  "hello/welcome" handshake message from external platforms.
- *send_external( instance_name, frames )* - This method sends input message to specified VOLTTRON platform/instance.
- *register( type, handler )* - Register method for PubSubService to register for connection and disconnection events.
- *disconnect_external_instances( instance_name )* - Disconnect from specified VOLTTRON platform.
- *close_external_connections( )* - Disconnect from all external VOLTTRON platforms.
- *get_connected_platforms( )* - Return list of connected platforms.


Methods for PubSubService
-------------------------

- *external_platform_add( instance_name )* - Send external subscription list to newly connected external VOLTTRON
  platform.
- *external_platform_drop( instance_name )* - Remove all subscriptions for the specified VOLTTRON platform
- *update_external_subscriptions( frames )* - Store/Update list of external subscriptions as per the subscription list
  provided in the message frame.
- *_distribute_external( frames )* - Publish the message all the external platforms that have subscribed to the topic. It
  uses send_external_pubsub_message() of router to send out the message.
- *external_to_local_publish( frames )* - This method retrieves actual message from the message frame, checks the message
  topic against list of external subscriptions and sends the message to corresponding subscribed agents.


Methods for agent pubsub subsystem
----------------------------------

To subscribe to topics from a remote platform, the subscribing agent has to add an additional input parameter -
``all_platforms`` to the pubsub subscribe method.

- *subscribe(peer, prefix, callback, bus='', all_platforms=False)* - The existing 'subscribe' method is modified to
  include optional keyword argument - 'all_platforms'. If 'all_platforms' is set to True, the agent is subscribing to
  topic from local publisher and from external platform publishers.

.. code:: python

    self.vip.pubsub.subscribe('pubsub', 'foo', self.on_match, all_platforms=True)

There is no change in the publish method pf PubSub subsystem. If all the configurations are correct and the publisher
agent on the remote platform is publishing message to topic=``foo``, then the subscriber agent will start receiving
those messages.
