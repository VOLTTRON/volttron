"""
Agent documentation goes here.
"""
import json

__docformat__ = 'reStructuredText'

import logging
import sys
import os
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
        return os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


    @RPC.export
    def verify_install_dir_permissions(self):
        """
        Checks if agent user has only read and execute permission on all directories under install directory except
        agent-data directory. user should have read, write, and execute permissions to agent-data directory.
        If there are no errors return None
        :return: If permissions are not right an error message is returned. If there are no errors return None
        """
        _log.debug("In verify_install_dir_permissions")
        data_dir = os.path.basename(self.get_agent_dir()) + ".agent-data"
        _log.debug("Agent dir is {}".format(self.get_agent_dir()))
        for (root, directories, files) in os.walk(self.get_agent_dir(), topdown=True):
            for directory in directories:
                dir_path = os.path.join(root, directory)
                _log.debug("Directory that is checked is " + dir_path)
                if not os.access(dir_path, os.R_OK):
                    return "Agent user does not have read access to directory {}".format(dir_path)
                if not os.access(dir_path, os.X_OK):
                    return "Agent user does not have execute access to directory {}".format(dir_path)
                write_access = os.access(dir_path, os.W_OK)
                if directory == data_dir and not write_access:
                    return "Agent user does not have write access to {}".format(dir_path)
                elif directory != data_dir and write_access:
                    return "Agent user has write access to {}".format(dir_path)
        return None


    @RPC.export
    def verify_vhome_dir_permissions(self):
        """
        Check permission of agent outside of agent install directory. Agent should have read+execute access to the
        following directories. Read access to other folders are based on default settings in the machine.
        We restrict only file access when necessary.
            - vhome
            - vhome/certificates and its subfolders
        :return:
        """
        install_dir = os.path.dirname(self.get_agent_dir())
        vhome = os.path.dirname(os.path.dirname(install_dir))
        certs_dir = os.path.join(vhome, "certificates/certs")
        key_dir = os.path.join(vhome, "certificates/private")
        paths = [vhome, certs_dir, key_dir]
        for p in paths:
            if not os.access(vhome, os.R_OK):
                return "Agent user does not have read access to file {}".format(p)
            if not os.access(vhome, os.X_OK):
                return "Agent user does not have read access to file {}".format(p)
        return None

    @RPC.export
    def verify_install_dir_file_permissions(self):

        """
        Checks if agent user has only read permission on all files under install directory except files in
        agent-data directory. User will be the owner of files in agent-data directory hence we need not check this dir.
        :return: If permissions are not right an error message is returned. If there are no errors return None
        """
        data_dir_name = os.path.basename(self.get_agent_dir()) + ".agent-data"
        install_dir = os.path.dirname(self.get_agent_dir())  # start at vhome/agents/<uuid> dir
        for (root, directories, files) in os.walk(install_dir, topdown=True):
            if os.path.basename(root) == data_dir_name:
                continue
            for f in files:
                file_path = os.path.join(root, f)
                if not os.access(file_path, os.R_OK):
                    return "Agent user does not have read access to file {}".format(file_path)
                if os.access(file_path, os.W_OK):
                    return "Agent user has write access to file {}".format(file_path)
                if os.access(file_path, os.X_OK):
                    return "Agent user has execute access to file {}".format(file_path)
        return None

    @RPC.export
    def verify_vhome_file_permissions(self, instance_name):

        """
        Test to make sure agent does not have any permissions on files outside agent's directory but for the below
        exceptions.
        Agent user should have read access to
            - vhome/config
            - vhome/known_hosts
            - vhome/certificates/certs/*
            - vhome/certificates/private/<agent_vip_id>.<instance_name>.pem (in case of rmq)
            - vhome/rabbitmq_config.yml( in case of rmq)

        Agent should have write access to volttron.log in the test home folder
        :return: If permissions are not right an error message is returned. If there are no errors return None
        """
        install_dir = os.path.dirname(self.get_agent_dir())
        vhome = os.path.dirname(os.path.dirname(install_dir))
        config = os.path.join(vhome, "config")
        known_hosts = os.path.join(vhome, "known_hosts")
        log = os.path.join(vhome, "volttron.log")
        rmq_yml = os.path.join(vhome, "rabbitmq_config.yml")
        key = os.path.join(vhome, "certificates/private", instance_name + "." + self.core.identity + ".pem")
        data_dir_name = os.path.basename(self.get_agent_dir()) + ".agent-data"
        ca_public = os.path.join(vhome, "certificates/remote_certs/requests_ca_bundle")
        paths = [config, known_hosts, rmq_yml, log, key, ca_public]
        public_key_dir = os.path.join(vhome, "certificates/certs")
        for (root, directories, files) in os.walk(vhome, topdown=True):
            if os.path.basename(root) == data_dir_name:
                continue  # files are owned by agent user
            if root.startswith(os.path.join(vhome, "rmq_node_data")):
                # rmq node data for test runs only. ignore
                continue
            for f in files:
                file_path = os.path.join(root, f)
                if file_path in paths or file_path.startswith(install_dir) or file_path.startswith(public_key_dir):
                    # should have read access alone
                    if not os.access(file_path, os.R_OK):
                        return "Agent user does not have read access to file {}. ".format(file_path)
                else:
                    if os.access(file_path, os.R_OK):
                        return "Agent user has read access to file {}" \
                            "Should have read access only to {}".format(file_path, paths)
                if file_path != log:
                    if os.access(file_path, os.W_OK):
                        return "Agent user has write access to file {}".format(file_path)
                if os.access(file_path, os.X_OK):
                    return "Agent user has execute access to file {}".format(file_path)
        return None

    @RPC.export
    def verify_config_store_access(self, agent2_identity):
        """
        Verify that agent is able to access its own config store. But agent should not be able edit another agent's
        config store either through vctl config command or by direct file access
        :return: If permissions are not right an error message is returned. If there are no errors return None
        """
        error = None
        try:
            self.vip.rpc.call('config.store', 'manage_store', "security_agent", 'config',
                              json.dumps({"name": "value"}), config_type='json').get(timeout=2)
        except Exception as e:
            error = str(e)

        if error:
            return error

        try:
            self.vip.rpc.call('config.store', 'manage_store', agent2_identity, 'config',
                              json.dumps({"test": "value"}), config_type='json').get(timeout=10)
            error = "Security agent is able to edit  config store entry of security_agent2"
        except Exception as e:
            error = e.message
            if error == "User can call method manage_store only with identity=security_agent " \
                        "but called with identity={}".format(agent2_identity):
               error = None

        # try accessing the file directly
        agent2_config = os.path.join(self.core.volttron_home, "configuration_store/{}.store".format(agent2_identity))
        if os.access(agent2_config, os.R_OK) or os.access(agent2_config, os.W_OK) or os.access(agent2_config, os.X_OK):
            error = "Agent has access to another agent's config store file"
        return error


def main():
    """Main method called to start the agent."""
    utils.vip_main(security_agent, version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
