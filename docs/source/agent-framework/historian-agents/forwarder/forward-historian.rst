.. _Forward-Historian:

=================
Forward Historian
=================

The primary use case for the Forward Historian or Forwarder is to send data to another instance of VOLTTRON as if the
data were live. This allows agents running on a more secure and/or more powerful machine to run analysis on data being
collected on a potentially less secure/powerful board.

Given this use case, it is not optimized for batching large amounts of data when "live-ness" is not needed.  For this
use case, please see the :ref:`Data Mover Historian <Data-Mover-Historian>`.

The Forward Historian can be found in the `services/core directory`.

Forward Historian can be used to forward data between two ZMQ instances, two RMQ instances, or between ZMQ and
RMQ instances. For Forward Historian to establish a successful connection to the destination VOLTTRON instance:

    1. forward historian should be configured to connect and authenticate the destination instance, and
    2. the remote instance should be configured to accept incoming connection from the forward historian

How we setup the above two depends on the message bus used in source instance and destination instance

***************************************************************************
Setup for two ZMQ VOLTTRON instance or a ZMQ and RabbitMQ VOLTTRON instance
***************************************************************************

When forwarder is used between two ZeroMQ instances it relies on the CurveMQ authentication mechanism used by ZMQ
based VOLTTRON. When the communication is between a ZeroMQ and RabbitMQ instance, the forward historian uses the
proxy ZMQ router agent on the RabbitMQ instance and hence once again uses the CurveMQ authentication

.. seealso::

    For more details about VIP authentication in ZMQ based VOLTTRON refer to :ref:`VIP Authentication<VIP-Authentication>`


Configuring Forwarder Agent
===========================

At a minimum, a forward historian's configuration should contain enough details to connect to and authenticate the
remote destination.  For this it needs

  1. the destination's :term:`VIP address` (`destination-vip`)
  2. the public key of the destination server (`destination-serverkey`)

There are two ways to provide these information

Minimum configuration: Option 1
-------------------------------

Provide the needed information in the configuration file. For example

.. code-block:: json

    {
        "destination-vip": "tcp://172.18.0.4:22916"
        "destination-serverkey": "D3tIAPOFf7wS3787FgEOLjoPfXUT9rAGpv80ryloZGE"
    }

The destination server key can be found by running the following command on the **destination volttron instance**:

.. code-block:: bash

    vctl auth serverkey


.. note::

    The example above uses the local IP address, the IP address for your configuration should match the intended target

An example configuration with above parameters is available at  `services/core/ForwardHistorian/config`.

.. _config_option_2:

Minimum configuration: Option 2
-------------------------------

If the destination volttron instance is web enabled then the forward historian can find the destination's vip address
and public key using the destination's web discovery page. All web enabled volttron instances provide a
**<instance's web address>/discovery/** page that provides the following server information
    1. server key
    2. vip address
    3. instance name
    4. RabbitMQ server's AMQP address (Only on RabbitMQ instances)
    5. RabbitMQ server's CA cert (Only on RabbitMQ instances)

To forward data to a web enabled volttron instance, forwarder can configured with the destination's web address
instead of destination's vip address and public key. For example

.. code-block:: json

    {
        "destination-address": "https://centvolttron2:8443"
    }

An example configuration with above parameters is available at  `services/core/ForwardHistorian/config_web_address`.

Optional Configurations
-----------------------

The most common use case for a forwarder is to forward data collected on a local instance to a remote historian. Due to
this forward historian by default forwards the default topics a historian subscribes to - devices, analysis, log, and record.
Forward historian can be configured to forward any custom topic or disable forwarding devices, analysis, log and/or
record topic data. For example

.. code-block:: json

    {
        "destination-address": "https://centvolttron2:8443",
        "custom_topic_list": ["heartbeat"],
        "capture_log_data": false
    }

See `Configuration Options <../../../volttron-api/services/ForwardHistorian/README.html#configuration-options>`_ for all
available forward historian configuration

Since forward historian extends BaseHistorian all BaseHistorian's configuration can be added to forwarder. Please see
`BaseHistorian Configurations <../../../agent-framework/historian-agents/historian-framework.html#configuration>`_ for the list
of available BaseHistorian configurations

Installation
------------

Once we have our configuration file ready we can install the forwarder agent using the command

.. code-block:: bash

    vctl install --agent-config <path to config file> services/core/ForwardHistorian

But before we start the agent we should configure the destination volttron instance to accept the connection from the
forwarder.

Configuring destination volttron instance
=========================================

When a forwarder tries to connect to a destination volttron instance, the destination instance will check the ip address
of the source and public key of connecting agent against its list of accepted peers. So before forwarder can connect to the
destination instance, we should add these two details to the destination's auth.json file.

