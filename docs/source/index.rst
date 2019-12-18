.. VOLTTRON documentation master file, created by
   sphinx-quickstart on Thu Feb  4 21:15:08 2016.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

====================================
|VOLTTRON|  documentation!
====================================



|VOLTTRON Tagline|

|VOLTTRON| is an open-source platform for distributed sensing and control. The platform provides services for collecting and storing data from buildings and devices and provides an environment for developing applications
that interact with that data.


Features
--------

Out of the box VOLTTRON provides:

- a secure :ref:`message bus <messagebus index>` allowing agents to subscribe to data sources and publish results and messages.
- secure connectivity between multiple instances.
- BACnet, ModBus and other device/system protocol connectivity through our :ref:`driver framework <VOLTTRON-Driver-Framework>` for collecting data from and sending control actions to buildings and devices.
- automatic data capture and retrieval through our :ref:`historian framework <Historian Index>`.
- platform based :ref:`agent lifecycle management <AgentManagement>`.
- a :ref:`web based management <VOLTTRON-Central>` tool for managing several instances from a central instance.
- the ability to easily extend the functionality of existing agents or create new ones for your specific purposes.


Background
----------

|VOLTTRON| is written in Python 2.7 and runs on Linux Operating Systems. For users unfamiliar with those technologies, the following resources are recommended:

- https://docs.python.org/2.7/tutorial/
- http://ryanstutorials.net/linuxtutorial/

License
-------

The project is :ref:`licensed <license>` under Apache 2 license.


Contents:

.. toctree::
   :maxdepth: 2

   overview/index
   community_resources/index
   setup/index
   devguides/index
   core_services/index
   specifications/index
   volttron_applications/index
   VOLTTRON Platform API <volttron_api/modules>


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


.. |VOLTTRON Logo| image:: images/volttron-webimage.jpg
.. |VOLTTRON| unicode:: VOLTTRON U+2122
.. |VOLTTRON Tagline| image:: images/VOLLTRON_Logo_Black_Horizontal_with_Tagline.png
