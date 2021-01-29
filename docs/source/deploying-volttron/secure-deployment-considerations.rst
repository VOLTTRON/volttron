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

One common indication of a potential problem, including tampering, would the the presense
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


Monitoring RabbitMQ Server
==========================

Monitoring of RabbitMQ server in deployment setup can be achieved in two ways.

1. Running RabbitMQ server as a systemd service
2. Configure VOLTTRON platform to monitor RabbitMQ server

In the first case, RabbitMQ server is configured to run as a systemd service and allow systemd to
monitor the status of the service. It can be further configured to detect and restart the RabbitMQ service
if it crashes. VOLTTRON agents have the ability to detect when the RabbitMQ server crashes/disconnects
and reconnect when it becomes available. In this deployment setup, a VOLTTRON platform will not
start/stop the RabbitMQ server.

In the second case, VOLTTRON is configured to monitor RabbitMQ server periodically and restart if a crash is detected.
This action is performed by the HealthService Agent. This is an optional feature and can be enabled using
'--monitor-rabbit' flag as part of VOLTTRON platform startup command.

.. code-block:: console

    $ volttron -vv -l volttron.log --monitor-rabbit > volttron.log 2>&1 &



