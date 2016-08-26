.. _VIP-Overview:

VIP - VOLTTRON™ Interconnect Protocol
+++++++++++++++++++++++++++++++++++++

This document specifies VIP, the VOLTTRON™ Interconnect Protocol. The use case for VIP is to provide communications between *agents*, *controllers*, *services*, and the supervisory *platform* in an abstract fashion so that additional protocols can be built and used above VIP. VIP defines how *peers* connect to the *router* and the messages they exchange.

* Name: github.com/VOLTTRON/volttron/wiki/VOLTTRON-Interconnect-Protocol
* Editor: Brandon Carpenter <brandon (dot) carpenter (at) pnnl (dot) gov>
* State: draft
* See also: ZeroMQ_, ZMTP_, CurveZMQ_, ZAP_

.. _ZeroMQ: http://zeromq.org
.. _ZMTP: http://rfc.zeromq.org/spec:23/ZMTP
.. _CurveZMQ: http://rfc.zeromq.org/spec:26/CURVEZMQ
.. _ZAP: http://rfc.zeromq.org/spec:27/ZAP.


Preamble
========

Copyright (c) 2015 Battelle Memorial Institute
All rights reserved

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

The views and conclusions contained in the software and documentation are those of the authors and should not be interpreted as representing official policies, either expressed or implied, of the FreeBSD Project.

This material was prepared as an account of work sponsored by an agency of the United States Government.  Neither the United States Government nor the United States Department of Energy, nor Battelle, nor any of their employees, nor any jurisdiction or organization that has cooperated in the development of these materials, makes any warranty, express or implied, or assumes any legal liability or responsibility for the accuracy, completeness, or usefulness or any information, apparatus, product, software, or process disclosed, or represents that its use would not infringe privately owned rights.

Reference herein to any specific commercial product, process, or service by trade name, trademark, manufacturer, or otherwise does not necessarily constitute or imply its endorsement, recommendation, or favoring by the United States Government or any agency thereof, or Battelle Memorial Institute. The views and opinions of authors expressed herein do not necessarily state or reflect those of the United States Government or any agency thereof.

PACIFIC NORTHWEST NATIONAL LABORATORY operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY under Contract DE-AC05-76RL01830

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in `RFC 2119`_.

.. _RFC 2119: http://tools.ietf.org/html/rfc2119


Overall Design
==============


What Problems does VIP Address?
-------------------------------

When VOLTTRON agents, controllers, or other entities needed to exchange data, they previously used the first generation pub/sub messaging mechanism and ad-hoc methods to set up direct connections. While the pub/sub messaging is easy to implement and use, it suffers from several limitations:

* It requires opening two listening sockets: one each for publishing and subscribing.
* There is no trivial way to prevent message spoofing.
* There is no trivial way to enable private messaging
* It is not ideal for peer-to-peer communications.

These limitations have severe security implications. For improved security in VOLTTRON, the communications protocol must provide a method for secure data exchange that is intuitive and simple to implement and use.

ZeroMQ already provides many of the building blocks to implement encrypted and authenticated communications over a shared socket. It already includes a socket type implementing the router pattern. What remains is a protocol built on ZeroMQ to provide a single connection point, secure message passing, and retain the ability for entities to come and go as they please.

VIP is just that protocol, specifically targeting the limitations above.


Why ZeroMQ?
-----------

Rather than reinvent the wheel, VIP makes use of many features already implemented in ZeroMQ, including ZAP and CurveMQ. While VIP doesn't require the use of ZAP or CurveMQ, their use substantially improves security by encrypting traffic over public networks and limiting connections to authenticated peers.

ZeroMQ also provides reliable transports with built-in framing, automatic reconnection, in-process zero-copy message passing, abstractions for underlying protocols, and so much more. While some of these features create other pain points, they are minimal compared with the effort of either reimplementing or cobbling together libraries.


VIP is a routing protocol
-------------------------

