.. _shovel-plugin:

RabbitMQ Multi-Platform Deployment Using Shovel Plugin
======================================================

In RabbitMQ based VOLTTRON, forwarder and data mover agents will be replaced by shovels
to send or receive remote pubsub messages.
Shovel behaves like a well written client application that connects to its source
( can be local or remote ) and destination ( can be local or remote instance ),
reads and writes messages, and copes with connection failures. In case of shovel, apart
from configuring the hostname, port and virtual host of the remote instance, we will
also have to provide list of topics that we want to forward to remote instance. Shovels
can also be used for remote RPC communication in which case we would have to create shovel
in both the instances, one to send the RPC request and other to send the response back.

Pubsub Communication
~~~~~~~~~~~~~~~~~~~~

1. Setup two VOLTTRON instances using the steps described in installation section.
Please note that each instance should have a unique instance name.

2. In a multi platform setup that need to communicate with each other with
   RabbitMQ over SSL, each VOLTTRON instance should should trust the ROOT CA of
   the other instance(RabbitMQ root ca)

   a.  Transfer (scp/sftp/similar)
       voltttron_home/certificates/certs/<instance_name>-root-ca.crt to a temporary
       location on the other volttron instance machine. For example, if you have two
       instance v1 and v2, scp v1's v1-root-ca.crt to v2 and
       v2-root-ca.crt to v1.

   b. Append the contents of the transferred root ca to the instance's root ca.

      For example:

      On v1

       cat /tmp/v2-root-ca.crt >> VOLTTRON_HOME/certificates/v1-root-ca.crt

      On v2

       cat /tmp/v1-root-ca.crt >> VOLTTRON_HOME/certificates/v2-root-ca.crt

3. Identify the instance that is going to act as the "publisher" instance. Suppose
   "v1" instance is the "publisher" instance and "v2" instance is the "subscriber"
   instance. Then we need to create a shovel on "v1" to forward messages matching
   certain topics to remote instance "v2".

    a.  On the publisher node,

        .. code-block:: bash

            vcfg --rabbitmq shovel [optional path to rabbitmq_shovel_config.yml]

        rabbitmq_shovel_config.yml should contain the details of the remote hostname, port, vhost
        and list of topics to forward. Example configuration for shovel is available
        in examples/configurations/rabbitmq/rabbitmq_shovel_config.yml


        For this example, let's set the topic to "devices"

        If no config file is provided, the script will prompt for
        hostname (or IP address), port, vhost and list of topics for each
        remote instance you would like to add. For
        bi-directional data flow, we will have to run the same script on both the nodes.

    b.  Create a user in the subscriber node with username set to publisher instance's
        agent name ( (instance-name)-PublisherAgent ) and allow the shovel access to
        the virtual host of the subscriber node.

        .. code-block:: bash

            cd $RABBITMQ_HOME
            vctl add-user <username> <password>

4. Test the shovel setup.

   a. Start VOLTTRON on publisher and subscriber nodes.

   b. On the publisher node, start a master driver agent that publishes messages related to
   a fake device. ( Easiest way is to run volttron-cfg command and follow the steps )

   c. On the subscriber node, run a listener agent which subscribes to messages
   from all platforms (set @PubSub.subscribe('pubsub', 'devices', all_platforms=True)
   instead of @PubSub.subscribe('pubsub', '') )

   d. Verify listener agent in subscriber node is able to receive the messages
   matching "devices" topic.

5. How to remove the shovel setup.

   a. Using the management web interface

      Log into management web interface using publisher instance's admin username.
      Navigate to admin tab and then to shovel management page. The status of the
      shovel will be displayed on the page. Click on the shovel name and delete the shovel.

   b. Using "volttron-ctl" command on the publisher node.

    .. code-block:: bash

     vctl rabbitmq list-shovel-parameters
     NAME                     SOURCE ADDRESS                                                 DESTINATION ADDRESS                                            BINDING KEY
     shovel-rabbit-3-devices  amqps://rabbit-1:5671/volttron1?cacertfile=/home/nidd494/.volttron1/certificates/certs/volttron1-root-ca.crt&certfile=/home/nidd494/.volttron1/certificates/certs/volttron1-admin.crt&keyfile=/home/nidd494/.volttron1/certificates/private/volttron1-admin.pem&verify=verify_peer&fail_if_no_peer_cert=true&auth_mechanism=external&server_name_indication=rabbit-1  amqps://rabbit-3:5671/volttron3?cacertfile=/home/nidd494/.volttron1/certificates/certs/volttron1-root-ca.crt&certfile=/home/nidd494/.volttron1/certificates/certs/volttron1-admin.crt&keyfile=/home/nidd494/.volttron1/certificates/private/volttron1-admin.pem&verify=verify_peer&fail_if_no_peer_cert=true&auth_mechanism=external&server_name_indication=rabbit-3  __pubsub__.volttron1.devices.#


    Grab the shovel name and run the below command to remove it.

    .. code-block:: bash

        vctl rabbitmq remove-shovel-parameters shovel-rabbit-3-devices

