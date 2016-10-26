.. VOLTTRON documentation master file, created by
   sphinx-quickstart on Thu Feb  4 21:15:08 2016.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

====================================================
Welcome to VOLTTRON\ :sup:`TM`\ 's documentation!
====================================================

|VOLTTRON Tagline|

VOLTTRON\ :sup:`TM` is an open source platform for distributed sensing and control. The platform provides services
for collecting and storing data from buildings and devices and provides an environment for developing applications
which interact with that data.

Features
--------

- :ref:`Message Bus <messagebus index>` allows agents to subcribe to data sources and publish results and messages
- :ref:`Driver framework <VOLTTRON-Driver-Framework>` for collecting data from and sending control actions to buildings and devices
- :ref:`Historian framework <Historian Index>` for storing data
- :ref:`Agent lifecycle managment <AgentManagement>` in the platform
- :ref:`Web UI <VOLTTRON-Central>` for managing deployed instances from a single central instance.


Background
----------

VOLTTRON\ :sup:`TM` is written in Python 2.7 and runs on Linux Operating Systems. For users unfamiliar with those
technologies, the following resources are recommended:

- https://docs.python.org/2.7/tutorial/
- http://ryanstutorials.net/linuxtutorial/


Installation
------------

:ref:`Install VOLTTRON <install>` by running the following commands which installs needed
:ref:`prerequisites <VOLTTRON-Prerequisites>`, clones the source code, then builds the virtual environment for using
the platform.

.. code-block:: bash

    sudo apt-get update
    sudo apt-get install build-essential python-dev openssl libssl-dev libevent-dev git
    git clone https://github.com/VOLTTRON/volttron
    cd volttron
    python bootstrap.py

This will build the platform and create a virtual Python environment. Activate this and then start the platform with:

.. code-block:: bash

    . env/bin/activate
    volttron -vv -l volttron.log&

This enters the virtual Python environment and then starts the platform in debug (vv) mode with a log file named
volttron.log.

Next, start an example listener to see it publish and subscribe to the message bus:

.. code-block:: bash

    scripts/core/make-listener


This script handles several different commands for installing and starting an agent after removing an old copy. This
simple agent publishes a heartbeat message and listens to everything on the message bus. Look at the VOLTTRON log
to see the activity:

.. code-block:: bash

    tail volttron.log

Results in:

.. code-block:: console

   2016-10-17 18:17:52,245 (listeneragent-3.2 11367) listener.agent INFO: Peer: 'pubsub', Sender: 'listeneragent-3.2_1'
   :, Bus: u'', Topic: 'heartbeat/ListenerAgent/f230df97-658e-45d3-8165-18a2ec834d3f', Headers:
   {'Date': '2016-10-18T01:17:52.239724+00:00', 'max_compatible_version': u'', 'min_compatible_version': '3.0'},
   Message: {'status': 'GOOD', 'last_updated': '2016-10-18T01:17:47.232972+00:00', 'context': 'hello'}

Stop the platform:

.. code-block:: bash

   volttron-ctl shutdown --platform


Next Steps
-----------

There are several :ref:`walkthroughs <devguides_index>` to explore additional aspects of the platform:

- :ref:`Agent Development Walkthrough <Agent-Development>`
- Demonstration of :ref:`the management UI <VOLTTRON-Central-Demo>`


Acquiring Third Party Agent Code
---------------------------------

Third party agents are available under volttron-applications repository. In order to use those agents, add
volttron-applications repository under the volttron/applications directory by using following command:

    git subtree add --prefix applications https://github.com/VOLTTRON/volttron-applications.git develop --squash


Contribute
----------

How to :ref:`contribute <contributing>` back:

- Issue Tracker: http://github.com/VOLTTRON/volttron/issues
- Source Code: http://github.com/VOLTTRON/volttron

=======
Support
=======

There are several options for VOLTTRON\ :sup:`TM` :ref:`support <VOLTTRON-Community>`.

- A VOLTTRON\ :sup:`TM` office hours telecon takes place every other Friday at 11am Pacific over Skype.
- A mailing list for announcements and reminders
- The VOLTTRON\ :sup:`TM` contact email for being added to office hours, the mailing list, and for inquiries is: volttron@pnnl.gov
- The preferred method for questions is through stackoverflow since this is easily discoverable by others who may have the same issue. http://stackoverflow.com/questions/tagged/volttron
- GitHub issue tracker for feature requests, bug reports, and following development activities http://github.com/VOLTTRON/volttron/issues



License
-------

The project is :ref:`licensed <license>` under a modified BSD license.




Contents:

.. toctree::
   :maxdepth: 2

   overview/index
   Install Instructions <install>
   community_resources/index

   core_services/index
   devguides/index
   sample_applications/index
   supporting/index
   scalability/index
   specifications/index
   roadmap/index

   API Documenation <apidocs>

   License <license>

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`



.. |VOLTTRON Logo| image:: images/volttron-webimage.jpg
.. |VOLTTRON Tagline| image:: images/VOLLTRON_Logo_Black_Horizontal_with_Tagline.png