VIP uses the ZeroMQ router pattern. Specifically, the router binds a ROUTER socket and peers connect using a DEALER or ROUTER socket. Unless the peer is connecting a single socket to multiple routers, using the DEALER socket is easiest, but there are instances where using a ROUTER is more appropriate. One must just exercise care to include the proper address envelope to ensure proper routing.


Extensible Security
-------------------

VIP makes no assumptions about the security mechanisms used. It works equally well over encrypted or unencrypted channels. Any connection-level authentication and encryption is handled by ZAP. Message-level authentication can be implemented in the protocols and services using VIP or by utilizing message properties set in ZAP replies.


ZeroMQ Compatibility
--------------------

For enhanced security, VOLTTRON recommends libzmq version 4.1 or greater, however, most features of VIP are available with older versions. The following is an incomplete list of core features available with recent versions of libzmq.

* Version 3.2:

  * Basic, unauthenticated, unencrypted routing
  * Use ZMQ_ROUTER_BEHAVIOR socket option instead of ZMQ_ROUTER_MANDATORY

* Version 4.0:

  * Adds authentication and encryption via ZAP

* Version 4.1:

  * Adds message properties allowing correlating authentication tokens to messages


Message Format and Version Detection
------------------------------------

VIP uses a simple, multi-frame format for its messages. The first one (for peers) or two (for router) frames contain the delivery address(es) and are follow immediately by the VIP signature ``VIP1``. The first characters of the signature are used to match the protocol and the last character digit indicates the protocol version, which will be incremented as the protocol is revised. This allows for fail-fast behavior and backward compatibility while being simple to implement in any language supported by ZeroMQ.


Formal Specification
====================


Architecture
------------

VIP defines a message-based dialog between a *router* that transfers data between *peers*. The *router* and *peers* SHALL communicate using the following socket types and transports:

* The router SHALL use a ROUTER socket.
* Peers SHALL use a DEALER or ROUTER socket.
* The router SHALL bind to one or more endpoints using inproc, tcp, or ipc address types.
* Peers SHALL connect to these endpoints.
* There MAY be any number of peers.


Message Format
--------------

A routing exchange SHALL consist of a peer sending a message to the router followed by the router receiving the message and sending it to the destination peer.

Messages sent to the router by peers SHALL consist of the following message frames:

* The *recipient*, which SHALL contain the socket identity of the destination peer.
* The protocol signature, which SHALL contain the four octets "VIP1".
* The *user id*, which SHALL be an implementation-defined value.
* The *request id*, which SHALL contain an opaque binary blob.
* The *subsystem*, which SHALL contain a string.
* The *data*, which SHALL be zero or more subsystem-specific opaque frames.

Messages received from a peer by the router will automatically have a *sender* frame prepended to the message by the ROUTER socket. When the router forwards the message, the sender and recipient fields are swapped so that the *recipient* is in the first frame and the *sender* is in the second frame. The *recipient* frame is automatically stripped by the ROUTER socket during delivery. Peers using ROUTER sockets must prepend the message with an *intermediary* frame, which SHALL contain the identity of a router socket.

Messages received from the router by peers SHALL consist of the following message frames:

* The *sender*, which SHALL contain the socket identity of the source peer.
* The protocol signature, which SHALL contain the four octets "VIP1".
* The *user id*, which MAY contain a UTF-8 encoded string.
* The *request id*, which SHALL contain an opaque binary blob.
* The *subsystem*, which SHALL contain a non-empty string.
* The *data*, which SHALL be zero or more subsystem-specific opaque frames.

The various fields have these meanings:

* sender: the ZeroMQ DEALER or ROUTER identity of the sending (source) peer.
* recipient: the ZeroMQ DEALER or ROUTER identity of the recipient (destination) peer.
* intermediary: the ZeroMQ ROUTER identity of the intermediary router.
* user id: VIP authentication metadata set in the authenticator. See the discussion below for more information on this value.
* request id: the meaning of this field is defined by the sending peer. Replies SHALL echo the request id without modifying it.
* subsystem: this specifies the peer subsystem the data is intended for. The length of a subsystem name SHALL NOT exceed 255 characters and MUST only contain ASCII characters.
* data: provides the data for the given subsystem. The number of frames required is defined by each subsystem.