To do this we can use the command

.. code-block:: bash

    vctl auth add --address <address of source instance where forwarder is installed> --credentials <publickey of installed forwarder agent>

Only the address and credential keys are mandatory. You can add additional fields such as comments or user id for reference.
In the above command address is the ip address of the source instance in which the forwarder is installed. Credentials
is the public key of the installed forwarder agent. You can get the forwarder agent's public key by running the following
command on the **source instance**

.. code-block:: bash

    vctl auth publickey <agent uuid or name>

.. seealso::

    For more details about VIP authentication in ZMQ based VOLTTRON refer to :ref:`VIP Authentication<VIP-Authentication>`

*****************************************
Setup for two RabbitMQ VOLTTRON instances
*****************************************

RabbitMQ based VOLTTRON instances use x509 certificate based authentication. A forward historian that forwards data from
one RMQ instance to another RMQ instance would need a x509 certificate that is signed by the destination volttron instance's
root certificate for authentication. To obtain a signed certificate, on start, the forward historian creates a certificate
signing request (CSR) and sends it to destination's instance for approval. An admin on the destination end, needs to
login into the admin web interface and approve the request. On approval a certificate signed by the destination CA is
returned to the forward historian and the forward historian can use this certificate for communication.

.. seealso::

    For more details about CSR approval process see
    :ref:`Agent communication to Remote RabbitMQ instance <Agent-Communication-to-Remote-RabbitMQ>`
    For an example CSR approval process see
    :ref:`VOLTTRON Central Multi-Platform Multi-Bus Demo <Multi-Platform-Multi-Bus>`

Forwarder Configuration
=======================

Since destination instance would have web enabled to approve the incoming CSR requests, forward historian can be configured
with just the destination instance web address similar to ref:`Minimum configuration: Option 2<config_option_2>`

.. code-block:: json

    {
        "destination-address": "https://centvolttron2:8443"
    }

On start, the forwarder makes Certificate signing request and retries periodically till the certificate is approved.

*************************
Testing Forward Historian
*************************

Once forward historian is configured and installed and the destination is configured to accept incoming connection from
the forwarder (either by adding to destination's auth.json as in the case of ZMQ or after CSR is approved in case of RMQ)
forwarder can forward any message published to the configured set of topics and re-publish on the destination's messagebus.

Testing with custom topic
=========================

1. Configure Forward historian to forward the topic heartbeat by adding the following to the forward historian's
   configuration

   .. code-block:: json

    "custom_topic_list": ["heartbeat"],

2. If forwarder is not already running start the forwarder agent. If it is already running the configuration change
   should get picked up automatically in a few seconds.

3. If there are no other agent in the source volttron instance, install a listener agent that periodically publishes to
   the topic 'heartbeat'

   .. code-block:: bash

    vctl install examples/ListenerAgent


   .. note::

    As of VOLTTRON 8.0, all agents by default publish a heartbeat message periodically unless the agent explicitly
    opted out of it. So if you already have other installed agents that publish heartbeat message you don't have to add the
    listener agent

4. On the destination instance install a listener agent and tail the volttron log file. You should be able to see the
   listener or any other source agent's heartbeat message on the destination volttron's log file

Testing with default topics
===========================

Forward historian by default forwards the default topics a historian subscribes to - devices, analysis, log, and record.
On the source instance, we can install a platform driver and configure it with a fake device to publish data to the devices
topic. Once the platform driver is started and data gets published to the devices topic, forwarder can re-publish these
to the destination message bus

1. Configure and install forward historian as explained in the sections above

2. Configure destination to accept incoming connection as explained in the above sections

3. Shutdown source volttron instance

   .. code-block:: bash

    vctl shutdown --platform

4. On source install platform driver using the below vcfg command. When prompted, choose to configure a fake device for
   the platform driver

   .. code-block:: bash

    vcfg --agent platform_driver

   Below is an example command with prompts

   .. code-block:: bash

    (volttron) [volttron@centvolttron1 myvolttron]$ vcfg --agent platform_driver

    Your VOLTTRON_HOME currently set to: /home/volttron/vhomes/rmq_instance1

    Is this the volttron you are attempting to setup? [Y]:
    Configuring /home/volttron/git/myvolttron/services/core/PlatformDriverAgent.
    ['volttron', '-vv', '-l', '/home/volttron/vhomes/rmq_instance1/volttron.cfg.log']
    Would you like to install a fake device on the platform driver? [N]: y
    Should the agent autostart? [N]: n

5. Start source volttron instance

   .. code-block:: bash

    ./start-volttron

6. Start platform driver and forwarder on source volttron instance
7. On the destination volttron instance install a listener agent and tail the volttron log. You should see the devices
   data periodically getting logged in the destination volttron instance.
