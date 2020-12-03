.. _Multi-platform-RabbitMQ-Deployment:

==================================
Multi-platform RabbitMQ Deployment
==================================

With ZeroMQ based VOLTTRON, multi-platform communication was accomplished in three different ways:

#. Direct connection to remote instance - Write an agent that would connect to a remote instance directly.

#. Special agents - Use special agents such as forward historian/data puller agents that would forward/receive messages
   to/from remote instances.  In RabbitMQ-VOLTTRON, we make use of the :ref:`Shovel Plugin <RabbitMQ-Shovel>` to achieve
   this behavior.

#. Multi-Platform RPC and PubSub - Configure :term:`VIP` address of all remote instances that an instance has to connect
   to it's `$VOLTTRON_HOME/external_discovery.json` and let the router module in each instance manage the connection
   and take care of the message routing for us.  In RabbitMQ-VOLTTRON, we make use of the
   :ref:`Federation Plugin <RabbitMQ-Federation>` to achieve this behavior.


Using the Federation Plugin
---------------------------

We can connect multiple VOLTTRON instances using the federation plugin. Before setting up federation links, we need to
first identify the  upstream server and downstream server.  The upstream server is the node that is publishing some
message of interest and downstream server is the node that wants to receive messages from the upstream server.  A
federation link needs to be established from the downstream VOLTTRON instance to the upstream VOLTTRON instance.  To
setup a federation link, we will need to add upstream server information in a RabbitMQ federation configuration file:

Path: `$VOLTTRON_HOME/rabbitmq_federation_config.yml`

.. code-block:: yaml

    # Mandatory parameters for federation setup
    federation-upstream:
      rabbit-4:
        port: '5671'
        virtual-host: volttron4
      rabbit-5:
        port: '5671'
        virtual-host: volttron5

To configure the VOLTTRON instance to setup federation, run the following command:

.. code-block:: bash

    vcfg --rabbitmq federation [optional path to rabbitmq_federation_config.yml]

This will setup federation links to upstream servers and sets policy to make the VOLTTRON exchange *federated*.  Once a
federation link is established to remote instance, the messages published on the remote instance become available to
local instance as if it were published on the local instance.

For detailed instructions to setup federation, please refer to the
:ref:`platform installation docs <Platform-Installation>`.


Multi-Platform RPC With Federation
----------------------------------

For multi-platform RPC communication, federation links need to be established on both the VOLTTRON
nodes.  Once the federation links are established, RPC communication becomes fairly simple.

.. image:: files/multiplatform_rpc.png

Consider Agent A on VOLTTRON instance "volttron1" on host "host_A" wants to make RPC call to Agent B
on VOLTTRON instance "volttron2" on host "host_B".

1. Agent A makes RPC call.

.. code-block:: Python

    kwargs = {"external_platform": self.destination_instance_name}
    agent_a.vip.rpc.call("agent_b", set_point, "point_name", 2.5, \**kwargs)

2. The message is transferred over federation link to VOLTTRON instance "volttron2" as both the exchanges are made
   *federated*.

3. The RPC subsystem of Agent B calls the actual RPC method and gets the result.  It encapsulates the message result
   into a VIP message object and sends it back to Agent A on VOLTTRON instance "volttron1".

4. The RPC subsystem on Agent A receives the message result and gives it to the Agent A application.


Multi-Platform PubSub With Federation
-------------------------------------

For multi-platform PubSub communication, it is sufficient to have federation link from the downstream server
to the upstream server.  In case of bi-directional data flow, links have to established in both the directions.

.. image:: files/multiplatform_pubsub.png

Consider Agent B on VOLTTRON instance "volttron2" on host "host_B" which wants to subscribe to messages from
VOLTTRON instance "volttron2" on host "host_B".  First, a federation link needs to be established from
"volttron2" to "volttron1".

1. Agent B makes a subscribe call:

.. code-block:: python

    agent_b.vip.subscribe.call("pubsub", prefix="devices", all_platforms=True)

2. The PubSub subsystem converts the prefix to ``__pubsub__.*.devices.#``. Here, "*" indicates that agent is subscribing
   to the "devices" topic from all VOLTTRON platforms.

3. A new queue is created and bound to VOLTTRON exchange with the above binding key.  Since the VOLTTRON exchange is a
   *federated exchange*, any subscribed message on the upstream server becomes available on the federated exchange and
   Agent B will be able to receive it.

4. Agent A publishes message to topic `devices/pnnl/isb1/hvac1`

5. The PubSub subsystem publishes this message on it's VOLTTRON exchange.

6. Due to the federation link, message is received by the Pubsub subsystem of Agent A.


Using the Shovel Plugin
-----------------------

Shovels act as well written client applications which move messages from a source to a destination broker.
The below configuration shows how to setup a shovel to forward PubSub messages or perform multi-platform RPC
communication from local to a remote instance.  It expects `hostname`, `port` and `virtual host` configuration values
for the remote instance.

