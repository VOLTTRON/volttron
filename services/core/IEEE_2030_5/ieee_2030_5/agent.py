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

import logging
import sys
from datetime import datetime
from pathlib import Path
from pprint import pformat
from typing import Dict

import ieee_2030_5.models as m
from ieee_2030_5 import AllPoints
from ieee_2030_5.client import IEEE2030_5_Client

try:    # for modular
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
        self._pin = config['pin']
        self._subscriptions = config["subscriptions"]
        self._server_hostname = config["server_hostname"]
        self._server_ssl_port = config.get("server_ssl_port", 443)
        self._server_http_port = config.get("server_http_port", None)
        self._mirror_usage_point_list = config.get("MirrorUsagePointList", [])
        self._der_capabilities_info = config.get("DERCapability")
        self._der_settings_info = config.get("DERSettings")
        self._der_status_info = config.get("DERStatus")
        self._default_config = {
            "subscriptions": self._subscriptions,
            "MirrorUsagePointList": self._mirror_usage_point_list
        }
        self._server_usage_points: m.UsagePointList
        self._client = IEEE_2030_5_Client(cafile=self._cacertfile,
                                          server_hostname=self._server_hostname,
                                          keyfile=self._keyfile,
                                          certfile=self._certfile,
                                          server_ssl_port=self._server_ssl_port,
                                          pin=self._pin)

        # Hook up events so we can respond to them appropriately
        self._client.der_control_event_started(self._control_event_started)
        self._client.der_control_event_ended(self._control_event_ended)

        self._client.start()
        _log.info(self._client.enddevice)
        assert self._client.enddevice
        self._point_to_reading_set: Dict[str, str] = {}
        self._mirror_usage_points: Dict[str, m.MirrorUsagePoint] = {}
        self._mup_readings: Dict[str, m.MirrorMeterReading] = {}
        self._mup_pollRate: int = 60
        self._times_published: Dict[str, int] = {}

        # Set a default configuration to ensure that self.configure is called immediately to setup
        # the agent.
        self.vip.config.set_default("config", self._default_config)
        # Hook self.configure up to changes to the configuration file "config".
        self.vip.config.subscribe(self.configure, actions=["NEW", "UPDATE"], pattern="config")

    @RPC.export
    def update_der_settings(self, href: str, new_settings: m.DERSettings) -> int:
        resp = self._client.put_der_settings(href, new_settings)
        return resp

    @RPC.export
    def update_der_availability(self, href: str, new_availability: m.DERAvailability) -> int:
        resp = self._client.put_der_availability(href, new_availability)
        return resp

    @RPC.export
    def update_der_status(self, href: str, new_availability: m.DERAvailability) -> int:
        resp = self._client.put_der_status(href, new_availability)
        return resp

    @RPC.export
    def get_der_references(self) -> List[str]:
        return self._client.get_der_hrefs()

    def _control_event_started(self, sender, **kwargs):
        _log.debug(f"Control event started {kwargs}")

    def _control_event_ended(self, sender, **kwargs):
        _log.debug(f"Control event ended {kwargs}")

    def dcap_updated(self, sender):
        _log.debug(f"Dcap was updated by {sender}")

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
            new_usage_points: Dict[str, m.MirrorUsagePoint] = {}

            for mup in config.get("MirrorUsagePointList", []):
                subscription_point = mup.pop('subscription_point')
                new_usage_points[mup['mRID']] = m.MirrorUsagePoint(**mup)
                new_usage_points[mup['mRID']].deviceLFDI = self._client.lfdi
                new_usage_points[mup['mRID']].MirrorMeterReading = []
                new_usage_points[mup['mRID']].MirrorMeterReading.append(
                    m.MirrorMeterReading(**mup['MirrorMeterReading']))
                mup['subscription_point'] = subscription_point

        except ValueError as e:
            _log.error("ERROR PROCESSING CONFIGURATION: {}".format(e))
            return

        for sub in self._subscriptions:
            self.vip.pubsub.unsubscribe(peer="pubsub", prefix=sub, callback=self._data_published)

        self._subscriptions = subscriptions

        self._mup_readings.clear()
        self._mirror_usage_points.clear()

        ed = self._client.end_device
        self._mirror_usage_points.update(new_usage_points)
        server_usage_points = self._client.mirror_usage_point_list()
        self._mup_pollRate = server_usage_points.pollRate if server_usage_points.pollRate else self._mup_pollRate

        for mup in self._mirror_usage_points.values():
            try:
                found = next(
                    filter(lambda x: x.mRID == mup.mRID, server_usage_points.MirrorUsagePoint))
            except StopIteration:
                # TODO Create new usage point
                location = self._client.create_mirror_usage_point(mup)
                mup_reading = m.MirrorMeterReading(
                    mRID=mup.MirrorMeterReading[0].mRID,
                    href=location,
                    description=mup.MirrorMeterReading[0].description)
                rs = m.MirrorReadingSet(mRID=mup_reading.mRID + "1",
                                        timePeriod=m.DateTimeInterval())
                rs.timePeriod.start = int(round(datetime.utcnow().timestamp()))
                rs.timePeriod.duration = self._mup_pollRate

                # new mrid is based upon the mirror reading.
                mup_reading.MirrorReadingSet.append(rs)
                rs.Reading = []

                self._mup_readings[mup_reading.mRID] = mup_reading

        self._server_usage_points = self._client.mirror_usage_point_list()

        for sub in self._subscriptions:
            self.vip.pubsub.subscribe(peer="pubsub", prefix=sub, callback=self._data_published)

    def _data_published(self, peer, sender, bus, topic, headers, message):
        """
        Callback triggered by the subscription setup using the topic from the agent's config file
        """
        _log.debug("DATA Published")
        points = AllPoints.frombus(message)

        _log.debug(points)

        for index, pt in enumerate(self._mirror_usage_point_list):
            if pt["subscription_point"] in points.points:
                reading_mRID = pt["MirrorMeterReading"]['mRID']
                reading = self._mup_readings[reading_mRID]
                for rs_index, rs in enumerate(reading.MirrorReadingSet):
                    rs = reading.MirrorReadingSet[rs_index]
                    rs.Reading.append(m.Reading(value=points.points[pt["subscription_point"]]))
                    start = rs.timePeriod.start
                    if start + self._mup_pollRate * 1000 > int(round(
                            datetime.utcnow().timestamp())):
                        self._times_published[reading_mRID] = self._times_published.get(
                            reading_mRID, 0) + 1
                        rs.mRID = "_".join(
                            [reading_mRID, str(self._times_published[reading_mRID])])

                        new_reading_href = self._client.post_mirror_reading(reading)
                        _log.debug(f"New readings available: {new_reading_href}")
                        rs.Reading.clear()
                        rs.timePeriod.start = int(round(datetime.utcnow().timestamp()))
                        rs.timePeriod.duration = self._mup_pollRate

        _log.debug(points.__dict__)


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
