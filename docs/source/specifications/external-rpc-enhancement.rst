.. _ExternalRPCEnhancement:

RPC Communication Between Remote Platforms
==========================================

This document describes RPC communication between different platforms. In the current setup of VOLTTRON, if an agent in
one platform wants to make a RPC method call on an agent in a different platform, it responsible for establishing and
managing the connection with the target platform. Instead, if allow the VIP routers of each platform to make the
connection and manage the RPC communication internally, this will reduce the burden on the agents and enable a more
seamless RPC communication between agents on different platforms.


VIP Router
**********

The VIP Router on each platform is responsible for establishing and maintaining the connection with remote platforms.


Router Functional Capabilities
******************************

1. Each VOLTTRON platform shall have a list of other VOLTTRON platforms that it has to establish connection in a config
file.

2. The VIP router of each platform connects to other platforms on startup. It is responsible for maintaining the
connection (detects disconnects and intiate reconnects etc).

3. The VIP router routes the external RPC message as described in "Messages for External RPC communication" section.


External RPC Subsystem
**********************

External RPC subsystem allows an agent to make RPC method calls on agents running in remote platforms.


External RPC Functional Capabilities
************************************
1. The agent needs to specify the remote platform name as an additional argument in the original RPC call or notify
method.

2. The external RPC subsystem on the agent side adds the remote platform name into its VIP frame and sends to the
VIP router for routing to correct destination platform. It is described in detail in the next section.


Messages for External RPC communication
***************************************

The VIP router and external RPC subsystem on the agent side will be using VIP protocol for communication. The
communication between the VIP routers and the external RPC susbsytem on the agent side can be best explained with an
example. Suppose an agent 1 on platform V1 wants to make RPC method call on agent 2 in platform V2. Then the underlying
messages exchanged between the two platforms will look like below.

Message format for external RPC subsystem of agent 1 on platform V1 to send to its VIP router.
::

    +-+
    | |                                 Empty recipient frame (implies VIP router is the destination)
    +-+----+
    | VIP1 |                            Signature frame
    +-+---------+
    |V1 user id |                       Empty user ID frame
    +-+---------+
    | 0001 |                            Method request ID, for example "0001"
    +-------------++
    | external_rpc |                    Subsystem, "external_rpc"
    +-----------------------------+
    | external RPC request message|     Dictionary containing destination platform name, destination agent identity,
    |                             |     source agent identity, method name and method arguments
    +-----------------------------+


Message sent by VIP router on platform V1 to VIP router of platform V2.

::

    +-----+
    | V2  |                             Destination platform ID, "V2" in this case
    +-+---+
    | |                                 Empty recipient frame
    +-+----+
    | VIP1 |                            Signature frame
    +-+---------+
    |V1 user id |                       Empty user ID frame
    +-+---------+
    | 0001 |                            Method Request ID, for example "0001"
    +--------------+
    | external_rpc |                    Subsystem, "external_rpc"
    +------------------------------+
    | external RPC request message |    Dictionary containing destination platform name, destination agent identity,
    |                              |    source platform name, source agent identity, method and arguments
    +------------------------------+


When the VIP router of platform V2 receives the message, it extracts the destination agent identity from the external
RPC request message frame and routes it to the intended agent.

The result of the RPC method execution needs to be returned back to the calling agent. So the messages for the return
path are as follows. The source and destination platforms and agents are interchanged in the reply message.

Message sent by external RPC subsystem of agent 2 on platform V2 to its VIP router.

::

    +-+
    | |                                 Empty recipient frame (implies destination is VIP router)
    +-+----+
    | VIP1 |                            Signature frame
    +-+---------+
    |V2 user id |                       Empty user ID frame
    +-+---------+
    | 0001 |                            Method Request ID, for example "0001"
    +--------------+
    | external_rpc |                    Subsystem, "external_rpc"
    +------------------------------+
    | external rpc reply message   |    Dictionary containing destination platform name, destination agent identity
    |                              |    source platform name, source agent identity and method result
    +------------------------------+


Message sent by VIP router of platform V2 to VIP router of platform V1.
::

    +-----+
    | V1  |                             Source platform ID frame, "V1" in this case
    +-+---+
    | |                                 Empty recipient frame
    +-+----+
    | VIP1 |                            Signature frame
    +-+---------+
    |V1 user id |                       Empty user ID frame
    +-+---------+
    | 0001 |                            Method Request ID, for example "0001"
    +--------------+
    | external_rpc |                    Subsystem, "external_rpc"
    +------------------------------+
    | external rpc reply message   |    Dictionary containing destination platform name, destination agent identity
    |                              |    source platform name, source agent identity and method result
    +------------------------------+

The VIP router of platform V1 extracts the destination agent identity from the external RPC reply message frame and
routes it to the calling agent.


Methods for External RPC Subsystem
**********************************

call(peer, method, \*args, \**kwargs) - New 'external_platform' parameter  need to be added in kwargs to the
original RPC subsystem call. If the platform name of the target platform is passed into the 'external_platform'
parameter, the RPC method on the target platform gets executed.

notify(peer, method, \*args, \**kwargs) - New 'external_platform' parameter  need to be added in kwargs to the
original RPC subsystem notify method. If the platform name of the target platform is passed into the 'external_platform'
parameter, the RPC method on the target platform gets executed.

handle_external_rpc_subsystem(message) - Handler for the external RPC subsystem messages. It executes the requested RPC
method and returns the result to the calling platform.