Path: `$VOLTTRON_HOME/rabbitmq_shovel_config.yml`

.. code-block:: yaml

    # Mandatory parameters for shovel setup
    shovel:
      rabbit-2:
        port: '5671'
        virtual-host: volttron
        # Configuration to forward pubsub topics
        pubsub:
          # Identity of agent that is publishing the topic
          platform.driver:
            - devices
        # Configuration to make remote RPC calls
        rpc:
          # Remote instance name
          volttron2:
            # List of pair of agent identities (local caller, remote callee)
            - [scheduler, platform.actuator]

To forward PubSub messages, the topic and agent identity of the publisher agent is needed.  To perform RPC, the instance
name of the remote instance and agent identities of the local agent and remote agent are needed.

To configure the VOLTTRON instance to setup shovel, run the following command.

.. code-block:: bash

    vcfg --rabbitmq shovel [optional path to rabbitmq_shovel_config.yml]

This setups up a shovel that forwards messages (either PubSub or RPC) from local exchange to remote exchange.


Multi-Platform PubSub With Shovel
---------------------------------

After the shovel link is established for Pubsub, the below figure shows how the communication happens.

.. note::

   For bi-directional pubsub communication, shovel links need to be created on both the nodes.  The "blue" arrows show
   the shovel binding key.  The pubsub topic configuration in `$VOLTTRON_HOME/rabbitmq_shovel_config.yml` gets
   internally converted to the shovel binding key: `"__pubsub__.<local instance name>.<actual topic>"`.

.. image:: files/multiplatform_shovel_pubsub.png

Now consider a case where shovels are setup in both the directions for forwarding "devices" topic.

1. Agent B makes a subscribe call to receive messages with topic "devices" from all connected platforms.

.. code-block:: python

    agent_b.vip.subscribe.call("pubsub", prefix="devices", all_platforms=True)

2. The PubSub subsystem converts the prefix to ``__pubsub__.*.devices.#``  "*" indicates that agent is subscribing to
   the "devices" topic from all the VOLTTRON platforms.

3. A new queue is created and bound to VOLTTRON exchange with above binding key.

4. Agent A publishes message to topic `devices/pnnl/isb1/hvac1`

5. PubSub subsystem publishes this message on it's VOLTTRON exchange.

6. Due to a shovel link from VOLTTRON instance "volttron1" to "volttron2", the message is forwarded from VOLTTRON
   exchange "volttron1" to "volttron2" and is picked up by Agent A on "volttron2".


Multi-Platform RPC With Shovel
------------------------------

After the shovel link is established for multi-platform RPC, the below figure shows how the RPC communication happens.

.. note::

    It is mandatory to have shovel links on both directions as it is request-response type of communication.  We will
    need to set the agent identities for caller and callee in the `$VOLTTRON_HOME/rabbitmq_shovel_config.yml`.  The
    "blue" arrows show the resulting the shovel binding key.

.. image:: files/multiplatform_shovel_rpc.png

Consider Agent A on VOLTTRON instance "volttron1" on host "host_A" wants to make RPC call on Agent B
on VOLTTRON instance "volttron2" on host "host_B".

1. Agent A makes RPC call:

.. code-block:: Python

    kwargs = {"external_platform": self.destination_instance_name}
    agent_a.vip.rpc.call("agent_b", set_point, "point_name", 2.5, \**kwargs)

2. The message is transferred over shovel link to VOLTTRON instance "volttron2".

3. The RPC subsystem of Agent B calls the actual RPC method and gets the result.  It encapsulates the message result
   into a VIP message object and sends it back to Agent A on VOLTTRON instance "volttron1".

4. The RPC subsystem on Agent A receives the message result and gives it to Agent A's application.


.. _RabbitMQ-Multi-platform-SSL:

Multi-Platform Communication With RabbitMQ SSL
==============================================

For multi-platform communication over federation and shovel, we need the connecting instances to trust each other.

.. image:: files/multiplatform_ssl.png

Suppose there are two VMs (VOLTTRON1 and VOLTTRON2) running single instances of RabbitMQ, and VOLTTRON1 and VOLTTRON2
want to talk to each other via either the federation or shovel plugins.  In order for VOLTTRON1 to talk to VOLTTRON2,
VOLTTRON1's root certificate must be appended to VOLTTRON's trusted CA certificate, so that when VOLTTRON1 presents it's
root certificate during connection, VOLTTRON2's RabbitMQ server can trust the connection.  VOLTTRON2's root CA must be
appended to VOLTTRON1's root CA and it must in turn present its root certificate during connection, so that VOLTTRON1
will know it is safe to talk to VOLTTRON2.

Agents trying to connect to remote instance directly need to have a public certificate signed by the remote instance for
authenticated SSL based connection.  To facilitate this process, the VOLTTRON platform exposes a web based server API
for requesting, listing, approving and denying certificate requests.  For more detailed description, refer to
:ref:`Agent communication to Remote RabbitMQ instance <Agent-Communication-to-Remote-RabbitMQ>`
