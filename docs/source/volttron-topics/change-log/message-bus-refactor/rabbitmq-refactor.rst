.. _RabbitMQ-VOLTTRON:

=======================
RabbitMQ Based VOLTTRON
=======================

RabbitMQ VOLTTRON uses the `Pika` library for the RabbitMQ message bus implementation.  To install Pika, it is
recommended to use the VOLTTRON :ref:`bootstrap.py <Platform-Installation>` script:

.. code-block:: bash

    python3 bootstrap.py --rabbitmq


Configuration
=============

To setup a VOLTTRON instance to use the RabbitMQ message bus, we need to first configure VOLTTRON to use the RabbitMQ
message library.  The contents of the RabbitMQ configuration file should follow the pattern below.

Path: `$VOLTTRON_HOME/rabbitmq_config.yml`

.. code-block:: yaml

    #host parameter is mandatory parameter. fully qualified domain name
    host: mymachine.pnl.gov

    # mandatory. certificate data used to create root ca certificate. Each volttron
    # instance must have unique common-name for root ca certificate
    certificate-data:
      country: 'US'
      state: 'Washington'
      location: 'Richland'
      organization: 'PNNL'
      organization-unit: 'VOLTTRON Team'
      # volttron1 has to be replaced with actual instance name of the VOLTTRON
      common-name: 'volttron1_root_ca'
    #
    # optional parameters for single instance setup
    #
    virtual-host: 'volttron' # defaults to volttron

    # use the below four port variables if using custom rabbitmq ports
    # defaults to 5672
    amqp-port: '5672'

    # defaults to 5671
    amqp-port-ssl: '5671'

    # defaults to 15672
    mgmt-port: '15672'

    # defaults to 15671
    mgmt-port-ssl: '15671'

    # defaults to true
    ssl: 'true'

    # defaults to ~/rabbitmq_server/rabbbitmq_server-3.7.7
    rmq-home: "~/rabbitmq_server/rabbitmq_server-3.7.7"

Each VOLTTRON instance resides within a RabbitMQ virtual host.  The name of the virtual host needs to be unique per
VOLTTRON instance if there are multiple virtual instances within a single host/machine.  The hostname needs to be able
to resolve to a valid IP.  The default port of an AMQP port without authentication is `5672` and with authentication
it is `5671`.  The default management HTTP port without authentication is `15672` and with authentication is `15671`.
These needs to be set appropriately if the default ports are not used.

The 'ssl' flag indicates if SSL based authentication is required or not.  If set to `True`, information regarding SSL
certificates needs to be also provided.  SSL based authentication is described in detail in
`Authentication And Authorization With RabbitMQ Message Bus <RabbitMQ-Auth>`_.

To configure the VOLTTRON instance to use RabbitMQ message bus, run the following command:

.. code-block:: bash

    vcfg --rabbitmq single [optional path to rabbitmq_config.yml]

At the end of the setup process, a RabbitMQ broker is setup to use the configuration provided.  A new topic exchange for
the VOLTTRON instance is created within the configured virtual host.

On platform startup, VOLTTRON checks for the type of message bus to be used. If using the RabbitMQ message bus, the
RabbitMQ platform router is instantiated. The RabbitMQ platform router:

* Connects to RabbitMQ broker (with or without authentication)
* Creates a VIP queue and binds itself to the "VOLTTRON" exchange with binding key `<instance-name>.router`.  This
  binding key makes it unique across multiple VOLTTRON instances in a single machine as long as each instance has a
  unique instance name.
* Handles messages intended for router module such as `hello`, `peerlist`, `query` etc.
* Handles "unrouteable" messages - Messages which cannot be routed to any destination agent are captured and an error
  message indicating "Host Unreachable" error is sent back to the caller.
* Disconnects from the broker when the platform shuts down.

When any agent is installed and started, the Agent Core checks for the type of message bus used.  If it is RabbitMQ
message bus then:

* It creates a RabbitMQ user for the agent
* If SSL based authentication is enabled, client certificates for the agent is created
* Connect to the RabbitQM broker with appropriate connection parameters
* Creates a VIP queue and binds itself to the "VOLTTRON" exchange with binding key `<instance-name>.<agent identity>`
* Sends and receives messages using Pika library methods.
* Checks for the type of subsystem in the message packet that it receives and calls the appropriate subsystem message
  handler.
* Disconnects from the broker when the agent stops or platform shuts down.


RPC In RabbitMQ VOLTTRON
========================

The agent functionality remain unchanged regardless of the underlying message bus used, meaning they can continue to use
the same RPC interfaces without any change.

.. image:: files/rpc.png

Consider two agents with VIP identities "agent_a" and "agent_b" connected to VOLTTRON platform
with instance name "volttron1".  Agent A and B each have a VIP queue with binding key volttron1.agent_a"
and "volttron1.agent_b".  Following is the sequence of operation when Agent A wants to make RPC
call to Agent B:

1. Agent A makes a RPC call to Agent B.

