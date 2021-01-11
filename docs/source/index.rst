.. VOLTTRON documentation master file

==========================
|VOLTTRON|  documentation!
==========================

|VOLTTRON Tagline|

|VOLTTRON| is an open-source platform for distributed sensing and control.  The platform provides services for
collecting and storing data from buildings and devices and provides an environment for developing applications that interact with that data.


Features
========

- a secure :ref:`message bus <Message-Bus>` allowing connectivity between modules on individual platforms and
  between platform instances in large scale deployments
- a flexible :ref:`agent framework <Agent-Framework>` allowing users to adapt the platform to their unique use-cases
- a configurable :ref:`driver framework <Driver-Framework>` for collecting data from and sending control
  signals to buildings and devices
- automatic data capture and retrieval through our :ref:`historian framework <Historian-Framework>`
- an extensible :ref:`web framework <Web-Framework>` allowing users and services to securely connect to the platform
  from anywhere

VOLTTRON™ is open source and publicly available from `GitHub <https://github.com/volttron/volttron.git>`_. The project
is supported by the U.S. Department of Energy and receives ongoing updates from a team of core developers at PNNL.  The
VOLTTRON team encourages and appreciates community involvement including issues and pull requests on Github, meetings
at our bi-weekly office-hours and on Slack. To be invited to office-hours or slack, please `send the team an email
<volttron@pnnl.gov>`_.


.. toctree::
   :caption: Introduction
   :hidden:
   :titlesonly:
   :maxdepth: 1

   introduction/what-is-volttron
   introduction/how-does-it-work
   introduction/platform-install
   introduction/definitions
   introduction/license


.. toctree::
   :caption: Developing in VOLTTRON
   :hidden:
   :titlesonly:
   :maxdepth: 1

   developing-volttron/community
   developing-volttron/development-environment/index
   developing-volttron/developing-agents/agent-development
   developing-volttron/developing-drivers/driver-development
   developing-volttron/contributing-code
   developing-volttron/contributing-documentation
   developing-volttron/jupyter/jupyter-notebooks
   developing-volttron/python-for-matlab-users


.. toctree::
   :caption: Deploying VOLTTRON
   :hidden:
   :titlesonly:
   :maxdepth: 1

   deploying-volttron/bootstrap-process
   deploying-volttron/platform-configuration
   deploying-volttron/deployment-planning-options
   deploying-volttron/single-machine
   deploying-volttron/multi-platform/index
   deploying-volttron/linux-system-hardening
   deploying-volttron/recipe-deployment


.. toctree::
   :caption: Agent Framework
   :hidden:
   :titlesonly:
   :maxdepth: 1

   agent-framework/agents-overview
   agent-framework/core-service-agents/index
   agent-framework/operations-agents/index
   agent-framework/historian-agents/historian-framework
   agent-framework/web-framework
   agent-framework/integrating-simulations/index
   agent-framework/platform-service-standardization
   agent-framework/third-party-agents


.. toctree::
   :caption: Driver Framework
   :hidden:
   :titlesonly:
   :maxdepth: 1

   driver-framework/drivers-overview
   driver-framework/master-driver/master-driver
   driver-framework/actuator/actuator-agent
   driver-framework/fake-driver/fake-driver
   driver-framework/bacnet/bacnet-driver
   driver-framework/chargepoint/chargepoint-driver
   driver-framework/dnp3-driver/dnp3-driver
   driver-framework/ecobee/ecobee-web-driver
   driver-framework/ieee-2030_5/ieee-2030_5-driver
   driver-framework/modbus/modbus-driver
   driver-framework/modbus/modbus-tk-driver
   driver-framework/obix/obix
   driver-framework/ted-driver/the-energy-detective-driver


.. toctree::
   :caption: Platform Features
   :hidden:
   :titlesonly:
   :maxdepth: 1

   platform-features/message-bus/index
   platform-features/control/index
   platform-features/config-store/configuration-store
   platform-features/security/volttron-security

.. toctree::
   :caption: VOLTTRON Core Agents
   :maxdepth: 2
   :glob:

   volttron-api/services/*/modules

.. toctree::
   :caption: VOLTTRON Topics
   :hidden:
   :titlesonly:
   :maxdepth: 1

   volttron-topics/troubleshooting/index
   volttron-topics/volttron-applications/index
   volttron-topics/change-log/index



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`

.. |VOLTTRON| unicode:: VOLTTRON U+2122
.. |VOLTTRON Tagline| image:: files/VOLLTRON_Logo_Black_Horizontal_with_Tagline.png
