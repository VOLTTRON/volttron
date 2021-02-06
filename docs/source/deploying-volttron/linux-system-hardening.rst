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

There is no such thing as "a secure system," rather any computing system must be evaluated in the context of its
deployment environment with considerations for assurance of confidentiality, integrity, and availability as well
as the potential impact of a breach and costs assocated with risk mitigation.
Threat profile analyses have been comleted for several VOLTTRON deployment configurations; the reports are available on
the `volttron website's publications section<https://volttron.org/publications>`_.


Recommendations
===============

The VOLTTRON  team recommends a risk-based cyber security approach that considers each risk, and the impact of an
exploit or failure.
After evaluating the potential impact of each risk, a suitable mitigation can be identified.

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

