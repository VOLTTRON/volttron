.. _VOLTTRON-Central-Platform-Agent:

===============================
VOLTTRON Central Platform Agent
===============================

The Platform Agent allows communication from a VOLTTRON Central instance.  Each VOLTTRON instance that is to be
controlled through the VOLTTRON Central agent should have one and only one Platform Agent.  The Platform Agent must have
the VIP identity of `platform.agent` which is specified by default by VOLTTRON
:ref:`known identities <VIP-Known-Identities>`.


Configuration
-------------

The minimal configuration (and most likely the only used) for a Platform Agent is as follows:

::

    {
        # Agent id is used in the display on volttron central.
        "agentid": "Platform 1",
    }
