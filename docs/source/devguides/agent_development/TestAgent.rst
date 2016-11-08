TestAgent Source Code
=====================

Full code of agent detailed in AgentDevelopment:

::

    import logging
    import sys

    from volttron.platform.vip.agent import Agent, PubSub
    from volttron.platform.agent import utils

    utils.setup_logging()
    _log = logging.getLogger(__name__)

    class TestAgent(Agent):

        def __init__(self, config_path, **kwargs):
            super(TestAgent, self).__init__(**kwargs)

            self.setting1 = 42
            self.default_config = {"setting1": self.setting1}

            self.vip.config.set_default("config", self.default_config)
            self.vip.config.subscribe(self.configure, actions=["NEW", "UPDATE"], pattern="config")

        def configure(self, config_name, action, contents):
            config = self.default_config.copy()
            config.update(contents)

            # make sure config variables are valid
            try:
                self.setting1 = int(config["setting1"])
            except ValueError as e:
                _log.error("ERROR PROCESSING CONFIGURATION: {}".format(e))

        @PubSub.subscribe('pubsub', 'heartbeat/listeneragent')
        def on_heartbeat_topic(self, peer, sender, bus, topic, headers, message):
               _log.debug("TestAgent got\nTopic: {topic}, {headers}, Message: {message}"
                          .format(topic=topic, headers=headers, message=message))


    def main(argv=sys.argv):
        '''Main method called by the platform.'''
        utils.vip_main(TestAgent)


    if __name__ == '__main__':
        # Entry point for script
        try:
            sys.exit(main())
        except KeyboardInterrupt:
            pass

Contents of setup.py for TestAgent:

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

Contents of testagent.config

::

    {
        "agentid": "Test1",
        "message": "hello"
    }
