.. VOLTTRON documentation master file

==========================
|VOLTTRON|  documentation!
==========================

|VOLTTRON Tagline|

|VOLTTRON| is an open-source platform for distributed sensing and control.  The platform is an open source tool for
performing simulations, improving building system performance, and creating a more flexible and reliable power grid.


Features
========

- a secure :ref:`message bus <messagebus index>` allowing connectivity between modules on individual platforms and
  between platform instances in large scale deployments
- a flexible :ref:`agent framework <Agent-Framework>` allowing users to adapt the platform to their unique use-cases
- a configurable :ref:`driver framework <VOLTTRON-Driver-Framework>` for collecting data from and sending control
  signals to buildings and devices
- automatic data capture and retrieval through our :ref:`historian framework <Historian Index>`
- an extensible :ref:`web framework <Web-Framework>` allowing users and services to securely connect to the platform
  from anywhere

VOLTTRON™ is open source and publicly available from `GitHub <https://github.com/volttron/volttron.git>`_. The project
is supported by the U.S. Department of Energy and receives ongoing updates from a team of core developers at PNNL.  The
VOLTTRON team encourages and appreciates community involvement including issues and pull requests on Github, meetings
at our bi-weekly office-hours and on Slack. To be invited to office-hours or slack, please `send the team an email
<volttron@pnnl.gov>`_.


.. toctree::
   :caption: Getting Started with VOLTTRON
   :hidden:
   :maxdepth: 1

   introduction/getting-started
   introduction/platform_install
   introduction/definitions
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

   deploying_volttron/Deployment-Walkthrough
   deploying_volttron/Deployment-Options
   deploying_volttron/SingleMachine-Walkthrough
   deploying_volttron/Multiplatform-Walkthrough
   deploying_volttron/Forward-Historian-Walkthrough
   deploying_volttron/Forward-Historian-Deployment
   deploying_volttron/Multiple-Address-Configuration
   deploying_volttron/VOLTTRON-Central-Demo
   deploying_volttron/Linux-Platform-Hardening-Recommendations-for-VOLTTRON-users


.. toctree::
   :caption: Frameworks and Integrations
   :hidden:
   :maxdepth: 1

   frameworks_and_integrations/driver_framework/index


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
   :maxdepth: 1

   volttron_topics/volttron_applications/index


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`


.. |VOLTTRON Logo| image:: images/volttron-webimage.jpg
.. |VOLTTRON| unicode:: VOLTTRON U+2122
.. |VOLTTRON Tagline| image:: images/VOLLTRON_Logo_Black_Horizontal_with_Tagline.png
