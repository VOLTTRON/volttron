"""
Agent documentation goes here.
"""

__docformat__ = 'reStructuredText'

import logging
import sys
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC

# from dnp3_python.dnp3station.outstation import MyOutStation as MyOutStationNew
from dnp3_python.dnp3station.outstation_new import MyOutStationNew
from pydnp3 import opendnp3
from typing import Dict



_log = logging.getLogger("Dnp3-agent")
utils.setup_logging()
__version__ = "0.2.0"

_log.level=logging.DEBUG
_log.addHandler(logging.StreamHandler(sys.stdout))  # Note: redirect stdout from dnp3 lib


# def agent_main(config_path, **kwargs):
#     """
#     Parses the Agent configuration and returns an instance of
#     the agent created using that configuration.
#
#     Note: config_path is by convention under .volttron home path, called config, e.g.
#     /home/kefei/.volttron/agents/6745e0ef-b500-495a-a6e8-120ec0ead4fd/testeragent-0.5/testeragent-0.5.dist-info/config
#
#     :param config_path: Path to a configuration file.
#     :type config_path: str
#     :returns: Tester
#     :rtype: Dnp3Agent
#     """
#     # _log.info(f"======config_path {config_path}")
#     # Note: config_path is by convention under .volttron home path, called config, e.g.
#     # /home/kefei/.volttron/agents/6745e0ef-b500-495a-a6e8-120ec0ead4fd/testeragent-0.5/testeragent-0.5.dist-info/config
#     # Note: the config file is attached when running `python scripts/install-agent.py -c TestAgent/config`
#     # NOte: the config file attached in this way will not appear in the config store.
#     # (Need to explicitly using `vctl config store`)
#     try:
#         config: dict = utils.load_config(config_path)
#     except Exception as e:
#         _log.info(e)
#         config = {}
#
#     if not config:
#         _log.info("Using Agent defaults for starting configuration.")
#
#     setting1 = int(config.get('setting1', 1))
#     setting2 = config.get('setting2', "some/random/topic")
#
#     return Dnp3Agent(config, **kwargs)


