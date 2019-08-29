.. RMQ-Backward-Compatability:

Backward Compatibility With ZeroMQ Message Based VOLTTRON
=========================================================

RabbitMQ VOLTTRON supports backward compatibility with ZeroMQ based VOLTTRON. RabbitMQ VOLTTRON has a ZeroMQ router running internally to accept incoming ZeroMQ connections and to route ZeroMQ messages coming in/going out of it's instance. There are multiple ways for an instance with a RabbitMQ message bus, and an instance with ZeroMQ message bus to connect with each other. For example, an agent from one instance can directly connect to the remote instance to publish or pull data from it. Another way is through multi-platform communication, where the VOLTTRON platform is responsible for connecting to the remote instance. For more information on multi-platform communication, see https://volttron.readthedocs.io/en/develop/core_services/multiplatform/Multiplatform-Communication.html.


Agent Connecting Directly to Remote Instance
--------------------------------------------

The following steps are to demonstrate how RabbitMQ VOLTTRON is backward compatible with ZeroMQ VOLTTRON, using the Forward Historian as an example. This example shows how to forward messages from local ZeroMQ based VOLTTRON to remote RabbitMQ based VOLTTRON instance. Similar steps can be followed if you needed to move messages from local RabbiMQ based VOLTTRON to ZeroMQ based VOLTTRON.

1. In order for RabbitMQ and ZeroMQ VOLTTRONs to communicate with each other, one needs two instances of VOLTTRON_HOME on the same VM. To create a new instance of VOLTTRON_HOME use the command.

   ``export VOLTTRON_HOME=~/.new_volttron_home``

   It is recommended that one uses multiple terminals to keep track of both instances.

2. Start VOLTTRON on both instances. Note: since the start-volttron script uses the volttron.log by default, the second instance will need be started manually in the background, using a separate log. For example:

   ``volttron -vv -l volttron-two.log&``