RPC Communication
~~~~~~~~~~~~~~~~~
Following are the steps to create Shovel for multi-platform RPC communication.

1. Setup two VOLTTRON instances using the steps described in installation section.
   Please note that each instance should have a unique instance name.

2. In a multi platform setup that need to communicate with each other with
   RabbitMQ over SSL, each VOLTTRON instance should should trust the ROOT CA of
   the other instance(RabbitMQ root ca)

    a. Transfer (scp/sftp/similar)
       voltttron_home/certificates/certs/<instance_name>-root-ca.crt to a temporary
       location on the other volttron instance machine. For example, if you have two
       instance v1 and v2, scp v1's v1-root-ca.crt to v2 and
       v2-root-ca.crt to v1.

    b. Append the contents of the transferred root ca to the instance's root ca.
       For example:

       On v1

        cat /tmp/v2-root-ca.crt >> VOLTTRON_HOME/certificates/v1-root-ca.crt

      On v2

        cat /tmp/v1-root-ca.crt >> VOLTTRON_HOME/certificates/v2-root-ca.crt

3. Typically RPC communication is 2 way communication so we will to setup shovel in both the VOLTTRON instances. In RPC calls
   there are two instances of shovel. One serving as the caller (makes RPC request) and the other acting as a callee (replies
   to RPC request). Identify the instance is the "caller" and which is the "callee." Suppose "v1" instance is the "caller"
   instance and "v2" instance is the "callee" instance.

   a. On both the caller and callee nodes, shovel instances need to be created. In this example, v1’s shovel would forward the
      RPC call request from an agent on v1 to v2 and similarly v2’s shovel will forward the RPC reply from agent on v2
      back to v1.

       .. code-block:: bash

        vcfg --rabbitmq shovel [optional path to rabbitmq_shovel_config.yml]

    rabbitmq_shovel_config.yml should contain the details of the
    **remote** hostname, port, vhost, volttron instance name (so in v1's yml file parameters would point to v2
    and vice versa), and list of agent pair identities (local caller, remote callee). Example configuration for shovel
    is available in examples/configurations/rabbitmq/rabbitmq_shovel_config.yml.

    For this example, let's say that we are using the schedule-example and acutator agents.

    For v1, the agent pair identities would be:

     - [Scheduler, platform.actuator]

    For v2, they would be:

     - [platform.actuator, Scheduler]

    Indicating the flow from local agent to remote agent.

   b. On the caller node create a user with username set to callee instance's agent name ( (instance-name)-RPCCallee ) and
      allow the  shovel access to the virtual host of the callee node. Similarly, on the callee node, create a user with
      username set to caller instance's agent name ( (instance-name)-RPCCaller ) and allow the shovel access to the virtual
      host of the caller node.

       .. code-block:: bash

        cd $RABBITMQ_HOME
        vctl add-user <username> <password>


4. Test the shovel setup

   a. **On caller node**:

      Make necessary changes to RPC methods of  caller agent.

      For this example, in volttron/examples/SchedulerExample/schedule_example/agent.py:

     * Search for 'campus/building/unit' in publish_schedule method. Replace with
       'devices/fake-campus/fake-building/fake-device'
     * Search for ['campus/building/unit3',start,end] in the use_rpc method, replace with:

       msg = ['fake-campus/fake-building/fake-device',start,end].
     * Add: kwargs = {"external_platform": 'v2'} on the line below
     * On the result = self.vip.rpc.call method below, replace "msg).get(timeout=10)" with:

       .. code-block:: bash

         msg, **kwargs).get(timeout=10),

     * In the second try clause of the use_rpc method:
     * Replace result['result'] with result[0]['result']
     * Add kwargs = {"external_platform": 'v2'} as the first line of the if statement
     * Replace 'campus/building/unit3/some_point' with 'fake-campus/fake-building/fake-device/PowerState'
     * Below 'fake-campus/fake-building/fake-device/PowerState' add: 0,
     * Replace

       .. code-block:: bash

        '0.0').get(timeout=10) with **kwargs).get(timeout=10)


    Next, install an example scheduler agent and start it:

    .. code-block:: bash

       #!/bin/bash
       python /home/username/volttron/scripts/install-agent.py -c /home/username/volttron/examples/SchedulerExample/schedule-example.agent -s examples/SchedulerExample --start --force -i Scheduler


   b. **On the callee node:**

    - Run upgrade script to install actuator agent.

      .. code-block:: bash

        #!/bin/bash
        python /home/username/volttron/scripts/install-agent.py -s services/core/ActuatorAgent --start --force -i platform.actuator


    - Run the upgrade script to install the listener agent.

      .. code-block:: bash

       scripts/core/upgrade-listener



    - Install master driver, configure fake device on upstream callee and start volttron and master driver.
      vcfg --agent master_driver command can install master driver and setup a fake device.

     .. code-block:: bash

        ./stop-volttron
        vcfg --agent master_driver
        ./start-volttron
        vctl start --tag master_driver


   -  Start actuator agent and listener agents.

    The output for the callee node with a successful shovel run should look similar to:

    .. code-block:: bash

       2018-12-19 15:38:00,009 (listeneragent-3.2 13039) listener.agent INFO: Peer: pubsub, Sender: platform.driver:, Bus: , Topic: devices/fake-campus/fake-building/fake-device/all, Headers: {'Date': '2018-12-19T20:38:00.001684+00:00', 'TimeStamp': '2018-12-19T20:38:00.001684+00:00', 'min_compatible_version': '5.0', 'max_compatible_version': u'', 'SynchronizedTimeStamp': '2018-12-19T20:38:00.000000+00:00'}, Message:
        [{'Heartbeat': True, 'PowerState': 0, 'ValveState': 0, 'temperature': 50.0},
         {'Heartbeat': {'type': 'integer', 'tz': 'US/Pacific', 'units': 'On/Off'},
          'PowerState': {'type': 'integer', 'tz': 'US/Pacific', 'units': '1/0'},
          'ValveState': {'type': 'integer', 'tz': 'US/Pacific', 'units': '1/0'},
          'temperature': {'type': 'integer',
                          'tz': 'US/Pacific',
                          'units': 'Fahrenheit'}}]