class Dnp3Agent(Agent):
    """This is class is a subclass of the Volttron Agent;
            This agent is an implementation of a DNP3 outstation;
            The agent overrides @Core.receiver methods to modify agent life cycle behavior;
            The agent exposes @RPC.export as public interface utilizing RPC calls.
        """

    def __init__(self, config_path: str, **kwargs) -> None:
        super(Dnp3Agent, self).__init__(**kwargs)

        # default_config, mainly for developing and testing purposes.
        default_config: dict = {'outstation_ip': '0.0.0.0', 'port': 20000, 'master_id': 2, 'outstation_id': 1}
        # agent configuration using volttron config framework
        # self._dnp3_outstation_config = default_config
        config_from_path = self._parse_config(config_path)

        # TODO: improve this logic by refactoring out the MyOutstationNew init,
        #  and add config from "config store"
        try:
            _log.info("Using config_from_path {config_from_path}")
            self._dnp3_outstation_config = config_from_path
            self.outstation_application = MyOutStationNew(**self._dnp3_outstation_config)
        except Exception as e:
            _log.error(e)
            _log.info(f"Failed to use config_from_path {config_from_path}"
                      f"Using default_config {default_config}")
            self._dnp3_outstation_config = default_config
            self.outstation_application = MyOutStationNew(**self._dnp3_outstation_config)

        # SubSystem/ConfigStore
        self.vip.config.set_default("config", default_config)
        self.vip.config.subscribe(
            self._config_callback_dummy,  # TODO: cleanup: used to be _configure_ven_client
            actions=["NEW", "UPDATE"],
            pattern="config",
        )  # TODO: understand what vip.config.subscribe does

    @property
    def dnp3_outstation_config(self):
        return self._dnp3_outstation_config

    @dnp3_outstation_config.setter
    def dnp3_outstation_config(self, config: dict):
        # TODO: add validation
        self._dnp3_outstation_config = config

    def _config_callback_dummy(self, config_name: str, action: str,
                               contents: Dict) -> None:
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

        # for dnp3 outstation
        self.outstation_application.start()

        # Example publish to pubsub
        # self.vip.pubsub.publish('pubsub', "some/random/topic", message="HI!")
        #
        # # Example RPC call
        # # self.vip.rpc.call("some_agent", "some_method", arg1, arg2)
        # pass
        # self._create_subscriptions(self.setting2)

    # ***************** Helper methods ********************
    def _parse_config(self, config_path: str) -> Dict:
        """Parses the agent's configuration file.

        :param config_path: The path to the configuration file
        :return: The configuration
        """
        # TODO: added capability to configuration based on tabular config file (e.g., csv)
        try:
            config = utils.load_config(config_path)
        except NameError as err:
            _log.exception(err)
            raise err
        except Exception as err:
            _log.error("Error loading configuration: {}".format(err))
            config = {}
        # print(f"============= def _parse_config config {config}")
        if not config:
            raise Exception("Configuration cannot be empty.")
        return config

    @RPC.export
    def rpc_dummy(self) -> str:
        """
        For testing rpc call
        """
        return "This is a dummy rpc call"

    @RPC.export
    def reset_outstation(self):
        """update`self._dnp3_outstation_config`, then init a new outstation.
        For post-configuration and immediately take effect.
        Note: will start a new outstation instance and the old database data will lose"""
        # self.dnp3_outstation_config(**kwargs)
        # TODO: this method might be refactored as internal helper method for `update_outstation`
        try:
            self.outstation_application.shutdown()
            outstation_app_new = MyOutStationNew(**self.dnp3_outstation_config)
            self.outstation_application = outstation_app_new
            self.outstation_application.start()
            _log.info(f"Outstation has restarted")
        except Exception as e:
            _log.error(e)

    @RPC.export
    def display_outstation_db(self) -> dict:
        """expose db"""
        return self.outstation_application.db_handler.db

    @RPC.export
    def get_outstation_config(self) -> dict:
        """expose get_config"""
        return self.outstation_application.get_config()

    @RPC.export
    def is_outstation_connected(self) -> bool:
        """expose is_connected, note: status, property"""
        return self.outstation_application.is_connected

    @RPC.export
    def apply_update_analog_input(self, val: float, index: int) -> dict:
        """public interface to update analog-input point value
        val: float
        index: int, point index
        """
        if not isinstance(val, float):
            raise f"val of type(val) should be float"
        self.outstation_application.apply_update(opendnp3.Analog(value=val), index)
        _log.debug(f"Updated outstation analog-input index: {index}, val: {val}")

        return self.outstation_application.db_handler.db

    @RPC.export
    def apply_update_analog_output(self, val: float, index: int) -> dict:
        """public interface to update analog-output point value
        val: float
        index: int, point index
        """

        if not isinstance(val, float):
            raise f"val of type(val) should be float"
        self.outstation_application.apply_update(opendnp3.AnalogOutputStatus(value=val), index)
        _log.debug(f"Updated outstation analog-output index: {index}, val: {val}")

        return self.outstation_application.db_handler.db

    @RPC.export
    def apply_update_binary_input(self, val: bool, index: int):
        """public interface to update binary-input point value
        val: bool
        index: int, point index
        """
        if not isinstance(val, bool):
            raise f"val of type(val) should be bool"
        self.outstation_application.apply_update(opendnp3.Binary(value=val), index)
        _log.debug(f"Updated outstation binary-input index: {index}, val: {val}")

        return self.outstation_application.db_handler.db

    @RPC.export
    def apply_update_binary_output(self, val: bool, index: int):
        """public interface to update binary-output point value
        val: bool
        index: int, point index
        """
        if not isinstance(val, bool):
            raise f"val of type(val) should be bool"
        self.outstation_application.apply_update(opendnp3.BinaryOutputStatus(value=val), index)
        _log.debug(f"Updated outstation binary-output index: {index}, val: {val}")

        return self.outstation_application.db_handler.db

    @RPC.export
    def update_outstation(self,
                          outstation_ip: str = None,
                          port: int = None,
                          master_id: int = None,
                          outstation_id: int = None,
                          **kwargs):
        """
        Update dnp3 outstation config and restart the application to take effect. By default,
        {'outstation_ip': '0.0.0.0', 'port': 20000, 'master_id': 2, 'outstation_id': 1}
        """
        config = self._dnp3_outstation_config.copy()
        for kwarg in [{"outstation_ip": outstation_ip},
                      {"port": port},
                      {"master_id": master_id}, {"outstation_id": outstation_id}]:
            if list(kwarg.values())[0] is not None:
                config.update(kwarg)
        self._dnp3_outstation_config = config
        self.reset_outstation()

