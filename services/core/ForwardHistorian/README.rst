.. _Forward_Historian

=================
Forward Historian
=================

The Forward Historian is used to send data from one instance of VOLTTRON to
another.  This agents primary purpose is to allow the target intance's pubsub
bus to simulate data coming from a real device.  If the target instance
becomes unavailable or one of the "required agents" becomes unavailable then
the cache of this agent will build up until it reaches it's maximum capacity
or the instance and agents come back online.

FAQ /Notes
----------

* By default the Forward Historian adds an X-Forwarded and X-Forwarded-From
header to the forwarded message.

Configuration Options
---------------------

The following JSON configuration file shows all the options currently supported
by the ForwardHistorian agent.  By default an empty config file is used.

.. code-block:: python

    {
        # destination-vip address
        #   Required if the host has not been added to the known-host file.
        #   See vctl auth --help for all intsance security options.
        #
        #   Examples:
        #       "destination-vip": "ipc://@/home/volttron/.volttron/run/vip.socket"
        #       "destination-vip": "tcp://127.0.0.1:22916"
        "destination-vip": "tcp://<ip address>:<port>"

        # destination-serverkey
        #   Required.  The destination instance's publickey.  This can be
        #   retrieved either through the command:
        #       vctl auth serverkey
        #   Or if the web is enabled on the destination through the browser at:
        #       http(s)://hostaddress:port/discovery/
        "destination-serverkey": null,

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
        "capture_device_data": True,

        # capture_analysis_data
        #   This is True by default and allows the Forwarder to forward
        #   data published from the device topic
        "capture_analysis_data": True,

        # capture_log_data
        #   This is True by default and allows the Forwarder to forward
        #   data published from the datalogger topic
        "capture_log_data": True,

        # capture_record_data
        #   This is True by default and allows the Forwarder to forward
        #   data published from the record topic
        "capture_record_data": True,

        # custom_topic_list
        #   Unlike other historians, the forward historian can re-publish from
        #   any topic.  The custom_topic_list is prefixes to subscribe to on
        #   the local bus and forwart to the destination instance.
        "custom_topic_list": [],

        # services_topic_list - Deprecated in favor of specific topic types
        #   Allow the forwarder to only forward specific "known" topic roots
        "services_topic_list": [
            "devices", "analysis", "record", "datalogger", "actuators"
        ],

        # topic_replace_list - Deprecated in favor of retrieving the list of
        #   replacements from the VCP on the current instance.
        "topic_replace_list": [
            #{"from": "FromString", "to": "ToString"}
        ]
    }