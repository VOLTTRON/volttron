# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2017, SLAC National Laboratory / Kisensum Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor SLAC / Kisensum,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# SLAC / Kisensum. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# }}}

from datetime import datetime, timedelta
import __init__ as sep2
import calendar
import pytz
import StringIO
import time
import xsd_models


class EndDevice:
    """ Object representing an End Device in SEP2

    End Devices talk with the SEP2 Agent over HTTP using XML formatting. This End Device representation stores
    configuration information about the End Device and exports that information as XSD Objects when various
    endpoint urls are queried.
    """
    enddevice_id = 0

    def __init__(self, sfdi, lfdi, load_shed_device_category, pin_code):
        """Representation of End Device object.

        :param sfdi: Short Form Device Identifier
        :param lfdi: Long Form Device Identifier
        :param load_shed_device_category: Load Shed Device Category
        :param pin_code: Pin Code
        """

        # Basic Device Configurations
        self.sfdi = sfdi
        self.lfdi = lfdi
        self.loadShedDeviceCategory = load_shed_device_category
        self.pinCode = pin_code
        self.registeredOn = datetime.utcnow().replace(tzinfo=pytz.utc)

        # Global Device ID. Updates as End Devices are registered.
        self.id = EndDevice.enddevice_id
        EndDevice.enddevice_id += 1

        # SEP2 Resource Initialization
        self._end_device = xsd_models.EndDevice(
            FunctionSetAssignmentsListLink=xsd_models.FunctionSetAssignmentsListLink(),
            RegistrationLink=xsd_models.RegistrationLink(),
        )
        self._end_device.set_href(sep2.SEP2_EDEV_ENDPOINTS['edev'].url.format(self.id))
        self._end_device.sFDI = xsd_models.SFDIType(valueOf_=self.sfdi)
        self._end_device.loadShedDeviceCategory = xsd_models.DeviceCategoryType(valueOf_=self.loadShedDeviceCategory)
        self._end_device.FunctionSetAssignmentsListLink.\
            set_href(sep2.SEP2_EDEV_ENDPOINTS['fsa-list'].url.format(self.id))
        self._end_device.FunctionSetAssignmentsListLink.set_all(1)
        self._end_device.RegistrationLink.set_href(sep2.SEP2_EDEV_ENDPOINTS['reg'].url.format(self.id))
        self._end_device.DeviceInformationLink = xsd_models.DeviceInformationLink()
        self._end_device.DeviceInformationLink.set_href(sep2.SEP2_EDEV_ENDPOINTS['di'].url.format(self.id))
        self._end_device.DeviceStatusLink = xsd_models.DeviceStatus()
        self._end_device.DeviceStatusLink.set_href(sep2.SEP2_EDEV_ENDPOINTS['dstat'].url.format(self.id))
        self._end_device.PowerStatusLink = xsd_models.PowerStatusLink()
        self._end_device.PowerStatusLink.set_href(sep2.SEP2_EDEV_ENDPOINTS['ps'].url.format(self.id))
        self._end_device.DERListLink = xsd_models.DERListLink()
        self._end_device.DERListLink.set_href(sep2.SEP2_EDEV_ENDPOINTS['der-list'].url.format(self.id))
        self._end_device.DERListLink.set_all(1)

        self._device_information = xsd_models.DeviceInformation()
        self._device_status = xsd_models.DeviceStatus()
        self._power_status = xsd_models.PowerStatus()

        self._function_set_assignments = xsd_models.FunctionSetAssignments(
            subscribable='0',
            mRID=xsd_models.mRIDType(valueOf_=mrid_helper(self.id, sep2.MRID_SUFFIX_FUNCTION_SET_ASSIGNMENT)),
            description="FSA",
        )
        self._function_set_assignments.set_href(sep2.SEP2_EDEV_ENDPOINTS["fsa"].url.format(self.id))
        self._function_set_assignments.DERProgramListLink = xsd_models.DERProgramListLink()
        self._function_set_assignments.DERProgramListLink.\
            set_href(sep2.SEP2_EDEV_ENDPOINTS["derp-list"].url.format(self.id))
        self._function_set_assignments.DERProgramListLink.set_all(1)
        self._function_set_assignments.TimeLink = xsd_models.TimeLink()
        self._function_set_assignments.TimeLink.set_href(sep2.SEP2_ENDPOINTS["tm"].url)

        self._registration = xsd_models.Registration(
            dateTimeRegistered=sep2_time(self.registeredOn),
            pIN=xsd_models.PINType(valueOf_=int(self.pinCode)))
        self._registration.set_href(sep2.SEP2_EDEV_ENDPOINTS['reg'].url.format(self.id))

        self._der = xsd_models.DER(
            AssociatedDERProgramListLink=xsd_models.AssociatedDERProgramListLink(),
            CurrentDERProgramLink=xsd_models.CurrentDERProgramLink(),
            DERAvailabilityLink=xsd_models.DERAvailabilityLink(),
            DERCapabilityLink=xsd_models.DERCapabilityLink(),
            DERSettingsLink=xsd_models.DERSettingsLink(),
            DERStatusLink=xsd_models.DERStatusLink()
        )
        self._der.set_href(sep2.SEP2_EDEV_ENDPOINTS['der'].url.format(self.id))
        self._der.AssociatedDERProgramListLink.set_href(sep2.SEP2_EDEV_ENDPOINTS['derp-list'].url.format(self.id))
        self._der.AssociatedDERProgramListLink.set_all(1)
        self._der.CurrentDERProgramLink.set_href(sep2.SEP2_EDEV_ENDPOINTS['derp'].url.format(self.id))
        self._der.DERAvailabilityLink.set_href(sep2.SEP2_EDEV_ENDPOINTS['dera'].url.format(self.id))
        self._der.DERCapabilityLink.set_href(sep2.SEP2_EDEV_ENDPOINTS['dercap'].url.format(self.id))
        self._der.DERSettingsLink.set_href(sep2.SEP2_EDEV_ENDPOINTS['derg'].url.format(self.id))
        self._der.DERStatusLink.set_href(sep2.SEP2_EDEV_ENDPOINTS['ders'].url.format(self.id))

        self._der_program = xsd_models.DERProgram(
            DERControlListLink=xsd_models.DERControlListLink(),
            primacy=xsd_models.PrimacyType(valueOf_=1)
        )
        self._der_program.set_href(sep2.SEP2_EDEV_ENDPOINTS['derp'].url.format(self.id))
        self._der_program.set_mRID(xsd_models.mRIDType(valueOf_=mrid_helper(self.id, sep2.MRID_SUFFIX_DER_PROGRAM)))
        self._der_program.set_version(xsd_models.VersionType(valueOf_='0'))
        self._der_program.set_description("DER Program")
        self._der_program.DERControlListLink.set_href(sep2.SEP2_EDEV_ENDPOINTS['derc-list'].url.format(self.id))
        self._der_program.DERControlListLink.set_all(1)

        self._der_settings = xsd_models.DERSettings()
        self._der_capability = xsd_models.DERCapability()
        self._der_status = xsd_models.DERStatus()
        self._der_availability = xsd_models.DERAvailability()

        self._der_control = xsd_models.DERControl(DERControlBase=xsd_models.DERControlBase())
        self._der_control.set_href(sep2.SEP2_EDEV_ENDPOINTS['derc'].url.format(self.id))
        self._der_control.set_description("DER Control")

        self._mup = None

    def meter_reading_helper(self, attr_name):
        """ Helper method for attributes that use meter readings

        :param attr_name: Name of SunSpec attribute
        :return: Value of SEP2 Meter Reading correlated with SunSpec attribute
        """
        if self.mup is not None:
            for reading in self.mup.mup_xsd.get_MirrorMeterReading():
                if reading.get_description() == attr_name:
                    power_of_ten = reading.get_ReadingType()
                    value = reading.get_Reading().get_value()
                    return float(value) * pow(10, int(power_of_ten.get_powerOfTenMultiplier().get_valueOf_())) \
                        if power_of_ten is not None else float(value)

    ##############################################################
    # These methods map SEP2 Resources to SunSpec registers.     #
    # Each variable is named according to SunSpec standard, with #
    # the preceding 'b<#>' representing which block the value    #
    # belongs to.                                                #
    ##############################################################

    @property
    def b1_Md(self): return self.device_information.get_mfModel()

    @property
    def b1_Opt(self): return self.lfdi

    @property
    def b1_SN(self): return self.sfdi

    @property
    def b1_Vr(self): return self.device_information.get_mfHwVer()

    @property
    def b113_A(self): return self.meter_reading_helper("PhaseCurrentAvg")

    @property
    def b113_DCA(self): return self.meter_reading_helper("InstantPackCurrent")

    @property
    def b113_DCV(self): return self.meter_reading_helper("LineVoltageAvg")

    @property
    def b113_DCW(self): return self.meter_reading_helper("PhasePowerAvg")

    @property
    def b113_PF(self): return self.meter_reading_helper("PhasePFA")

    @property
    def b113_WH(self): return self.meter_reading_helper("EnergyIMP")

    @property
    def b120_AhrRtg(self): return expand_multiplier(self.der_capability.get_rtgAh())

    @property
    def b120_ARtg(self): return expand_multiplier(self.der_capability.get_rtgA())

    @property
    def b120_MaxChaRte(self): return expand_multiplier(self.der_capability.get_rtgMaxChargeRate())

    @property
    def b120_MaxDisChaRte(self): return expand_multiplier(self.der_capability.get_rtgMaxDischargeRate())

    @property
    def b120_WHRtg(self): return expand_multiplier(self.der_capability.get_rtgWh())

    @property
    def b120_WRtg(self): return expand_multiplier(self.der_capability.get_rtgW())

    @property
    def b121_WMax(self): return expand_multiplier(self.der_settings.get_setMaxChargeRate())

    @property
    def b122_ActWh(self): return self.meter_reading_helper("EnergyEXP")

    @property
    def b122_StorConn(self): return status_value(self.der_status.get_storConnectStatus())

    @property
    def b124_WChaMax(self): return self.der_control.get_DERControlBase().get_opModFixedFlow()

    @b124_WChaMax.setter
    def b124_WChaMax(self, value):
        now = datetime.utcnow().replace(tzinfo=pytz.utc)
        mrid = mrid_helper(self.id, long(time.mktime(now.timetuple())))
        self.der_control.get_DERControlBase().set_opModFixedFlow(xsd_models.SignedPerCent(valueOf_=value))
        self.der_control.set_mRID(xsd_models.mRIDType(valueOf_=mrid))
        self.der_control.set_creationTime(sep2_time(now))
        self.der_control.set_EventStatus(xsd_models.EventStatus(
            currentStatus=sep2.EVENT_STATUS_ACTIVE,
            dateTime=sep2_time(now),
            potentiallySuperseded=True,
            potentiallySupersededTime=sep2_time(now),
            reason="Dispatch"
        ))
        self.der_control.set_interval(xsd_models.DateTimeInterval(duration=3600 * 24, start=sep2_time(now)))

    @property
    def b403_Tmp(self): return self.meter_reading_helper("InstantPackTemp")

    @property
    def b404_DCW(self):
        if self.power_status.get_PEVInfo() is not None:
            return expand_multiplier(self.power_status.get_PEVInfo().get_chargingPowerNow())

    @property
    def b404_DCWh(self):
        if self.der_availability.get_availabilityDuration() is not None and self.b121_WMax is not None:
            return (self.der_availability.get_availabilityDuration()/3600.0)*self.b121_WMax

    @property
    def b802_LocRemCtl(self):
        return status_value(self.der_status.get_localControlModeStatus())

    @property
    def b802_State(self): return status_value(self.der_status.get_inverterStatus())

    @property
    def b802_SoC(self): return percent_to_float(self.der_status.get_stateOfChargeStatus())


    ############################################################
    # XSD Object representation methods.                       #
    # These objects represent various SEP2 Resources.          #
    # These Resource objects mirror HTTP request GET and POSTS #
    ############################################################

    @property
    def end_device(self):
        return self._end_device

    @property
    def device_information(self):
        return self._device_information

    @device_information.setter
    def device_information(self, value):
        self._device_information = value
        self._device_information.set_href(sep2.SEP2_EDEV_ENDPOINTS['di'].url.format(self.id))

    @property
    def device_status(self):
        return self._device_status

    @device_status.setter
    def device_status(self, value):
        self._device_status = value
        self._device_status.set_href(sep2.SEP2_EDEV_ENDPOINTS['dstat'].url.format(self.id))

    @property
    def function_set_assignments(self):
        return self._function_set_assignments

    @property
    def power_status(self):
        return self._power_status

    @power_status.setter
    def power_status(self, value):
        self._power_status = value
        self._power_status.set_href(sep2.SEP2_EDEV_ENDPOINTS['ps'].url.format(self.id))

    @property
    def registration(self):
        return self._registration

    @property
    def der(self):
        return self._der

    @property
    def der_program(self):
        return self._der_program

    @property
    def der_control(self):
        return self._der_control

    @property
    def der_availability(self):
        return self._der_availability

    @der_availability.setter
    def der_availability(self, value):
        self._der_availability = value
        self._der_availability.set_href(sep2.SEP2_EDEV_ENDPOINTS['dera'].url.format(self.id))

    @property
    def der_capability(self):
        return self._der_capability

    @der_capability.setter
    def der_capability(self, value):
        self._der_capability = value
        self._der_capability.set_href(sep2.SEP2_EDEV_ENDPOINTS['dercap'].url.format(self.id))

    @property
    def der_status(self):
        return self._der_status

    @der_status.setter
    def der_status(self, value):
        self._der_status = value
        self._der_status.set_href(sep2.SEP2_EDEV_ENDPOINTS['ders'].url.format(self.id))

    @property
    def der_settings(self):
        return self._der_settings

    @der_settings.setter
    def der_settings(self, value):
        self._der_settings = value
        self._der_settings.set_href(sep2.SEP2_EDEV_ENDPOINTS['derg'].url.format(self.id))

    @property
    def mup(self):
        return self._mup

    @mup.setter
    def mup(self, value):
        self._mup = value


