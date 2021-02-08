.. _Linux-System-Hardening:

======================
Linux System Hardening
======================


Introduction
============

VOLTTRON is built with modern security principles in mind [security-wp] and implements many security features for hosted
agents.
However, VOLTTRON is deployed on top of a Linux-based operating system and evaluating the security of a deployment must
include the configuration of the host system itself, as well as any other applications deployed on the system, both of
which provide additional attack surface and failure opportunities.

There is no such thing as "a secure system."
Rather, any computing system must be evaluated in the context of its deployment environment with considerations for
assurance of confidentiality, integrity, and availability.
The impact of a compromised system must be considered, along with the costs assocated with risk mitigation.
Threat profile analyses have been comleted for several VOLTTRON deployment configurations; the reports are available on
the `VOLTTRON website's publications section <https://volttron.org/publications>`_.


Recommendations
===============

The VOLTTRON  team recommends a risk-based cyber security approach that considers each risk, the impact of an
exploit or failure, and the costs associated with the available mitigation strategies.
Based on this evaluation, a set of mitigations can be identified to meet deployment requirements.

In many cases, the first step is to coordinate with the cyber security team at your institution; they should be able
to help you with risk assessment and mitigation strategies, as well s as understanding any relevant regulartory
requirements.

For continuously running and production-like systems, one common area of concern is hardening of the host operating
system.
Instructions are maintained by OpenSCAP for a large number of operating systems and guides are available for a
`range of common linux distrobutions <https://static.open-scap.org>`_.
You are encouraged to select the operating system and profile corresponding to your security requirements.
The guides there provide instruction for compliance in regulated environments, but are also appropriate in less
regulated environments where risk levels are equivalent.

It is also important to evaluate any other applications running on the same system.
In addtion to the potential for exploitation or failure of the individual application, it is important to consider
the ways in which the risks associated with one application may expose new risks in another application.
For example, if a system is running a webserver which is exploited in a way that provides unauthorized access to
the host system, then the VOLTTRON system is now exposed to attack from local users.
