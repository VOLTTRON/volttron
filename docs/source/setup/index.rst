.. _setup:
===================
Setting up VOLTTRON
===================

Installation
------------

:ref:`Install VOLTTRON <install>` by running the following commands that installs needed
:ref:`prerequisites <VOLTTRON-Prerequisites>`, clones the source code, then builds the virtual environment for using the platform.

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

This enters the virtual Python environment and then starts the platform in debug (vv) mode with a log file named volttron.log.

Next, start an example listener to see it publish and subscribe to the message bus:

.. code-block:: bash

    scripts/core/make-listener


This script handles several different commands for installing and starting an agent after removing an old copy. This simple agent publishes a heartbeat message and listens to everything on the message bus. Look at the VOLTTRON log
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




.. toctree::
    :glob:
    :maxdepth: 2

   VOLTTRON-Prerequisites
   Building-VOLTTRON
   VOLTTRON-Sourcce-Options
   Volttron-Restricted

   *

