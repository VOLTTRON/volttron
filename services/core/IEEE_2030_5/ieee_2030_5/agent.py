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
from dataclasses import dataclass, field

import logging
import sys
from datetime import datetime
from pathlib import Path
from pprint import pformat
from typing import Any, Dict, List

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

# These items are global for the agent and will periodically be
# sent to the 2030.5 server based upon the post interval.
DER_SETTINGS = m.DERSettings()
DER_CAPABILITIES = m.DERCapability()
# This is used for default control and control events.
DER_CONTROL_BASE = m.DERControlBase()
# Used for sending status message to the 2030.5 server.
DER_STATUS = m.DERStatus()


@dataclass
class MappedPoint:
    """The MappedPoint class models the mapping points.
    
    The MappedPoint class allows mapping of points from/to the platform.driver and
    2030.5 objects.
    
    Only points that have point_on_bus and parameter_type will be mapped.
    
    The format of the parameter_type is <object>::<property> where object is one of
    DERSettings, DERCapability, DERControlBase, or DERStatus.  The property must be
    a valid property of the object.
    """

    point_on_bus: str
    description: str
    multiplier: int
    mrid: str
    writable: bool
    parameter_type: str
    notes: str
    parent_object: object = None
    parameter: str = None
    value_2030_5: Any = None
    changed: bool = False

    def reset_changed(self):
        self.changed = False

    def set_value(self, value: Any):
        current_value = getattr(self.parent_object, self.parameter)
        if value != current_value:
            setattr(self.parent_object, self.parameter, value)
            self.changed = True

    def __post_init__(self):
        params = self.parameter_type.split("::")

        # Only if we have a proper object specifier that we know about
        if len(params) == 2:
            if params[0] == 'DERSettings':
                self.parent_object = DER_SETTINGS
            elif params[0] == 'DERCapability':
                self.parent_object = DER_CAPABILITIES
            elif params[0] == 'DERControlBase':
                self.parent_object = DER_CONTROL_BASE
            elif params[0] == 'DERStatus':
                self.parent_object = DER_STATUS

            assert self.parent_object is not None, f"The parent object type {params[0]} is not known, please check spelling in configuration file."
            assert hasattr(
                self.parent_object, params[1]
            ), f"{params[0]} does not have property {params[1]}, please check spelling in configuration file."
            self.parameter = params[1]

    @staticmethod
    def build_from_csv(data: Dict[str, str]) -> MappedPoint:
        return MappedPoint(point_on_bus=data['Point Name'].strip(),
                           description=data['Description'].strip(),
                           multiplier=data['Multiplier'].strip(),
                           mrid=data['MRID'].strip(),
                           writable=data['Writeable'].strip(),
                           parameter_type=data['Parameter Type'].strip(),
                           notes=data['Notes'].strip())


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
        self._log_req_resp = bool(config.get('log_req_resp', False))
        self._subscriptions = config["subscriptions"]
        self._server_hostname = config["server_hostname"]
        self._server_ssl_port = config.get("server_ssl_port", 443)
        self._server_http_port = config.get("server_http_port", None)
        self._mirror_usage_point_list = config.get("MirrorUsagePointList", [])
        self._der_capabilities_info = config.get("DERCapability")
        self._der_settings_info = config.get("DERSettings")
        self._der_status_info = config.get("DERStatus")
        #self._point_map = config.get("point_map")
        self._mapped_points: Dict[str, MappedPoint] = {}
        self._default_config = {
            "subscriptions": self._subscriptions,
            "MirrorUsagePointList": self._mirror_usage_point_list,
            "point_map": config.get("point_map")
        }
        self._server_usage_points: m.UsagePointList

        self._client = IEEE_2030_5_Client(cafile=self._cacertfile,
                                          server_hostname=self._server_hostname,
                                          keyfile=self._keyfile,
                                          certfile=self._certfile,
                                          server_ssl_port=self._server_ssl_port,
                                          pin=self._pin,
                                          log_req_resp=self._log_req_resp)

        # Hook up events so we can respond to them appropriately
        self._client.der_control_event_started(self._control_event_started)
        self._client.der_control_event_ended(self._control_event_ended)
        self._client.der_active_controls_changed(self._active_controls_changed)
        self._client.der_default_control_changed(self._default_control_changed)

        self._last_settings = m.DERSettings()
        self._last_capabilities = m.DERCapability()
        self._last_status = m.DERStatus()

        try:
            self._client.start()
        except ConnectionRefusedError:
            _log.error(f"Could not connect to server {self._server_hostname} agent exiting.")
            sys.exit(1)
        _log.info(self._client.enddevice)
        assert self._client.enddevice
        ed = self._client.enddevice
        self._client.get_der_list()
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

    def _active_controls_changed(self, active: m.DERControlList):
        if not isinstance(active, m.DERControlList):
            _log.error("Invalid instance passed to active control changed")
            return
        _log.debug(active)

    def _default_control_changed(self, default_control: m.DefaultDERControl):
        if not isinstance(default_control, m.DefaultDERControl):
            _log.error("Invalid instance of default control")
            return
        _log.debug(default_control)

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

        It is called every time the configuration in the store changes for this agent.
        """
        config = self._default_config.copy()
        config.update(contents)

        if not config.get('point_map'):
            raise ValueError(
                "Must have point_map specified in config store or referenced to a config store entry!"
            )
        # Only deal with points that have both on bus point and
        # a 2030.5 parameter type
        for item in config['point_map']:
            if item.get('Point Name').strip() and item.get('Parameter Type').strip():
                if 'DERSettings' in item['Parameter Type'] or \
                    'DERCapability' in item['Parameter Type'] or \
                        'DERStatus' in item['Parameter Type']:
                    point = MappedPoint.build_from_csv(item)
                    self._mapped_points[point.point_on_bus] = point
                    # self._mapped_points[point.parameter_type] = point
                else:
                    _log.debug(
                        f"Skipping {item['Point Name']} because it does not have a valid Parameter Type"
                    )

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

    def _cast_multipler(self, value: str) -> int:
        try:
            return int(value)
        except ValueError:
            _log.warning(f"Casting multiplier to int failed: {value}")
            return 1

    def _set_correct_value(self, value: Any) -> Any:
        value_of_instance = value.value
        if isinstance(value_of_instance, type(value)):
            value_of_instance.value = value_of_instance.value.value
        return value_of_instance

    def _transform_settings(self, points: List[MappedPoint]) -> m.DERSettings:
        """Update a DERSettings object so that it is correctly formatted to send to the server.
        
        The point has a parent_object property that must be a DERSettings object.  Each setting
        that requires a transition from a single element to a complex element is handled here.
        
        :param point: The point that is being updated.
        :return: The updated DERSettings object.
        :rtype: m.DERSettings
        :raises AssertionError: If the parent_object is not a DERSettings object.        
        """
        # all of the settings are in the same envelope so we use the same
        # server time for all of them.
        server_time = self._client.server_time
        settings = None

        for point in points:
            assert isinstance(
                point.parent_object,
                m.DERSettings), f"Parent object is not a DERSettings object: {p.parent_object}"

            settings: m.DERSettings = point.parent_object

            # Transform point values into their correct object types.
            if point.parameter == 'setMaxA':
                point.multiplier = self._cast_multipler(point.multiplier)
                settings.setMaxA = m.CurrentRMS(multiplier=point.multiplier,
                                                value=settings.setMaxA)

            if point.parameter == 'setMaxAh':
                point.multiplier = self._cast_multipler(point.multiplier)
                settings.setMaxAh = m.AmpereHour(multiplier=point.multiplier,
                                                 value=settings.setMaxAh)

            if point.parameter == 'setMaxChargeRateVA':
                point.multiplier = self._cast_multipler(point.multiplier)
                settings.setMaxChargeRateVA = m.ApparentPower(multiplier=point.multiplier,
                                                              value=settings.setMaxChargeRateVA)

            if point.parameter == 'setMaxChargeRateW':
                point.multiplier = self._cast_multipler(point.multiplier)
                settings.setMaxChargeRateW = m.ActivePower(multiplier=point.multiplier,
                                                           value=settings.setMaxChargeRateW)

            if point.parameter == 'setMaxDischargeRateVA':
                point.multiplier = self._cast_multipler(point.multiplier)
                settings.setMaxDischargeRateVA = m.ApparentPower(
                    multiplier=point.multiplier, value=settings.setMaxDischargeRateVA)

            if point.parameter == 'setMaxDischargeRateW':
                point.multiplier = self._cast_multipler(point.multiplier)
                settings.setMaxDischargeRateW = m.ActivePower(multiplier=point.multiplier,
                                                              value=settings.setMaxDischargeRateW)

            if point.parameter == 'setMaxV':
                point.multiplier = self._cast_multipler(point.multiplier)
                settings.setMaxV = m.VoltageRMS(multiplier=point.multiplier,
                                                value=settings.setMaxV)

            if point.parameter == 'setMaxVA':
                point.multiplier = self._cast_multipler(point.multiplier)
                settings.setMaxVA = m.ApparentPower(multiplier=point.multiplier,
                                                    value=settings.setMaxVA)

            if point.parameter == 'setMaxVar':
                point.multiplier = self._cast_multipler(point.multiplier)
                settings.setMaxVar = m.ReactivePower(multiplier=point.multiplier,
                                                     value=settings.setMaxVar)

            if point.parameter == 'setMaxVarNeg':
                point.multiplier = self._cast_multipler(point.multiplier)
                settings.setMaxVarNeg = m.ReactivePower(multiplier=point.multiplier,
                                                        value=settings.setMaxVarNeg)

            if point.parameter == 'setMaxW':
                point.multiplier = self._cast_multipler(point.multiplier)
                settings.setMaxW = m.ActivePower(multiplier=point.multiplier,
                                                 value=settings.setMaxW)

            if point.parameter == 'setMaxWh':
                point.multiplier = self._cast_multipler(point.multiplier)
                settings.setMaxWh = m.WattHour(multiplier=point.multiplier,
                                               value=settings.setMaxWh)

            if point.parameter == 'setMinPFOverExcited':
                point.multiplier = self._cast_multipler(point.multiplier)
                settings.setMinPFOverExcited = m.PowerFactor(multiplier=point.multiplier,
                                                             value=settings.setMinPFOverExcited)

            if point.parameter == 'setMinPFUnderExcited':
                point.multiplier = self._cast_multipler(point.multiplier)
                settings.setMinPFUnderExcited = m.PowerFactor(multiplier=point.multiplier,
                                                              value=settings.setMinPFUnderExcited)

            if point.parameter == 'setMinV':
                point.multiplier = self._cast_multipler(point.multiplier)
                settings.setMinV = m.VoltageRMS(multiplier=point.multiplier,
                                                value=settings.setMinV)

            if point.parameter == 'setSoftGradW':
                point.multiplier = self._cast_multipler(point.multiplier)
                settings.setSoftGradW = m.ActivePower(multiplier=point.multiplier,
                                                      value=settings.setSoftGradW)

            if point.parameter == 'setVNom':
                point.multiplier = self._cast_multipler(point.multiplier)
                settings.setVNom = m.VoltageRMS(multiplier=point.multiplier,
                                                value=settings.setVNom)

            if point.parameter == 'setVRef':
                point.multiplier = self._cast_multipler(point.multiplier)
                settings.setVRef = m.VoltageRMS(multiplier=point.multiplier,
                                                value=settings.setVRef)

            if point.parameter == 'setVRefOfs':
                point.multiplier = self._cast_multipler(point.multiplier)
                settings.setVRefOfs = m.VoltageRMS(multiplier=point.multiplier,
                                                   value=settings.setVRefOfs)
            settings.updatedTime = server_time

        return settings

    def _transform_status(self, points: List[MappedPoint]) -> m.DERStatus:
        """Update a derstatus object so that it is correctly formatted to send to the server.
        
        The point has a parent_object property that must be a DERStatus object.  Each setting
        that requires a transition from a single element to a complex element is handled here.
        
        :param point: The point that is being updated.
        :return: The updated DERStatus object.
        :rtype: m.DERStatus
        :raises AssertionError: If the parent_object is not a DERStatus object.        
        """

        server_time = self._client.server_time
        status = None

        for point in points:
            assert isinstance(
                point.parent_object,
                m.DERStatus), f"Parent object is not a DERStatus object: {p.parent_object}"

            status: m.DERStatus = point.parent_object

            if point.parameter == 'genConnectStatus':
                status.genConnectStatus = m.ConnectStatusType(dateTime=server_time,
                                                              value=status.genConnectStatus)

            if point.parameter == 'inverterStatus':
                status.inverterStatus = m.InverterStatusType(dateTime=server_time,
                                                             value=status.inverterStatus)

            if point.parameter == 'localControlModeStatus':
                status.localControlModeStatus = m.LocalControlModeStatusType(
                    dateTime=server_time, value=status.localControlModeStatus)

            if point.parameter == 'manufacturerStatus':
                status.manufacturerStatus = m.ManufacturerStatusType(
                    dateTime=server_time, value=status.manufacturerStatus)

            if point.parameter == 'operationalModeStatus':
                status.operationalModeStatus = m.OperationalModeStatusType(
                    dateTime=server_time, value=status.operationalModeStatus)

            if point.parameter == 'stateOfChargeStatus':
                status.stateOfChargeStatus = m.StateOfChargeStatusType(
                    dateTime=server_time, value=status.stateOfChargeStatus)

            if point.parameter == 'storageModeStatus':
                status.storageModeStatus = m.StorageModeStatusType(dateTime=server_time,
                                                                   value=status.storageModeStatus)

            if point.parameter == 'storConnectStatus':
                status.storConnectStatus = m.ConnectStatusType(dateTime=server_time,
                                                               value=status.storConnectStatus)

            status.readingTime = server_time
        return status

    def _transform_capabilities(self, points: List[MappedPoint]) -> m.DERCapability:
        """Update a DERCapability object so that it is correctly formatted to send to the server.
        
        The point has a parent_object property that must be a DERCapability object.  Each setting
        that requires a transition from a single element to a complex element is handled here.
        
        :param point: The point that is being updated.
        :return: The updated DERCapability object.
        :rtype: m.DERCapability
        :raises AssertionError: If the parent_object is not a DERCapability object.        
        """

        server_time = self._client.server_time
        capabilities = None

        for point in points:

            assert isinstance(
                point.parent_object, m.DERCapability
            ), f"Parent object is not a DERCapability object: {point.parent_object}"

            capabilities: m.DERCapability = point.parent_object

            if point.parameter == 'rtgMaxA':
                capabilities.rtgMaxA = m.CurrentRMS(multiplier=point.multiplier,
                                                    value=self.rtgMaxA)

            if point.parameter == 'rtgMaxAh':
                capabilities.rtgMaxAh = m.AmpereHour(multiplier=point.multiplier,
                                                     value=self.rtgMaxAh)

            if point.parameter == 'rtgMaxChargeRateVA':
                capabilities.rtgMaxChargeRateVA = m.ApparentPower(multiplier=point.multiplier,
                                                                  value=self.rtgMaxChargeRateVA)

            if point.parameter == 'rtgMaxChargeRateW':
                capabilities.rtgMaxChargeRateW = m.ActivePower(multiplier=point.multiplier,
                                                               value=self.rtgMaxChargeRateW)

            if point.parameter == 'rtgMaxV':
                capabilities.rtgMaxV = m.VoltageRMS(multiplier=point.multiplier,
                                                    value=self.rtgMaxV)

            if point.parameter == 'rtgMaxVA':
                capabilities.rtgMaxVA = m.ApparentPower(multiplier=point.multiplier,
                                                        value=self.rtgMaxVA)

            if point.parameter == 'rtgMaxVar':
                capabilities.rtgMaxVar = m.ReactivePower(multiplier=point.multiplier,
                                                         value=self.rtgMaxVar)

            if point.parameter == 'rtgMaxVarNeg':
                capabilities.rtgMaxVarNeg = m.ReactivePower(multiplier=point.multiplier,
                                                            value=self.rtgMaxVarNeg)

            if point.parameter == 'rtgMaxW':
                capabilities.rtgMaxW = m.ActivePower(multiplier=point.multiplier,
                                                     value=self.rtgMaxW)

            if point.parameter == 'rtgMaxWh':
                capabilities.rtgMaxWh = m.WattHour(multiplier=point.multiplier,
                                                   value=self.rtgMaxWh)

            if point.parameter == 'rtgMinPFOverExcited':
                capabilities.rtgMinPFOverExcited = m.PowerFactor(multiplier=point.multiplier,
                                                                 value=self.rtgMinPFOverExcited)

            if point.parameter == 'rtgMinPFUnderExcited':
                capabilities.rtgMinPFUnderExcited = m.PowerFactor(multiplier=point.multiplier,
                                                                  value=self.rtgMinPFUnderExcited)

            if point.parameter == 'rtgNormalCategory':
                capabilities.rtgNormalCategory = m.RtgNormalCategoryType(
                    dateTime=server_time, value=self.rtgNormalCategory)

            if point.parameter == 'rtgOverExcitedPF':
                capabilities.rtgOverExcitedPF = m.PowerFactor(multiplier=point.multiplier,
                                                              value=self.rtgOverExcitedPF)

            if point.parameter == 'rtgOverExcitedW':
                capabilities.rtgOverExcitedW = m.ActivePower(multiplier=point.multiplier,
                                                             value=self.rtgOverExcitedW)

            if point.parameter == 'rtgReactiveSusceptance':
                capabilities.rtgReactiveSusceptance = m.ReactiveSusceptance(
                    multiplier=point.multiplier, value=self.rtgReactiveSusceptance)

            if point.parameter == 'rtgUnderExcitedPF':
                capabilities.rtgUnderExcitedPF = m.PowerFactor(multiplier=point.multiplier,
                                                               value=self.rtgUnderExcitedPF)

            if point.parameter == 'rtgUnderExcitedW':
                capabilities.rtgUnderExcitedW = m.ActivePower(multiplier=point.multiplier,
                                                              value=self.rtgUnderExcitedW)

            if point.parameter == 'rtgVNom':
                capabilities.rtgVNom = m.VoltageRMS(multiplier=point.multiplier,
                                                    value=self.rtgVNom)

            if point.parameter == 'type':
                capabilities.type = m.DERTypeType(dateTime=server_time, value=self.type)

        return capabilities

    def _data_published(self, peer, sender, bus, topic, headers, message):
        """
        Callback triggered by the subscription setup using the topic from the agent's config file
        """
        _log.debug(f"DATA Received from {sender}")
        points = AllPoints.frombus(message)

        parent_objects: Dict[type, List[MappedPoint]] = {}
        transforms = {
            m.DERSettings: (self._transform_settings, self._client.put_der_settings),
            m.DERCapability: (self._transform_capabilities, self._client.put_der_capability),
            m.DERStatus: (self._transform_status, self._client.put_der_status)
        }

        for obj_type in transforms.keys():
            # Create a list of properties that are for each of the types.
            parent_objects[obj_type] = list(
                filter(lambda x: isinstance(x.parent_object, obj_type),
                       self._mapped_points.values()))

            # Make sure that there is some points to update.
            if parent_objects[obj_type]:
                list(
                    map(lambda x: x.set_value(points.get(x.point_on_bus)),
                        parent_objects[obj_type]))

            # Do the transform from simple int/floats to complex objects.
            sendable = transforms[obj_type][0](parent_objects[obj_type])
            if sendable:
                # Send the data to the server.
                transforms[obj_type][1](sendable)

        for mp in self._mapped_points.values():
            mp.reset_changed()

        for index, pt in enumerate(self._mirror_usage_point_list):
            if pt["subscription_point"] in points.points:
                reading_mRID = pt["MirrorMeterReading"]['mRID']
                reading = self._mup_readings[reading_mRID]
                for rs_index, rs in enumerate(reading.MirrorReadingSet):
                    rs = reading.MirrorReadingSet[rs_index]
                    rs.Reading.append(m.Reading(value=points.points[pt["subscription_point"]]))
                    start = rs.timePeriod.start
                    if start + self._mup_pollRate < self._client.server_time:
                        self._times_published[reading_mRID] = self._times_published.get(
                            reading_mRID, 0) + 1
                        rs.mRID = "_".join(
                            [reading_mRID, str(self._times_published[reading_mRID])])

                        new_reading_href = self._client.post_mirror_reading(reading)
                        _log.info(
                            f"New readings({len(rs.Reading)}) posted available at: {new_reading_href}"
                        )
                        rs.Reading.clear()
                        rs.timePeriod.start = self._client.server_time
                        rs.timePeriod.duration = self._mup_pollRate


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
