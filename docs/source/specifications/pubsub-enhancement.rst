.. _PubSubEnhancement:

PubSub Communication Between Remote Platforms
=============================================

This document describes pubsub communication between different platforms. The goal of this specification is to improve the current setup of having a forward historian to forward local pubsub messages to remote platforms. The specification also covers pubsub communication between platforms that are multiple hops away. The VIP router of each platform will maintain a routing table and will use it to forward pubsub messages to subscribed platforms that are multiple hops away. The routing table will contain shortest path to each destination platform.


Functional Capabilities
========================

1. Each VOLTTRON platform shall have a list of other VOLTTRON platforms that it has to get connected to in a config file.

2. The VIP router of each platform connects to other platforms on startup.

3. The VIP router shall maintain a routing table containing a list of all the remote platforms and corresponding shortest, most stable route/path to each platform. The behavior of routing table is described in the Routing table section.

4. Platform to platform pubsub communication shall be using VIP protocol with the subsystem frame set to "pubsub".

5. PubSubService of each VOLTTRON platform shall maintain a list of local and external subscriptions.

6. Each VIP router sends its list of local and external subscriptions to other connected platforms in the following cases

    a. On startup

    b. When a new subscription is added

    c. When an existing subscription is removed

    d. When a new platform gets connected

7. Each platform sends periodic heartbeat messages to its connected platforms to confirm its aliveness.

8. Heartbeat communication between VIP routers shall also be using VIP protocol with the subsystem frame set to "heartbeat".

9. When a platform does not receive a heartbeat message from its neighboring platform within a specific grace period, it sets that platform as disconnected and informs the same to other platforms. All stale subscriptions of the disconnected platform shall be removed.

10. Whenever an agent publishes a message to a specific topic, the PubSubService on the local platform first checks the topic against its list of local subscriptions. If a local subscription exists, it sends the publish message to corresponding local subscribers.

11. PubSubService shall also check the topic against list of external subscriptions. If an external subscription exists, it hands over the message and destination platform identity to the VIP router.

12. The VIP router checks its routing table to find the forwarding path to the destination platform and forwards forwarding path and publish message to the first platform in the forwarding path.

13. Whenever a router receives messages from other platform, it shall check the destination platform in the forwarding path in the incoming message.

    a. If the destination platform is the local platform, it hand overs the publish message to PubSubService which checks the topic against list of local subscriptions. If local subscription exists, PubSubService forwards the message to all the local subscribers.

    b. If the destination platform is not the local platform, it retrieves the next hop in the forwarding path and forwards the message to that platform.


Routing Table
++++++++++++++


1. VIP routers shall exchange routing information using VIP protocol with the subsystem frame set to "routing_table".

2. Each VIP router shall exchange its routing table with its connected platforms on startup and whenever a new platform gets connected or disconnected.

3. The router shall go through each entry in the routing table that it received from other platforms and calculate the shortest, most stable path to each remote platform. It then sends the updated routing table to other platforms for adjustments in the forwarding paths (in their local routing table) if any.

4. Whenever a VIP router detects a new connection, it adds an entry into the routing table and sends updated routing table to its neighboring platforms. Each router in the other platforms shall update and re-calculate the forwarding paths in its local routing table and forward to rest of the platforms.

5. Similarly, whenever a VIP router detects a remote platform disconnection, it deletes the entry in the routing table for that platform and forwards the routing table to other platforms to do the same.


Messages for Routing information
********************************
The VIP routers in each platform shall use VIP protocol message semantics to send routing information. Below example shows the routing table information sent by VOLTTRON platform V1 to VOLTTRON platform V2.

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
    | data  |               Routing table dictionary
    +-------+


This shows routing table information received by VOLTTRON platform V2 router from VOLTTRON platform V1 router.
::

    +-------+
    | V1    |               Sender frame, "V1" in this case
    +-+-----+
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
    | data  |               Routing table dictionary
    +-------+


Messages for PubSub communication
*********************************
The VIP routers of each platform shall send pubsub messages between platforms using VIP protocol message semantics. Below shows an example of external subscription list message sent by VOLTTRON platform V1 router to VOLTTRON platform V2.

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


This shows an example of external subscription list message received by VOLTTRON platform V2 router from
VOLTTRON platform V1.

