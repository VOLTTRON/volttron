
__docformat__ = 'reStructuredText'

import logging
import sys
from pprint import pformat
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, PubSub, RPC

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.3"


def matlabV2(config_path, **kwargs):
    """Parses the Agent configuration and returns an instance of
    the agent created using that configuration.

    :param config_path: Path to a configuration file.

    :type config_path: str
    :returns: MatlabAgentV2
    :rtype: MatlabAgent2
    """
    try:
        config = utils.load_config(config_path)
    except StandardError:
        config = {}

    if not config:
        _log.info("Using Agent defaults for starting configuration.")

    script_names = config.get('script_names', ["testScript.py"])
    script_args = config.get('script_args', [["20"]])
    topics_to_matlab = config.get('topics_to_matlab', ["matlab/to_matlab/1"])
    topics_to_volttron = config.get('topics_to_volttron', "matlab/to_volttron/")


    return MatlabAgentV2(script_names, script_args, topics_to_matlab, topics_to_volttron, **kwargs)


class MatlabAgentV2(Agent):

    def __init__(self,script_names=[], script_args=[], topics_to_matlab=[], 
            topics_to_volttron=None,**kwargs):

        super(MatlabAgentV2, self).__init__(**kwargs)
        _log.debug("vip_identity: " + self.core.identity)

        self.script_names = script_names
        self.script_args = script_args
        self.topics_to_matlab = topics_to_matlab
        self.topics_to_volttron = topics_to_volttron
        self.default_config = {"script_names": script_names,
                               "script_args": script_args,
                               "topics_to_matlab": topics_to_matlab,
                               "topics_to_volttron": topics_to_volttron}


        #Set a default configuration to ensure that self.configure is called immediately to setup
        #the agent.
        self.vip.config.set_default("config", self.default_config)
        #Hook self.configure up to changes to the configuration file "config".
        self.vip.config.subscribe(self.configure, actions=["NEW", "UPDATE"], pattern="config")

    def configure(self, config_name, action, contents):
        """
        Called after the Agent has connected to the message bus. 
        If a configuration exists at startup this will be 
        called before onstart.
        Is called every time the configuration in the store changes.
        """
        config = self.default_config.copy()
        config.update(contents)

        _log.debug("Configuring Agent")

        try:
            script_names = config["script_names"]
            script_args = config["script_args"]
            topics_to_matlab = config["topics_to_matlab"]
            topics_to_volttron = config["topics_to_volttron"]

        except ValueError as e:
            _log.error("ERROR PROCESSING CONFIGURATION: {}".format(e))
            return

        self.script_names = script_names
        self.script_args = script_args
        self.topics_to_matlab = topics_to_matlab
        self.topics_to_volttron = topics_to_volttron
        self._create_subscriptions(self.topics_to_volttron)

        for script in range(len(self.script_names)):
            cmd_args = ""
            for x in range(len(self.script_args[script])):
                cmd_args += ",{}".format(self.script_args[script][x])
            _log.debug("Publishing on: {}".format(self.topics_to_matlab[script]))
            self.vip.pubsub.publish('pubsub', topic=self.topics_to_matlab[script], 
                    message="{}{}".format(self.script_names[script],cmd_args))
            _log.debug("Sending message: {}{}".format(self.script_names[script],cmd_args))
        
        _log.debug("Agent Configured!")

    def _create_subscriptions(self, topic):
        #Unsubscribe from everything.
        self.vip.pubsub.unsubscribe("pubsub", None, None)


        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix=topic,
                                  callback=self._handle_publish)

    def _handle_publish(self, peer, sender, bus, topic, headers,
                                message):
        _log.info("Agent: " + topic + "\nMessage: \n" + pformat(message[:-1]))

def main():
    """Main method called to start the agent."""
    utils.vip_main(matlabV2, 
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
