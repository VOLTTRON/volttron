.. _VOLTTRON-Central-Agent:

=====================
VOLTTRON Central (VC)
=====================

The VC Agent is responsible for controlling multiple VOLTTRON instances through a single interfaces.
The VOLTTRON instances can be either local or remote. VC leverages an internal VOLTTRON web server providing a
interface to our JSON-RPC based web API.  Both the web api and the interface are served through the VC agent.

Instance Configuration
======================

In order for any web agent to be enabled, there must be a port configured to serve the content. The easiest way to do
this is to create a config file in the root of your VOLTTRON_HOME directory (to do this automatically see
:ref:`VOLTTRON Config <VOLTTRON-Config>`.)

The following is an example of the configuration file

::

    [volttron]
    instance-name = volttron1
    message-bus = rmq
    vip-addres = tcp://127.0.0.1:22916
    bind-web-address = https://localhost:8443
    volttron-central-address = https://localhost:8443


.. Note:

    The above configuration will open a discoverable port for the volttron instance.  In addition, the opening of this
    web address allows you to serve both static as well as dynamic pages.

Verify that the instance is serving properly by pointing your web browser to ``https://localhost:8443/index.html``


Agent Execution
===============

To setup an instance of VC, it is recommended to follow one of the following guides depending on your use case.
For a single instance, please consult the :ref:`VOLTTRON Central Demo <VOLTTRON-Central-Deployment>`.
For controlling multiple instances with different message busses, consider the
:ref:`VOLTTRON Central Multi-Platform Multi-Bus Demo <Multi-Platform-Multi-Bus>`.

However, if you already have an instance of VOLTTRON configured that you wish to make an instance of VOLTTRON Central.
you may install and start it as follows:

.. code-block:: bash

    # Arguments are package to execute, config file to use, tag to use as reference
    ./scripts/core/pack_install.sh services/core/VolttronCentral services/core/VolttronCentral/config vc

    # Start the agent
    vctl start --tag vc

