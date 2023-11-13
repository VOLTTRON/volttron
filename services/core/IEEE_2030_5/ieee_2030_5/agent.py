# Copyright 2022 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
from __future__ import annotations

import datetime
import logging
import sys
from pathlib import Path
from pprint import pformat

from ieee_2030_5 import AllPoints
from ieee_2030_5.client import IEEE2030_5_Client

try:  # for modular
    from volttron import utils
    from volttron.client.messaging.health import STATUS_GOOD
    from volttron.client.vip.agent import RPC, Agent, Core, PubSub
    from volttron.client.vip.agent.subsystems.query import Query
    from volttron.utils.commands import vip_main
except ImportError:
    from volttron.platform.agent import utils
    from volttron.platform.agent.utils import vip_main
    from volttron.platform.vip.agent import RPC, Agent, Core, PubSub
    from volttron.platform.vip.agent.subsystems.query import Query

# from . import __version__
__version__ = "0.1.0"

# Setup logging so that it runs within the platform
utils.setup_logging()

# The logger for this agent is _log and can be used throughout this file.
_log = logging.getLogger(__name__)


class IEEE_2030_5_Agent(Agent):
    """
    IEEE_2030_5_Agent
    """

    def __init__(self, config_path: str, **kwargs):
        super().__init__(**kwargs)
        _log.debug("vip_identity: " + self.core.identity)

        config = utils.load_config(config_path)

        self._cacertfile = Path(config['cacertfile']).expanduser()
        self._keyfile = Path(config['keyfile']).expanduser()
        self._certfile = Path(config['certfile']).expanduser()
        self._subscriptions = config["subscriptions"]
        self._server_hostname = config["server_hostname"]
        self._server_ssl_port = config.get("server_ssl_port", 443)
        self._server_http_port = config.get("server_http_port", None)
        self._default_config = {"subscriptions": self._subscriptions}

        self._client = IEEE2030_5_Client(cafile=self._cacertfile,
                                         server_hostname=self._server_hostname,
                                         keyfile=self._keyfile,
                                         certfile=self._certfile,
                                         server_ssl_port=self._server_ssl_port)

        # Set a default configuration to ensure that self.configure is called immediately to setup
        # the agent.
        self.vip.config.set_default("config", self._default_config)
        # Hook self.configure up to changes to the configuration file "config".
        self.vip.config.subscribe(self.configure,
                                  actions=["NEW", "UPDATE"],
                                  pattern="config")

    def configure(self, config_name, action, contents):
        """
        Called after the Agent has connected to the message bus. If a configuration exists at startup
        this will be called before onstart.

        Is called every time the configuration in the store changes.
        """
        config = self._default_config.copy()
        config.update(contents)

        _log.debug("Configuring Agent")

        try:
            subscriptions = config['subscriptions']
        except ValueError as e:
            _log.error("ERROR PROCESSING CONFIGURATION: {}".format(e))
            return

        for sub in self._subscriptions:
            _log.info(f"Removing subscription: {sub}")
            self.vip.pubsub.unsubscribe(peer="pubsub",
                                        prefix=sub,
                                        callback=self._data_published)

        self._subscriptions = subscriptions

        for sub in self._subscriptions:
            _log.info(f"Subscribing to: {sub}")
            self.vip.pubsub.subscribe(peer="pubsub",
                                      prefix=sub,
                                      callback=self._data_published)

    def _data_published(self, peer, sender, bus, topic, headers, message):
        """
        Callback triggered by the subscription setup using the topic from the agent's config file
        """
        points = AllPoints.frombus(message)
        _log.debug(points.__dict__)

    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        """
        This is method is called once the Agent has successfully connected to the platform.
        This is a good place to setup subscriptions if they are not dynamic or
        do any other startup activities that require a connection to the message bus.
        Called after any configurations methods that are called at startup.

        Usually not needed if using the configuration store.
        """
        # Example publish to pubsub
        # self.vip.pubsub.publish('pubsub', "some/random/topic", message="HI!")

        # Example RPC call
        # self.vip.rpc.call("some_agent", "some_method", arg1, arg2)
        pass

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

        May be called from another agent via self.vip.rpc.call
        """
        return self.setting1 + arg1 - arg2

    @PubSub.subscribe('pubsub', '', all_platforms=True)
    def on_match(self, peer, sender, bus, topic, headers, message):
        """Use match_all to receive all messages and print them out."""
        _log.debug(
            "Peer: {0}, Sender: {1}:, Bus: {2}, Topic: {3}, Headers: {4}, "
            "Message: \n{5}".format(peer, sender, bus, topic, headers,
                                    pformat(message)))


def main():
    """
    Main method called during startup of agent.
    :return:
    """
    try:
        vip_main(IEEE_2030_5_Agent, version=__version__)
    except Exception as e:
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
