# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
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

from .end_device import EndDevice, MUP, IEEE2030_5Renderer, IEEE2030_5Time
from datetime import datetime, timedelta
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC
import IEEE2030_5
import base64
import logging
import pytz
import sys
from . import xsd_models

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '1.0'


class IEEE2030_5Exception(Exception):
    pass


def IEEE2030_5_agent(config_path, **kwargs):
    """Parses the IEEE2030_5 Agent configuration and returns an instance of
    the agent created using that configuation.

    :param config_path: Path to a configuation file.

    :type config_path: str
    :returns: IEEE 2030.5 Agent
    :rtype: IEEE2030_5Agent
    """
    try:
        config = utils.load_config(config_path)
    except Exception:
        config = {}

    if not config:
        _log.info("Using IEEE 2030.5 Agent defaults for starting configuration.")

    devices = config.get('devices', [])  # To add devices, include them in a config file
    # This default should be overridden in config file
    IEEE2030_5_server_sfdi = config.get('IEEE2030_5_server_sfdi', 'foo')
    # This default should be overridden in config file
    IEEE2030_5_server_lfdi = config.get('IEEE2030_5_server_lfdi', 'bar')
    load_shed_device_category = config.get('load_shed_device_category', '0020')
    timezone = config.get('timezone', 'America/Los_Angeles')

    return IEEE2030_5Agent(devices,
                           IEEE2030_5_server_sfdi,
                           IEEE2030_5_server_lfdi,
                           load_shed_device_category,
                           timezone,
                           **kwargs)


