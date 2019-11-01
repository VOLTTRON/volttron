# }}}

from datetime import datetime, timedelta
import sep2
import calendar
import logging
import pytz
import io
import time
from . import xsd_models
from volttron.platform.agent import utils

utils.setup_logging()
_log = logging.getLogger(__name__)


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

        self.mappings = {}

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
        return None

    ##############################################################
    # Currently WChaMax is the only SunSpec register we support  #
    # writing to. Because of the way SEP2 is set up, we can read #
    # any register by giving it a proper SEP2 resource and field #
    # but writing to registers will require special agent config #
    ##############################################################

    def b124_WChaMax(self, value):
        now = datetime.utcnow().replace(tzinfo=pytz.utc)
        mrid = mrid_helper(self.id, int(time.mktime(now.timetuple())))
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

    def field_value(self, resource, field):
        """ Given a SEP2 resource and field name, return the value of that field.

        :param resource: SEP2 resource name
        :param field: SEP2 field name (may be dotted notation if a nested field)
        :return: field value
        """

        # Special Corner cases that exist outside of official SEP2 fields
        if field == 'sFDI':
            return self.sfdi
        elif field == 'SOC':
            _log.debug('Calculating DERAvailability.soc...')
            if self.field_value("DERAvailability", "availabilityDuration") is not None and \
                            self.field_value("DERSettings", "setMaxChargeRate") is not None:
                duration = self.field_value("DERAvailability", "availabilityDuration") / 3600.0
                max_charge = self.field_value("DERSettings", "setMaxChargeRate")
                soc = duration * max_charge
            else:
                soc = None
            return soc

        # Translate from SEP2 resource (DeviceInformation) to EndDevice attribute (device_information)
        converted_resource = sep2.RESOURCE_MAPPING[resource]
        if hasattr(self, converted_resource):
            sep2_resource = getattr(self, converted_resource)
        else:
            raise AttributeError("{} is not a valid SEP2 Resource".format(resource))

        # MUPs have special case handling
        if converted_resource == "mup":
            return self.meter_reading_helper(field)

        sep2_field = self.get_field(sep2_resource, field)
        if hasattr(sep2_field, 'value'):
            field_value = sep2_field.value
            if hasattr(sep2_field, 'multiplier') and type(sep2_field.multiplier) == xsd_models.PowerOfTenMultiplierType:
                field_value = float(field_value) * pow(10, int(sep2_field.multiplier.get_valueOf_()))
            elif type(field_value) == xsd_models.PerCent:
                field_value = int(field_value.get_valueOf_()) / 100.0
            else:
                # Depending on field choice, this could be a nested xsd model, not JSON serializable.
                pass
        else:
            field_value = sep2_field

        return field_value

    @staticmethod
    def get_field(resource, field):
        """ Recursive helper method to retrieve field from SEP2 resource

        If SEP2 fields have not been defined, this method will return None

        :param resource: SEP2 resource (xsd_models object)
        :param field: SEP2 field name
        :return: value of field
        """
        fields = field.split('.', 1)
        if len(fields) == 1:
            sep2_field = getattr(resource, field, None)
        else:
            meta_field = getattr(resource, fields[0], None)
            sep2_field = EndDevice.get_field(meta_field, fields[1]) if meta_field else None
        return sep2_field

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
        buff = io.StringIO()
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
    hex_string = hex(int(edev_pk)*10000000000000+resource_suffix*100)[2:].upper()
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
