.. _Agent-Development:
Agent Creation Walkthrough
--------------------------

The VOLTTRON platfrom now has utilities to speed the creation and installation
of new agents. To use these utilities the VOLTTRON environment must be activated.

From the project directory, activate the VOLTTRON environment with:

``. env/bin/activate``

Create Agent Code
~~~~~~~~~~~~~~~~~

Run the following command to start the Agent Creation Wizard:

``vpkg init TestAgent tester``

`TestAgent` is the directory that the agent code will be placed in. The directory must
not exist when the command is run.

`tester` is the name of the agent module created by wizard.

The Wizard will prompt for the following information:

::

    Agent version number: [0.1]: 0.5
    Agent author: []: VOLTTRON Team
    Author's email address: []: volttron@pnnl.gov
    Agent homepage: []: https://volttron.org/
    Short description of the agent: []: Agent development tutorial.

Once the last question is answered the following will print to the console:

::

    2018-08-02 12:20:56,604 () volttron.platform.packaging INFO: Creating TestAgent
    2018-08-02 12:20:56,604 () volttron.platform.packaging INFO: Creating TestAgent/tester
    2018-08-02 12:20:56,604 () volttron.platform.packaging INFO: Creating TestAgent/setup.py
    2018-08-02 12:20:56,604 () volttron.platform.packaging INFO: Creating TestAgent/config
    2018-08-02 12:20:56,604 () volttron.platform.packaging INFO: Creating TestAgent/tester/agent.py
    2018-08-02 12:20:56,604 () volttron.platform.packaging INFO: Creating TestAgent/tester/__init__.py

The TestAgent directory is created with the new Agent inside.

Agent Directory
~~~~~~~~~~~~~~~

At this point, the contents of the TestAgent directory should look like:

::

    TestAgent/
    ├── setup.py
    ├── config
    └── tester
        ├── agent.py
        └── __init__.py


Examine the Agent Code
~~~~~~~~~~~~~~~~~~~~~~

The resulting code is well documented with comments and documentation strings. It
gives examples of how to do common tasks in VOLTTRON Agents.

The main agent code is found in `tester/agent.py`

Here we will cover the highlights.

Parse Packaged Configuration and Create Agent Instance
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The code to parse a configuration file packaged and installed with the agent
is found in the `tester` function:

::

    def tester(config_path, **kwargs):
        """Parses the Agent configuration and returns an instance of
        the agent created using that configuration.

        :param config_path: Path to a configuration file.

        :type config_path: str
        :returns: Tester
        :rtype: Tester
        """
        try:
            config = utils.load_config(config_path)
        except StandardError:
            config = {}

        if not config:
            _log.info("Using Agent defaults for starting configuration.")

        setting1 = int(config.get('setting1', 1))
        setting2 = config.get('setting2', "some/random/topic")

        return Tester(setting1,
                      setting2,
                      **kwargs)

The configuration is parsed with the `utils.load_config` function and the results
are stored in the `config` variable.

An instance of the Agent is created from the parsed values and is returned.

Initialization and Configuration Store Support
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The configuration store is a powerful feature introduced in VOLTTRON 4.
The agent template provides a simple example of setting up default configuration
store values and setting up a configuration handler.

::

    class Tester(Agent):
        """
        Document agent constructor here.
        """

        def __init__(self, setting1=1, setting2="some/random/topic",
                     **kwargs):
            super(Tester, self).__init__(**kwargs)
            _log.debug("vip_identity: " + self.core.identity)

            self.setting1 = setting1
            self.setting2 = setting2

            self.default_config = {"setting1": setting1,
                                   "setting2": setting2}


            #Set a default configuration to ensure that self.configure is called immediately to setup
            #the agent.
            self.vip.config.set_default("config", self.default_config)
            #Hook self.configure up to changes to the configuration file "config".
            self.vip.config.subscribe(self.configure, actions=["NEW", "UPDATE"], pattern="config")

        def configure(self, config_name, action, contents):
            """
            Called after the Agent has connected to the message bus. If a configuration exists at startup
            this will be called before onstart.

            Is called every time the configuration in the store changes.
            """
            config = self.default_config.copy()
            config.update(contents)

            _log.debug("Configuring Agent")

            try:
                setting1 = int(config["setting1"])
                setting2 = str(config["setting2"])
            except ValueError as e:
                _log.error("ERROR PROCESSING CONFIGURATION: {}".format(e))
                return

            self.setting1 = setting1
            self.setting2 = setting2

            self._create_subscriptions(self.setting2)

Values in the default config can be built into the agent or come from the
packaged configuration file. The subscribe method tells our agent which function
to call whenever there is a new or updated config file. For more information
on using the configuration store see :doc:`Agent Configuration Store <Agent-Configuration-Store>`

`_create_subscriptions` (convered in the next section) will use the value in self.setting2
to create a new subscription.

Setting up a Subscription
^^^^^^^^^^^^^^^^^^^^^^^^^

The Agent creates a subscription using the value of self.setting2 in the method
`_create_subscription`. The messages for this subscription hare handeled with
the `_handle_publish` method:

::

        def _create_subscriptions(self, topic):
            #Unsubscribe from everything.
            self.vip.pubsub.unsubscribe("pubsub", None, None)

            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=topic,
                                      callback=self._handle_publish)

        def _handle_publish(self, peer, sender, bus, topic, headers,
                                    message):
            pass

