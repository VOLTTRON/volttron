.. _VOLTTRON-Security:

=================
Platform Security
=================

There are various security-related topics throughout VOLTTRON's documentation.  This is a quick roadmap for finding
security documentation.

A core component of VOLTTRON is its :ref:`message bus<Message-Bus>`.  The security of this message bus is
crucial to the entire system.  The :ref:`VOLTTRON Interconnect Protocol<VIP-Overview>` provides communication over the
message bus.

VIP was built with security in mind from the ground up.  VIP uses encrypted channels and enforces agent
:ref:`authentication<VIP-Authentication>` by default for all network communication. VIP's
:ref:`authorization<VIP-Authorization>` mechanism allows system  administrators to limit agent capabilities with fine
granularity.

Even with these security mechanisms built into VOLTTRON, it is important for system administrators to
:ref:`harden VOLTTRON's underlying OS <Linux-System-Hardening>`.

The VOLTTRON team has engaged with PNNL's Secure Software Central team to create a threat profile document.  You can
read about the threat assessment findings and how the VOLTTRON team is addressing them here: `SSC Threat Profile
<https://volttron.org/sites/default/files/publications/VolttronThreatProfile_v1.1.pdf>`_

Additional documentation related to VIP authentication and authorization is available here:

.. toctree::

   protecting-pubsub-topics
   running-agent-as-user
   key-stores
   known-hosts-file
