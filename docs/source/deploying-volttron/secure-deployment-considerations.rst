.. _Secure-Deployment-Considerations:

=====================================
Security Considerations of Deployment
=====================================

Security of computing systems is a complex topic which depends not only on the
security of each component, but on how software components interact and on the
environment in which they are running.
In the subsections here, we will discuss a variety of possible actions which
may increase the security of a particular deployment, along with their context.

For more examples and discussion, see the `Publications section of the VOLTTRON website
<https://volttron.org/publications>`_ where there are a number of Threat Profile reports.

Running as a Managed System Process
===================================

It is possible that the running VOLTTRON process could exit undesirably (either due
to a bug, or some malicious action).
For scenarios where not having the VOLTTRON process running presents a business
risk, it is recommended to follow the :ref:`system service setup`
to leverage the host system's process monitoring and management system.
Under this configuration, the system will be configured to restart VOLTTRON in the
event that it fails.

.. note::

    For this configuration to be effective, it is important that the platfrom
    is configured such that it automatically starts up in the desired state.
    In particular, review the installed agents and be sure that agents which
    should be running are "enabled" and that their priorities are set such
    that they start in the intended order.

There are scenarios when this configuration may not be desired:

1. If a system restarts cleanly after an unexpected failure, it is possible that
   the underlying issue could go unnoticed (and therefore unresolved). This would
   happen if a user checks the system and sees it is running but does not have a
   way to realize that there has been one or more restarts. For development systems
   it may be desirable to not restart, leaving the system in a failed state which
   is more likely to be noticed as unusual, and with the failure details still present
   in the recent logs. Consider the relative value of platform up-time and failure
   this kind of failure discovery. If both are highly valuable, it may be possible
   to add extra notifications to the process monitoring system (systemd, initd, or
   other) so that records are retained while service is restored.
2. For development systems, or systems that are frequently stopped or restarted,
   it can be more convenient to use the normal start and stop scripts packaged
   with VOLTTRON. These do not require the user have system-level permissions
   and are easily used from the terminal.


Run Web Server Behind Proxy
===========================

A VOLTTRON deployment may be web-enabled, allowing various interactions over HTTP.
There are many reasons why it is often desirable to deploy an external reverse
proxy in front of the system, including:

- Allows regular security patching of the exposed web server independent of the VOLTTRON
  process's lifecycle.
- Prevents DDoS and similar attacks, which may successfuly impact the web server, from
  impacting the VOLTTRON process itself.
- Provides a opportunity for institutional cyber security experts to help maintain a
  secure and compliant web server configuration without needing to gain VOLTTRON-specific
  experience.
- Many other traffic management and filtering options which are documented by the various
  tools (load balancing, http header management, etc.).

Configuring a reverse proxy is outside the scope of this documentation. For reference,
two common open source options are `apache httpd <https://httpd.apache.org/docs/2.4/howto/reverse_proxy.html>`_
and `nginx <https://docs.nginx.com/nginx/admin-guide/web-server/reverse-proxy/>`_
(relevant portions of their respective documentation pages are linked).


Monitor for Data Tampering
==========================

One common indication of a potential problem, including tampering, would be the presense
of out of bounds values.
The :ref:`Threshold-Agent` can be used leveraged to create alerts in the event that a
topic has a value which is out of reasonable bounds.

This approach has some limitations, including:

- There can be subtleties in selecting the correct bounds to both ensure issues are seen
  while minimizing false positives.
- Including value limits adds a significant amount of configuration to maintain, and which
  is not necessarily high-visibility because it is in another agent.
- Currently there is only support for monitoring for values crossing a threshold, more
  complex conditional logic would require a custom monitor.
- There could be cases where tampering adjusts values to incorrect but in-bounds values
  which would not be detected.


Limit Publishing on the Devices Topic to Platform Driver
========================================================

To further reduce the chances of malicious data disrupting your system, you can limit the
ability to publish to the devices topic to the platform driver only.

To accomplish this, you will need to modify protected_topics.json,
found in your $VOLTTRON_HOME directory. In this specific case, you would need
to add the topic "devices" and some capability, for example "can_publish_to_devices".

.. code-block:: json

    {
       "write-protect": [
          {"topic": "devices", "capabilities": ["can_publish_to_devices"]}
       ]
    }

Next, using ``vctl auth list`` get the auth index for the platform.driver,
and use the command ``vctl auth update <index of platform.driver>``.
You will get a prompt to update the auth entry. Skip through the prompts until it prompts for
capabilities, and add can_publish_to_devices.

.. code-block:: console

    capabilities (delimit multiple entries with comma) []: can_publish_to_devices

For more information, refer to the section on :ref:`Protected-Topics`.


Limit Access to RPC Methods Using Capabilities
==============================================

RPC enabled methods provide convenient interfaces between agents.
When they are unrestricted however, the open up the potential for malicious agents
to cause harm to yoru system. The best way to prevent this is through the use of capabilities.
A capability is an arbitrary string used by an agent to describe its exported RPC method.
It is used to limit the access to that RPC method to only those agents who have that capability listed in
their authentication record.

To add a capability restriction to an RPC method, the ``RPC.allow`` decorator is used.
For example, to limit those who can call the RPC enabled method "foo" to those with the capability "can_call_foo":

.. code-block:: python

    @RPC.export
    @RPC.allow("can_call_foo")
    def foo:
        print("hello")

To give an agent permission to access this method, the auth file must be updated.
As in the above example for limiting publishing to the devices topic, vctl can be
used to update the auth file and grant the specific agent permission to access the RPC enabled method.

.. code-block:: console

    capabilities (delimit multiple entries with comma) []: can_call_foo

For a secure system, only add capabilties to the agents that will need to call a specific RPC enabled method,
and apply the allow decorator to all RPC enabled methods.

For more information, refer to the section on :ref:`VIP-Authorization`.
