.. _VIP-Known-Identities:

====================
VIP Known Identities
====================

It is critical for systems to have known locations for receiving resources and services from in a networked environment.
The following table details the vip identities that are reserved for VOLTTRON specific usage.

.. csv-table:: Known Identities
    :header: "VIP Identity","Agent/Feature","Notes"

    "platform","",""
    "platform.agent","Platform Agent","Used to allow the VolttronCentralAgent to control and individual platform"
    "platform.auth","Platform Auth","The identity of VolttronCentralAgent"
    "volttron.central","VOLTTRON Central","The identity of VolttronCentralAgent"
    "platform.historian","User-Selected Historian","An individual platform may have many historians available to it, however this is one available through Volttron Central. Note that this does not require a specific type of historian, just that it's :term:`VIP Identity`"
    "platform.topic_watcher","TopicWatcher","Agent which publishes alerts for topics based on timing thresholds"
    "platform.sysmon","Sysmon","Agent which publishes System Monitoring statistics"
    "platform.emailer","Emailer","Agent used by other agents on the platform to send email notifications"
    "platform.health","Platform Health","Agent health service"
    "platform.market","Market Services","The default identity for Market Service agents"
    "control","Platform Control","Control service facilitates the starting, stopping, removal, and installation of the agents on an instance.  This agent is executing within the main volttron process"
    "control.connection","Platform Control","Short lived identity used by all of the volttron-ctl (`vctl`) commands"
    "pubsub","Pub/Sub Router","Pub/Sub subsystem router. Allows backward compatibility with version 4.1"
    "master_web","Platform Web Service","Facilitates HTTP/HTTPS requests from browsers and routes them to the corresponding agent for processing (will be renamed to platform.web in future update)"
    "keydiscovery","Server Key Discovery","Agent that enables discovery of server keys of remote platforms in a multi-platform setup"
    "platform.actuator","Actuator","Agent which coordinates sending control commands to devices"
    "config.store","Configuration Store","The configuration subsystem service agent on the platform.  Includes scheduling"
    "platform.driver","Master Driver","The default identity for the Master Driver Agent (will be renamed Platform Driver Agent) which is responsible for coordinating device communication"
    "zmq.proxy.router","Zero MQ Proxy","ZeroMQ's proxy service for Pub/Sub subsystem router.  Allows backward compatibility between rmq and zmq instances of VOLTTRON"
