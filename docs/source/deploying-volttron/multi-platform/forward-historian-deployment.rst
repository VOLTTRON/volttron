.. _Forward-Historian-Deployment:

=================
Forward Historian
=================

This guide describes a simple setup where one VOLTTRON instance collects data from a fake device and sends to another
instance. Consider the following scenario:

We have two VOLTTRON instances that are configured with ZMQ, have no agents installed, and are currently running. One VOLTTRON instance will be known as the "source" instance; the other will be known as the "destination" instance.
The "source" instance will run a fake driver that subscribes to values from a fake device; the source instance will then sends those values to the destination instance.


VOLTTRON source instance configuration
--------------------------------------------------------

We will install the ForwardHistorian on the source instance, which will create the connection from the source instance to the destination instance.
The Forward Historian can be found in the *services/core* directory.
The default configuration file is services/core/ForwardHistorian/config.
We will use this configuration file to create the ForwardHistorian agent. However, we need to modify the following fields:

VOLTTRON instance 1 
^^^^^^^^^^^^^^^^^^^

-  ``vctl shutdown –platform`` (if the platform is already working)
-  ``vcfg`` (this helps in configuring the volttron instance
   http://volttron.readthedocs.io/en/releases-4.1/core_services/control/VOLTTRON-Config.html

   -  Specify the IP of the machine: ``tcp://130.20.*.*:22916``
   -  Specify the port you want to use
   -  Specify if you want to run VC(Volttron Central) here or this this instance would be controlled 
      by a VC and the IP and port of the VC

      - Then install agents like Platform Driver Agent with a fake driver for the instance.
      - Install a listener agent so see the topics that are coming from the diver agent
      - Then run the volttron instance by using the following command: ``./start-volttron``

- Volttron authentication: We need to add the IP of the instance 2 in the `auth.config` file of the VOLTTRON agent.
  This is done as follows:

   -  ``vctl auth-add``
   -  We specify the IP of the instance 2 and the credentials of the agent (read
      :ref:`Agent Authentication <Agent-Authentication>`
   -  For specifying authentication for all the agents , we specify ``/.*/``
   -  This should enable authentication for all the volttron-instance based on the IP you specify here
   - 'destination-vip': this should be the IP address and port of the destination instance which will receive data from the ForwardHistorian.
     number.  Example : ``tcp://130.20.*.*:22916``
   - 'destination-serverkey': The server key of the destination instance. The server key can be retrieved in two ways:

       - On the destination instance, run the following command: ``vctl auth serverkey``
       - If web is enabled on the destination instance, open a browser and open the url at 'http(s)://hostaddress:port/discovery/'. For example: ``https://172.28.5.1:8443/discovery/``

With the configuration of ForwardHistorian set, install the ForwardHistorian agent by running the following command:

.. code-block:: bash

    python3 ./scripts/install-agent.py \
    -s ~/<path to volttron code>/services/core/ForwardHistorian \
    -c ~/<path to volttron code>/services/core/ForwardHistorian/config \
    --start


VOLTTRON destination instance configuration
--------------------------------------------------------

The destination instance needs to authenticate the source instance so that it can receive data from the source instance. To authenticate the source instance, we need an add an authentication record
for the source instance by running the following command on the destination instance: ``vctl auth add``. This will open an interactive session that will prompt for input.
Accept the defaults for all fields except for two:

  - 'credentials': this should be the credentials key of the forward historian agent on the source instance; you can get the credentials key by running ``vctl auth list`` on the source instance and looking for the 'credentials' key under the forward historian agent index
  - 'address': this should be the IP address of the source instance

To verify that the source instance authentication was setup, run ``vctl auth list`` on the destination instance to view the authentication record that you just added.


Sending messages from source to destination instance
------------------------------------------------------------


Now that we have setup the ForwardHistorian and thereby establishing connection between the source and destination instances, we can now send data
from the source instance to the destination instance. By default, the Forward Historian will send all messages from the 'devices' topic on the source instance to the destination instance.
In order to setup the 'devices' topic on the source instance, install the Master Driver Agent with a fake driver.

To verify that the destination instance is receiving messages, install a Listener agent on the destination instance. Once installed,
check the logs of the destination instance for data from the source instance's Forward Historian agent.