DataMover Communication
~~~~~~~~~~~~~~~~~~~~~~~

The DataMover historian running on one instance makes RPC call to platform historian running on remote
instance to store data on remote instance. Platform historian agent returns response back to DataMover
agent. For such a request-response behavior, shovels need to be created on both instances.

1. Please ensure that preliminary steps for multi-platform communication are completed (namely,
   steps 1-3 described above) .

2. To setup a data mover to send messages from local instance (say v1) to remote instance (say v2)
   and back, we would need to setup shovels on both instances.

   Example of RabbitMQ shovel configuration on v1

   .. code-block:: json

      shovel:
      # hostname of remote machine
       rabbit-2:
        port: 5671
        rpc:
          # Remote instance name
          v2:
          # List of pair of agent identities (local caller, remote callee)
          - [data.mover, platform.historian]
        virtual-host: v1

   This says that DataMover agent on v1 wants to make RPC call to platform historian on v2.

  .. code-block:: bash

    vcfg --rabbitmq shovel [optional path to rabbitmq_shovel_config.yml


   Example of RabbitMQ shovel configuration on v2

  .. code-block:: json

   shovel:
    # hostname of remote machine
    rabbit-1:
      port: 5671
      rpc:
      # Remote instance name
      v1:
      # List of pair of agent identities (local caller, remote callee)
      - [platform.historian, data.mover]
    virtual-host: v2

   This says that Hplatform historian on v2 wants to make RPC call to DataMover agent on v1.

   a. On v1, run below command to setup a shovel from v1 to v2.

  .. code-block:: bash

     vcfg --rabbitmq shovel [optional path to rabbitmq_shovel_config.yml

   b. Create a user on v2 with username set to remote agent's username
      ( for example, v1.data.mover i.e., <instance_name>.<agent_identity>) and allow
      the shovel access to the virtual host of v2.

  .. code-block:: bash

      cd $RABBITMQ_HOME
      vctl add-user <username> <password>

   c. On v2, run below command to setup a shovel from v2 to v1

  .. code-block:: bash

      vcfg --rabbitmq shovel [optional path to rabbitmq_shovel_config.yml

   d. Create a user on v1 with username set to remote agent's username
     ( for example, v2.patform.historian i.e., <instance_name>.<agent_identity>) and allow
     the shovel access to the virtual host of the v1.

  .. code-block:: bash

      cd $RABBITMQ_HOME
      vctl add-user <username> <password>

3. Start Master driver agent on v1

   .. code-block:: bash

       ./stop-volttron
       vcfg --agent master_driver
       ./start-volttron
       vctl start --tag master_driver

4. Install DataMover agent on v1. Contents of the install script can look like below.

   .. code-block:: bash

       #!/bin/bash
       export CONFIG=$(mktemp /tmp/abc-script.XXXXXX)
       cat > $CONFIG <<EOL
       {
           "destination-vip": "",
           "destination-serverkey": "",
           "destination-instance-name": "volttron2",
           "destination-message-bus": "rmq"
       }
       EOL
       python scripts/install-agent.py -s services/core/DataMover -c $CONFIG --start --force -i data.mover

    Execute the install script.

5. Start platform historian of your choice on v2. Example shows starting SQLiteHistorian

   .. code-block:: bash

       ./stop-volttron
       vcfg --agent platform_historian
       ./start-volttron
       vctl start --tag platform_historian

6. Observe data getting stored in sqlite historian on v2.
