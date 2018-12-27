.. _RabbitMQ-Auth:
==========================================================
Authentication And Authorization With RabbitMQ Message Bus
==========================================================


Authentication In RabbitMQ VOLTTRON
***********************************
RabbitMQ VOLTTRON uses SSL based authentication, rather than the default username and password authentication. You can
see this by running the command:

``cat ~/rabbitmq_server/rabbitmq_server-3.7.7/etc/rabbitmq/rabbitmq.conf``

Note that auth_mechanisms.1 is set to EXTERNAL.

SSL uses the `Public Key Infrastructure <https://en.wikipedia.org/wiki/Public_key_infrastructure>`_ where public and
private certificates are used to construct / verify ones digital identity.

SSL in RabbitMQ VOLTTRON
------------------------
When one creates a single instance of RabbitMQ using the command ``vcfg --rabbitmq single``, the following is created /
re-created from rabbitmq.conf:

- Public and private Certificate Authority (CA) files

- Public (automatically signed by the CA) and private server certificates

- Admin certificate for the RabbitMQ instance

The public files can be found at ``VOLTTRON_HOME/certificates/certs`` and the private files can be found
at ``/VOLTTRON_HOME/certificates/private``

There is also a trusted-cas.crt file that is only created once, but can be updated.
Initially, the trusted-ca.crt is a copy of the the CA file <rmq-instance-name>-root-ca.crt, but as more agents and more instances of the RabbitMQServer are added to the trusted certificate, this changes.

When each agent is started for the first time with the RMQ message bus, the agent will have a new public - private key
pair created for them, where the certificate is the public key. This certificate will be signed by the volttron
instance's RootCA.

.. image:: files/rmq_server_ssl_certs.png

In order to interact with the RabbitMQ server, each agent must present its certificate and private key (since this is in one instance of the VOLTTRON platform). Since the agents public certificate has been signed by the ROOTCA, it is trusted and can interact with the RABBITMQ server in scenarios such as interacting with agents on another RabbitMQ server via federation or shovel. 

.. image:: files/multiplatform_ssl.png

Suppose there are two VMs (VOLTTRON1 and VOLTTRON2) running single instances of RabbitMQ, and VOLTTRON1 and VOLTTRON2 want to talk to each other via either the federation or shovel plugins. In order for VOLTTRON1 to talk to VOLTTRON2, VOLTTRON1 must present it's root certificate, and have it appended to VOLTTRON2's trusted ca. VOLTTRON2 must in turn present its root certificate to VOLTTRON1's trusted ca, so that VOLTTRON1 will know it is safe to talk to VOLTTRON2. 

For more detailed information about SSL based authentication control, please refer to
RabbitMQ documentation `TLS Support <https://www.rabbitmq.com/ssl.html>`_.

Authorization in RabbitMQ VOLTTRON
==================================
To be implemented in VOLTTRON

For more detailed information about access control, please refer to RabbitMQ documentation
`Access Control <https://www.rabbitmq.com/access-control.html>`_.