class MUP:
    """ Object representing an MUP in SEP2 """
    mup_id = 0

    def __init__(self, xsd):
        self.id = MUP.mup_id
        MUP.mup_id += 1
        self.mup_xsd = xsd


class SEP2Renderer:
    """ Takes SEP2 Type objects and renders them as XML formatted data for HTTP response. """

    media_type = 'application/sep+xml'

    @staticmethod
    def export(xsd_object, make_pretty=True):
        """Export SEP2 object into serializable XML

        :param xsd_object: SEP2 object to export
        :param make_pretty: Boolean value determining whether or not to use newline characters between XML elements.

        :return: String of XML serialized data.
        """
        buff = StringIO.StringIO()
        xsd_object.export(
            buff,
            1,
            namespacedef_='xmlns="http://zigbee.org/sep" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
            pretty_print=make_pretty
        )
        return buff.getvalue()

    @staticmethod
    def render(data):
        """ Wrapper function around the export method.

        :param data: XSD object to render. Empty string if data does not come in correctly.
        :return: Formatted XML string.
        """
        if data is None:
            return ''

        if 'rendered_result' not in data:
            if 'result' not in data:
                data['rendered_result'] = ''
            else:
                make_pretty = True
                data['rendered_result'] = SEP2Renderer.export(data['result'], make_pretty)

        return data['rendered_result']