# class Dnp3Agent(Agent):
#     """
#     Dnp3 agent mainly to represent a dnp3 outstation
#     """
#
#     def __init__(self, setting1={}, setting2="some/random/topic", **kwargs):
#         # TODO: clean-up the bizarre signature. Note: may need to reinstall the agent for testing.
#         super(Dnp3Agent, self).__init__(**kwargs)
#         _log.debug("vip_identity: " + self.core.identity)  # Note: consistent with IDENTITY in `vctl status`
#
#
#         # self.setting1 = setting1
#         # self.setting2 = setting2
#         config_when_installed = setting1
#         # TODO: new-feature: load_config from config store
#         # config_at_configstore =
#
#         self.default_config = {'outstation_ip': '0.0.0.0', 'port': 20000,
#                                'master_id': 2, 'outstation_id': 1}
#         # agent configuration using volttron config framework
#         # get_volttron_cofig, set_volltron_config
#         self._volttron_config: dict
#
#         # for dnp3 features
#         try:
#             self.outstation_application = MyOutStation(**config_when_installed)
#             _log.info(f"init dnp3 outstation with {config_when_installed}")
#             self._volttron_config = config_when_installed
#         except Exception as e:
#             _log.error(e)
#             self.outstation_application = MyOutStation(**self.default_config)
#             _log.info(f"init dnp3 outstation with {self.default_config}")
#             self._volttron_config = self.default_config
#         # self.outstation_application.start()  # moved to onstart
#
#         # Set a default configuration to ensure that self.configure is called immediately to setup
#         # the agent.
#         self.vip.config.set_default(config_name="default-config", contents=self.default_config)
#         self.vip.config.set_default(config_name="_volttron_config", contents=self._volttron_config)
#         # Hook self.configure up to changes to the configuration file "config".
#         self.vip.config.subscribe(self.configure, actions=["NEW", "UPDATE"], pattern="config")
#
#     def _get_volttron_config(self):
#         return self._volttron_config
#
#     def _set_volttron_config(self, **kwargs):
#         """set self._volttron_config using **kwargs.
#         EXAMPLE
#         self.default_config = {'outstation_ip': '0.0.0.0', 'port': 21000,
#                                'master_id': 2, 'outstation_id': 1}
#         set_volttron_config(port=30000, unused_key="unused")
#         # outcome
#         self.default_config = {'outstation_ip': '0.0.0.0', 'port': 30000,
#                                'master_id': 2, 'outstation_id': 1,
#                                'unused_key': 'unused'}
#                                """
#         self._volttron_config.update(kwargs)
#         _log.info(f"Updated self._volttron_config to {self._volttron_config}")
#         return {"_volttron_config": self._get_volttron_config()}
#
#     @RPC.export
#     def outstation_reset(self, **kwargs):
#         """update`self._volttron_config`, then init a new outstation.
#
#         For post-configuration and immediately take effect.
#         Note: will start a new outstation instance and the old database data will lose"""
#         self._set_volttron_config(**kwargs)
#         try:
#             outstation_app_new = MyOutStation(**self._volttron_config)
#             self.outstation_application.shutdown()
#             self.outstation_application = outstation_app_new
#             self.outstation_application.start()
#         except Exception as e:
#             _log.error(e)
#
#     @RPC.export
#     def outstation_get_db(self):
#         """expose db"""
#         return self.outstation_application.db_handler.db
#
#     @RPC.export
#     def outstation_get_config(self):
#         """expose get_config"""
#         return self.outstation_application.get_config()
#
#     @RPC.export
#     def outstation_get_is_connected(self):
#         """expose is_connected, note: status, property"""
#         return self.outstation_application.is_connected
#
#     @RPC.export
#     def outstation_apply_update_analog_input(self, val, index):
#         """public interface to update analog-input point value
#
#         val: float
#         index: int, point index
#         """
#         if not isinstance(val, float):
#             raise f"val of type(val) should be float"
#         self.outstation_application.apply_update(opendnp3.Analog(value=val), index)
#         _log.debug(f"Updated outstation analog-input index: {index}, val: {val}")
#
#         return self.outstation_application.db_handler.db
#
#     @RPC.export
#     def outstation_apply_update_analog_output(self, val, index):
#         """public interface to update analog-output point value
#
#         val: float
#         index: int, point index
#         """
#
#         if not isinstance(val, float):
#             raise f"val of type(val) should be float"
#         self.outstation_application.apply_update(opendnp3.AnalogOutputStatus(value=val), index)
#         _log.debug(f"Updated outstation analog-output index: {index}, val: {val}")
#
#         return self.outstation_application.db_handler.db
#
#     @RPC.export
#     def outstation_apply_update_binary_input(self, val, index):
#         """public interface to update binary-input point value
#
#         val: bool
#         index: int, point index
#         """
#         if not isinstance(val, bool):
#             raise f"val of type(val) should be bool"
#         self.outstation_application.apply_update(opendnp3.Binary(value=val), index)
#         _log.debug(f"Updated outstation binary-input index: {index}, val: {val}")
#
#         return self.outstation_application.db_handler.db
#
#     @RPC.export
#     def outstation_apply_update_binary_output(self, val, index):
#         """public interface to update binary-output point value
#
#         val: bool
#         index: int, point index
#         """
#         if not isinstance(val, bool):
#             raise f"val of type(val) should be bool"
#         self.outstation_application.apply_update(opendnp3.BinaryOutputStatus(value=val), index)
#         _log.debug(f"Updated outstation binary-output index: {index}, val: {val}")
#
#         return self.outstation_application.db_handler.db
#
#     @RPC.export
#     def outstation_display_db(self):
#         return self.outstation_application.db_handler.db
#
#     def configure(self, config_name, action, contents):
#         """
#         # TODO: clean-up this bizarre method
#         """
#         config = self.default_config.copy()
#         config.update(contents)
#
#         _log.debug("Configuring Agent")
#
#         try:
#             setting1 = int(config["setting1"])
#             setting2 = str(config["setting2"])
#         except ValueError as e:
#             _log.error("ERROR PROCESSING CONFIGURATION: {}".format(e))
#             return
#
#         self.setting1 = setting1
#         self.setting2 = setting2
#
#         self._create_subscriptions(self.setting2)
#
#     def _create_subscriptions(self, topic):
#         """
#         Unsubscribe from all pub/sub topics and create a subscription to a topic in the configuration which triggers
#         the _handle_publish callback
#         """
#         self.vip.pubsub.unsubscribe("pubsub", None, None)
#
#         topic = "some/topic"
#         self.vip.pubsub.subscribe(peer='pubsub',
#                                   prefix=topic,
#                                   callback=self._handle_publish)
#
#     def _handle_publish(self, peer, sender, bus, topic, headers, message):
#         """
#         Callback triggered by the subscription setup using the topic from the agent's config file
#         """
#         _log.debug(f" ++++++handleer++++++++++++++++++++++++++"
#                    f"peer {peer}, sender {sender}, bus {bus}, topic {topic}, "
#                    f"headers {headers}, message {message}")
#
#     @Core.receiver("onstart")
#     def onstart(self, sender, **kwargs):
#         """
#         This is method is called once the Agent has successfully connected to the platform.
#         This is a good place to setup subscriptions if they are not dynamic or
#         do any other startup activities that require a connection to the message bus.
#         Called after any configurations methods that are called at startup.
#
#         Usually not needed if using the configuration store.
#         """
#
#         # for dnp3 outstation
#         self.outstation_application.start()
#
#         # Example publish to pubsub
#         # self.vip.pubsub.publish('pubsub', "some/random/topic", message="HI!")
#         #
#         # # Example RPC call
#         # # self.vip.rpc.call("some_agent", "some_method", arg1, arg2)
#         # pass
#         # self._create_subscriptions(self.setting2)
#
#
#     @Core.receiver("onstop")
#     def onstop(self, sender, **kwargs):
#         """
#         This method is called when the Agent is about to shutdown, but before it disconnects from
#         the message bus.
#         """
#         pass
#         self.outstation_application.shutdown()
#
#     # @RPC.export
#     # def rpc_demo_load_config(self):
#     #     """
#     #     RPC method
#     #
#     #     May be called from another agent via self.core.rpc.call
#     #     """
#     #     try:
#     #         config = utils.load_config("/home/kefei/project-local/volttron/TestAgent/config")
#     #     except Exception:
#     #         config = {}
#     #     return config
#
#     # @RPC.export
#     # def rpc_demo_config_list_set_get(self):
#     #     """
#     #     RPC method
#     #
#     #     May be called from another agent via self.core.rpc.call
#     #     """
#     #     default_config = {"setting1": "setting1-xxxxxxxxx",
#     #                       "setting2": "setting2-xxxxxxxxx"}
#     #
#     #     # Set a default configuration to ensure that self.configure is called immediately to setup
#     #     # the agent.
#     #     # self.vip.config.set_default("config", default_config)  # set_default can only be used before onstart
#     #     self.vip.config.set(config_name="config_2", contents=default_config,
#     #                         trigger_callback=False, send_update=True)
#     #     get_result = [
#     #         self.vip.config.get(config) for config in self.vip.config.list()
#     #     ]
#     #     return self.vip.config.list(), get_result
#
#     # @RPC.export
#     # def rpc_demo_config_set_default(self):
#     #     """
#     #     RPC method
#     #
#     #     May be called from another agent via self.core.rpc.call
#     #     """
#     #     default_config = {"setting1": "setting1-xxxxxxxxx",
#     #                       "setting2": "setting2-xxxxxxxxx"}
#     #
#     #     # Set a default configuration to ensure that self.configure is called immediately to setup
#     #     # the agent.
#     #     self.vip.config.set_default("config", default_config)
#     #     return self.vip.config.list()
#     #     # # Hook self.configure up to changes to the configuration file "config".
#     #     # self.vip.config.subscribe(self.configure, actions=["NEW", "UPDATE"], pattern="config")
#
#     # @RPC.export
#     # def rpc_demo_pubsub(self):
#     #     """
#     #     RPC method
#     #
#     #     May be called from another agent via self.core.rpc.call
#     #     """
#     #
#     #     # pubsub_list = self.vip.pubsub.list('pubsub', 'some/')
#     #     # list(self, peer, prefix='', bus='', subscribed=True, reverse=False, all_platforms=False)
#     #     # # return pubsub_list
#     #     self.vip.pubsub.publish('pubsub', 'some/topic/', message="+++++++++++++++++++++++++ something something")
#     #     # self.vip.pubsub.subscribe('pubsub', 'some/topic/', callable=self._handle_publish)
#     #     # return pubsub_list
#     #     # # Hook self.configure up to changes to the configuration file "config".
#     #     # self.vip.config.subscribe(self.configure, actions=["NEW", "UPDATE"], pattern="config")


def main():
    """Main method called to start the agent."""
    utils.vip_main(Dnp3Agent,
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