class IEEE2030_5Agent(Agent):
    """
        Agent that handles IEEE 2030.5 communication.

        IEEE2030_5Agent uses the VOLTTRON web service to communicate with IEEE 2030.5  end devices.
        End device configuration is outlined in the agent config file.

        IEEE 2030.5 data is exposed via get_point(), get_points() and set_point() calls.
        A IEEE 2030.5 device driver (IEEE2030_5.py under MasterDriverAgent) can be configured,
        which gets and sets data by sending RPCs to this agent.

        For further information about this subsystem, please see the VOLTTRON
        IEEE 2030.5 DER Support specification, which is located in VOLTTRON readthedocs
        under specifications/IEEE2030_5_agent.html.

        This agent can be installed as follows:
            export IEEE2030_5_ROOT=$VOLTTRON_ROOT/services/core/IEEE2030_5Agent
            cd $VOLTTRON_ROOT
            python scripts/install-agent.py -s $IEEE2030_5_ROOT -i IEEE2030_5agent -c $IEEE2030_5_ROOT/IEEE2030_5.config
                -t IEEE2030_5agent -f
    """

    def __init__(self, device_config=[], IEEE2030_5_server_sfdi='foo', IEEE2030_5_server_lfdi='bar',
                 load_shed_device_category='0020', timezone='America/Los_Angeles', **kwargs):
        super(IEEE2030_5Agent, self).__init__(enable_web=True, **kwargs)

        self.device_config = device_config
        self.IEEE2030_5_server_sfdi = IEEE2030_5_server_sfdi
        self.IEEE2030_5_server_lfdi = IEEE2030_5_server_lfdi
        self.load_shed_device_category = load_shed_device_category
        self.timezone = timezone
        self.devices = {}

        self.default_config = {"devices": device_config,
                               "IEEE2030_5_server_sfdi": IEEE2030_5_server_sfdi,
                               "IEEE2030_5_server_lfdi": IEEE2030_5_server_lfdi,
                               "load_shed_device_category": load_shed_device_category,
                               "timezone": timezone}
        self.vip.config.set_default("config", self.default_config)
        self.devices = self.register_devices(device_config)
        self.mups = []

        self.vip.config.subscribe(self.configure, actions=["NEW", "UPDATE"], pattern="config")

    def configure(self, configure, actions, contents):
        config = self.default_config.copy()
        config.update(contents)
        _log.debug("Configuring IEEE 2030.5 Agent")

        self.device_config = config["devices"]
        self.IEEE2030_5_server_sfdi = config["IEEE2030_5_server_sfdi"]
        self.IEEE2030_5_server_lfdi = config["IEEE2030_5_server_lfdi"]
        self.load_shed_device_category = config["load_shed_device_category"]
        self.timezone = config["timezone"]
        self.devices = self.register_devices(self.device_config)
        self.register_endpoints(self)

    @Core.receiver('onstart')
    def register_endpoints(self, sender):
        """ Register HTTP endpoints.

        Registers all IEEE 2030.5 related endpoints. Endpoints are defined in the end_device.py file.
        """
        # _log.debug("Deregistering Endpoints: {}".format(self.__class__.__name__))
        for endpoint in self.vip.web._endpoints:
            try:
                split_path = endpoint.split('/')
                if split_path[2] == 'edev' and int(split_path[3]):
                    if int(split_path[3]) not in self.devices.keys():
                        pass
                        # If code is ever introduced to unregister an endpoint, do so here!
                        # self.vip.web.unregister_endpoint(endpoint)
            except (IndexError, ValueError):
                pass

        _log.debug("Registering Endpoints: {}".format(self.__class__.__name__))
        for _, endpoint in IEEE2030_5.IEEE2030_5_ENDPOINTS.items():
            if endpoint.url not in self.vip.web._endpoints:
                self.vip.web.register_endpoint(endpoint.url, getattr(self, endpoint.callback), "raw")
        for device_id, device in self.devices.items():
            for _, endpoint in IEEE2030_5.IEEE2030_5_EDEV_ENDPOINTS.items():
                if endpoint.url.format(device_id) not in self.vip.web._endpoints:
                    self.vip.web.register_endpoint(endpoint.url.format(device_id),
                                                   getattr(self, endpoint.callback), "raw")

    def register_devices(self, devices):
        """ Register IEEE 2030.5 end devices.

        :param devices: End devices from agent config file.
        :type devices: List

        :return: Dictionary of EndDevice objects keyed by ID.
        """
        _log.debug("Loading Devices: {}".format(self.__class__.__name__))
        end_devices = self.devices
        for device in devices:
            if device['sfdi'] not in [k.sfdi for k in end_devices.values()]:
                d = EndDevice(sfdi=device["sfdi"],
                              lfdi=device["lfdi"],
                              load_shed_device_category=device["load_shed_device_category"],
                              pin_code=device["pin_code"])
                end_devices[d.id] = d
            else:
                d = self.get_end_device(sfdi=device['sfdi'])
                d.lfdi = device['lfdi']
                d.load_shed_device_category = device['load_shed_device_category']
                d.pin_code = device['pin_code']

        old_indices = []
        for index, d in end_devices.items():
            if d.sfdi not in [device['sfdi'] for device in devices]:
                old_indices.append(index)
        for i in old_indices:
            end_devices.pop(i)
        return end_devices

    def get_end_device(self, path=None, sfdi=None, lfdi=None):
        """ Helper function to return end device object.

        Only one of path or sfdi should be used for End Device lookup

        :param path: Path Info of HTTP endpoint request
        :param sfdi: SFDI of end device
        :param lfdi: LFDI of end device
        :return: EndDevice object
        """
        if path:
            end_device_id = path.split('/')[3]
            try:
                device = self.devices[int(end_device_id)]
                return device
            except KeyError:
                raise IEEE2030_5Exception("Invalid end device requested")
        else:
            end_device = None
            for device in self.devices.values():
                if device.sfdi == sfdi or device.lfdi == lfdi:
                    end_device = device
            if end_device is None:
                raise IEEE2030_5Exception("Invalid end device requested")
            return end_device

    def process_edev(self, env, data, xsd_type, attr_name):
        """ Process HTTP requests and prepare response

        :param env: Request Environment variables
        :param data: Request data
        :param xsd_type: XSD object type request represents
        :param attr_name: Attribute of EndDevice object that corresponds to the XSD Object
        :return: Tuple of (Status Code, Response Data, Headers)
        """
        device = self.get_end_device(env['PATH_INFO'])
        if env['REQUEST_METHOD'] in ('POST', 'PUT'):
            obj = xsd_models.parseString(data, silence=True)
            if type(obj) == xsd_type:
                setattr(device, attr_name, obj)
                return [IEEE2030_5.STATUS_CODES[204], '', IEEE2030_5.CREATED_HEADERS]
            else:
                _log.warning("Bad XML input for HTTP Endpoint.")
                return [IEEE2030_5.STATUS_CODES[500], '', IEEE2030_5.XML_HEADERS]
        else:
            return IEEE2030_5Agent.prep_200_response({'received_data': data, 'result': getattr(device, attr_name)})

    @staticmethod
    def add_meter_readings(mup, meter_readings):
        """ Update/Create Meter Readings for MUP based on existance.

        If Meter Reading already exists, send an update.  If it does not, create new Meter Reading for MUP.

        :param mup: MUP object
        :param meter_readings: List of incoming Meter Readings to insert into MUP object.
        :return: None
        """
        for meter_reading in meter_readings:
            flag = True
            for index, xsd in enumerate(mup.mup_xsd.get_MirrorMeterReading()):
                if meter_reading.description == mup.mup_xsd.get_MirrorMeterReading()[index].description:
                    mup.mup_xsd.replace_MirrorMeterReading_at(index, meter_reading)
                    flag = False
            if flag:
                mup.mup_xsd.add_MirrorMeterReading(meter_reading)

    @staticmethod
    def prep_200_response(render_dict):
        """Helper function to prep standard 200 responses with XML formatted data

        :param render_dict: dictionary to render into XML serializable string

        :return: Tuple of (Status Code, Response Data, Headers)
        """
        return (IEEE2030_5.STATUS_CODES[200],
                base64.b64encode(IEEE2030_5Renderer.render(render_dict)).decode('ascii'),
                IEEE2030_5.XML_HEADERS)

    @RPC.export
    def get_point(self, sfdi, point_name):
        _log.debug("EndDevice {0}: Getting value for {1}".format(sfdi, point_name))
        end_device = self.get_end_device(sfdi=sfdi)
        try:
            point_definition = end_device.mappings[point_name]
            return end_device.field_value(point_definition['IEEE 2030.5 Resource Name'],
                                          point_definition['IEEE 2030.5 Field Name'])
        except KeyError:
            raise IEEE2030_5Exception("{0} not a configured point name.".format(point_name))

    @RPC.export
    def get_points(self, sfdi):
        _log.debug("EndDevice {0}: Getting all configured point values".format(sfdi))
        end_device = self.get_end_device(sfdi=sfdi)
        try:
            end_device_points = {}
            for volttron_point_name, point_definition in end_device.mappings.items():
                field_value = end_device.field_value(point_definition['IEEE 2030.5 Resource Name'],
                                                     point_definition['IEEE 2030.5 Field Name'])
                end_device_points[volttron_point_name] = field_value
            return end_device_points
        except Exception as e:
            raise IEEE2030_5Exception(e)

    @RPC.export
    def set_point(self, sfdi, point_name, value):
        _log.debug("EndDevice {0}: Setting {1} to {2}".format(sfdi, point_name, value))
        end_device = self.get_end_device(sfdi=sfdi)
        try:
            setattr(end_device, point_name, value)
        except Exception as e:
            raise IEEE2030_5Exception(e)

    @RPC.export
    def config_points(self, sfdi, point_map):
        _log.debug("EndDevice {0}: Configuring points: {1}".format(sfdi, point_map))
        end_device = self.get_end_device(sfdi=sfdi)
        end_device.mappings = point_map

    ##########################################################################
    # The following methods are callback functions for IEEE 2030.5 Endpoints #
    ##########################################################################

    def dcap(self, env, data):
        dcap = xsd_models.DeviceCapability(
            EndDeviceListLink=xsd_models.EndDeviceListLink(),
            MirrorUsagePointListLink=xsd_models.MirrorUsagePointListLink(),
            SelfDeviceLink=xsd_models.SelfDeviceLink()
        )
        dcap.set_href(IEEE2030_5.IEEE2030_5_ENDPOINTS["dcap"].url)

        dcap.EndDeviceListLink.set_href(IEEE2030_5.IEEE2030_5_ENDPOINTS["edev-list"].url)
        dcap.SelfDeviceLink.set_href(IEEE2030_5.IEEE2030_5_ENDPOINTS["sdev"].url)

        dcap.TimeLink = xsd_models.TimeLink()
        dcap.TimeLink.set_href(IEEE2030_5.IEEE2030_5_ENDPOINTS["tm"].url)

        dcap.MirrorUsagePointListLink.set_href(IEEE2030_5.IEEE2030_5_ENDPOINTS["mup-list"].url)

        return IEEE2030_5Agent.prep_200_response({"result": dcap})

    def sdev(self, env, data):
        sdev = xsd_models.SelfDevice()
        sdev.sFDI = xsd_models.SFDIType(valueOf_=int(self.IEEE2030_5_server_sfdi))
        sdev.loadShedDeviceCategory = xsd_models.DeviceCategoryType(valueOf_=self.load_shed_device_category)
        sdev.DeviceInformationLink = xsd_models.DeviceInformationLink()
        sdev.DeviceInformationLink.set_href(IEEE2030_5.IEEE2030_5_ENDPOINTS["sdev-di"].url)
        sdev.LogEventListLink = xsd_models.LogEventListLink()
        sdev.LogEventListLink.set_href(IEEE2030_5.IEEE2030_5_ENDPOINTS["sdev-log"].url)
        sdev.LogEventListLink.set_all(1)
        return IEEE2030_5Agent.prep_200_response({"result": sdev})

    def sdev_di(self, env, data):
        sep_device_information = xsd_models.DeviceInformation(lFDI=self.IEEE2030_5_server_lfdi)
        return IEEE2030_5Agent.prep_200_response({"result": sep_device_information})

    def sdev_log(self, env, data):
        sep_log_event_list = xsd_models.LogEventList()
        return IEEE2030_5Agent.prep_200_response({"result": sep_log_event_list})

    def tm(self, env, data):
        now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
        local_tz = pytz.timezone(self.timezone)
        now_local = datetime.now().replace(tzinfo=local_tz)

        start_dst_utc, end_dst_utc = [dt for dt in local_tz._utc_transition_times if dt.year == now_local.year]

        utc_offset = local_tz.utcoffset(start_dst_utc - timedelta(days=1))
        dst_offset = local_tz.utcoffset(start_dst_utc + timedelta(days=1)) - utc_offset
        local_but_utc = datetime.now().replace(tzinfo=pytz.utc)

        tm = xsd_models.Time(
            currentTime=IEEE2030_5Time(now_utc),
            dstEndTime=IEEE2030_5Time(end_dst_utc.replace(tzinfo=pytz.utc)),
            dstOffset=xsd_models.TimeOffsetType(valueOf_=int(dst_offset.total_seconds())),
            dstStartTime=IEEE2030_5Time(start_dst_utc.replace(tzinfo=pytz.utc)),
            localTime=IEEE2030_5Time(local_but_utc),
            quality=IEEE2030_5.QUALITY_NTP,
            tzOffset=xsd_models.TimeOffsetType(valueOf_=int(utc_offset.total_seconds()))
        )
        tm.set_href(IEEE2030_5.IEEE2030_5_ENDPOINTS["tm"].url)
        return IEEE2030_5Agent.prep_200_response({"result": tm})

    def edev_list(self, env, data):
        device_list = xsd_models.EndDeviceList()
        start, limit = parse_list_query(env['QUERY_STRING'].encode('ascii', 'ignore'), len(self.devices))

        for i in range(start, limit):
            device_list.add_EndDevice(self.devices[i].end_device)

        device_list.set_href(IEEE2030_5.IEEE2030_5_ENDPOINTS["edev-list"].url)
        device_list.set_results(max(0, len(range(start, limit))))
        device_list.set_all(len(self.devices))

        return IEEE2030_5Agent.prep_200_response({'received_data': data, 'result': device_list})

    def edev(self, env, data):
        return self.process_edev(env=env, data=data, xsd_type=xsd_models.EndDevice, attr_name="end_device")

    def edev_di(self, env, data):
        return self.process_edev(env=env, data=data,
                                 xsd_type=xsd_models.DeviceInformation, attr_name="device_information")

    def edev_dstat(self, env, data):
        return self.process_edev(env=env, data=data, xsd_type=xsd_models.DeviceStatus, attr_name="device_status")

    def edev_fsa_list(self, env, data):
        device = self.get_end_device(env['PATH_INFO'])
        fsa_list = xsd_models.FunctionSetAssignmentsList()
        fsa_list.set_href(IEEE2030_5.IEEE2030_5_EDEV_ENDPOINTS["fsa-list"].url.format(device.id))
        fsa_list.add_FunctionSetAssignments(device.function_set_assignments)
        fsa_list.set_all(1)
        fsa_list.set_results(1)
        return IEEE2030_5Agent.prep_200_response({"result": fsa_list})

    def edev_fsa(self, env, data):
        return self.process_edev(env=env, data=data,
                                 xsd_type=xsd_models.FunctionSetAssignments, attr_name="function_set_assignments")

    def edev_ps(self, env, data):
        return self.process_edev(env=env, data=data, xsd_type=xsd_models.PowerStatus, attr_name="power_status")

    def edev_reg(self, env, data):
        return self.process_edev(env=env, data=data, xsd_type=xsd_models.Registration, attr_name="registration")

    def edev_der_list(self, env, data):
        device = self.get_end_device(env['PATH_INFO'])
        der_list = xsd_models.DERList()
        der_list.set_all(1)
        der_list.set_results(1)
        der_list.set_href(IEEE2030_5.IEEE2030_5_EDEV_ENDPOINTS["der-list"].url.format(device.id))
        der_list.add_DER(device.der)
        return IEEE2030_5Agent.prep_200_response({"result": der_list})

    def edev_der(self, env, data):
        return self.process_edev(env=env, data=data, xsd_type=xsd_models.DER, attr_name="der")

    def edev_dera(self, env, data):
        return self.process_edev(env=env, data=data, xsd_type=xsd_models.DERAvailability, attr_name="der_availability")

    def edev_derc_list(self, env, data):
        device = self.get_end_device(env['PATH_INFO'])
        derc_list = xsd_models.DERControlList()
        derc_list.set_all(1)
        derc_list.set_results(1)
        derc_list.set_href(IEEE2030_5.IEEE2030_5_EDEV_ENDPOINTS["derc-list"].url.format(device.id))
        derc_list.add_DERControl(device.der_control_xsd_object())
        return IEEE2030_5Agent.prep_200_response({"result": derc_list})

    def edev_derc(self, env, data):
        return self.process_edev(env=env, data=data, xsd_type=xsd_models.DERControl, attr_name="der_control")

    def edev_dercap(self, env, data):
        return self.process_edev(env=env, data=data, xsd_type=xsd_models.DERCapability, attr_name="der_capability")

    def edev_derg(self, env, data):
        return self.process_edev(env=env, data=data, xsd_type=xsd_models.DERSettings, attr_name="der_settings")

    def edev_derp_list(self, env, data):
        device = self.get_end_device(env['PATH_INFO'])
        derp_list = xsd_models.DERProgramList()
        derp_list.set_all(1)
        derp_list.set_results(1)
        derp_list.set_href(IEEE2030_5.IEEE2030_5_EDEV_ENDPOINTS["derp-list"].url.format(device.id))
        derp_list.add_DERProgram(device.der_program)
        return IEEE2030_5Agent.prep_200_response({"result": derp_list})

    def edev_derp(self, env, data):
        return self.process_edev(env=env, data=data, xsd_type=xsd_models.DERProgram, attr_name="der_program")

    def edev_ders(self, env, data):
        return self.process_edev(env=env, data=data, xsd_type=xsd_models.DERStatus, attr_name="der_status")

    def mup_list(self, env, data):
        if env['REQUEST_METHOD'] in ('POST', 'PUT'):
            endpoint = IEEE2030_5.IEEE2030_5_MUP_ENDPOINTS["mup"]
            mup = xsd_models.parseString(data, silence=True)
            device = self.get_end_device(lfdi=mup.get_deviceLFDI())
            if device.mup is None:
                m = MUP(mup)
                m.mup_xsd.set_href(endpoint.url.format(m.id))
                device.mup = m
                self.mups.append(m)
                if endpoint.url.format(m.id) not in self.vip.web._endpoints:
                    self.vip.web.register_endpoint(endpoint.url.format(m.id), getattr(self, endpoint.callback), "raw")
            else:
                IEEE2030_5Agent.add_meter_readings(device.mup, mup.get_MirrorMeterReading())

            return [IEEE2030_5.STATUS_CODES[201],
                    '',
                    IEEE2030_5.XML_HEADERS+[("Location", endpoint.url.format(device.mup.id))]]

        else:
            mup_list = xsd_models.MirrorUsagePointList()

            start, limit = parse_list_query(env['QUERY_STRING'].encode('ascii', 'ignore'), len(self.mups))

            for i in range(start, limit):
                mup_list.add_MirrorUsagePoint(self.mups[i].mup_xsd)

            mup_list.set_href(IEEE2030_5.IEEE2030_5_ENDPOINTS["mup-list"].url)
            mup_list.set_results(max(0, len(range(start, limit))))
            mup_list.set_all(len(self.mups))

            return IEEE2030_5Agent.prep_200_response({"result": mup_list})

    def mup(self, env, data):
        mup_id = env['PATH_INFO'].split('/')[3]
        mup = self.mups[int(mup_id)]
        if env['REQUEST_METHOD'] in ('POST', 'PUT'):
            device = self.get_end_device(lfdi=mup.mup_xsd.get_deviceLFDI())
            obj = xsd_models.parseString(data, silence=True)
            if type(obj) == xsd_models.MirrorUsagePoint:
                readings = obj.get_MirrorMeterReading()
            elif type(obj) == xsd_models.MirrorMeterReading:
                readings = [obj]
            else:
                _log.warning("Bad XML input for HTTP Endpoint.")
                return [IEEE2030_5.STATUS_CODES[500], '', IEEE2030_5.XML_HEADERS]
            IEEE2030_5Agent.add_meter_readings(device.mup, readings)

            return [IEEE2030_5.STATUS_CODES[201],
                    '',
                    IEEE2030_5.XML_HEADERS + [
                        ("Location", IEEE2030_5.IEEE2030_5_MUP_ENDPOINTS["mup"].url.format(mup.id))]]
        else:
            xsd_object = getattr(mup, 'mup_xsd')
            return IEEE2030_5Agent.prep_200_response({'received_data': data, 'result': xsd_object})


def parse_list_query(query, length):
    """Parses the IEEE 2030.5 query string parameters associated with list resources.

    There is some defensive code here to avoid errors on negative numbers.

    :param query: The request QUERY PARAMS dictionary
    :param length: Length of the list
    :return: (start index 0 based, limit) - xrange style
    """
    params = {a[0]: a[1] for a in [x.split('=') for x in query.split("&")]} if len(query) > 0 else {}
    start = max(0, int(params.get('s', '0')))
    limit = max(0, min(length, start + int(params.get('l', '255'))))
    return start, limit


def main():
    """Main method called to start the agent."""
    utils.vip_main(IEEE2030_5_agent, identity='IEEE2030_5agent',
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
