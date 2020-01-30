.. _VIP-Enhancements:


VIP Enhancements
================

Outline a vision of how VOLTTRON Message Bus should work

When creating VIP for VOLTTRON 3.0 we wanted to address two security
concerns and one user request:

-  Security Concern 1: Agents can spoof each other on the VOLTTRON
   message bus and fake messages.
-  Security Concern 2: Agents can subscribe to topics that they are not
   authorized to subscribe to.
-  User Request 1: Several users requested means to transfer large
   amounts of data between agents without using the message bus.

VOLTTRON Interconnect Protocol (VIP) was created to address these issues
but unfortunately, it broke the easy to use pub-sub messaging model of
VOLTTRON. Additionally to use the security features of VOLTTRON in 3.0
code has become an ordeal especially when multiple platforms are
concerned. Finally, VIP has introduced the requirement for knowledge of
specific other platforms to agents written by users in order to be able
to communicate. The rest of this memo focuses on defining the way
VOLTTRON message bus will work going forward indefinitely and should be
used as the guiding principles for any future work on VIP and VOLTTRON.
 

VOLTTRON Message Bus Guiding Principles:

#. | All communications between two or more different VOLTTRON platforms
   MUST go through the VIP Router. Said another way, a user agent
   (application) should have NO capability to reach out to an agent on a
   different VOLTTRON platform directly.
   | All communications between two or more VOLTTRON platforms must be
   in the form of topics on the message bus. Agents MUST not use a
   distinct platform address or name to communicate via a direct
   connection between two platforms.

#. VOLTTRON will use two TCP ports. One port is used to extend VIP
   across platforms. A second port is used for the VOLTTRON discovery
   protocol (more on this to come on a different document). VIP will
   establish bi-directional communication via a single TCP port.

#. In order to solve the bootstrapping problem that CurveMQ has punted
   on, we will modify VIP to operate similar (behaviorally) to SSH.

A. On a single VOLTTRON platform, the platform’s public key will be made
available via an API so that all agents will be able to communicate with
the platform. Additionally, the behavior of the platform will be changed
so that agents on the same platform will automatically be added to
auth.json file. No more need for user to add the agents manually to the
file. The desired behavior is similar to how SSH handles known\_hosts.
Note that this behavior still addresses the security request 1 & 2.

B. When connecting VOLTTRON platforms, VOLTTRON Discovery Protocol (VDP)
will be used to discover the other platforms public key to establish the
router to router connection. Note that since we BANNED agent to agent
communication between two platforms, we have prevented an O(N^2)
communication pattern and key bootstrapping problem.

#. Authorization determines what agents are allowed to access what
   topics. Authorization MUST be managed by the VOLTTRON Central
   platform on a per organization basis. It is not recommended to have
   different authorization profiles on different VOLTTRON instances
   belonging to the same organization.

#. VOLTTRON message bus uses topics such as and will adopt an
   information model agreed upon by the VOLTTRON community going
   forward. Our initial information model is based on the OpenEIS schema
   going forward. A different document will describe the information
   model we have adopted going forward. All agents are free to create
   their own topics but the VOLTTRON team (going forward) will support
   the common VOLTTRON information model and all agents developed by
   PNNL will be converted to use the new information model.

#. Two connected VOLTTRON systems will exchange a list of available
   topics via the message router. This will allow each VIP router to
   know what topics are available at what VOLTTRON platform.

#. Even though each VOLTTRON platform will have knowledge of what topics
   are available around itself, no actual messages will be forwarded
   between VOLTTRON platforms until an agent on a specific platform
   subscribes to a topic. When an agent subscribes to a topic that has a
   publisher on a different VOLTTRON platform, the VIP router will send
   a request to its peer routers so that the messages sent to that topic
   will be forwarded. There will be cases (such as clean energy
   transactive project) where the publisher to a topic may be multiple
   hops away. In this case, the subscribe request will be sent towards
   the publisher through other VIP routers. In order to find the most
   efficient path, we may need to keep track of the total number of hops
   (in terms of number of VIP routers).

#. The model described in steps 5/6/7 applies to data collection. For
   control applications, VOLTTRON team only allows control actions to be
   originated from the VOLTTRON instance that is directly connected to
   that controlled device. This decision is made to increase the
   robustness of the control agent and to encourage truly distributed
   applications to be developed.

#. Direct agent to agent communication will be supported by creation of
   an ephemeral topic under the topic hierarchy. Our measurements have
   shown repeatedly that the overhead of using the ZeroMQ message
   pub/sub is minimal and has zero impact on communications throughput.

In summary, by making small changes to the way VIP operates, I believe
that we can significantly increase the usability of the platform and
also correct the mixing of two communication platforms into VIP.
VOLTTRON message bus will return to being a pub/sub messaging system
going forward. Direct agent to agent communication will be supported
through the message bus.
