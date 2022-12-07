# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}
import logging
import asyncio
import sys
import gevent

from pathlib import Path
from pprint import pformat

from typing import Callable, Dict
from volttron.platform.agent.utils import (
    get_aware_utc_now,
    setup_logging,
    format_timestamp,
    load_config,
    vip_main,
)
from volttron.platform.messaging import topics, headers
from volttron.platform.vip.agent import Agent, RPC
from .volttron_openadr_client import (
    VolttronOpenADRClient,
    OpenADREvent,
    OpenADRReportName,
    OpenADRMeasurements,
    OpenADROpt,
)

from .constants import (
    REQUIRED_KEYS,
    VEN_NAME,
    VTN_URL,
    DEBUG,
    CERT,
    KEY,
    PASSPHRASE,
    VTN_FINGERPRINT,
    SHOW_FINGERPRINT,
    CA_FILE,
    VEN_ID,
    DISABLE_SIGNATURE,
)

from openleadr.objects import Event

setup_logging()
_log = logging.getLogger(__name__)
__version__ = "1.0"


class OpenADRVenAgent(Agent):
    """This is class is a subclass of the Volttron Agent; it is an OpenADR VEN client and is a wrapper around OpenLEADR,
    an open-source implementation of OpenADR 2.0.b for both servers, VTN, and clients, VEN.
    This agent creates an instance of OpenLEADR's VEN client, which is used to communicated with a VTN.
    OpenADR (Automated Demand Response) is a standard for alerting and responding
    to the need to adjust electric power consumption in response to fluctuations in grid demand.
    OpenADR communications are conducted between Virtual Top Nodes (VTNs) and Virtual End Nodes (VENs).

    :param config_path: path to agent config
    """

    def __init__(self, config_path: str, **kwargs) -> None:
        # adding 'fake_ven_client' to support dependency injection and preventing call to super class for unit testing
        if kwargs.get("fake_ven_client"):
            self.ven_client = kwargs["fake_ven_client"]
        else:
            self.ven_client: VolttronOpenADRClient
            super(OpenADRVenAgent, self).__init__(enable_web=True, **kwargs)

        self.default_config = self._parse_config(config_path)

        # SubSystem/ConfigStore
        self.vip.config.set_default("config", self.default_config)
        self.vip.config.subscribe(
            self._configure_ven_client,
            actions=["NEW", "UPDATE"],
            pattern="config",
        )

    def _configure_ven_client(
        self, config_name: str, action: str, contents: Dict
    ) -> None:
        """Initializes the agent's configuration, creates and starts VolttronOpenADRClient.

        :param config_name:
        :param action: the action
        :param contents: the configuration used to update the agent's configuration
        """
        config = self.default_config.copy()
        config.update(contents)

        _log.info(f"config_name: {config_name}, action: {action}")
        _log.info(f"Configuring VEN client with: \n {pformat(config)} ")

        self.ven_client = VolttronOpenADRClient.build_client(config)

        # Add event handling capability to the client
        # if you want to add more handlers on a specific event, you must create a coroutine in this class
        # and then add it as the second input for 'self.ven_client.add_handler(<some event>, <coroutine>)'
        self.ven_client.add_handler("on_event", self.handle_event)

        _log.info("Starting OpenADRVen agent...")
        gevent.spawn_later(3, self._start_asyncio_loop)

    def _start_asyncio_loop(self) -> None:
        loop = asyncio.get_event_loop()
        loop.create_task(self.ven_client.run())
        loop.run_forever()

    # ***************** Methods for Servicing VTN Requests ********************

    async def handle_event(self, event: Event) -> OpenADROpt:
        """Publish event to the Volttron message bus. This coroutine will be called when there is an event to be handled.

        :param event: The event sent from a VTN
        :return: Message to VTN to opt in to the event.
        """
        openadr_event = OpenADREvent(event)
        try:
            _log.info(
                f"Received event. Processing event now...\n Event signal:\n {pformat(openadr_event.get_event_signals())}"
            )
        except IndexError as e:
            _log.debug(
                f"Event signals is empty. {e} \n Showing whole event: {pformat(openadr_event)}"
            )
            pass

        self.publish_event(openadr_event)

        return OpenADROpt.OPT_IN

    @RPC.export
    def add_report_capability(
        self,
        callback: Callable,
        report_name: OpenADRReportName,
        resource_id: str,
        measurement: OpenADRMeasurements,
    ) -> tuple:
        """Add a new reporting capability to the client.

        This method is remotely accessible by other agents through Volttron's feature Remote Procedure Call (RPC);
        for reference on RPC, see https://volttron.readthedocs.io/en/develop/platform-features/message-bus/vip/vip-json-rpc.html?highlight=remote%20procedure%20call

        :param callback: A callback or coroutine that will fetch the value for a specific report. This callback will be passed the report_id and the r_id of the requested value.
        :param report_name: An OpenADR name for this report
        :param resource_id: A specific name for this resource within this report.
        :param measurement: The quantity that is being measured
        :return: Returns a tuple consisting of a report_specifier_id (str) and an r_id (str) an identifier for OpenADR messages
        """
        report_specifier_id, r_id = self.ven_client.add_report(
            callback=callback,
            report_name=report_name,
            resource_id=resource_id,
            measurement=measurement,
        )
        _log.info(
            f"Output from add_report: report_specifier_id: {report_specifier_id}, r_id: {r_id}"
        )
        return report_specifier_id, r_id

    # ***************** VOLTTRON Pub/Sub Requests ********************
    def publish_event(self, event: OpenADREvent) -> None:
        """Publish an event to the Volttron message bus. When an event is created/updated, it is published to the VOLTTRON bus with a topic that includes 'openadr/event_update'.

        :param event: The Event received from the VTN
        """
        # OADR rule 6: If testEvent is present and != "false", handle the event as a test event.
        try:
            if event.isTestEvent():
                _log.debug("Suppressing publication of test event")
                return
        except KeyError as e:
            _log.debug(f"Key error: {e}")
            pass

        _log.debug(f"Publishing real/non-test event \n {pformat(event)}")
        self.vip.pubsub.publish(
            peer="pubsub",
            topic=f"{topics.OPENADR_EVENT}/{self.ven_client.get_ven_name()}",
            headers={headers.TIMESTAMP: format_timestamp(get_aware_utc_now())},
            message=event.parse_event(),
        )

        return

    # ***************** Helper methods ********************
    def _parse_config(self, config_path: str) -> Dict:
        """Parses the OpenADR agent's configuration file.

        :param config_path: The path to the configuration file
        :return: The configuration
        """
        try:
            config = load_config(config_path)
        except NameError as err:
            _log.exception(err)
            raise
        except Exception as err:
            _log.error("Error loading configuration: {}".format(err))
            config = {}

        if not config:
            raise Exception("Configuration cannot be empty.")

        req_keys_actual = {k: "" for k in REQUIRED_KEYS}
        for required_key in REQUIRED_KEYS:
            key_actual = config.get(required_key)
            self._check_required_key(required_key, key_actual)
            req_keys_actual[required_key] = key_actual

        # optional configurations
        cert = config.get(CERT)
        if cert:
            cert = str(Path(cert).expanduser().resolve(strict=True))
        key = config.get(KEY)
        if key:
            key = str(Path(key).expanduser().resolve(strict=True))
        ca_file = config.get(CA_FILE)
        if ca_file:
            ca_file = str(Path(ca_file).expanduser().resolve(strict=True))
        debug = config.get(DEBUG)
        ven_name = config.get(VEN_NAME)
        vtn_url = config.get(VTN_URL)
        passphrase = config.get(PASSPHRASE)
        vtn_fingerprint = config.get(VTN_FINGERPRINT)
        show_fingerprint = bool(config.get(SHOW_FINGERPRINT, True))
        ven_id = config.get(VEN_ID)
        disable_signature = bool(config.get(DISABLE_SIGNATURE))

        return {
            VEN_NAME: ven_name,
            VTN_URL: vtn_url,
            DEBUG: debug,
            CERT: cert,
            KEY: key,
            PASSPHRASE: passphrase,
            VTN_FINGERPRINT: vtn_fingerprint,
            SHOW_FINGERPRINT: show_fingerprint,
            CA_FILE: ca_file,
            VEN_ID: ven_id,
            DISABLE_SIGNATURE: disable_signature,
        }

    def _check_required_key(self, required_key: str, key_actual: str) -> None:
        """Checks if the given key and its value are required by this agent

        :param required_key: the key that is being checked
        :param key_actual: the key value being checked
        :raises KeyError:
        """
        if required_key == VEN_NAME and not key_actual:
            raise KeyError(f"{VEN_NAME} is required.")
        elif required_key == VTN_URL and not key_actual:
            raise KeyError(
                f"{VTN_URL} is required. Ensure {VTN_URL} is given a URL to the VTN."
            )
        return


def main():
    """Main method called to start the agent."""
    vip_main(OpenADRVenAgent)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
