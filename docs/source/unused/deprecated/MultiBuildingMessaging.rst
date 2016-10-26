MultiBuilding Agent
===================

This agent has been superseded by the VIP functionality introduced in 3.0 and should be considered deprecated. However it is still a usable agent.

Multi-building (or multi-node) messaging is implemented as a
service-style agent. Its use is optional and it can be enabled/disabled
by simply enabling/disabling the multibuilding service agent. It is
easily configured using the service configuration file and provides
several new topics for use in the local agent exchange bus.

Configuration
~~~~~~~~~~~~~

The service configuration file may contain the declarations below:

-  | *building-publish-address*:
   | A ØMQ address on which to listen for messages published by other
   nodes. Defaults to 'tcp://0.0.0.0:9161'.

-  | *building-subscribe-address*:
   | A ØMQ address on which to listen for messages subscribed to by
   other nodes. Defaults to 'tcp://0.0.0.0:9160'.

-  | *public-key*, *secret-key*:
   | Curve keypair (create with zmq.curve\_keypair()) to use for
   authentication and encryption. If not provided, all communications
   will be unauthenticated and unencrypted.

-  | *hosts*:
   | A mapping (dictionary) of building names to publish/subscribe
   addresses. Each entry is of the form:

   ::

       "CAMPUS/BUILDING": {"pub": "PUB_ADDRESS", "sub": "SUB_ADDRESS", "public-key": "PUBKEY", "allow": "PUB_OR_SUB"}

-  CAMPUS/BUILDING: building for which the given parameters apply
-  PUB\_ADDRESS: ØMQ address used to connect to the building for
   publishing
-  SUB\_ADDRESS: ØMQ address used to connect to the building
   subscriptions
-  PUBKEY: curve public key of the host used to authenticate incoming
   connections
-  PUB\_OR\_SUB: the string "pub" to allow publishing only or "sub" to
   allow both publish and subscribe

-  *cleanup-period*: Frequency, in seconds, to check for and close stale
   connections. Defaults to 600 seconds (10 minutes).

-  *uuid*: A UUID to use in the Cookie header. If not given, one will be
   automatically generated.

Sending and Receiving Inter-building Messages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Three topics are provided for inter-building messaging:

-  | building/recv/\ ``CAMPUS/BUILDING/TOPIC``:
   | Agents can subscribe to to this topic to receive messages sent to
   ``TOPIC`` at the building specified by ``CAMPUS``/``BUILDING``.

-  | building/send/\ ``CAMPUS/BUILDING/TOPIC``:
   | Agents can send messages to this topic to have them forwarded to
   ``TOPIC`` at the building specified by ``CAMPUS``/``BUILDING``.

-  | building/error/\ ``CAMPUS/BUILDING/TOPIC``:
   | Errors encountered during sending/receiving to/from the above two
   topics will be sent over this topic.

Limitations and Future Work
~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  | Requires opening multiple listening ports:
   | It would be nice to multiplex all inter-building communications
   over a single port to decrease the attack footprint and ease firewall
   administration.

-  | There is limited authorization:
   | a remote host can either publish or publish and subscribe. Perhaps
   a filter list can be included to limit which topics a host may
   subscribe to or publish on.

-  | Remote host lookup is kept in a static file:
   | Ideally, host lookup would be done through some central directory
   service, but that is not currently implemented.


