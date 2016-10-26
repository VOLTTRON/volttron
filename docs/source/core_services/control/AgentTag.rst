.. _AgentTag:

Tagging Agents
==============

Agents can be tagged as they are installed with:

``volttron-ctl install <TAG>=<AGENT_PACKAGE>``

Agents can be tagged after installation with:

``volttron-ctl tag <AGENT_UUID> <TAG>``

Agents can be "tagged" to provide a meaningful user defined way to
reference the agent instead of the uuid or the name. This allows users
to differentiate between instances of agents which use the same codebase
but are configured differently. For instance, the AFDDAgent can be
configured to work against a single HVAC unit and can have any number of
instances running on one platform. A tagging scheme for this could be by
unit: afdd-rtu1, afdd-rtu2, etc.

Commands which operate off an agent's UUID can optionally operate off
the tag by using "--tag ". This can use wildcards to catch multiple
agents at once.