3. Modify the configuration file for both instances. The config file is located at ``$VOLTTRON_HOME/config``

   For RabbitMQ VOLTTRON, the config file should look similar to:

  .. code-block:: bash

    [volttron]
    message-bus = rmq
    vip-address = tcp://127.0.0.1:22916
    instance-name = volttron_rmq

  The ZeroMQ config file should look similar, with all references to RMQ being replaced with ZMQ, and a different vip-address
  (e.g. tcp://127.0.0.2:22916).

4. On the instance running ZeroMQ:

   a. Install the Forward Historian agent using an upgrade script similar to:

     .. code-block:: python

       #!/bin/bash
       export CONFIG=$(mktemp /tmp/abc-script.XXXXXX)
       cat > $CONFIG <<EOL
       {
           "destination-vip": "tcp://127.0.0.1:22916",
           "destination-serverkey": "key"
       }
       EOL
       python /home/username/volttron/scripts/install-agent.py -c $CONFIG -s services/core/ForwardHistorian --start --force -i forward.historian
       # Finally remove the temporary config file
       rm $CONFIG


     Since we are attempting to push data from the local (ZeroMQ in this example) to the remote (RabbitMQ) instance, the we
     would need the RabbitMQ serverkey, which can be obtained by running ``vctl auth serverkey`` on the RabbitMQ instance.

     Start the Forward Historian.

   b. Install master driver, configure fake device on upstream server and start volttron and master driver. vcfg --agent
      master_driver command can install master driver and setup a fake device.

     .. code-block:: bash

       ./stop-volttron
       vcfg --agent master_driver
       ./start-volttron
       vctl start --tag master_driver

5. On the instance running RabbitMQ:

   a. Run a listener agent which subscribes to messages from all platforms

     - Open the file examples/ListenerAgent/listener/agent.py. Search for @PubSub.subscribe('pubsub', '') and replace that
       line with @PubSub.subscribe('pubsub', 'devices', all_platforms=True)
     - updgrade the listener

     .. code-block:: bash

        scripts/core/upgrade-listener


   b. Provide the RabbitMQ instance with the public key of the Forward Historian running on ZeroMQ instance.

      Run ``vctl auth public key`` on the ZeroMQ instance. Copy the output and add the public key to the RabbitMQ instance's
      auth.config file, using the defaults except for the user_id and credentials.

     .. code-block:: bash

      vctl auth add
      domain []:
      address []:
      user_id []: forward
      capabilities (delimit multiple entries with comma) []:
      roles (delimit multiple entries with comma) []:
      groups (delimit multiple entries with comma) []:
      mechanism [CURVE]:
      credentials []: key
      comments []:
      enabled [True]:


      Once that is completed you should be able to see data similar to below in the log of the volttron instance running RabbitMQ:

     .. code-block:: bash

           2018-12-31 14:48:10,043 (listeneragent-3.2 7175) listener.agent INFO: Peer: pubsub, Sender: forward.historian:, Bus: , Topic: devices/fake-campus/fake-building/fake-device/all, Headers: {'X-Forwarded': True, 'SynchronizedTimeStamp': '2018-12-31T19:48:10.000000+00:00', 'TimeStamp': '2018-12-31T19:48:10.001966+00:00', 'max_compatible_version': u'', 'min_compatible_version': '3.0', 'Date': '2018-12-31T19:48:10.001966+00:00'}, Message:
       [{'Heartbeat': True, 'PowerState': 0, 'ValveState': 0, 'temperature': 50.0},
        {'Heartbeat': {'type': 'integer', 'tz': 'US/Pacific', 'units': 'On/Off'},
         'PowerState': {'type': 'integer', 'tz': 'US/Pacific', 'units': '1/0'},
         'ValveState': {'type': 'integer', 'tz': 'US/Pacific', 'units': '1/0'},
         'temperature': {'type': 'integer',
                         'tz': 'US/Pacific',
                         'units': 'Fahrenheit'}}]

Multi-Platform Connection
-------------------------

The below example demonstrates backward compatibility using multi-platform connection method.

1. Refer to steps 1 -3 in the previous section for configuring two VOLTTRON instances (one with RabbitMQ and one with ZeroMQ).
   For step 3, the VOLTTRON config files need to account for a web-server, which is necessary for multi-platform communication.
   As such, the config files should look similar to the following:

  .. code-block:: bash

   [volttron]
   message-bus = rmq
   vip-address = tcp://127.0.0.1:22916
   instance-name = volttron_rmq
   bind-web-address = http://127.0.0.1:8080

2. Create an external_address.json file in the VOLTTRON_HOME directory for both instances, with the IP address and port of the
   remote instance(s) it will need to connect to. In this example, the RabbitMQ would have the address of the ZeroMQ instance,
   and vice versa. Below is an example for one instance:

  .. code-block:: json

   [
      "http://127.0.0.2:8080"
   ]

3. On the instance running ZeroMQ:

   a. Install the DataMover agent using an upgrade script similar to:


    .. code-block:: python

     #!/bin/bash
     export CONFIG=$(mktemp /tmp/abc-script.XXXXXX)
     cat > $CONFIG <<EOL
     {
        "destination-vip": "tcp://127.0.0.1:22916",
        "destination-serverkey": "rmq server key",
        "destination-instance-name": "volttron_rmq",
        "destination-message-bus": "zmq"
     }
     EOL
     python /home/osboxes/volttron/scripts/install-agent.py -c $CONFIG -s services/core/DataMover --start --force -i data.mover
     # Finally remove the temporary config file
     rm $CONFIG


    Replace "rmq server key" with the RabbitMQ server key.

    In this example the DataMover will be running on the ZeroMQ instance, which means that the destination vip, serverkey, and
    instance name are configured to the RabbitMQ instance. However, destination-message-bus should be set to zmq. Start
    DataMover agent.

   b. Install master driver, configure fake device on upstream server and start volttron and master driver. 'vcfg --agent
      master_driver' command can install master driver and setup a fake device.

    .. code-block:: python

     ./stop-volttron
     vcfg --agent master_driver
     ./start-volttron
     vctl start --tag master_driver

4. On the instance running RabbitMQ:

    a. Start SQLHistorian. Easiest way to accomplish this is to stop VOLTTRON, reconfigure to have RabbitMQ message bus and
       install platform.historian already installed, and start VOLTTRON again.

     .. code-block:: bash

       ./stop-volttron
        vcfg --agent platform_historian
        ./start-volttron
        vctl start --tag platform_historian

    b.  Run a listener agent which subscribes to messages from all platforms

       - Open the file examples/ListenerAgent/listener/agent.py. Search for @PubSub.subscribe('pubsub', '') and replace that
         line with @PubSub.subscribe('pubsub', 'devices', all_platforms=True)
       - updgrade the listener

        .. code-block:: bash

         scripts/core/upgrade-listener

    c. Provide the RabbitMQ instance with the public key of the DataMover running on ZeroMQ instance.

       Run ``vctl auth public key`` on the ZeroMQ instance. Copy the output and add the public key to the RabbitMQ instance's
       auth.config file, using the defaults except for the user_id and credentials.

        .. code-block:: bash

         vctl auth add
         domain []:
         address []:
         user_id []: forward
         capabilities (delimit multiple entries with comma) []:
         roles (delimit multiple entries with comma) []:
         groups (delimit multiple entries with comma) []:
         mechanism [CURVE]:
         credentials []: key
         comments []:
         enabled [True]:


5. Stop VOLTTRON on both instances, and restart using setup mode.

  .. code-block:: bash

   volttron -vv -l volttron.log --setup-mode&


  If you tail the logs of both instances, there should be a message indicating that starting with setup mode was complete upon
  success.

  After a successful start, a new file called external_platform_discovery.json should be located in the $VOLTTRON_HOME
  directory of both instances. The file will contain the platform discovery information ( ), of all external platforms the
  respective VOLTTRON instance is aware of. The file will look something like:

  .. code-block:: bash

   {"<platform1 name>": {"vip-address":"tcp://<ip1>:<vip port1>",
                     "instance-name":"<platform1 nam>",
                     "serverkey":"<serverkey1>"
                     },
    "<platform2 name>": {"vip-address":"tcp://<ip2>:<vip port2>",
                     "instance-name":"<platform2 name>",
                     "serverkey":"<serverkey2>"
                     },
    "<platform3 name>": {"vip-address":"tcp://<ip3>:<vip port3>",
                     "instance-name":"<platform3 name>",
                     "serverkey":"<serverkey3>"
                     },
    ......
   }


Additionally for different combinations of multi-bus, multi-platform setup, please refer to :ref:`Multi-Platform Multi-Bus Walk-through <_Multi_Platform_Walkthrough>`