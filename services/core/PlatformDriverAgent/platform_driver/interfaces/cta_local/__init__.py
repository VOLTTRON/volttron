# Copyright (c) 2019, ACE IoT Solutions LLC.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.

"""
The Venstar  Driver allows control and monitoring of Venstar Thermostats via an HTTP API
"""

import atexit
import logging
import gevent
import time
import json
from enum import Enum
from paho.mqtt import client as mqtt

from volttron.platform.agent import utils
from platform_driver.interfaces import BaseRegister, BaseInterface, BasicRevert
from volttron.platform.vip.agent import Agent, Core, RPC, PubSub
from .cta_resources import CTA2045Parser
from .cta_resources import WH_EVENT_STATE_MAP

_log = logging.getLogger("skycentrics_local")

class EventStates(str, Enum):
    """
    Enumeration class for DER event states
    While this is a string enumeration, we're using it
    as an integer enum as well, so ordering must be preserved, new states
    must be defined at the end of the list.
    """

    NOT_STARTED = "NOT_STARTED"
    PRE_EVENT = "PRE_EVENT"
    CURTAILED = "CURTAILED"
    POST_EVENT = "POST_EVENT"
    ENDED = "ENDED"
    CANCELLED = "CANCELLED"
    OPTED_OUT = "OPTED_OUT"
    IDLE = "IDLE"

WH_MQTT_PUBLISH_STATES = ["EndShed", "LoadUp", "Shed"]

class Register(BaseRegister):
    """
    Generic class for containing information about the points exposed by the Venstar API


    :param register_type: Type of the register. Either "bit" or "byte". Usually "byte".
    :param pointName: Name of the register.
    :param units: Units of the value of the register.
    :param description: Description of the register.

    :type register_type: str
    :type pointName: str
    :type units: str
    :type description: str

    The TED Meter Driver does not expose the read_only parameter, as the TED API does not
    support writing data.
    """

    def __init__(self, volttron_point_name, units, description):
        super(Register, self).__init__(
            "byte", True, volttron_point_name, units, description=description
        )


class Interface(BasicRevert, BaseInterface):
    """Create an interface for the Venstar Thermostat using the standard BaseInterface convention"""

    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)
        _log.info("Initializing CTA Local Interface")
        self.device_path = kwargs.get("device_path")
        self.logger = _log
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.current_data_buffer = {}
        self.current_registers = []
        self.device_mac = ""

        self.mqtt_loop = gevent.spawn(self.mqtt_client_thread)
        _log.debug("starting mqtt loop thread")
        self.mqtt_loop.start()
        atexit.register(self.mqtt_loop.kill)

    def configure(self, config_dict, registry_config_str):
        """Configure method called by the platform driver with configuration
        stanza and registry config file
        """
        if not config_dict.get("device_mac"):
            raise ValueError("Missing device_mac in config")
        self.device_mac = config_dict.get("device_mac")
        for entry in self.current_data_buffer.keys():
            if entry == "name":
                continue
            _log.debug(f"inserting register {entry=}")
            self.insert_register(Register(entry, "", ""))

    def _create_registers(self, ted_config):
        """
        Processes the config scraped from the device and generates
        register for each available parameter
        """
        return

    def set_multiple_points(self, path, points_tuple: tuple, **kwargs): # pylint: disable=W0221:arguments-differ
        """
        Set or unset water heater curtailment mode
        """
        try:
            points = {"wh_state": points_tuple[0],
                      "duration": points_tuple[1]}
        except IndexError:
            _log.error(f"missing required points: {points_tuple=}")
            return
        if points['wh_state'] not in EventStates.__members__:
            _log.error(f"invalid wh_state: {points['wh_state']=}")
            return

        self.set_wh_status(path, points["wh_state"], points["duration"])

    def _set_point(self, point_name, value):
        if point_name == "wh_state" and value == "normal":
            self.set_multiple_points((point_name, 0))
        else:
            _log.error(f"trying to set to mode {point_name} with no duration")

    def mqtt_client_thread(self):
        self.client.connect("localhost", 1883)
        while True:
            self.client.loop()
            gevent.sleep(0.5)

    def get_point(self, point_name):
        """Get specified point"""
        points = self._scrape_all()
        return points.get(point_name)

    def on_connect(self, client, data, flags, rc):
        """Run when MQTT client initially connects"""
        _log.info("Connected to MQTT broker")
        self.client.subscribe("#")

    def on_message(self, client, data, message):
        """
        Continuously listen for messages from the MQTT broker
        """
        required_data = {}
        payload = CTA2045Parser.process_received_packet(message.payload)
        _log.debug(f"{payload=}")
        if not payload or not payload.get("GetCommodityReadReply", {}):
            return
        if payload.get("GetCommodityReadReply", {}).get("resp_code") != 0:
            _log.error(
                f"Error in payload: {payload.get('GetCommodityReadReply', {}).get('resp_code')}"
            )
            return {}
        for commodity in payload["GetCommodityReadReply"]["commodities"].values():
            print(f"{commodity=}")
            if commodity["name"] == "Electricity Consumed":
                required_data["electricity_consumed_instantaneous_rate"] = commodity[
                    "instantaneous_rate"
                ]
                required_data["electricity_consumed_cumulative_amount"] = commodity[
                    "cumulative_amount"
                ]
            if commodity["name"] == "Total Energy Storage/Take Capacity":
                required_data["total_energy_storage_instantaneous"] = commodity[
                    "instantaneous_rate"
                ]
                required_data["total_energy_storage_cumulative"] = commodity[
                    "cumulative_amount"
                ]
            if commodity["name"] == "Present Energy Storage/Take Capacity":
                required_data["present_energy_storage_instantaneous"] = commodity[
                    "instantaneous_rate"
                ]
                required_data["present_energy_storage_cumulative"] = commodity[
                    "cumulative_amount"
                ]

        self.current_data_buffer.update(required_data)
        for entry in self.current_data_buffer:
            if entry not in self.current_registers:
                _log.debug(f"inserting register {entry=}")
                self.insert_register(Register(entry, "", ""))
                self.current_registers.append(entry)

        # return payload
        return {}

    def set_wh_status(self, path, wh_state, duration):
        """Set curtailment"""
        _log.debug(f"setting water heater event mode to {wh_state} for {duration} seconds")
        mqtt_topic = f"devices/{self.device_mac}/ctl/shedLoad"
        # TODO: add the water heater index (wh0, wh1 etc) to the topic
        ace_client = path.split("/")[0]
        ace_site_name = path.split("/")[1]
        wh_index = path.split("/")[2]
        vtron_topic = f"devices/{ace_client}/{ace_site_name}/{wh_index}/all"
        mqtt_message = CTA2045Parser.build_event_duration_message(wh_state, duration)
        vtron_message = [{
            "requested_mode": WH_MQTT_PUBLISH_STATES.index(WH_EVENT_STATE_MAP[wh_state]),
            "requested_duration": duration
        }]
        self.client.publish(mqtt_topic, mqtt_message)
        _log.debug(f"publishing to {vtron_topic} with {vtron_message}")
        self.vip.pubsub.publish("pubsub", topic=vtron_topic, message=vtron_message)
        return {}

    def get_data(self):
        data = self.current_data_buffer
        self.current_data_buffer = {}
        return data

    def _scrape_all(self):
        data = self.get_data()
        _log.debug(f"{data=}")
        return data
