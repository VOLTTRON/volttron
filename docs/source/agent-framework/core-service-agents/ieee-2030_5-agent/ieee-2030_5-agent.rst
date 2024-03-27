.. _IEEE-2030_5-Agent:

===========================
IEEE 2030.5 EndDevice Agent
===========================

The IEEE 2030.5 Agent (IEEE_2030_5 in the VOLTTRON repository) acts as an IEEE 2030.5 EndDevice (client). This
agent establishes a secure connection to a TLS-enabled 2030.5 server and discovers its capabilities. It verifies
the server's identity based on the Registration function set and uses the FunctionSetAssignments function set to
determine the appropriate DERProgram to run. The agent regularly checks for changes in default controls and
active DERControls and responds accordingly. It also listens to one or more subscriptions to the VOLTTRON message
bus for information (points) to POST/PUT to the 2030.5 server.

You can access the agent code, README, and demo from `IEEE_2030_5 Agent <https://github.com/VOLTTRON/volttron/tree/develop/services/core/IEEE_2030_5/>`_.

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Common Smart Inverter Profile (CSIP)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This agent is not a fully compliant CSIP client, meaning it does not support all of the function sets
within the CSIP Profile of 2030.5.  It provides the following function sets:

- End Device
- Time
- Distributed Energy Resources
- Metering
- Metering Mirror

As time goes on it is likely that this list will be extended through user supported additions and project needs.

################
2030.5 Reference
################

`IEEE 2030.5 Standards <https://standards.ieee.org/ieee/2030.5/5897/>`_
`IEEE_2030_5 Agent <https://github.com/VOLTTRON/volttron/tree/develop/services/core/IEEE_2030_5/>`_
