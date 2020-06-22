.. VOLTTRON documentation master file

==========================
|VOLTTRON|  documentation!
==========================

|VOLTTRON Tagline|

|VOLTTRON| is an open-source platform for distributed sensing and control.  The platform provides services for
collecting and storing data from buildings and devices and provides an environment for developing applications
that interact with that data.


Features
========

Out of the box VOLTTRON provides:

- a secure :ref:`message bus <messagebus index>` allowing agents to subscribe to data sources and publish results and
  messages.
- secure connectivity between multiple VOLTTRON instances.
- BACnet, ModBus and other device/system protocol connectivity through our
  :ref:`driver framework <VOLTTRON-Driver-Framework>` for collecting data from and sending control actions to buildings
  and devices.
- automatic data capture and retrieval through our :ref:`historian framework <Historian Index>`.
- platform based :ref:`agent lifecycle management <AgentManagement>`.
- a :ref:`web based management <VOLTTRON-Central>` tool for managing several instances from a central instance.
- the ability to easily extend the functionality of existing agents or create new ones for your specific purposes.


Background
==========

|VOLTTRON| is written in Python 3.6 and runs on Linux Operating Systems.  For users unfamiliar with those technologies,
the following resources are recommended:

- https://docs.python.org/3.6/tutorial/
- http://ryanstutorials.net/linuxtutorial/

License
=======

The project is :ref:`licensed <license>` under Apache 2 license.


.. toctree::
   :caption: Getting Started with VOLTTRON
   :hidden:
   :maxdepth: 1

   getting_started/getting-started
   getting_started/platform_install
   getting_started/definitions
   getting_started/license


.. toctree::
   :caption: Developing in VOLTTRON
   :hidden:
   :maxdepth: 1

   developing_volttron/contributing/index
   developing_volttron/developing_agents/agent-development-walkthrough
   developing_volttron/developing_drivers/driver-development-walkthrough
   developing_volttron/development_environment/index


.. toctree::
   :caption: Deploying VOLTTRON
   :hidden:
   :maxdepth: 1


.. toctree::
   :caption: Platform Features
   :hidden:
   :maxdepth: 1

   platform_features/messagebus/index
   platform_features/security/index
   platform_features/multiplatform/index
   platform_features/config_store/index


.. toctree::
   :caption: VOLTTRON Topics
   :hidden:

   agent_framework/agents-overview


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


.. |VOLTTRON Logo| image:: images/volttron-webimage.jpg
.. |VOLTTRON| unicode:: VOLTTRON U+2122
.. |VOLTTRON Tagline| image:: images/VOLLTRON_Logo_Black_Horizontal_with_Tagline.png
