from collections import defaultdict
from csv import DictWriter
import logging
import weakref
from cStringIO import StringIO

from bacpypes.object import get_datatype
from bacpypes.primitivedata import (Enumerated, Unsigned, Boolean, Integer,
                                    Real, Double)

_log = logging.getLogger(__name__)

# Deals with the largest numbers that can be reported.
# see proxy_grab_bacnet_config.py
MAX_RANGE_REPORT = 1.0e+20


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
        _log.info('read_device_extended called.')
        default_range_report = 1.0e+20
        for bac_type, indexes in filter.items():
            query = {}

            for point_index in indexes:
                self.process_object(target_address, bac_type, point_index,
                                    default_range_report)

    def build_query_map_for_type(self, object_type, index):
        """ Build a map that can be sent to the read_props function.

            This function build keys based upon the object_type and index so
            that the return value from the eventual read_prosps call to the
            bacnet proxy can be read easily.

            This function was a based upon the process_object function.
            Instead of each level of the if then else structure making its
            own call to the query map, it makes a single call and retireves
            the properties.  This makes it  much more efficient in terms of
            the rpc call through the bacnet proxy.

        """
        query_map = {}

        # Retrieve the class object for the object type.  This allows
        # interrogation of the class to make decisions on what should be
        # loaded into the query_map.
        present_value_type = get_datatype(object_type, 'presentValue')

        # The object name translates into the point name of the object.
        key = '{}-{}'.format(index, "objectName")
        query_map[key] = [object_type, index, "objectName"]

        key = '{}-{}'.format(index, 'description')
        query_map[key] = [object_type, index, "description"]

        if issubclass(present_value_type, Enumerated):
            key = '{}-{}'.format(index, "relinquishDefault")
            query_map[key] = [object_type, index, "relinquishDefault"]

        elif issubclass(present_value_type, Boolean):
            pass
        elif get_datatype(object_type, 'units') is None:
            key = '{}-{}'.format(index, 'numberOfStates')
            query_map[key] = [object_type, index, "numberOfStates"]

            key = '{}-{}'.format(index, 'stateText')
            query_map[key] = [object_type, index, "stateText"]

            if object_type != 'multiSTateInput':
                key = '{}-{}'.format(index, "relinquishDefault")
                query_map[key] = [object_type, index, "relinquishDefault"]
            elif object_type == 'loop':
                pass
            else:
                pass
        else:
            key = '{}-{}'.format(index, 'units')
            query_map[key] = [object_type, index, "units"]

            key = '{}-{}'.format(index, 'resolution')
            query_map[key] = [object_type, index, "resolution"]

            if object_type not in (
                    'largeAnalogValue', 'integerValue',
                    'positiveIntegerValue'):

                key = '{}-{}'.format(index, 'minPresValue')
                query_map[key] = [object_type, index, 'minPresValue']

                key = '{}-{}'.format(index, 'maxPresValue')
                query_map[key] = [object_type, index, 'maxPresValue']

            if object_type != 'analogInput':
                key = '{}-{}'.format(index, "relinquishDefault")
                query_map[key] = [object_type, index, "relinquishDefault"]

        return query_map

    def build_results(self, object_type, query_map, result_map):
        objects = defaultdict(dict)
        for key in query_map:
            if key not in result_map:
                print("MISSING KEY {}".format(key))
                continue
            index, property = key.split('-')

            obj = objects[index]
            obj['index'] = index
            obj[property] = result_map[key]
            if 'object_type' not in obj:
                obj['object_type'] = object_type
        print('Built objects: {}'.format(objects))
        return objects

    def process_enumerated(self, object_type, obj):
        units = ''
        units_details = ''
        notes = ''

        units = 'Enum'
        present_value_type = get_datatype(object_type, 'presentValue')
        values = present_value_type.enumerations.values()
        min_value = min(values)
        max_value = max(values)

        vendor_range = ''
        if hasattr(present_value_type, 'vendor_range'):
            vendor_min, vendor_max = present_value_type.vendor_range
            vendor_range = ' (vendor {min}-{max})'.format(min=vendor_min,
                                                          max=vendor_max)

        units_details = '{min}-{max}{vendor}'.format(min=min_value,
                                                     max=max_value,
                                                     vendor=vendor_range)

        if not object_type.endswith('Input'):
            default_value = obj.get("relinquishDefault")
            if default_value:
                _log.debug('DEFAULT VALUE IS: {}'.format(default_value))
                _log.debug('ENUMERATION VALUES: {}'.format(
                    present_value_type.enumerations))
                for k, v in present_value_type.enumerations.items():
                    print("key {} value {}".format(k, v))
                    if v == default_value:
                        units_details += ' (default {default})'.format(
                            default=k)

        if not notes:
            enum_strings = []
            for name in Enumerated.keylist(present_value_type(0)):
                value = present_value_type.enumerations[name]
                enum_strings.append(str(value) + '=' + name)

            notes = present_value_type.__name__ + ': ' + ', '.join(
                enum_strings)

        return units, units_details, notes


    def process_units(self, object_type, obj):
        units = ''
        units_details = ''
        notes = ''

        if object_type.startswith('multiState'):
            units = 'State'
            state_count = obj.get('numberOfStates')
            if state_count:
                units_detailes = 'State count: {}'.format(state_count)

            enum_strings = []
            state_list = obj.get('stateText')
            if state_list:
                for name in state_list[1:]:
                    enum_strings.append(name)
                notes = ', '.join('{}={}'.format(x, y) for x, y in
                                             enumerate(enum_strings, start=1))

            if object_type != 'multiStateInput':
                default_value = obj.get('relinquishDefault')
                if default_value:
                    units_details += ' (default {default})'.format(
                        default=default_value)
                    units_details = units_details.strip()
        elif object_type == 'loop':
            units = 'Loop'
        else:
            units = 'UNKNOWN UNITS'

        return units, units_details, notes

    def process_unknown(self, object_type, obj):
        units = obj.get('units', 'UNKNOWN UNITS')
        units_details = ''
        notes = ''
        if isinstance(units, (int, long)):
            units = 'UNKNOWN UNIT ENUM VALUE: ' + str(units)

        if object_type.startswith('analog') or object_type in (
                'largeAnalogValue', 'integerValue',
                'positiveIntegerValue'):
            if not object_type.endswith('Value'):
                res_value = obj.get('resolution')
                if res_value:
                    notes = 'Resolution: {resolution:.6g}'.format(
                        resolution=res_value)

        if object_type not in (
                'largeAnalogValue', 'integerValue',
                'positiveIntegerValue'):

            min_value = obj.get('minPresValue', -MAX_RANGE_REPORT)
            max_value = obj.get('maxPresValue', MAX_RANGE_REPORT)

            has_min = min_value > -MAX_RANGE_REPORT
            has_max = max_value < MAX_RANGE_REPORT
            if has_min and has_max:
                units_details = '{min:.2f} to {max:.2f}'.format(
                    min=min_value, max=max_value)
            elif has_min:
                units_details = 'Min: {min:.2f}'.format(
                    min=min_value)
            elif has_max:
                units_details = 'Max: {max:.2f}'.format(
                    max=max_value)
            else:
                units_details = 'No limits.'

        if object_type != 'analogInput':
            default_value = obj.get('relinquishDefault')
            if default_value:
                units_details += ' (default {default})'.format(
                    default=default_value)

                units_details = units_details.strip()

        return units, units_details, notes

    def emit_responses(self, device_id, objects):
        """
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

        :param objects:
        :return:
        """
        for index, obj in objects.items():
            print('Object: {}'.format(obj))
            object_type = obj['object_type']
            present_value_type = get_datatype(object_type, 'presentValue')

            object_units_details = ''
            object_units = ''
            object_notes = ''

            if issubclass(present_value_type, Boolean):
                object_units = 'Boolean'
            elif issubclass(present_value_type, Enumerated):
                object_units, object_units_details, object_notes = \
                    self.process_enumerated(object_type, obj)
            elif get_datatype(object_type, 'units') is None:
                object_units, object_units_details, object_notes = \
                    self.process_units(object_type, obj)
            else:
                object_units, object_units_details, object_notes = \
                    self.process_unknown(object_type, obj)

            results = {}
            # results['Reference Point Name'] = results[
            #     'Volttron Point Name'] = object_name
            results['Units'] = object_units
            results['Unit Details'] = object_units_details
            results['BACnet Object Type'] = object_type
            results['Property'] = 'presentValue'
            results['Writable'] = 'FALSE'
            results['Index'] = obj['index']
            results['Notes'] = object_notes

            self._response_function(dict(device_id=device_id), results)

    def process_input(self, target_address, device_id, input_items, extended):

        query_mapping = {}
        results = None
        object_notes = None
        count = 0
        output = {}
        for item in input_items:
            index = item['index']
            object_type = item['bacnet_type']

            new_map = self.build_query_map_for_type(object_type, index)
            query_mapping.update(new_map)

            if count >= 5:
                print('QueryMap: {}'.format(query_mapping))
                results = self.read_props(target_address, query_mapping)
                print('RESULTS: {}'.format(results))
                objects = self.build_results(object_type, query_mapping,
                                             results)
                print('OBJECTS: {}'.format(objects))
                self.emit_responses(device_id, objects)
                #break
                count = 0
                query_mapping = {}
            count += 1

        if query_mapping:
            results = self.read_props(target_address, query_mapping)
            objects = self.build_results(object_type, query_mapping,
                                         results)
            print('OBJECTS: {}'.format(objects))
            self.emit_responses(device_id, objects)

    def _filter_present_value_from_results(self, results):
        """ Filter the results so that only presentValue datatypes are kept.

        The results of this function have an array of dictionaries.

        :param results: The results from a read_props function.
        :return: An array of dictionaries.
        """
        # Currently our driver only deals with objects that have a
        # presentValue datatype.  This gives a list of dictionary's that
        # represent the individual lines in the config file (note not all of
        # the properties are currently present in the dictionary)
        presentValues = [dict(index=v[1], writable="FALSE",
                              datatype=get_datatype(v[0], 'presentValue'),
                              bacnet_type=v[0])
                         for k, v in results.items()
                         if get_datatype(v[0], 'presentValue')]
        return presentValues

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
                def read_prop(self, address, obj_type, obj_inst, prop_id, index=None):
        point_map = {"result": [obj_type,
                                obj_inst,
                                prop_id,
                                index]}

        """
        _log.info('read_device_primary called.')
        try:
            object_count = self.read_prop(target_address, "device", device_id,
                                          "objectList", index=0)
            list_property = "objectList"
        except TypeError:
            object_count = self.read_prop(target_address, "device", device_id,
                                          "structuredObjectList", index=0)
            list_property = "structuredObjectList"

        _log.debug('object_count = ' + str(object_count))

        query_map = {}
        count = 0
        results = None

        # type_map contains a dictionary keyed off of the bacnet_type string
        # each value holds a list of the lines in the csv file that contains
        # that specific datatype.
        type_map = defaultdict(list)

        # Loop over each of the objects and interrogate the device for the
        # properties types and indexes.  After this for loop type_map will
        # hold the readable properties from the bacnet device ordered by
        # the type i.e. type_map['analogInput'] = [300324,304050]
        for object_index in xrange(1, object_count + 1):
            count += 1

            query_map[object_index] = [
                "device", device_id, list_property, object_index
            ]
            if count >= 100:
                results = self.read_props(target_address, query_map)
                presentValues = self._filter_present_value_from_results(results)
                for pv in presentValues:
                    type_map[pv['bacnet_type']].append(pv)
                query_map = {}
                count = 0

        if count > 0:
            results = self.read_props(target_address, query_map)
            presentValues = self._filter_present_value_from_results(results)
            for pv in presentValues:
                type_map[pv['bacnet_type']].append(pv)
            query_map = {}

        print('TYPE_MAP: {}'.format(type_map))

        processing_map = {
            # get data for any analog, largeAnalogValue, integerValue or
            # positiveIntegerValue objects.
            '*Input': self.process_input
        }
        #
        # for k, v in type_map.items():
        #     if k.endswith('Input'):
        #         processing_map['*Input'](target_address, device_id, v)

        for k, v in type_map.items():
            _log.debug('Processing *Input {}'.format(k))
            processing_map['*Input'](target_address, device_id, v, False)

    def process_enum(self, address, obj_type, index, present_value_type):
        """
        results['Reference Point Name'] = results[
            'Volttron Point Name'] = object_name
        results['Units'] = object_units
        results['Unit Details'] = object_units_details
        results['BACnet Object Type'] = obj_type
        results['Property'] = 'presentValue'
        results['Writable'] = writable
        results['Index'] = index
        results['Notes'] = object_notes
        :param address:
        :param obj_type:
        :param index:
        :param present_value_type:
        :return:
        """
        results = dict(Units='Enum', Property='presentValue', Notes='')

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

        results['Unit Details'] = object_units_details

        enum_strings = []
        for name in Enumerated.keylist(present_value_type(0)):
            value = present_value_type.enumerations[name]
            enum_strings.append(str(value) + '=' + name)

        results['Notes'] = present_value_type.__name__ + ': ' + ', '.join(
            enum_strings)

        return results

    def read_device_properties(self, target_address, device_id):
        buffer = StringIO()
        config_writer = DictWriter(buffer, ('Reference Point Name',
                                            'Volttron Point Name',
                                            'Units',
                                            'Unit Details',
                                            'BACnet Object Type',
                                            'Property',
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

        index_list = []
        queries = {}

        for object_index in xrange(1, object_count + 1):

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

        sval = buffer.getvalue()
        _log.debug('VALUE is: {}'.format(sval))
        buffer.close()
        return sval

    def read_props(self, address, parameters):
        return self._rpc().call(self._proxy_identity, "read_properties",
                                address,
                                parameters).get(timeout=20)

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
        context = None
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
