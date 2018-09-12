TestAgent Source Code
=====================

Full code of agent detailed in AgentDevelopment:

::

    """
    Agent documentation goes here.
    """

    __docformat__ = 'reStructuredText'

    import logging
    import sys
    from volttron.platform.agent import utils
    from volttron.platform.vip.agent import Agent, Core, RPC

    _log = logging.getLogger(__name__)
    utils.setup_logging()
    __version__ = "0.5"


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

        def _create_subscriptions(self, topic):
            #Unsubscribe from everything.
            self.vip.pubsub.unsubscribe("pubsub", None, None)

            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=topic,
                                      callback=self._handle_publish)

        def _handle_publish(self, peer, sender, bus, topic, headers,
                                    message):
            pass

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

        @RPC.export
        def rpc_method(self, arg1, arg2, kwarg1=None, kwarg2=None):
            """
            RPC method

            May be called from another agent via self.core.rpc.call """
            return self.setting1 + arg1 - arg2

    def main():
        """Main method called to start the agent."""
        utils.vip_main(tester,
                       version=__version__)


    if __name__ == '__main__':
        # Entry point for script
        try:
            sys.exit(main())
        except KeyboardInterrupt:
            pass


Contents of setup.py for TestAgent:

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

Contents of config:

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
