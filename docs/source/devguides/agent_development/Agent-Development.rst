.. _Agent-Development:
Agent Creation Walkthrough
--------------------------

It is recommended that developers look at the
`ListenerAgent <https://github.com/VOLTTRON/volttron/tree/master/examples/ListenerAgent>`__
before developing their own agent. That agent expresses the basic
functionality this example will walk through and being familiar with the
concepts will be useful.

Full versions of the files discussed below are at:
:doc:`TestAgent <TestAgent>`

Additional details about the commands used in this walkthrough are at:
:doc:`AgentManagement <../../core_services/AgentManagement>`

Create Folders
~~~~~~~~~~~~~~

-  In the "applications" directory, create a new directory called
   TestAgent.
-  In TestAgent, create a new folder tester, this is the package where
   our python code will be created

Create Agent Code
~~~~~~~~~~~~~~~~~

-  In tester, create a file called ``__init__.py`` which tells Python to
   treat this folder as a package
-  In the tester package folder, create the file ``agent.py``
-  Create a class called TestAgent

   -  Import the packages and classes we will need:

.. raw:: html

   <!-- -->

::

    import sys

    from volttron.platform.vip.agent import Agent, PubSub
    from volttron.platform.agent import utils

-  This agent will extend BaseAgent to get all the default functionality

   -  Since we want to publish we will import the PubSub module

.. raw:: html

   <!-- -->

::

    class TestAgent(Agent):

-  Create an init method to deal with creating the agent and getting the
   config file later

   ::

       def __init__(self, config_path, **kwargs):
           super(TestAgent, self).__init__(**kwargs)

Setting up a Subscription
^^^^^^^^^^^^^^^^^^^^^^^^^

We will set our agent up to listen to heartbeat messages (published by
ListenerAgent). Using the PubSub decorator, we declare we want to match
all topics which start with "heartbeat/listeneragent". This will give us
all heartbeat messages from all listeneragents but no others.

::

        @PubSub.subscribe('pubsub', 'heartbeat/listeneragent')
        def on_heartbeat_topic(self, peer, sender, bus, topic, headers, message):
               print "TestAgent got\nTopic: {topic}, {headers}, Message: {message}".format(topic=topic, headers=headers, message=message)

Argument Parsing and Main
^^^^^^^^^^^^^^^^^^^^^^^^^

Our agent will need to be able to parse arguments being passed on the
command line by the agent launcher. Use the utils.default-main method to
handle argument parsing and other default behavior. Create a main method
which can be called by the launcher.

::

    def main(argv=sys.argv):
        '''Main method called by the platform.'''
        utils.vip_main(TestAgent)


    if __name__ == '__main__':
        # Entry point for script
        try:
            sys.exit(main())
        except KeyboardInterrupt:
            pass

Create Support Files for Agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Volttron agents need some configuration files for packaging,
configuration, and launching.

Packaging Configuration
^^^^^^^^^^^^^^^^^^^^^^^

In the TestAgent folder, create a file called "setup.py" (or copy the
setup.py in ListenerAgent) which the platform will use to create a
[wheel].(https://pypi.python.org/pypi/wheel). This file sets up the
name, version, required packages, method to execute, etc. for the agent.
The packaging process will also use this information to name the
resulting file.

::

    from setuptools import setup, find_packages

    packages = find_packages('.')
    package = packages[0]

    setup(
        name = package + 'agent',
        version = "0.1",
        install_requires = ['volttron'],
        packages = packages,
        entry_points = {
            'setuptools.installation': [
                'eggsecutable = ' + package + '.agent:main',
            ]
        }
    )

Launch Configuration
^^^^^^^^^^^^^^^^^^^^

In TestAgent, create a file called "testagent.config". This is the file
the platform will use to launch the agent. It can also contain
configuration information for the agent.

For TestAgent,

::

    {
        "agentid": "Test1",
        "message": "hello"    
    }

Agent Directory
~~~~~~~~~~~~~~~

At this point, the contents of the TestAgent directory should look like:

::

    applications/TestAgent/
    ├── setup.py
    ├── testagent.config
    └── tester
        ├── agent.py
        └── __init__.py

Packaging Agent
~~~~~~~~~~~~~~~

The agent code must now be packaged up for use by the platform. The
package command will build the Python wheel using the setup.py file we
defined earlier.

From the project directory, activate the VOLTTRON environment with:

``. env/bin/activate``

Then call:

``volttron-pkg package applications/TestAgent``

By default, this creates a wheel file in the VOLTTRON\_HOME directory
(~/.volttron by default) in the ``packaged`` dreictory. Next, we add our
configuration file to this package with:

``volttron-pkg configure ~/.volttron/packaged/testeragent-0.1-py2-none-any.whl applications/TestAgent/testagent.config``

Installing the Agent
~~~~~~~~~~~~~~~~~~~~

Now we must install it into the platform. Use:

``volttron-ctl install ~/.volttron/packaged/testeragent-0.1-py2-none-any.whl``

Testing the Agent
~~~~~~~~~~~~~~~~~

From the Command Line
^^^^^^^^^^^^^^^^^^^^^

To test the agent, we will start the platform, launch the agent, and
check the log file.

-  With the VOLTTRON environment activated, start the platform by
   running

``volttron -l volttron.log -vv&``

-  Launch the agent by running:

``volttron-ctl start --name testeragent-0.1``

-  Check that it is `running <AgentStatus>`__:

``volttron-ctl status``

-  Start the ListenerAgent as in
   `BuildingTheProject <BuildingTheProject>`__
-  Check the log file for messages indicating the TestAgent is receiving
   the ListenerAgents messages:

``tail volttron.log``

::

    2014-09-17 15:30:50,088 (testeragent-0.1 3792) <stdout> INFO: Topic: heartbeat/listeneragent, Headers({u'Date': u'2014-09-17 22:30:50.079548Z', u'AgentID': u'listener1', u'Content-Type': u'text/plain'}), Message:   ['2014-09-17 22:30:50.079548Z']

In Eclipse
^^^^^^^^^^

-  If you are working in Eclipse, create a run configuration for
   TestAgent based on the ListenerAgent configuration in
   EclipseDevEnvironment.
-  Launch the platform
-  Launch the TestAgent
-  Launch the ListenerAgent

TestAgent should start receiving the heartbeats from ListenerAgent
