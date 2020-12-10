.. _Forward-Historian-Deployment:

=================
Forward Historian
=================

This guide describes a simple setup where one VOLTTRON instance collects data from a fake devices and sends to another
instance .  Lets consider the following example.

We are going to create two VOLTTRON instances and send data from one VOLTTRON instance running a fake driver(subscribing
values from a fake device) and sending the values to the second VOLTTRON instance.


VOLTTRON instance 1 forwards data to VOLTTRON instance 2
--------------------------------------------------------


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


For this documentation, the topics from the driver agent will be send to the instance 2
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

-  We use the existing agent called the Forward Historian for this purpose which is available in service/core in the
   VOLTTRON directory.
-  In the config file under the Forward Historian directory, we modify the following fields:

   - Destination-vip: the IP of the volttron instance to which we have to forward the data to along with the port
     number.  Example : ``tcp://130.20.*.*:22916``
   - Destination-serverkey: The server key of the VOLTTRON instance to which we need to forward the data to.
     This can be obtained at the VOLTTRON instance by typing ``vctl auth serverkey``

-  Service_topic_list: specify the topics you want to forward specifically instead of all the values.
-  Once the above values are set, your forwarder is all set .
-  You can create a script file for the same and execute the agent.


VOLTTRON instance 2
^^^^^^^^^^^^^^^^^^^

-  ``vctl shutdown –platform`` (if the platform is already working)
-  ``volttron-cfg`` (this helps in configuring the volttron instance)
   http://volttron.readthedocs.io/en/releases-4.1/core_services/control/VOLTTRON-Config.html

   -  Specify the IP of the machine : ``tcp://130.20.*.*:22916``
   -  Specify the port you want to use.
   -  Install the listener agent (this will show the connection from instance 1 if its successful 
      and then show all the topics from instance 1.

-  Volttron authentication: We need to add the IP of the instance 1 in the auth.config file of the VOLTTRON agent . This
   is done as follows:

   -  ``vctl auth-add``
   -  We specify the IP of the instance 1 and the credentials of the agent
   -  For specifying authentication for all the agents , we specify ``/.*/``
   -  This should enable authentication for all the volttron-instance based on the IP you specify here 


Listener Agent
^^^^^^^^^^^^^^

Run the listener agent on this instance to see the values being forwarded from instance 1.  Once the above setup is
done, you should be able to see the values from instance 1 on the listener agent of instance 2.