User ID
-------

The value in the *user id* frame depends on the implementation and the version of ZeroMQ. If ZAP is used with libzmq 4.1.0 or newer, peers should send an empty string for the user id and the ZAP authenticator will replace it with an authentication token which receiving peers may use to authorize access. If ZAP is not used or a version of libzmq is used which lacks support for retrieving the user id metadata, an authentication subsystem may be used to authenticate peers. The authentication subsystem SHALL provide peers with private tokens that must be sent with each message in the user id frame and which the router will substitute with a public token before forwarding. If the message cannot be authenticated, the user id received by peers SHALL be a zero-length string.


Socket Types
------------

Peers communicating via the router will typically use DEALER sockets and should not require additional handling. However, a DEALER peer may only connect to a single router. Peers may use ROUTER sockets to connect to multiple endpoints, but must prepend the routing ID of the destination.

When using a DEALER socket:

* A peer SHALL not send in intermediary address.
* A peer SHALL connect to a single endpoint.

When using a ROUTER socket:

* A peer SHALL prepend the intermediary routing ID of to the message frames.
* A peer MAY connect to multiple endpoints.


Routing Identities
------------------

Routing identities are set on a socket using the ZMQ_IDENTITY socket option and MUST be set on both ROUTER and DEALER sockets. The following additional requirements are placed on the use of peer identities:

* Peers SHALL set a valid identity rather than rely on automatic identity generation.
* The router MAY drop messages with automatically generated identities, which begin with the zero byte ('\0').

A zero length identity is invalid for peers and is, therefore, unroutable. It is used instead to address the router itself.

* Peers SHALL use a zero length recipient to address the router.
* Messages sent from the router SHALL have a zero length sender address.


Error Handling
==============

The documented default behavior of ZeroMQ ROUTER sockets when entering the mute state (when the send buffer is full) is to silently discard messages without blocking. This behavior, however, is not consistently observed. Quietly discarding messages is not the desired behavior anyway because it prevents peers from taking appropriate action to the error condition.

* Routers SHALL set the ZMQ_SNDTIMEO socket option to 0.
* Routers SHALL forward EAGAIN errors to sending peers.

It is also the default behavior of ROUTER sockets to silently drop messages addressed to unknown peers.

* Routers SHALL set the ZMQ_ROUTER_MANDATORY socket option.
* Routers SHALL forward EHOSTUNREACH errors to sending peers, unless the recipient address matches the sender.

Most subsystems are optional and some way of communicating unsupported subsystems to peers is needed.

* The error code 93, EPROTONOSUPPORT, SHALL be returned to peers to indicate unsupported or unimplemented subsystems.

The errors above are reported via the *error* subsystem. Other errors MAY be reported via the *error* subsystem, but subsystems SHOULD provide mechanisms for reporting subsystem-specific errors whenever possible.

An error message must contain the following:

* The recipient frame SHALL contain the socket identity of the original sender of the message.
* The sender frame SHALL contain the socket identity of the reporting entity, usually the router.
* The request ID SHALL be copied from the from the message which triggered the error.
* The subsystem frame SHALL be the 5 octets 'error'.
* The first data frame SHALL be a string representation of the error number.
* The second data frame SHALL contain a UTF-8 string describing the error.
* The third data frame SHALL contain the identity of the original recipient, as it may differ from the reporter.
* The fourth data frame SHALL contain the subsystem copied from the subsystem field of the offending message.


Subsystems
==========

Peers may support any number of communications protocols or subsystems. For instance, there may be a remote procedure call (RPC) subsystem which defines its own protocol. These subsystems are outside the scope of VIP and this document with the exception of the *hello* and *ping* subsystems.

* A router SHALL implement the hello subsystem.
* All peers and routers SHALL implement the ping subsystem.


The hello Subsystem
-------------------

The hello subsystem provides one simple RPC-style routine for peers to probe the router for version and identity information.

A peer hello request message must contain the following:

* The recipient frame SHALL have a zero length value.
* The request id MAY have an opaque binary value.
* The subsystem SHALL be the 5 characters "hello".
* The first data frame SHALL be the five octets 'hello' indicating the operation.

