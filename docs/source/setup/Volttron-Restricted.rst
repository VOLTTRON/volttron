.. _Volttron-Restricted: 

VOLTTRON Restricted Code
=========================

Volttron Restricted adds a broader security layer on top of the volttron
platform. If you are interested in this package please contact the
volttron team at volttron@pnnl.gov.

-  NOTE: Once the package is installed all aspects of the package will
   be enforced. To override the behavior add no-verify, no-mobility, or
   no-resource-monitor to the :ref:`configuration
   file <PlatformConfiguration>`.

The Volttron Restricted package contains the following security
enhancements:

-  The creation and usage of platform specific Certificate Authority
   (CA) certificates.
-  Multi-level signing of agent packages.
-  Multi-level verification of signed packages during agent execution.
-  Command line and agent based mobility.
-  Allows developer to customize an execution contract for required
   resources on the current and move requested platform.

The following pages describe the functionality exposed by the Volttron
Restricted package:

-  :ref:`Signing and Verification of Agent Packages <Agent-Signing>`
-  :ref:`Resource Monitor <Resource-Monitor>`
-  :ref:`PingPongAgent <PingPongAgent>`

Note: VOLTTRON-Restricted supports VOLTTRON 2.x and is being update to VOLTTRON 3.5

Installation
---

VOLTTRON-Restricted requires a software development tool called SWIG
(>=2.0.4). To install VOLTTRON-Restricted, follow the steps below. Enter
all terminal commands from the VOLTTRON directory.

-  Extract the VOLTTRON-Restricted code to a new directory. These steps
   assume the location is ``~/volttron-restricted``

-  Install VOLTTRON-Restricted dependency:

   **sudo apt-get install swig**

-  Activate the VOLTTRON Platform (note the space after the period):

   **. env/bin/activate**

-  Install VOLTTRON-Restricted:

   **pip install -e ~/volttron-restricted**

|Successful install of VOLTTRON-Restricted|

.. |Successful install of VOLTTRON-Restricted| image:: files/install-volttron-restricted.png
