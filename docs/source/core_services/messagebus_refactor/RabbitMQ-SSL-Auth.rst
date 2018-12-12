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

However, suppose there are two VMs (v1 amd v2) running single instances of RabbitMQ, and v1 wants to talk to v2. In
order for this to occur, one would have to transfer (scp/sftp/similar) v1-root.ca.crt from v1 to v2 and append the
transferred v1-root.ca.crt to v2-trusted-ca.crt:

For example:

On v1: cat /tmp/rmq2-root-ca.crt >> /home/vdev/ .my_volttron_home/certificates/v1-trusted-cas.crt

On v2: cat /tmp/rmq1-root-ca.crt >> /home/vdev/ .my_volttron_home/certificates/v2-trusted-cas.crt


For more detailed information about SSL based authentication control, please refer to
RabbitMQ documentation `TLS Support <https://www.rabbitmq.com/ssl.html>`_.

Authorization in RabbitMQ VOLTTRON
==================================
For more detailed information about access control, please refer to RabbitMQ documentation
`Access Control <https://www.rabbitmq.com/access-control.html>`_.
