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
When each agent is started for the first time with the RMQ message bus, the agent will have a new public - private key
pair created for them, where the certificate is the public key. This certificate will be signed by the volttron
instance's root CA.


When one creates a single instance of RabbitMQ using the command ``vcfg --rabbitmq single`, the following is created /
re-created from rabbitmq.conf:

- Public and private Certificate Authority (CA) files

- Public (automatically signed by the CA) and private server certificates

- Admin certificate for the RabbitMQ instance

The public files can be found at ``/home/vdev/ .my_volttron_home/certificates/certs`` and the private files can be found
at ``/home/vdev/ .my_volttron_home/certificates/private``

There is also a trusted-cas.crt file that is only created once, but can be updated.
Initially, the trusted-ca.crt is a copy of the the CA file <rmq-instance-name>-root-ca.crt.

.. image:: files/multiplatform_ssl.png

However, suppose there are two VMs (VOLTTRON1 and VOLTTRON2) running single instances of RabbitMQ, and VOLTTRON1 and VOLTTRON2 want to talk to each other via either the federation or shovel plugins. In order for VOLTTRON1 to talk to VOLTTRON2, VOLTTRON1 must present it's root certificate, and have it appended to VOLTTRON2's trusted ca. VOLTTRON2 must in turn present its root certificate to VOLTTRON1's trusted ca, so that VOLTTRON1 will know it is safe to talk to VOLTTRON2. 



For more detailed information about SSL based authentication control, please refer to
RabbitMQ documentation `TLS Support <https://www.rabbitmq.com/ssl.html>`_.

Authorization in RabbitMQ VOLTTRON
==================================
For more detailed information about access control, please refer to RabbitMQ documentation
`Access Control <https://www.rabbitmq.com/access-control.html>`_.
