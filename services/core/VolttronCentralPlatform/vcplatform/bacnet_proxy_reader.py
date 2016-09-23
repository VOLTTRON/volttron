from csv import DictWriter
import logging
import weakref
from cStringIO import StringIO

from bacpypes.object import get_datatype
from bacpypes.primitivedata import (Enumerated, Unsigned, Boolean, Integer,
                                    Real, Double)

_log = logging.getLogger(__name__)


class BACnetReader(object):
    def __init__(self, rpc, bacnet_proxy_identity, response_function=None):
        _log.info("Creating {}".format(self.__class__.__name__))
        self._rpc = weakref.ref(rpc)
        self._proxy_identity = bacnet_proxy_identity
        self._response_function = response_function

    def read_device_name(self, address, device_id):
        try:
            device_name = self.read_prop(address, "device", device_id,
                                         "objectName")
            _log.debug('device_name = ' + str(device_name))
        except TypeError:
            _log.debug("device missing objectName")
            device_name = None
        return device_name

    def read_device_description(self, address, device_id):
        try:
            device_description = self.read_prop(address, "device", device_id,
                                                "description")
            _log.debug('description = ' + str(device_description))
        except TypeError:
            _log.debug('device missing description')
            device_description = None
        return device_description

    def read_device_extended(self, target_address, device_id, filter):
        """Read the extended device properties

        This function will publish the

        :param target_address:
        :param device_id:
        :param filter:
        :return:
        """

        default_range_report = 1.0e+20
        for bac_type, indexes in filter.items():
            query = {}

            for point_index in indexes:
                self.process_object(target_address, bac_type, point_index,
                                    default_range_report)

    def read_device_primary(self, target_address, device_id):
        """('Reference Point Name',
            'Volttron Point Name',
            'Units',
            'Unit Details',
            'BACnet Object Type',
            'Property',
            'Writable',
            'Index',
            'Write Priority',
            'Notes')
        """
        try:
            object_count = self.read_prop(target_address, "device", device_id,
                                          "objectList", index=0)
            list_property = "objectList"
        except TypeError:
            object_count = self.read_prop(target_address, "device", device_id,
                                          "structuredObjectList", index=0)
            list_property = "structuredObjectList"

        _log.debug('object_count = ' + str(object_count))

        for object_index in xrange(1, object_count + 1):
            _log.debug('object_device_index = ' + repr(object_index))

            bac_object = self.read_prop(target_address,
                                        "device",
                                        device_id,
                                        list_property,
                                        index=object_index)

            obj_type, index = bac_object
            # Deals with the largest numbers that can be reported.
            # see proxy_grab_bacnet_config.py
            default_range_report = 1.0e+20
            self.process_object(target_address, obj_type, index,
                                default_range_report)

        # sval = buffer.getvalue()
        # _log.debug('VALUE is: {}'.format(sval))
        # buffer.close()
        # return sval

    def read_device_properties(self, target_address, device_id):
        buffer = StringIO()
        config_writer = DictWriter(buffer, ('Reference Point Name',
                                            'Volttron Point Name',
                                            'Units',
                                            'Unit Details',
                                            'BACnet Object Type',
                                            'Propert.y',
                                            'Writable',
                                            'Index',
                                            'Write Priority',
                                            'Notes'))
        try:
            object_count = self.read_prop(target_address, "device", device_id,
                                          "objectList", index=0)
            list_property = "objectList"
        except TypeError:
            object_count = self.read_prop(target_address, "device", device_id,
                                          "structuredObjectList", index=0)
            list_property = "structuredObjectList"

        _log.debug('object_count = ' + str(object_count))

        for object_index in xrange(1, object_count + 1):
            _log.debug('object_device_index = ' + repr(object_index))

            bac_object = self.read_prop(target_address,
                                        "device",
                                        device_id,
                                        list_property,
                                        index=object_index)

            obj_type, index = bac_object
            # Deals with the largest numbers that can be reported.
            # see proxy_grab_bacnet_config.py
            default_range_report = 1.0e+20
            self.process_object(target_address, obj_type, index,
                                default_range_report, config_writer)

        sval = buffer.getvalue()
        _log.debug('VALUE is: {}'.format(sval))
        buffer.close()
        return sval

    def read_props(self, address, parameters):
        return self._rpc().call(self._proxy_identity, "read_properties",
                                address,
                                parameters).get(timeout=5)

    def read_prop(self, address, obj_type, obj_inst, prop_id, index=None):
        point_map = {"result": [obj_type,
                                obj_inst,
                                prop_id,
                                index]}

        result = self.read_props(address, point_map)
        try:
            return result["result"]
        except KeyError:
            pass

    def process_device_object_reference(self, address, obj_type, obj_inst,
                                        property_name,
                                        max_range_report, config_writer):
        object_count = self.read_prop(address, obj_type, obj_inst,
                                      property_name, index=0)

        for object_index in xrange(1, object_count + 1):
            _log.debug('property_name index = ' + repr(object_index))

            object_reference = self.read_prop(address,
                                              obj_type,
                                              obj_inst,
                                              property_name,
                                              index=object_index)

            # Skip references to objects on other devices.
            if object_reference.deviceIdentifier is not None:
                continue

            sub_obj_type, sub_obj_index = object_reference.objectIdentifier

            self.process_object(address, sub_obj_type, sub_obj_index,
                                max_range_report,
                                config_writer)

    def process_object(self, address, obj_type, index, max_range_report):
        _log.debug('obj_type = ' + repr(obj_type))
        _log.debug('bacnet_index = ' + repr(index))
        context=None
        if obj_type == "device":
            context = dict(address=address, device=index)

        writable = 'FALSE'

        subondinate_list_property = get_datatype(obj_type, 'subordinateList')
        if subondinate_list_property is not None:
            _log.debug('Processing StructuredViewObject')
            # self.process_device_object_reference(address, obj_type, index,
            #                                      'subordinateList',
            #                                      max_range_report,
            #                                      config_writer)
            return

        subondinate_list_property = get_datatype(obj_type, 'zoneMembers')
        if subondinate_list_property is not None:
            _log.debug('Processing LifeSafetyZoneObject')
            # self.process_device_object_reference(address, obj_type, index,
            #                                      'zoneMembers',
            #                                      max_range_report,
            #                                      config_writer)
            return

        present_value_type = get_datatype(obj_type, 'presentValue')
        if present_value_type is None:
            _log.debug('This object type has no presentValue. Skipping.')
            return

        if not issubclass(present_value_type, (Enumerated,
                                               Unsigned,
                                               Boolean,
                                               Integer,
                                               Real,
                                               Double)):
            _log.debug(
                'presenValue is an unsupported type: ' + repr(
                    present_value_type))
            return

        try:
            object_name = self.read_prop(address, obj_type, index, "objectName")
            _log.debug('object name = ' + object_name)
        except TypeError:
            object_name = "NO NAME! PLEASE NAME THIS."

        try:
            object_notes = self.read_prop(address, obj_type, index,
                                          "description")

        except TypeError:
            object_notes = ''

        object_units_details = ''

        if issubclass(present_value_type, Enumerated):
            object_units = 'Enum'
            values = present_value_type.enumerations.values()
            min_value = min(values)
            max_value = max(values)

            vendor_range = ''
            if hasattr(present_value_type, 'vendor_range'):
                vendor_min, vendor_max = present_value_type.vendor_range
                vendor_range = ' (vendor {min}-{max})'.format(min=vendor_min,
                                                              max=vendor_max)

            object_units_details = '{min}-{max}{vendor}'.format(min=min_value,
                                                                max=max_value,
                                                                vendor=vendor_range)

            if not obj_type.endswith('Input'):
                try:
                    default_value = self.read_prop(address, obj_type, index,
                                                   "relinquishDefault")
                    object_units_details += ' (default {default})'.format(
                        default=present_value_type.enumerations[default_value])
                    # writable = 'TRUE'
                except KeyError:
                    pass
                except TypeError:
                    pass
                except ValueError:
                    pass

            if not object_notes:
                enum_strings = []
                for name in Enumerated.keylist(present_value_type(0)):
                    value = present_value_type.enumerations[name]
                    enum_strings.append(str(value) + '=' + name)

                object_notes = present_value_type.__name__ + ': ' + ', '.join(
                    enum_strings)

        elif issubclass(present_value_type, Boolean):
            object_units = 'Boolean'

        elif get_datatype(obj_type, 'units') is None:
            if obj_type.startswith('multiState'):
                object_units = 'State'
                try:
                    state_count = self.read_prop(address, obj_type, index,
                                                 "numberOfStates")
                    object_units_details = 'State count: {}'.format(state_count)
                except TypeError:
                    pass

                try:
                    enum_strings = []
                    state_list = self.read_prop(address, obj_type, index,
                                                "stateText")
                    for name in state_list[1:]:
                        enum_strings.append(name)

                    object_notes = ', '.join('{}={}'.format(x, y) for x, y in
                                             enumerate(enum_strings, start=1))

                except TypeError:
                    pass

                if obj_type != 'multiStateInput':
                    try:
                        default_value = self.read_prop(address, obj_type, index,
                                                       "relinquishDefault")
                        object_units_details += ' (default {default})'.format(
                            default=default_value)
                        object_units_details = object_units_details.strip()
                        # writable = 'TRUE'
                    except TypeError:
                        pass
                    except ValueError:
                        pass

            elif obj_type == 'loop':
                object_units = 'Loop'
            else:
                object_units = 'UNKNOWN UNITS'
        else:
            try:
                object_units = self.read_prop(address, obj_type, index, "units")
            except TypeError:
                object_units = 'UNKNOWN UNITS'

            if isinstance(object_units, (int, long)):
                object_units = 'UNKNOWN UNIT ENUM VALUE: ' + str(object_units)

            if obj_type.startswith('analog') or obj_type in (
                    'largeAnalogValue', 'integerValue', 'positiveIntegerValue'):
                # Value objects never have a resolution property in practice.
                if not object_notes and not obj_type.endswith('Value'):
                    try:
                        res_value = self.read_prop(address, obj_type, index,
                                                   "resolution")
                        object_notes = 'Resolution: {resolution:.6g}'.format(
                            resolution=res_value)
                    except (TypeError, ValueError):
                        pass

                if obj_type not in (
                        'largeAnalogValue', 'integerValue',
                        'positiveIntegerValue'):
                    try:
                        min_value = self.read_prop(address, obj_type, index,
                                                   "minPresValue")
                        max_value = self.read_prop(address, obj_type, index,
                                                   "maxPresValue")

                        has_min = min_value > -max_range_report
                        has_max = max_value < max_range_report

                        if has_min and has_max:
                            object_units_details = '{min:.2f} to {max:.2f}'.format(
                                min=min_value, max=max_value)
                        elif has_min:
                            object_units_details = 'Min: {min:.2f}'.format(
                                min=min_value)
                        elif has_max:
                            object_units_details = 'Max: {max:.2f}'.format(
                                max=max_value)
                        else:
                            object_units_details = 'No limits.'
                    except (TypeError, ValueError):
                        pass

                if obj_type != 'analogInput':
                    try:
                        default_value = self.read_prop(address, obj_type, index,
                                                       "relinquishDefault")
                        object_units_details += ' (default {default})'.format(
                            default=default_value)
                        object_units_details = object_units_details.strip()
                        # writable = 'TRUE'
                    except (TypeError, ValueError):
                        pass

        _log.debug('  object units = ' + str(object_units))
        _log.debug('  object units details = ' + str(object_units_details))
        _log.debug('  object notes = ' + str(object_notes))

        results = {}
        results['Reference Point Name'] = results[
            'Volttron Point Name'] = object_name
        results['Units'] = object_units
        results['Unit Details'] = object_units_details
        results['BACnet Object Type'] = obj_type
        results['Property'] = 'presentValue'
        results['Writable'] = writable
        results['Index'] = index
        results['Notes'] = object_notes

        self._response_function(context, results)

        # config_writer.writerow(results)