A peer hello reply message must contain the following:

* The sender frame SHALL have a zero length value.
* The request id SHALL be copied unchanged from the associated request.
* The subsystem SHALL be the 7 characters "hello".
* The first data frame SHALL be the 7 octets 'welcome'.
* The second data frame SHALL be a string containing the router version number.
* The third data frame SHALL be the router's identity blob.
* The fourth data frame SHALL be the peer's identity blob.

The hello subsystem can help a peer with the following tasks:

* Test that a connection is established.
* Discover the version of the router.
* Discover the identity of the router.
* Discover the identity of the peer.
* Discover authentication metadata.

For instance, if a peer will use a ROUTER socket for its connections, it must first know the identity of the router. The peer might first connect with a DEALER socket, issue a hello, and use the returned identity to then connect the ROUTER socket.


The ping Subsystem
------------------

The *ping* subsystem is useful for testing the presence of a peer and the integrity and latency of the connection. All endpoints, including the router, must support the ping subsystem.

A peer ping request message must contain the following:

* The recipient frame SHALL contain the identity of the endpoint to query.
* The request id MAY have an opaque binary value.
* The subsystem SHALL be the 4 characters "ping".
* The first data frame SHALL be the 4 octets 'ping'.
* There MAY be zero or more additional data frames containing opaque binary blobs.

A ping response message must contain the following:

* The sender frame SHALL contain the identity of the queried endpoint.
* The request id SHALL be copied unchanged from the associated request.
* The subsystem SHALL be the 4 characters "ping".
* The first data frame SHALL be the 4 octets 'pong'.
* The remaining data frames SHALL be copied from the ping request unchanged, starting with the second data frame.

Any data can be included in the ping and should be returned unchanged in the pong, but limited trust should be placed in that data as it is possible a peer might modify it against the direction of this specification.


Discovery
---------

VIP does not define how to discover peers or routers. Typical options might be to hard code the router address in peers or to pass it in via the peer configuration. A well known (i.e. statically named) directory service might be used to register connected peers and allow for discovery by other peers.


Example Exchanges
=================

These examples show the messages *as sent on the wire* as sent or received by peers using DEALER sockets. The messages received or sent by peers or routers using ROUTER sockets will have an additional address at the start. We do not show the frame sizes or flags, only frame contents.


Example of hello Request
------------------------

This shows a hello request sent by a peer, with identity "alice", to a connected router, with identity "router".

::

    +-+
    | |                 Empty recipient frame
    +-+----+
    | VIP1 |            Signature frame
    +-+----+
    | |                 Empty user ID frame
    +-+----+
    | 0001 |            Request ID, for example "0001"
    +------++
    | hello |           Subsystem, "hello" in this case
    +-------+
    | hello |           Operation, "hello" in this case
    +-------+

This example assumes a DEALER socket. If a peer uses a ROUTER socket, it SHALL prepend an additional frame containing the router identity, similar to the following example.

This shows the example request received by the router:

::

    +-------+
    | alice |           Sender frame, "alice" in this case
    +-+-----+
    | |                 Empty recipient frame
    +-+----+
    | VIP1 |            Signature frame
    +-+----+
    | |                 Empty user ID frame
    +-+----+
    | 0001 |            Request ID, for example "0001"
    +------++
    | hello |           Subsystem, "hello" in this case
    +-------+
    | hello |           Operation, "hello" in this case
    +-------+

This shows an example reply sent by the router:

::

    +-------+
    | alice |           Recipient frame, "alice" in this case
    +-+-----+
    | |                 Empty sender frame
    +-+----+
    | VIP1 |            Signature frame
    +-+----+
    | |                 Empty authentication metadata in user ID frame
    +-+----+
    | 0001 |            Request ID, for example "0001"
    +------++
    | hello |           Subsystem, "hello" in this case
    +-------+-+
    | welcome |         Operation, "welcome" in this case
    +-----+---+
    | 1.0 |             Version of the router
    +-----+--+
    | router |          Router ID, "router" in this case
    +-------++
    | alice |           Peer ID, "alice" in this case
    +-------+

