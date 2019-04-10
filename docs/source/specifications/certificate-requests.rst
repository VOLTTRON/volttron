.. _CertificateRequestsAPISpecification:

=====================================
Certificate Request API Specification
=====================================

Communication between two VOLTTRON instances, for a Rabbit-MQ based instance, must be done through
certificates.  To facility the approval of certificates there will be a web based server api for
requesting, listing, approving and denying certificate requests.  This api will be exposed
via the MasterWebService and will be available to any rabbitmq with ssl enabled.  This api will
be tested and used in the following agents:

- ForwarderAgent
- DataPuller
- VolttronCentralPlatform

For the following document we will assume we have two instances volttron-server and volttron-client.
The volttron-server will be configured to allow certificate requests to be sent to it from the
volttron-client.

.. todo::

    Add sequence diagram between the volttron-server and volttron-client


Configuration
-------------

Both volttron-server and volttron-client must be configured using the standard **reference the setup rabbitmq section**

In addtion the volttron-servers configuration file must have the bind-web-address specified in the
main VOLTTRON instance config file.

volttron-server
::

    [volttron]
    ...

    # The bind-web-address must be https protocol and should use the
    # dns name of the host for where the instance is running.  We use
    # a non-root elevated port that has become semi-standard in this example.
    #
    # note the use of 443 has not been tested.
    bind-web-address = https://volttron:8443

    ...

Background
~~~~~~~~~~

By default the `bind-web-address` parameter will use the `MasterWebService`'s certificate and
private key to reference.  Both are necessary in order to bind the port to the socket for
incoming connections.  The `/etc/hosts` file should be modified in order for the dns name
to be used for the bound address.

Agent Example
-------------

The `auth` subsystem of the volttron architecture is how a `volttron-client` will connect to the
remote platform.

The following is a snippet from the `ForwarderHistorian` using the new function to connect
to a remote instance.

.. note::

    The remote instance could be either zmq or rmq.  The subsystem does its best to determine
    which it protocol it should use to connect.

.. code-block:: python

    ...
    # in the context of an agent this code would either go in a loop until value wasn't
    # None or
    value = self.vip.auth.connect_remote_platform(address,
                                                  serverkey=self.destination_serverkey)



.. todo::

    Add more content here.


Web Server API
--------------

.. todo::

    Document web api

Creating a CSR Request
~~~~~~~~~~~~~~~~~~~~~~

Approving a CSR Request
~~~~~~~~~~~~~~~~~~~~~~~

Denying a CSR Request
~~~~~~~~~~~~~~~~~~~~~

