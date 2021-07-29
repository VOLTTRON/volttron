.. _Troubleshooting-RMQ:

========================
RabbitMQ Troubleshooting
========================


Check the status of the federation connection
---------------------------------------------

.. code-block:: bash

    $RABBITMQ_HOME/sbin/rabbitmqctl eval 'rabbit_federation_status:status().'

If everything is properly configured, then the status is set to `running`.  If not look for the error status.  Some of
the typical errors are:

a. **failed_to_connect_using_provided_uris** - Check if RabbitMQ user is created in downstream server node.  Refer to
   step 3-b of federation setup

b. **unknown ca** - Check if the root CAs are copied to all the nodes correctly.  Refer to step 2 of federation setup

c. **no_suitable_auth_mechanism** - Check if the AMPQ/S ports are correctly configured.


Check the status of the shovel connection
-----------------------------------------

.. code-block:: bash

    RABBITMQ_HOME/sbin/rabbitmqctl eval 'rabbit_shovel_status:status().'

If everything is properly configured, then the status is set to `running`.  If not look for the error status.  Some of
the typical errors are:

a. **failed_to_connect_using_provided_uris** - Check if RabbitMQ user is created in subscriber node.  Refer to step 3-b
   of shovel setup

b. **unknown ca** - Check if the root CAs are copied to remote servers correctly.  Refer to step 2 of shovel setup

c. **no_suitable_auth_mechanism** - Check if the AMPQ/S ports are correctly configured.


Check the RabbitMQ logs for any errors
---------------------------------------

.. code-block:: bash

    tail -f <volttron source dir>/rabbitmq.log


Rabbitmq startup hangs
----------------------

a. Check for errors in the RabbitMQ log. There is a `rabbitmq.log` file in your VOLTTRON source directory that is a
   symbolic link to the RabbitMQ server logs.

b. Check for errors in syslog (`/var/log/syslog` or `/var/log/messages`)

c. If there are no errors in either of the logs, restart the RabbitMQ server in foreground and see if there are any
   errors written on the console.  Once you find the error you can kill the process by entering `Ctl+C`, fix the error
   and start rabbitmq again using ``./start-rabbitmq`` from VOLTTRON source directory.

    .. code-block:: bash

        ./stop-volttron
        ./stop-rabbitmq
        @RABBITMQ_HOME/sbin/rabbitmq-server


SSL trouble shooting
--------------------
There are few things that are essential for SSL certificates to work right.

a. Please use a unique common-name for CA certificate for each VOLTTRON instance.  This is configured under
   `certificate-data` in the `rabbitmq_config.yml` or if no yml file is used while configuring a VOLTTRON single
   instance (using ``vcfg rabbitmq single``).  Certificate generated for agent will automatically get agent's VIP
   identity as the certificate's common-name

b. The host name in the SSL certificate should match hostname used to access the server.  For example, if the fully
   qualified domain name was configured in the `certificate-data`, you should use the fully qualified domain name to
   access RabbitMQ's management url.

c. Check if your system time is correct especially if you are running virtual machines.  If the system clock is not
   right, it could lead to SSL certificate errors


DataMover troubleshooting
-------------------------

If output from `volttron.log` is not as expected check for  ``{'alert_key': 'historian_not_publishing'}`` in the callee
node's `volttron.log`.  Most likely cause is the historian is not running properly or credentials between caller and
callee nodes was not set properly.
