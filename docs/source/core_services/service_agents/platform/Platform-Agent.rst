.. _Platform-Agent:

Platform Agent
~~~~~~~~~~~~~~

Introduction
============

The Platform Agent allows communication from a VOLTTRON Central
instance. Each VOLTTRON instance that is to be controlled through the
VOLTTRON Central agent should have one and only one Platform Agent. The
Platform Agent must have the VIP identity of platform.agent.

Configuration
-------------

The minimal configuration (and most likely the only used) for a Platform
Agent is as follows

::

    {
        # Agent id is used in the display on volttron central.
        "agentid": "Platform 1",
    }

The other options for the Platform Agent configuration can be found in
the Platform Agent source directory.