class SEP2Parser:
    """ Takes XML formatted string and renders it as an XSD object. """
    media_type = 'application/sep+xml'

    @staticmethod
    def parse(stream):
        """ Parses the incoming bytestream as XML and returns the resulting data. """
        return xsd_models.parseString(stream, silence=True)


def mrid_helper(edev_pk, resource_suffix):
    """ Helper method to create universally unique ID for any resource object

    :param edev_pk: Primary Key of End Device object
    :param resource_suffix: Suffix to add to hash to create unique ID
    :return: UUID (MRID) value. (In hex-decimal)
    """
    hex_string = hex(int(edev_pk)*10000000000000L+resource_suffix*100)[2:].upper()
    if hex_string.endswith('L'):
        hex_string = hex_string[:-1]
    if (len(hex_string)) % 2 == 1:
        hex_string = "0{0}".format(hex_string)
    return hex_string


def sep2_time(dt_obj, local=False):
    """ Return a proper Sep2 TimeType object for the dt_obj passed in.

        From SEP2 spec:
            TimeType Object (Int64)
                Time is a signed 64 bit value representing the number of seconds
                since 0 hours, 0 minutes, 0 seconds, on the 1st of January, 1970,
                in UTC, not counting leap seconds.

    :param dt_obj: Datetime object to convert to SEP2 TimeType object.
    :param local: dt_obj is in UTC or Local time. Default to UTC time.
    :return: Time XSD object
    :raises: If utc_dt_obj is not UTC
    """

    if dt_obj.tzinfo is None:
        raise Exception("SEP2 times should be timezone aware UTC or local")

    if dt_obj.utcoffset() != timedelta(0) and not local:
        raise Exception("SEP2 TimeType should be based on UTC")

    if local:
        return xsd_models.TimeType(valueOf_=int(time.mktime(dt_obj.timetuple())))
    else:
        return xsd_models.TimeType(valueOf_=int(calendar.timegm(dt_obj.timetuple())))


def expand_multiplier(multiplied_element):
    """ Expand SEP2 Element with value and multiplier

    :param multiplied_element: XSD Element (includes power of ten multiplier and value)
    :return: power in kw
    """
    if multiplied_element is not None:
        multiplier = multiplied_element.multiplier
        value = multiplied_element.value
        if multiplier is not None and value is not None:
            return float(value) * pow(10, int(multiplier.get_valueOf_()))


def percent_to_float(percent_element):
    """ Convert XSD PerCent object to float percent value.

    :param percent_element: XSD PerCent element
    :return: 0-100 value as percent
    """
    if percent_element is not None:
        return int(percent_element.get_value().get_valueOf_())/100.0


def status_value(status_element):
    """ Helper method to extract value from XSD Status element

    :param status_element: XSD Status element
    :return: value from status_element
    """
    if status_element is not None:
        return status_element.get_value()
