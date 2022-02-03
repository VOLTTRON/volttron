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

from abc import ABC
from functools import partial
from lxml import etree

from openleadr.client import OpenADRClient
from openleadr.preflight import preflight_message
from openleadr.messaging import TEMPLATES, SIGNER, _create_replay_protect
from openleadr import utils, enums

from volttron.platform.agent.utils import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


class OpenADRClientBase(OpenADRClient, ABC):
    """
        The Volttron OpenADR VEN agent uses the python library OpenLEADR https://github.com/openleadr/openleadr-python to create
        an OpenADR VEN client. OpenADRClientBase is extended from OpenLEADR's OpenADRClient, giving us the flexibility
        to connect to any implementation of an OpenADR VTN. For example, to connect to an IPKeys VTN that was implemented
        on an old OpenADR protocol, the IPKeysClient subclass was created so that it can successfully connect to an IPKeys VTN.

        If you have a specific VTN that you want to connect to and require further customization of the OpenADRVEN client, create your
        own OpenADRClient by extending the base class OpenADRClientBase, updating your client with your business logic, and putting that subclass in this module.
    """

    def __init__(self, ven_name, vtn_url, disable_signature=False, **kwargs):
        """
        Initializes a new OpenADR Client (Virtual End Node)

        :param str ven_name: The name for this VEN
        :param str vtn_url: The URL of the VTN (Server) to connect to
        :param bool: The boolean flag to disable signatures on messages
        """
        super().__init__(ven_name, vtn_url, **kwargs)
        self.disable_signature = disable_signature


class IPKeysClient(OpenADRClientBase, ABC):
    def __init__(self, ven_name, vtn_url, disable_signature, **kwargs):
        """
        Initializes a new OpenADR Client (Virtual End Node)

        :param str ven_name: The name for this VEN
        :param str vtn_url: The URL of the VTN (Server) to connect to
        :param bool: The boolean flag to disable signatures on messages
        """
        super().__init__(ven_name, vtn_url, disable_signature, **kwargs)

        self._create_message = partial(
            self.create_message_ipkeys,
            cert=self.cert_path,
            key=self.key_path,
            passphrase=self.passphrase,
            disable_signature=self.disable_signature,
        )

    async def _on_event(self, message):
        """
        :param message dict: dictionary containing event information
        """
        logger.debug("The VEN received an event")
        events = message["events"]
        try:
            results = []

            for event in message["events"]:
                event_id = event["event_descriptor"]["event_id"]
                event_status = event["event_descriptor"]["event_status"]
                modification_number = event["event_descriptor"][
                    "modification_number"
                ]
                received_event = utils.find_by(
                    self.received_events, "event_descriptor.event_id", event_id
                )

                if received_event:
                    if (
                        received_event["event_descriptor"][
                            "modification_number"
                        ]
                        == modification_number
                    ):
                        # Re-submit the same opt type as we already had previously
                        result = self.responded_events[event_id]
                    else:
                        # Replace the event with the fresh copy
                        utils.pop_by(
                            self.received_events,
                            "event_descriptor.event_id",
                            event_id,
                        )
                        self.received_events.append(event)
                        # Wait for the result of the on_update_event handler
                        result = await utils.await_if_required(
                            self.on_update_event(event)
                        )
                else:
                    # Wait for the result of the on_event
                    self.received_events.append(event)
                    result = self.on_event(event)
                if asyncio.iscoroutine(result):
                    result = await result
                results.append(result)
                if (
                    event_status
                    in (
                        enums.EVENT_STATUS.COMPLETED,
                        enums.EVENT_STATUS.CANCELLED,
                    )
                    and event_id in self.responded_events
                ):
                    self.responded_events.pop(event_id)
                else:
                    self.responded_events[event_id] = result
            for i, result in enumerate(results):
                if (
                    result not in ("optIn", "optOut")
                    and events[i]["response_required"] == "always"
                ):
                    logger.error(
                        "Your on_event or on_update_event handler must return 'optIn' or 'optOut'; "
                        f"you supplied {result}. Please fix your on_event handler."
                    )
                    results[i] = "optOut"
        except Exception as err:
            logger.error(
                "Your on_event handler encountered an error. Will Opt Out of the event. "
                f"The error was {err.__class__.__name__}: {str(err)}"
            )
            results = ["optOut"] * len(events)

        event_responses = [
            {
                "response_code": 200,
                "response_description": "OK",
                "opt_type": results[i],
                "request_id": message["request_id"],
                "modification_number": events[i]["event_descriptor"][
                    "modification_number"
                ],
                "event_id": events[i]["event_descriptor"]["event_id"],
            }
            for i, event in enumerate(events)
            if event["response_required"] == "always"
            and not utils.determine_event_status(event["active_period"])
            == "completed"
        ]

        if len(event_responses) > 0:
            response = {
                "response_code": 200,
                "response_description": "OK",
                "request_id": message["request_id"],
            }
            message = self._create_message(
                "oadrCreatedEvent",
                response=response,
                event_responses=event_responses,
                ven_id=self.ven_id,
            )
            service = "EiEvent"
            response_type, response_payload = await self._perform_request(
                service, message
            )
            logger.info(response_type, response_payload)
        else:
            logger.info(
                "Not sending any event responses, because a response was not required/allowed by the VTN."
            )

    @staticmethod
    def create_message_ipkeys(
        message_type,
        cert=None,
        key=None,
        passphrase=None,
        disable_signature=False,
        **message_payload,
    ):
        """
        Create and optionally sign an OpenADR message. Returns an XML string.

        :param message_type string: The type of message you are sending
        :param str cert: The path to a PEM-formatted Certificate file to use
                         for signing messages.
        :param str key: The path to a PEM-formatted Private Key file to use
                        for signing messages.
        :param str passphrase: The passphrase for the Private Key
        :param bool: The boolean flag to disable signatures on messages
        """
        message_payload = preflight_message(message_type, message_payload)
        template = TEMPLATES.get_template(f"{message_type}.xml")
        signed_object = utils.flatten_xml(template.render(**message_payload))
        envelope = TEMPLATES.get_template("oadrPayload.xml")
        if cert and key and not disable_signature:
            tree = etree.fromstring(signed_object)
            signature_tree = SIGNER.sign(
                tree,
                key=key,
                cert=cert,
                passphrase=utils.ensure_bytes(passphrase),
                reference_uri="#oadrSignedObject",
                signature_properties=_create_replay_protect(),
            )
            signature = etree.tostring(signature_tree).decode("utf-8")
        else:
            signature = None
        msg = envelope.render(
            template=f"{message_type}",
            signature=signature,
            signed_object=signed_object,
        )
        return msg


def openadr_clients():
    """
        Returns a dictionary in which the keys are the class names of OpenADRClientBase subclasses and the values are the subclass objects.
        For example:

        { "IPKeysClient": IPKeysClient }
    """
    clients = {}
    children = [OpenADRClient]
    while children:
        parent = children.pop()
        for child in parent.__subclasses__():
            child_name = child.__name__
            if child_name not in clients:
                clients[child_name] = child
                children.append(child)
    return clients
