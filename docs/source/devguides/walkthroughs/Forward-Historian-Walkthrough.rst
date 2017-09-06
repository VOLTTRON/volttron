.. _Forward-Historian-Walkthrough:

Forward Historian Walkthrough
=============================

This guide describes a simple setup where one VOLTTRON instance collects
data from a fake devices and sends to another instance . Lets consider the
following example.

We are going to create two VOLTTRON instances and send data from one VOLTTRON 
instance running a fake driver(subscribing values from a fake device)and sending
the values to the second VOLTTRON instance.

VOLTTRON instance 1 forwards data to VOLTTRON instance 2
--------------------------------------------------------

VOLTTRON INSTANCE 1 
~~~~~~~~~~~~~~~~~~~
- ``volttron-ctl shutdown --platform`` (If VOLTTRON is already running it must be shut down before running ``volttron-cfg``).
- ``volttron-cfg`` - this helps in configuring the VOLTTRON instance(:ref:`VOLTTRON Config <VOLTTRON-Config>`).

  - Specify the IP of the machine : ``tcp://127.0.0.1:22916``.
  - Specify the port you want to use.
  - Specify if you want to run VC ( VOLTTRON Central) here or this this instance would be controlled by a VC and the IP and port of the VC.
- Then start the VOLTTRON instance by : ``volttron -vv & > volttron.log&``.
- Then install agents like Master driver Agent with fake driver agent for the instance.
- Install a listener agent so see the topics that are coming from the diver agent.
- VOLTTRON authentication : We need to add the IP of the instance 1 in the auth.config file of the VOLTTRON agent .This is done as follow :

  - ``volttron-ctl auth-add``
  - We specify the IP of the instance 1 and the credentials of the agent.(:ref:`Agent authentication walkthrough <AgentAuthentication>`)
  - For specifying authentication for all the agents , we specify ``/.*/`` for credentials as shown in :ref:`Agent Development<Agent_Development>`.
  - This should enable authentication for all the VOLTTRON instances based on the IP you specify here .

For this documentation, the topics from the driver agent will be sent to the instance 2
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
- We use the existing agent called the Forward Historian for this purpose which is available in ``service/core`` in the VOLTTRON directory.
- In the config file under the ForwardHistorian directory , we modify the following field:

  - destination-vip : the IP of the VOLTTRON instance to which we have to forward the data to along with the port number . Example : ``tcp://130.20.*.*:22916``.
  - destination-serverkey: The server key of the VOLTTRON instance to which we need to forward the data to. This can be obtained at the VOLTTRON instance by typing ``volttron-ctl auth serverkey``.
  - service_topic_list: specify the topics you want to forward specifically instead of all the values.
- Once the above values are set, your forwarder is all set .
- You can create a script file for the same and execute the agent.

VOLTTRON INSTANCE 2
~~~~~~~~~~~~~~~~~~~

- ``volttron-ctl shutdown --platform`` (If VOLTTRON is already running it must be shut down before running ``volttron-cfg``).
- ``volttron-cfg`` - this helps in configuring the VOLTTRON instance.(:ref:`VOLTTRON Config <VOLTTRON-Config>`)
  - Specify the IP of the machine : ``tcp://127.0.0.1:22916``.
  - Specify the port you want to use.
  - Install the listener agent (this will show the connection from instance 1 if its successful and then show all the topics from instance 1.
- Then start the VOLTTRON instance by : ``volttron -vv & > volttron.log&``.
- VOLTTRON authentication : We need to add the IP of the instance 1 in the auth.config file of the VOLTTRON agent .This is done as follow :

  - ``volttron-ctl auth-add``
  - We specify the IP of the instance 1 and the credentials of the agent.(:ref:`Agent authentication walkthrough <AgentAuthentication>`)
  - For specifying authentication for all the agents , we specify ``/.*/`` for credentials as shown in :ref:`Agent Development<Agent_Development>`.
  - This should enable authentication for all the VOLTTRON instances based on the IP you specify here .

LISTENER AGENT

- Run the listener agent on this instance to see the values being forwarded from instance 1.

Once the above setup is done, you should be able to see the values from instance 1 on the listener agent of instance 2.