Agent Lifecycle Events
^^^^^^^^^^^^^^^^^^^^^^

Methods may be setup to be called at agent startup and shudown:

::

        @Core.receiver("onstart")
        def onstart(self, sender, **kwargs):
            """
            This is method is called once the Agent has successfully connected to the platform.
            This is a good place to setup subscriptions if they are not dynamic or
            do any other startup activities that require a connection to the message bus.
            Called after any configurations methods that are called at startup.

            Usually not needed if using the configuration store.
            """
            #Example publish to pubsub
            #self.vip.pubsub.publish('pubsub', "some/random/topic", message="HI!")

            #Exmaple RPC call
            #self.vip.rpc.call("some_agent", "some_method", arg1, arg2)

        @Core.receiver("onstop")
        def onstop(self, sender, **kwargs):
            """
            This method is called when the Agent is about to shutdown, but before it disconnects from
            the message bus.
            """
            pass

As the comment mentions. With the new configuration store feature `onstart` methods
are mostly unneeded. However this code does include an example of how to do a Remote
Proceedure Call to another agent.

Agent Remote Proceedure Calls
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

An agent may receive commands from other agents via a Remote Proceedure Call or RPC for short.
This is done with the @RPC.export decorattor:

::

        @RPC.export
        def rpc_method(self, arg1, arg2, kwarg1=None, kwarg2=None):
            """
            RPC method

            May be called from another agent via self.core.rpc.call """
            return self.setting1 + arg1 - arg2


Packaging Configuration
~~~~~~~~~~~~~~~~~~~~~~~

The wizard will automatically create a setup.py file. This file sets up the
name, version, required packages, method to execute, etc. for the agent based on
your answers to the wizard. The packaging process will also use this
information to name the resulting file.

::

    from setuptools import setup, find_packages

    MAIN_MODULE = 'agent'

    # Find the agent package that contains the main module
    packages = find_packages('.')
    agent_package = 'tester'

    # Find the version number from the main module
    agent_module = agent_package + '.' + MAIN_MODULE
    _temp = __import__(agent_module, globals(), locals(), ['__version__'], -1)
    __version__ = _temp.__version__

    # Setup
    setup(
        name=agent_package + 'agent',
        version=__version__,
        author_email="volttron@pnnl.gov",
        url="https://volttron.org/",
        description="Agent development tutorial.",
        author="VOLTTRON Team",
        install_requires=['volttron'],
        packages=packages,
        entry_points={
            'setuptools.installation': [
                'eggsecutable = ' + agent_module + ':main',
            ]
        }
    )

Launch Configuration
~~~~~~~~~~~~~~~~~~~~

In TestAgent, the wizard will automatically create a file called "config".
It contains configuration information for the agent. This file contains
examples every datatype supported by the configuration system:

::

    {
      # VOLTTRON config files are JSON with support for python style comments.
      "setting1": 2, #Integers
      "setting2": "some/random/topic2", #strings
      "setting3": true, #Booleans: remember that in JSON true and false are not capitalized.
      "setting4": false,
      "setting5": 5.1, #Floating point numbers.
      "setting6": [1,2,3,4], # Lists
      "setting7": {"setting7a": "a", "setting7b": "b"} #Objects
    }




Packaging and Installing the Agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To install the agent the platform must be running. Start the platform with the command:

``volttron -l volttron.log -vv&``

Now we must install it into the platform. Use the following command to install it and add a tag for easily referring to
the agent. From the project directory, run the following command:

``python scripts/install-agent.py -s TestAgent/ -c TestAgent/config -t testagent``

To verify it has been installed, use the following command:
``volttron-ctl list``

This will result in output similar to the following:

.. code-block:: bash

      AGENT                    IDENTITY           TAG       STATUS          HEALTH
    e testeragent-0.5          testeragent-0.5_1  testagent

Where the number or letter is the unique portion of the full uuid for the agent. AGENT is
the "name" of the agent based on the contents of its class name and the version in its setup.py. IDENTITY is the
agent's identity in the platform. This is automatically assigned based on class name and instance number. This agent's
ID is _1 because it is the first instance. TAG is the name we assigned in the command above. HEALTH
is the current health of the agent as reported by the agents health subsystem. 

When using lifecycle commands on agents, they can be referred to be UUID (default) or AGENT (name) or TAG.


Testing the Agent
~~~~~~~~~~~~~~~~~

From the Command Line
^^^^^^^^^^^^^^^^^^^^^

To test the agent, we will start the platform (if not already running), launch the agent, and
check the log file.

-  With the VOLTTRON environment activated, start the platform by
   running (if needed):

``volttron -l volttron.log -vv&``

-  Launch the agent by <uuid> using the result of the list command:

``vctl start <uuid>``

-  Launch the agent by name with:

``vctl start --name testeragent-0.1``

-  Launch the agent by tag with:

``volttron-ctl start --tag testagent``

-  Check that it is :ref:`running <AgentStatus>`:

``volttron-ctl status``

-  Start the ListenerAgent as in :ref:`Building VOLTTRON <Building-VOLTTRON>`
-  Check the log file for messages indicating the TestAgent is receiving
   the ListenerAgents messages:
