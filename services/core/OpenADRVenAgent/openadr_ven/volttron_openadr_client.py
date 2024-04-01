# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
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
#
# ===----------------------------------------------------------------------===
# }}}


from openleadr.client import OpenADRClient
from openleadr.objects import Event
from volttron.platform import jsonapi
import abc

from .constants import (
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
from openleadr.enums import OPT, REPORT_NAME, MEASUREMENTS
from datetime import timedelta, datetime, date, time, timezone
from typing import Callable
from volttron.platform.agent.utils import format_timestamp


class OpenADRReportName(REPORT_NAME):
    def __init__(self):
        super.__init__()


class OpenADRMeasurements(MEASUREMENTS):
    def __init__(self):
        super.__init__()


class OpenADROpt(OPT):
    def __init__(self):
        super.__init__()


class OpenADREvent:
    def __init__(self, event: Event):
        self.event = event

    def get_event_signals(self):
        return self.event.get("event_signals")[0]

    def isTestEvent(self):
        return self.event["event_descriptor"]["test_event"]

    def parse_event(self) -> Event:
        """Parse event so that it properly displays on message bus.

        :param obj: The event received from a VTN
        :return: A deserialized Event that is converted into a python object
        """

        # function that gets called for objects that can’t otherwise be serialized.
        def _default_serialzer(x):
            if isinstance(x, timedelta):
                return int(x.total_seconds())
            elif isinstance(x, datetime):
                return format_timestamp(x)
            elif isinstance(x, date):
                return x.isoformat()
            elif isinstance(x, time):
                return x.isoformat()
            elif isinstance(x, timezone):
                return int(x.utcoffset().total_seconds())
            else:
                return None

        obj_string = jsonapi.dumps(self.event, default=_default_serialzer)
        return jsonapi.loads(obj_string)


class OpenADRClientInterface(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def run(self):
        pass

    @abc.abstractmethod
    def get_ven_name(self):
        pass

    @abc.abstractmethod
    def add_handler(self, event: OpenADREvent, function):
        pass

    @abc.abstractmethod
    def add_report(
        self,
        callback: Callable,
        report_name: OpenADRReportName,
        resource_id: str,
        measurement: OpenADRMeasurements,
    ):
        pass


class VolttronOpenADRClient(OpenADRClientInterface):
    def __init__(self, openadr_client: OpenADRClient) -> None:
        self._openadr_client = openadr_client

    @staticmethod
    def build_client(config):
        # Creates a VEN client using openleadr library
        return VolttronOpenADRClient(
            OpenADRClient(
                config.get(VEN_NAME),
                config.get(VTN_URL),
                debug=config.get(DEBUG),
                cert=config.get(CERT),
                key=config.get(KEY),
                passphrase=config.get(PASSPHRASE),
                vtn_fingerprint=config.get(VTN_FINGERPRINT),
                show_fingerprint=config.get(SHOW_FINGERPRINT, True),
                ca_file=config.get(CA_FILE),
                ven_id=config.get(VEN_ID),
                disable_signature=config.get(DISABLE_SIGNATURE),
            )
        )

    ##### Abstract methods implemented#####
    async def run(self):
        await self._openadr_client.run()

    def get_ven_name(self):
        self._openadr_client.ven_name

    def add_handler(self, event, function):
        self._openadr_client.add_handler(event, function)

    def add_report(self, callback, report_name, resource_id, measurement):
        self._openadr_client.add_report(callback, report_name, resource_id, measurement)