This shows an example reply received by the peer:

::

    +-+
    | |                 Empty sender frame
    +-+----+
    | VIP1 |            Signature frame
    +-+----+
    | |                 Empty authentication metadata in user ID frame
    +-+----+
    | 0001 |            Request ID, for example "0001"
    +------++
    | hello |           Subsystem, "hello" in this case
    +-------+-+
    | welcome |         Operation, "welcome" in this case
    +-----+---+
    | 1.0 |             Version of the router
    +-----+--+
    | router |          Router ID, "router" in this case
    +-------++
    | alice |           Peer ID, "alice" in this case
    +-------+


Example of ping Subsystem
-------------------------

This shows a ping request sent by the peer "alice" to the peer "bob" through the router "router".

::

    +-----+
    | bob |             Recipient frame, "bob" in this case
    +-----++
    | VIP1 |            Signature frame
    +-+----+
    | |                 Empty user ID frame
    +-+----+
    | 0002 |            Request ID, for example "0002"
    +------+
    | ping |            Subsystem, "ping" in this case
    +------+
    | ping |            Operation, "ping" in this case
    +------+-----+
    | 1422573492 |      Data, a single frame in this case (Unix timestamp)
    +------------+

This shows the example request received by the router:

::

    +-------+
    | alice |           Sender frame, "alice" in this case
    +-----+-+
    | bob |             Recipient frame, "bob" in this case
    +-----++
    | VIP1 |            Signature frame
    +-+----+
    | |                 Empty user ID frame
    +-+----+
    | 0002 |            Request ID, for example "0002"
    +------+
    | ping |            Subsystem, "ping" in this case
    +------+
    | ping |            Operation, "ping" in this case
    +------+-----+
    | 1422573492 |      Data, a single frame in this case (Unix timestamp)
    +------------+

This shows the example request forwarded by the router:

::

    +-----+
    | bob |             Recipient frame, "bob" in this case
    +-----+-+
    | alice |           Sender frame, "alice" in this case
    +------++
    | VIP1 |            Signature frame
    +-+----+
    | |                 Empty authentication metadata in user ID frame
    +-+----+
    | 0002 |            Request ID, for example "0002"
    +------+
    | ping |            Subsystem, "ping" in this case
    +------+
    | ping |            Operation, "ping" in this case
    +------+-----+
    | 1422573492 |      Data, a single frame in this case (Unix timestamp)
    +------------+

This shows the example request received by "bob":

::

    +-------+
    | alice |           Sender frame, "alice" in this case
    +------++
    | VIP1 |            Signature frame
    +-+----+
    | |                 Empty authentication metadata in user ID frame
    +-+----+
    | 0002 |            Request ID, for example "0002"
    +------+
    | ping |            Subsystem, "ping" in this case
    +------+
    | ping |            Operation, "ping" in this case
    +------+-----+
    | 1422573492 |      Data, a single frame in this case (Unix timestamp)
    +------------+

If "bob" were using a ROUTER socket, there would be an additional frame prepended to the message containing the router identity, "router" in this case.

This shows an example reply from "bob" to "alice"

::

    +-------+
    | alice |           Recipient frame, "alice" in this case
    +------++
    | VIP1 |            Signature frame
    +-+----+
    | |                 Empty user ID frame
    +-+----+
    | 0002 |            Request ID, for example "0002"
    +------+
    | ping |            Subsystem, "ping" in this case
    +------+
    | pong |            Operation, "pong" in this case
    +------+-----+
    | 1422573492 |      Data, a single frame in this case (Unix timestamp)
    +------------+

The message would make its way back through the router in a similar fashion to the request.


Reference Implementation
========================

Reference VIP router: https://github.com/VOLTTRON/volttron/blob/master/volttron/platform/vip/router.py

Reference VIP peer: https://github.com/VOLTTRON/volttron/blob/master/volttron/platform/vip/socket.py


.. vim: set fenc=utf-8 ft=rst wrap spell:
