.. VOLTTRON documentation master file

==========================
|VOLTTRON|  documentation!
==========================

|VOLTTRON Tagline|

|VOLTTRON| is an open-source platform for distributed sensing and control.  The platform is an open source tool for
performing simulations, improving building system performance, and creating a more flexible and reliable power grid.


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
   :maxdepth: 1

   introduction/what-is-volttron
   introduction/how-does-it-work
   introduction/platform-install
   introduction/definitions
   introduction/license


.. toctree::
   :caption: Developing in VOLTTRON
   :hidden:
   :maxdepth: 1

   developing-volttron/contributing/community
   developing-volttron/development-environment/index
   developing-volttron/developing-agents/agent-development-walk-through
   developing-volttron/developing-drivers/driver-development-walk-through
   developing-volttron/jupyter-notebooks
   developing-volttron/python-for-matlab-users


.. toctree::
   :caption: Deploying VOLTTRON
   :hidden:
   :maxdepth: 1

   deploying-volttron/deployment-walk-through
   deploying-volttron/single-machine-walk-through
   deploying-volttron/multi-platform-walk-through
   deploying-volttron/volttron-central
   deploying-volttron/platform-hardening


.. toctree::
   :caption: Agent Framework
   :hidden:
   :maxdepth: 1

   agent-framework/agents-overview
   agent-framework/core-service-agents/index
   agent-framework/historian-agents/historian-framework
   agent-framework/operations-agents/index
   agent-framework/example-agents/index
   agent-framework/web-framework
   agent-framework/platform-service-standardization
   agent-framework/third-party-agents


.. toctree::
   :caption: Driver Framework
   :hidden:
   :maxdepth: 1

   driver-framework/drivers-overview
   driver-framework/fake-driver/fake-driver
   driver-framework/actuator/actuator-agent
   driver-framework/bacnet/bacnet-driver
   driver-framework/chargepoint/chargepoint-driver
   driver-framework/dnp3-driver/dnp3-driver
   driver-framework/ecobee/ecobee-web-driver
   driver-framework/ieee-2030_5/ieee-2030-driver
   driver-framework/modbus/modbus-driver
   driver-framework/modbus/modbus-tk-driver
   driver-framework/obix/obix
   driver-framework/ted-driver/the-energy-detective-driver


.. toctree::
   :caption: Platform Features
   :hidden:
   :maxdepth: 1

   platform-features/message-bus/index
   platform-features/control/index
   platform-features/config-store/configuration-store
   platform-features/security/volttron-security
   platform-features/web-framework/web-framework-overview


.. toctree::
   :caption: VOLTTRON Topics
   :hidden:
   :maxdepth: 1

   volttron-topics/troubleshooting/index
   volttron-topics/volttron-applications/index
   volttron-topics/change-log/index


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`


.. |VOLTTRON Logo| image:: images/volttron-webimage.jpg
.. |VOLTTRON| unicode:: VOLTTRON U+2122
.. |VOLTTRON Tagline| image:: images/VOLLTRON_Logo_Black_Horizontal_with_Tagline.png
