import logging
import weakref

from bacpypes.object import get_datatype
from bacpypes.primitivedata import (Enumerated, Unsigned, Boolean, Integer,
                                    Real, Double)

_log = logging.getLogger(__name__)


class BACnetReader(object):
    def __init__(self, rpc, bacnet_proxy_identity):
        _log.info("Creating {}".format(self.__class__.__name__))
        self._rpc = weakref.ref(rpc)
        self._proxy_identity = bacnet_proxy_identity

    def read_props(self, address, parameters):
        return self._rpc().call("platform.bacnet_proxy", "read_properties",
                                address,
                                parameters).get(timeout=5)

    def read_prop(self, address, obj_type, obj_inst, prop_id, index=None):
        point_map = {"result": [obj_type,
                                obj_inst,
                                prop_id,
                                index]}

        result = self.read_props(address, point_map)

        return result.get("result")

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

    def process_object(self, address, obj_type, index, max_range_report,
                       config_writer):
        _log.debug('obj_type = ' + repr(obj_type))
        _log.debug('bacnet_index = ' + repr(index))

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
                    except TypeError:
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
                    except TypeError:
                        pass

                if obj_type != 'analogInput':
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

        _log.debug('  object units = ' + str(object_units))
        _log.debug('  object units details = ' + str(object_units_details))
        _log.debug('  object notes = ' + object_notes)

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

        config_writer.writerow(results)
