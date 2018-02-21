.. _Forward_Historian

=================
Forward Historian
=================

The Forward Historian is used to send data from one instance of VOLTTRON to
another.  This agents primary purpose is to allow the target instance's pubsub
bus to simulate data coming from a real device.  If the target instance
becomes unavailable or one of the "required agents" becomes unavailable then
the cache of this agent will build up until it reaches it's maximum capacity
or the instance and agents come back online.

The Forward Historian now uses the configuration store for storing its
configurations. This allows dynamic updating of configuration without having
to rebuild the agent.

FAQ /Notes
----------

* By default the Forward Historian adds an X-Forwarded and X-Forwarded-From
header to the forwarded message.  The X-Forwarded-From uses the instance-name
of the platform (ip address:port by default).

Configuration Options
---------------------

The following JSON configuration file shows all the options currently supported
by the ForwardHistorian agent.

.. code-block:: python

    {
        # destination-serverkey
        #   The destination instance's publickey. Required if the
        #   destination-vip-address has not been added to the known-host file.
        #   See vctl auth --help for all instance security options.
        #
        #   This can be retrieved either through the command:
        #       vctl auth serverkey
        #   Or if the web is enabled on the destination through the browser at:
        #       http(s)://hostaddress:port/discovery/
        "destination-serverkey": null,

        # destination-vip-address - REQUIRED
        #   Address of the target platform.
        #   Examples:
        #       "destination-vip": "ipc://@/home/volttron/.volttron/run/vip.socket"
        #       "destination-vip": "tcp://127.0.0.1:22916"
        "destination-vip": "tcp://<ip address>:<port>"

        # required_target_agents
        #   Allows checking on the remote instance to verify peer identtites
        #   are connected before publishing.
        #
        #   Example:
        #       Require the platform.historian agent to be present on the
        #       destination instance before publishing.
        #       "required_target_agent" ["platform.historian"]
        "required_target_agents": [],

        # capture_device_data
        #   This is True by default and allows the Forwarder to forward
        #   data published from the device topic
        "capture_device_data": true,

        # capture_analysis_data
        #   This is True by default and allows the Forwarder to forward
        #   data published from the device topic
        "capture_analysis_data": true,

        # capture_log_data
        #   This is True by default and allows the Forwarder to forward
        #   data published from the datalogger topic
        "capture_log_data": true,

        # capture_record_data
        #   This is True by default and allows the Forwarder to forward
        #   data published from the record topic
        "capture_record_data": true,

        # custom_topic_list
        #   Unlike other historians, the forward historian can re-publish from
        #   any topic.  The custom_topic_list is prefixes to subscribe to on
        #   the local bus and forward to the destination instance.
        "custom_topic_list": ["actuator", "alert"],

        # cache_only
        #   Allows one to put the forward historian in a cache only mode so that
        #   data is backed up while doing operations on the destination
        #   instance.
        #
        #   Setting this to true will start cache to backup and not attempt
        #   to publish to the destination instance.
        "cache_only": false,

        # topic_replace_list - Deprecated in favor of retrieving the list of
        #   replacements from the VCP on the current instance.
        "topic_replace_list": [
            #{"from": "FromString", "to": "ToString"}
        ],

        # Publish a message to the log after a certain number of "successful"
        # publishes.  To disable the message to not print anything set the
        # count to 0.
        #
        # Note "successful" means that it was removed from the backup cache.
        "message_publish_count": 10000

    }
