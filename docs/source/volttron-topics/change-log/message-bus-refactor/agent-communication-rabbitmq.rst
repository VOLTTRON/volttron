.. _Agent-Communication-to-Remote-RabbitMQ:

===============================================
Agent communication to Remote RabbitMQ instance
===============================================

Communication between two RabbitMQ based VOLTTRON instances must be done using SSL certificate based authentication.
Non SSL based authentication will not be supported for communication to remote RabbitMQ based VOLTTRON instances.
An volttron instance that wants to communicate with a remote instance should first request a SSL certificate that is
signed by the remote instance. To facilitate this process there will be a web based server api for requesting, listing,
approving and denying certificate requests.  This api will be exposed via the MasterWebService and will be available
to any RabbitMQ based VOLTTRON instance with ssl enabled.  This api will be tested and used in the following agents:

- ForwarderAgent
- DataPuller
- VolttronCentralPlatform

For the following document we will assume we have two instances a local-instance and remote-volttron-instance.
The remote-volttron-instance will be configured to allow certificate requests to be sent to it from the
local-instance. A remote-agent running in local-instance will attempt to establish a connection to the
remote-volttron-instance


Configuration
-------------

Both volttron-server and volttron-client must be configured for RabbitMQ message bus with SSL using the step described
at :ref:`Installing Volttron <Platform-Installation>`.

In addition the remote-volttron-instance configuration file must have a https bind-web-address specified in the
instance config file. Below is an example config file with bind-web-address. Restart volttron after editing the config
file

.. code-block:: bash

    [volttron]
    message-bus = rmq
    vip-address = tcp://127.0.0.1:22916
    bind-web-address = https://volttron1:8443
    instance-name = volttron1

By default the `bind-web-address` parameter will use the `MasterWebService` agent's certificate and private key.
Both private and public key are necessary in order to bind the port to the socket for incoming connections. This key
pair is auto generated for RabbitMQ based VOLTTRON at the time of platform startup.  Users can provide a different
certificate and private key to be used for the bind-web-address by specifying web-ssl-cert and web-ssl-key in the
config file. Below is an example config file with the additional entries

.. code-block:: bash

    [volttron]
    message-bus = rmq
    vip-address = tcp://127.0.0.1:22916
    bind-web-address = https://volttron1:8443
    instance-name = volttron1
    web-ssl-cert = /path/to/cert/cert.pem
    web-ssl-key = /path/to/cert/key.pem

.. note::

    - The `/etc/hosts` file should be modified in order for the dns name to be used for the bound address.

remote-agent on local-instance
------------------------------

The `auth` subsystem of the volttron architecture is how a remote-agent on local instnace will connect to the remote
volttron instance.

The following is a code snippet from the remote-agent to connect to the remote volttron instance.

.. code-block:: python

    ...
    value = self.vip.auth.connect_remote_platform(address)

The above function call will return an agent that connects to the remote instance only after the request is approved
by an administrator of the remote instance. It is up to the agent to repeat calling `connect_remote_platform`
periodically until an agent object is obtained.


Approving a CSR Request
~~~~~~~~~~~~~~~~~~~~~~~

The following diagram shows the sequence of events when an access request is approved by the administrator of remote
volttron instance. In this case, the volttron-client agent will get a Agent object that is connected to the
remote instance. The diagram shows the client agent repeating the call to connect_remote_platform until the return value
is not None.

|CSR Approval|


Denying a CSR Request
~~~~~~~~~~~~~~~~~~~~~
The following diagram shows the sequence of events when an access request is denied by the administrator. The client
agent repeats the call to connect_remote_platform until the return value is not None. When the remote instance's
administrator denies a access request, the auth subsystem will raise an alert and shutdown the agent.

|CSR Denied|


.. |CSR Approval| image:: files/csr-sequence-approval.png
.. |CSR Denied| image:: files/csr-sequence-deny.png


Follow walk-through in :ref:`Multi-Platform Multi-Bus Walk-through <Multi-Platform-Walk-through>` for setting up
different combinations of multi-bus multi-platform setup using CSR.
