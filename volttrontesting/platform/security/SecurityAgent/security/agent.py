"""
Agent documentation goes here.
"""

__docformat__ = 'reStructuredText'

import logging
import sys
import os
import subprocess
from volttron.platform.agent import utils
from volttron.platform.messaging import headers
from volttron.platform.vip.agent import Agent, Core, RPC

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"

TEST_PUBLISH_TOPIC = "test/publish"
TEST_READ_TOPIC = "test/read"

HEADER_NAME_DATE = headers.DATE
HEADER_NAME_CONTENT_TYPE = headers.CONTENT_TYPE


def security_agent(config_path, **kwargs):
    """Parses the Agent configuration and returns an instance of
    the agent created using that configuration.

    :param config_path: Path to a configuration file.

    :type config_path: str
    :returns: TestSecureAgents
    :rtype: TestSecureAgents
    """
    config = {}

    _log.debug("config_dict before init: {}".format(config))
    utils.update_kwargs_with_config(kwargs, config)

    return SecurityAgent(**kwargs)


class SecurityAgent(Agent):
    """
    Document agent constructor here.
    """

    def __init__(self, **kwargs):
        super(SecurityAgent, self).__init__(**kwargs)
        _log.debug("vip_identity: " + self.core.identity)

        self.default_config = {}
        self.subscription_hits = 0

        self.vip.config.set_default("config", self.default_config)
        self.vip.config.subscribe(self.configure,
                                  actions=["NEW", "UPDATE"],
                                  pattern="config")

        _log.debug("Finished init method in security agent")

    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        self.vip.pubsub.subscribe('pubsub', TEST_READ_TOPIC,
                                  self.increment_hits)

    def increment_hits(self, peer, sender, bus, topic, headers, message):
        self.subscription_hits += 1

    def configure(self, config_name, action, contents):
        """
        Called after the Agent has connected to the message bus. If a
        configuration exists at startup this will be called before onstart.

        Is called every time the configuration in the store changes.
        """
        config = self.default_config.copy()
        config.update(contents)

        try:
            _log.debug("Configuring Agent")
        except ValueError as e:
            _log.error("ERROR PROCESSING CONFIGURATION: {}".format(e))
            return

    @RPC.export
    def can_receive_rpc_calls(self):
        """Used for determining that agents can send and receive RPC calls"""
        return True

    @RPC.export
    def can_make_rpc_calls(self, peer):
        return self.vip.rpc.call(peer, "can_receive_rpc_calls").get(timeout=3)

    @RPC.export
    def can_publish_to_pubsub(self):
        """Agents should be able to publish to the pubsub"""
        self.vip.pubsub.publish(peer="pubsub", topic=TEST_PUBLISH_TOPIC,
                                message="Security agent test message")

    @RPC.export
    def can_subscribe_to_messagebus(self):
        """Agents should be able to create messagebus subscriptions, run after
            making a publish to the <topic> topic"""
        return self.subscription_hits

    @RPC.export
    def get_agent_dir(self):
        """Get the agent's directory for testing purposes"""
        return os.path.dirname(os.path.realpath(__file__))

    def try_read_write_execute_dir(self, path):
        rwx = {"read": False,
               "write": False,
               "execute": False
               }
        # Try to read test file
        try:
            with open(path, "r") as p:
                line = p.readline()
                rwx["read"] = True
        except OSError as e:
            _log.debug(e)
        # Try to write test file
        try:
            with open(path, "w") as p:
                p.write("test")
                rwx["write"] = True
        except OSError as e:
            _log.debug(e)
        # TODO most unsure about this
        # Try to run test file
        try:
            hello_world = subprocess.Popen(path,
                                           stderr=subprocess.PIPE)
            hello_world.wait()
            stderr = hello_world.communicate()
            # Check to see the reason for error was permissions related
            if stderr:
                _log.info(stderr)
                assert "permission denied" in stderr
            else:
                rwx["execute"] = True
        except OSError as e:
            _log.debug(e)
        return rwx

    @RPC.export
    def can_execute_only_agent_install_dir(self):
        """Agents should be able to execute only from the agent directory"""
        test_path = os.path.join(self.get_agent_dir(), "test_perms.sh")
        _log.debug("Testing permissions on {}".format(test_path))
        return self.try_read_write_execute_dir(test_path)

    @RPC.export
    def can_read_only_agent_data_dir(self):
        """Agents should be able read only in the agent's agent-data
        directory"""
        agent_path_name = os.path.dirname(
            self.get_agent_dir()).rsplit("/", 1)[1]
        # Can't really used packaged files here
        test_path = os.path.join(os.path.dirname(self.get_agent_dir()),
                                 "{}.agent-data".format(agent_path_name),
                                 "USER_ID")
        _log.debug("Testing permissions on {}".format(test_path))
        return self.try_read_write_execute_dir(test_path)

    @RPC.export
    def can_read_only_data_dir(self):
        """Agents should be able to read"""
        # Can't really used packaged files here
        test_path = os.path.join(self.get_agent_dir(), "data", "test_perms.sh")
        _log.debug("Testing permissions on {}".format(test_path))
        return self.try_read_write_execute_dir(test_path)

    # @RPC.export
    # def can_read_write_execute_other_dir(self, directory):
    #     """Agents should not be able to read/write/execute anything outside of
    #         their own directory"""
    #     return self.try_read_write_execute_dir(directory)
    #
    #
    # @RPC.export
    # def can_act_as_root(self):
    #     """Agents should not be able to read/write/execute as root."""


def main():
    """Main method called to start the agent."""
    utils.vip_main(security_agent, version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