.. code-block:: python

   agent_a.vip.rpc.call("agent_b", set_point, "point_name", 2.5)

2. RPC subsystem wraps this call into a VIP message object and sends it to Agent B.
3. The VOLTTRON exchange routes the message to Agent B as the destination routing in the VIP message object matches with
   the binding key of Agent B.
4. Agent Core on Agent B receives the message, unwraps the message to find the subsystem type and calls the RPC
   subsystem handler.
5. RPC subsystem makes the actual RPC call `set_point()` and gets the result.  It then wraps into VIP message object and
   sends it back to the caller.
6. The VOLTTRON exchange routes it to back to Agent A.
7. Agent Core on Agent A calls the RPC subsystem handler which in turn hands over the RPC result to Agent A application.


PUBSUB In RabbitMQ VOLTTRON
===========================

The agent functionality remains unchanged irrespective of the platform using ZeroMQ based pubsub or
RabbitMQ based pubsub, i.e. agents continue to use the same PubSub interfaces and use the same topic
format delimited by “/”.  Since RabbitMQ expects binding key to be delimited by '.', RabbitMQ PUBSUB
internally replaces '/' with ".".  Additionally, all agent topics are converted to
``_pubsub__.<instance_name>.<remainder of topic>`` to differentiate them from the main Agent VIP queue binding.

.. image:: files/pubsub.png

Consider two agents with VIP identities "agent_a" and "agent_b" connected to VOLTTRON platform
with instance name "volttron1". Agent A and B each have a VIP queue with binding key "volttron1.agent_a"
and "volttron1.agent_b".  Following is the sequence of operation when Agent A subscribes to a topic and Agent B
publishes to same the topic:

1. Agent B makes subscribe call for topic "devices".

.. code-block:: python

      agent_b.vip.pubsub.subscribe("pubsub", prefix="devices", callback=self.onmessage)

2. Pubsub subsystem creates binding key from the topic ``__pubsub__.volttron1.devices.#``

3. It creates a queue internally and binds the queue to the VOLTTRON exchange with the above binding key.

4. Agent B is publishing messages with topic: "devices/hvac1".

.. code-block:: python

   agent_b.vip.pubsub.publish("pubsub", topic="devices/hvac1", headers={}, message="foo").

5. PubSub subsystem internally creates a VIP message object and publishes on the VOLTTRON exchange.

6. RabbitMQ broker routes the message to Agent B as routing key in the message matches with the binding key of the topic
   subscription.

7. The pubsub subsystem unwraps the message and calls the appropriate callback method of Agent A.

If agent wants to subscribe to topic from remote instances, it uses:

.. code-block:: python

    agent.vip.subscribe('pubsub', 'devices.hvac1', all_platforms=True)

It is internally set to ``__pubsub__.*.<remainder of topic>``


Further Work
------------

The Pubsub subsystem for the ZeroMQ message bus performs O(N) comparisons where N is the number of unique subscriptions.
The RabbitMQ Topic Exchange was enhanced in version 2.6.0 to reduce the overhead of additional unique subscriptions to
almost nothing in most cases.  We speculate they are using a tree structure to store the binding keys which would reduce
the search time to O(1) in most cases and O(ln) in the worst case.  The VOLTTRON PubSub with ZeroMQ could be updated to
match this performance scalability with some effort.


RabbitMQ Management Tool Integrated Into VOLTTRON
=================================================

Some of the important native RabbitMQ control and management commands are now integrated with the
:ref`volttron-ctl <Platform-Commands>` (vctl) utility.  Using `volttron-ctl`'s RabbitMQ management utility, we can
control and monitor the status of RabbitMQ message bus:

.. code-block:: console

    vctl rabbitmq --help
    usage: vctl command [OPTIONS] ... rabbitmq [-h] [-c FILE] [--debug]
                                                       [-t SECS]
                                                       [--msgdebug MSGDEBUG]
                                                       [--vip-address ZMQADDR]
                                                       ...
    subcommands:

        add-vhost           add a new virtual host
        add-user            Add a new user. User will have admin privileges
                            i.e,configure, read and write
        add-exchange        add a new exchange
        add-queue           add a new queue
        list-vhosts         List virtual hosts
        list-users          List users
        list-user-properties
                            List users
        list-exchanges      add a new user
        list-exchange-properties
                            list exchanges with properties
        list-queues         list all queues
        list-queue-properties
                            list queues with properties
        list-bindings       list all bindings with exchange
        list-federation-parameters
                            list all federation parameters
        list-shovel-parameters
                            list all shovel parameters
        list-policies       list all policies
        remove-vhosts       Remove virtual host/s
        remove-users        Remove virtual user/s
        remove-exchanges    Remove exchange/s
        remove-queues       Remove queue/s
        remove-federation-parameters
                            Remove federation parameter
        remove-shovel-parameters
                            Remove shovel parameter
        remove-policies     Remove policy

For information about using RabbitMQ in multi-platform deployments, view the :ref:`docs
<Multi-platform-RabbitMQ-Deployment>`