::

    +-------+
    | V1    |           Sender frame, "V1" in this case
    +-+-----+
    | |                 Empty recipient frame
    +-+----+
    | VIP1 |            Signature frame
    +-+---------+
    |V1 user id |       Empty user ID frame
    +-+---------+
    | 0001 |            Request ID, for example "0001"
    +-------++
    | pubsub |          Subsystem, "pubsub"
    +---------------+
    | external_list |   Operation, "external_list" in this case
    +---------------+
    | List of       |   Subscriptions dictionary consisting of VOLTTRON platform id and list of topics as
    | subscriptions |   key - value pairings, for example: { "V1": ["devices/rtu3"]}
    +---------------+


This shows an example of external publish message sent by VOLTTRON platform V2 router to VOLTTRON platform V1.
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
    | forwarding path  |    Forwarding path containing list of VOLTTRON platform IDs in the path. For example, ["V1"]
    +------------------+
    | publish message  |    Actual publish message frame
    +------------------+


This shows an example of external publish message received by VOLTTRON platform V1 router from VOLTTRON platform V2.

::


    +-------+
    | V2    |               Sender frame, "V2" in this case
    +-+-----+
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
    | forwarding path  |    Forwarding path containing list of VOLTTRON platform IDs in the path. For example, ["V1"]
    +------------------+
    | publish message  |    Actual publish message frame
    +------------------+



Messages for Heartbeat
***********************
Heartbeat messages shall also follow VIP protocol semantics. Below an example of external heartbeat message sent by VOLTTRON platform V1 router to VOLTTRON platform V2.
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
    | heartbeat     |       Subsystem, "heartbeat"
    +---------------+
    | alive |               heartbeat status - "alive"
    +-------+


This shows an example of external heartbeat message received by VOLTTRON platform V2 router from VOLTTRON platform V1.
::

    +-------+
    | V2    |               Sender frame, "V2" in this case
    +-+-----+
    | |                     Empty recipient frame
    +-+----+
    | VIP1 |                Signature frame
    +-+----+
    | |                     Empty user ID frame
    +-+----+
    | 0001 |                Request ID, for example "0001"
    +--------------++
    | routing_table |       Subsystem, "heartbeat"
    +---------------+
    | alive  |              heartbeat status - "alive"
    +--------+


Methods for Router
******************

external_route() - This method receives message frames from external platforms, checks the subsystem frame and redirects to appropriate subsystem (routing table, pubsub, heartbeat) handler. It shall run within a separate thread and get executed whenever there is a new incoming message from other platforms.

manage_routing_table( external_routing_table ) - This method manages the local routing table. It performs the following operations

 - Go through each entry in the external routing table and recalculates the routing path to all platforms

 - Update local routing table if necessary

 - If any changes are made to local routing table, send routing table message to all neighboring platforms.

connect_external_platforms() - Connect to all VOLTTRON platforms provided in the config file. This method is called during router startup.

disconnect_external_platforms(platform_ids) - Disconnect from all VOLTTRON platforms provided in "platform_ids" list.

send_periodic_heartbeat() - Send periodic heartbeat messages to all connected platforms

update_heartbeat_replies(frames) - Update status of other platforms (GOOD or BAD) based on heartbeat message received from other platforms.

check_heartbeat_status() - This method periodically checks the status of all heartbeat messages received from external platforms so far. If any of the heartbeat messages are missing, it does the following

 - Set the platform as disconnected

 - Remove the platform from routing table

 - Remove corresponding subscriptions for the platform

 - Send updated routing table to other platforms

get_connected_platforms() - Return list of connected platforms.

send_external_pubsub_message( frames, platform_ids ) - Send the pubsub message to all the platforms in the platform ids list.


Methods for PubSubService
*************************

external_peer_add( platform_id ) - Add external VOLTTRON platform.

external_peer_drop( platform_id ) - Remove all subscriptions for the specified VOLTTRON platform

update_external_subscriptions( frames ) - Update list of external subscriptions as per the subscription list provided in the message frame.

publish_external_message( topic, headers, message, platform_ids ) - Publish the message all the external platforms that have subscribed to the topic. It uses send_external_pubsub_message() of router to send out the message.

external_to_local_publish( frames ) - This method retrieves actual message from the message frame, checks the message topic against list of local subscriptions and sends the message to corresponding subscribed agents.