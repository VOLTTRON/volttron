.. _federation-plugin:

RabbitMQ Multi-Platform Deployment Using Federation Plugin
==========================================================

Federation pluggin allows us to send and receive messages to/from remote instances with
few simple connection settings. Once a federation link is established to remote instance,
the messages published on the remote instance become available to local instance as if it
were published on the local instance. Before, we illustrate the steps to setup a federation
link, let us start by defining the concept of upstream and downstream server.

**Upstream Server** - The node that is publishing some message of interest

**DownStream Server** - The node that wants to receive messages from the upstream server

A federation link needs to be established from downstream server to the upstream server. The
data flows in single direction from upstream server to downstream server. For bi-directional
data flow we would need to create federation links on both the nodes.

1. Setup two VOLTTRON instances using the instructions at :ref:`RMQ Setup<Setup-RMQ>`. **Please note that each instance should have a unique instance name and should be running on machine/VM that has a unique host name.**

2. In a multi platform setup that need to communicate with each other with RabbitMQ over SSL, each VOLTTRON instance should should trust the ROOT CA of the other instance(RabbitMQ root ca)

   a. Transfer (scp/sftp/similar) voltttron_home/certificates/certs/<instance_name>-root-ca.crt to a temporary
      location on the other volttron instance machine. For example, if you have two instance v1 and v2,
      scp v1's v1-root-ca.crt to v2 and v2-root-ca.crt to v1.

       Note: If using VMs, in order to scp files between VM openssh should be installed and running.

   b. Append the contents of the transferred root ca to the instance's trusted-cas.crt file. Do this on both the instances. Now both
      the instances <instance_name>-trusted-cas.crt will have two certificates.

      For example:

      On v1:
      cat /tmp/v2-root-ca.crt >> VOLTTRON_HOME/certificates/certs/v1-trusted-cas.crt

      On v2:
      cat /tmp/v1-root-ca.crt >> VOLTTRON_HOME/certificates/certs/v2-trusted-cas.crt

3. Stop volttron, stop rabbitmq server and start volttron on both the
instances. This is required only when you update the root certificate and not
required when you add a new shovel/federation between the same hosts

.. code-block:: bash

    ./stop-volttron
    ./stop-rabbitmq
    ./start-volttron

4. Identify upstream servers (publisher nodes) and downstream servers
(collector nodes). To create a RabbitMQ federation, we have to configure
upstream servers on the downstream server and make the VOLTTRON exchange
"federated".

    a.  On the downstream server (collector node)

        .. code-block:: bash

            vcfg --rabbitmq federation [optional path to rabbitmq_federation_config.yml
            containing the details of the upstream hostname, port and vhost.


        Example configuration for federation is available
        in examples/configurations/rabbitmq/rabbitmq_federation_config.yml]


        If no config file is provided, the script will prompt for
        hostname (or IP address), port, and vhost of each upstream node you
        would like to add. Hostname provided should match the hostname in the
        SSL certificate of the upstream server. For bi-directional data flow,
        we will have to run the same script on both the nodes.

    b.  Create a user in the upstream server(publisher) with
        username=<downstream admin user name> (i.e. (instance-name)-admin) and
        provide it access to the  virtual host of the upstream RabbitMQ server. Run
        the below command in the upstream server

        .. code-block:: bash

             volttron-ctl rabbitmq add-user <username> <password>
             Do you want to set READ permission  [Y/n]
             Do you want to set WRITE permission  [Y/n]
             Do you want to set CONFIGURE permission  [Y/n]

5.  Test the federation setup.

   a. On the downstream server run a listener agent which subscribes to messages from all platforms

     - Open the file examples/ListenerAgent/listener/agent.py. Search for @PubSub.subscribe('pubsub', '') and replace that         line with @PubSub.subscribe('pubsub', 'devices', all_platforms=True)
     - updgrade the listener

         .. code-block:: bash

            scripts/core/upgrade-listener


   b. Install master driver, configure fake device on upstream server and start volttron and master driver. vcfg --agent master_driver command can install master driver and setup a fake device.

       .. code-block:: bash

           ./stop-volttron
           vcfg --agent master_driver
           ./start-volttron
           vctl start --tag master_driver


   c. Verify listener agent in downstream VOLTTRON instance is able to receive the messages. downstream volttron instance's volttron.log should display device data scrapped by master driver agent in upstream volttron instance

6. Open ports and https service if needed
   On Redhat based systems ports used by RabbitMQ (defaults to 5671, 15671 for
   SSL, 5672 and 15672 otherwise) might not be open by default. Please
   contact system administrator to get ports opened on the downstream server.

   Following are commands used on centos 7.

   .. code-block:: bash

       sudo firewall-cmd --zone=public --add-port=15671/tcp --permanent
       sudo firewall-cmd --zone=public --add-port=5671/tcp --permanent
       sudo firewall-cmd --reload

7. How to remove federation link

   a. Using the management web interface

      Log into management web interface using downstream server's admin username.
      Navigate to admin tab and then to federation management page. The status of the
      upstream link will be displayed on the page. Click on the upstream link name and
      delete it.

   b. Using "volttron-ctl" command on the upstream server.

       .. code-block:: bash

           vctl rabbitmq list-federation-parameters
           NAME                         URI
           upstream-volttron2-rabbit-2  amqps://rabbit-2:5671/volttron2?cacertfile=/home/nidd494/.volttron1/certificates/certs/volttron1-root-ca.crt&certfile=/home/nidd494/.volttron1/certificates/certs/volttron1-admin.crt&keyfile=/home/nidd494/.volttron1/certificates/private/volttron1-admin.pem&verify=verify_peer&fail_if_no_peer_cert=true&auth_mechanism=external&server_name_indication=rabbit-2

     Grab the upstream link name and run the below command to remove it.

       .. code-block:: bash

         vctl rabbitmq remove-federation-parameters upstream-volttron2-rabbit-2