VOLTTRON
========

VOLTTRON(TM) is an open source platform for distributed sensing and control. The platform provides services
for collecting and storing data from buildings and devices and provides an environment for developing applications
which interact with that data.


Features
--------

- Driver framework for collecting data from and sending control actions to buildings and devices
- Historian framework for storing data
- Agent lifecycle managment

Installation
------------

Install VOLTTRON by running:

    git clone https://github.com/VOLTTRON/volttron
    cd volttron
    python bootstrap.py

This will build the platform and create a virtual Python environment. Activate this and then start the platform with:

    . env/bin/activate
    volttron -vv -l volttron.log&

This enters the virtual Python environment and then starts the platform in debug (vv) mode with a log file named
volttron.log.

Next, start an example listener to see it publish and subscribe to the message bus:

    scripts/core/make-listener

This script handles several different commands for installing and starting an agent after removing an old copy. This
 simple agent publishes a heartbeat message and listens to everything on the message bus. Look at the VOLTTRON log
 to see the activity:

    tail volttron.log

        2016-10-17 18:17:52,245 (listeneragent-3.2 11367) listener.agent INFO: Peer: 'pubsub', Sender: 'listeneragent-3.2_1'
        :, Bus: u'', Topic: 'heartbeat/ListenerAgent/f230df97-658e-45d3-8165-18a2ec834d3f', Headers:
        {'Date': '2016-10-18T01:17:52.239724+00:00', 'max_compatible_version': u'', 'min_compatible_version': '3.0'},
        Message: {'status': 'GOOD', 'last_updated': '2016-10-18T01:17:47.232972+00:00', 'context': 'hello'}


Contribute
----------

- Issue Tracker: github.com/VOLTTRON/volttron/issues
- Source Code: github.com/VOLTTRON/volttron

Support
-------

If you are having issues, please let us know.
We have a mailing list located at: volttron@pnnl.gov and also hold regular office hours where you can call in
for support and discussion of the platform.

License
-------

The project is licensed under a modified BSD license.
