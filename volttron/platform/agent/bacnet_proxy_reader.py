# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2017, Battelle Memorial Institute
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
# Government nor the United States Department of Energy, nor Battelle,
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
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}


from __future__ import absolute_import, print_function
from collections import defaultdict
import logging
import weakref

from bacpypes.object import get_datatype
from bacpypes.primitivedata import (Enumerated, Unsigned, Boolean, Integer,
                                    Real, Double)

from volttron.platform.jsonrpc import RemoteError

# Deals with the largest numbers that can be reported.
# see proxy_grab_bacnet_config.py
MAX_RANGE_REPORT = 1.0e+20


class BACnetReader(object):
    def __init__(self, rpc, bacnet_proxy_identity,
                 response_function=None):
        self._log = logging.getLogger(self.__class__.__name__)
        self._log.info("Creating {}".format(self.__class__.__name__))
        self._rpc = weakref.ref(rpc)
        self._proxy_identity = bacnet_proxy_identity
        self._response_function = response_function

    def read_device_name(self, address, device_id):
        """ Reads the device name from the specified address and device_id

            :param address: Address of the bacnet device
            :param device_id: The device id of the bacnet device.
            :return: The device name or the string "MISSING DEVICE NAME"
        """
        try:
            self._log.debug("Reading device name.")
            device_name = self._read_prop(address, "device", device_id,
                                         "objectName")
            self._log.debug('device_name = ' + str(device_name))
        except TypeError:
            self._log.debug("device missing objectName")
            device_name = "MISSING DEVICE NAME"
        return device_name

    def read_device_description(self, address, device_id):
        """ Reads the device name from the specified address and device_id

            :param address: Address of the bacnet device
            :param device_id: The device id of the bacnet device.
            :return: The device desciption or an empty string
        """
        try:
            self._log.debug("Reading device description.")
            device_description = self._read_prop(address, "device", device_id,
                                                "description")
            self._log.debug('description = ' + str(device_description))
        except TypeError:
            self._log.debug('device missing description')
            device_description = ""
        except RemoteError as e:
            self._log.error("REMOTE ERROR")
            self._log.error(e.args)
            device_description = ""

        return device_description

    def read_device_properties(self, target_address, device_id, filter):
        """ Starts the processes of reading a device's meta data.

            The device will first be queried for all of it's objects.  For each
            of the returned indexes only the properties that have a
            presentValue as a property will be used.  Processing of the objects
            will continue in batches until all of the device points have been
            received.

            Data will ultimately be written through the `self._emit_reresponses`
            function.  The `self._response_function` that was set in the
            constructor of the object will be used to return the data to the
            caller.

            :param target_address: The address of the bacnet device
            :param device_id: The device_id of the bacnet device
            :param filter: A list of two-tuples with (bacnet_type, [index])
                where the bacnet_type is one of the bacnet_type strings and the
                [index] is an array of indexes to return.
        """
        self._log.info(
            'read_device_properties called target_address: {} device_id: {}'.format(
                target_address, device_id
            ))
        try:
            self._log.debug("Reading objectList from device index 0")
            object_count = self._read_prop(target_address, "device", device_id,
                                           "objectList", index=0)
            list_property = "objectList"
        except TypeError:
            self._log.debug("Type error so reading structuredObjectList of index 0")
            object_count = self._read_prop(target_address, "device", device_id,
                                           "structuredObjectList", index=0)
            list_property = "structuredObjectList"
        except RemoteError as e:
            self._log.error("REMOTE ERROR read_device_properties")
            self._log.error(e.args)
            object_count = 0

        self._log.debug('object_count = ' + str(object_count))

        query_map = {}
        count = 0
        results = None

        # type_map contains a dictionary keyed off of the bacnet_type string
        # each value holds a list of the lines in the csv file that contains
        # that specific datatype.
        type_map = defaultdict(list)

        self._log.debug("query_map: {}".format(query_map))
        # Loop over each of the objects and interrogate the device for the
        # properties types and indexes.  After this for loop type_map will
        # hold the readable properties from the bacnet device ordered by
        # the type i.e. type_map['analogInput'] = [300324,304050]
        for object_index in xrange(1, object_count + 1):
            count += 1

            query_map[object_index] = [
                "device", device_id, list_property, object_index
            ]

            if count >= 25:
                self._log.debug("query_map: {}".format(query_map))
                results = self._read_props(target_address, query_map)
                present_values = self._filter_present_value_from_results(
                    results)
                self._process_input(target_address, device_id, present_values)
                query_map = {}
                count = 0

        if count > 0:
            self._log.debug("query_map: {}".format(query_map))
            results = self._read_props(target_address, query_map)
            present_values = self._filter_present_value_from_results(results)
            self._process_input(target_address, device_id, present_values)

        self._response_function(dict(device_id=device_id,
                                     address=target_address,
                                     status="COMPLETE"), {})

    def _build_query_map_for_type(self, object_type, index):
        """ Build a map that can be sent to the _read_props function.

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

    def _build_results(self, object_type, query_map, result_map):
        """ Create dictionary objects.

        The `build_results` function creates a dictionary of dictionaries.  The
        results will be keyed off of the index of the device property.  Each
        key query_map will be split on a - producing (index, property) tuple.
        The property will then be added as a key to the dictionary
        corresponding to the dictionary.

        :param: object_type: string representation of the bacnet type
        :param: query_map: mapping of request values that were sent to the
            `_read_props` function.
        :param: result_map: mapping that was returned from the `_read_props`
            function.
        :returns: dict: dictionary of dictinaries based upon the index of
            device properties.
        """
        objects = defaultdict(dict)
        for key in query_map:
            if key not in result_map:
                print("MISSING KEY {}".format(key))
                continue
            index, property = key.split('-')

            obj = objects[index]
            obj['index'] = index
            if property == 'objectName':
                if not result_map[key]:
                    obj['object_name'] = 'MISSING OBJECT NAME'
                else:
                    obj['object_name'] = result_map[key]
            obj[property] = result_map[key]
            if 'object_type' not in obj:
                obj['object_type'] = object_type
        print('Built objects: {}'.format(objects))
        return objects

    def _process_enumerated(self, object_type, obj):
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
                self._log.debug('DEFAULT VALUE IS: {}'.format(default_value))
                self._log.debug('ENUMERATION VALUES: {}'.format(
                    present_value_type.enumerations))
                for k, v in present_value_type.enumerations.items():
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

    def _process_units(self, object_type, obj):
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

    def _process_unknown(self, object_type, obj):
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

    def _emit_responses(self, device_id, target_address, objects):
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

        self._log.debug('emit_responses: objects: {}'.format(objects))
        for index, obj in objects.items():
            object_type = obj['object_type']
            present_value_type = get_datatype(object_type, 'presentValue')

            object_units_details = ''
            object_units = ''
            object_notes = ''

            if issubclass(present_value_type, Boolean):
                object_units = 'Boolean'
            elif issubclass(present_value_type, Enumerated):
                object_units, object_units_details, object_notes = \
                    self._process_enumerated(object_type, obj)
            elif get_datatype(object_type, 'units') is None:
                object_units, object_units_details, object_notes = \
                    self._process_units(object_type, obj)
            else:
                object_units, object_units_details, object_notes = \
                    self._process_unknown(object_type, obj)

            results = {}
            results['Reference Point Name'] = results[
                 'Volttron Point Name'] = obj['object_name']
            results['Units'] = object_units
            results['Unit Details'] = object_units_details
            results['BACnet Object Type'] = object_type
            results['Property'] = 'presentValue'
            results['Writable'] = 'FALSE'
            results['Index'] = obj['index']
            results['Notes'] = object_notes
            self._response_function(dict(device_id=device_id,
                                         address=target_address), results)

    def _process_input(self, target_address, device_id, input_items):
        self._log.debug('process_input: items: {}'.format(input_items))
        query_mapping = {}
        results = None
        object_notes = None
        count = 0
        output = {}
        processed = {}

        for item in input_items:
            index = item['index']
            object_type = item['bacnet_type']
            key = (target_address, device_id, object_type, index)
            if key in processed:
                self._log.debug("Duplicate detected continuing")
                continue

            processed[key] = 1

            new_map = self._build_query_map_for_type(object_type, index)
            query_mapping.update(new_map)

            if count >= 25:
                try:

                    results = self._read_props(target_address, query_mapping)
                    objects = self._build_results(object_type, query_mapping,
                                                  results)
                    self._log.debug('Built bacnet Objects 1: {}'.format(objects))
                    self._emit_responses(device_id, target_address, objects)
                    count = 0
                except RemoteError as e:
                    self._log.error('REMOTE ERROR: {}'.format(e))
                query_mapping = {}
            count += 1

        if query_mapping:
            try:
                results = self._read_props(target_address, query_mapping)
                objects = self._build_results(object_type, query_mapping,
                                              results)
            except RemoteError as e:
                self._log.error("REMOTE ERROR 2:")
                self._log.error(e.args)
            else:
                self._log.debug('Built bacnet Objects 2: {}'.format(objects))
                self._emit_responses(device_id, target_address, objects)

    def _filter_present_value_from_results(self, results):
        """ Filter the results so that only presentValue datatypes are kept.

        The results of this function have an array of dictionaries.

        :param results: The results from a _read_props function.
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

    def _read_props(self, address, parameters):
        self._log.debug("_read_props for address: {} params: {}".format(
            address, parameters
        ))
        return self._rpc().call(self._proxy_identity, "read_properties",
                                address,
                                parameters).get(timeout=20)

    def _read_prop(self, address, obj_type, obj_inst, prop_id, index=None):
        point_map = {"result": [obj_type,
                                obj_inst,
                                prop_id,
                                index]}

        result = self._read_props(address, point_map)
        try:
            return result["result"]
        except KeyError:
            pass

    # =========================================================================
    # Untested and commented out calles to this code. I am leavingg it in
    # so that we don't have to rewrite it later ;)
    # =========================================================================
    def _process_device_object_reference(self, address, obj_type, obj_inst,
                                         property_name,
                                         max_range_report, config_writer):
        object_count = self._read_prop(address, obj_type, obj_inst,
                                       property_name, index=0)

        for object_index in xrange(1, object_count + 1):
            self._log.debug('property_name index = ' + repr(object_index))

            object_reference = self._read_prop(address,
                                               obj_type,
                                               obj_inst,
                                               property_name,
                                               index=object_index)

            # Skip references to objects on other devices.
            if object_reference.deviceIdentifier is not None:
                continue

            sub_obj_type, sub_obj_index = object_reference.objectIdentifier

            self._process_object(address, sub_obj_type, sub_obj_index,
                                 max_range_report,
                                 config_writer)

    def _process_object(self, address, obj_type, index, max_range_report):
        self._log.debug('obj_type = ' + repr(obj_type))
        self._log.debug('bacnet_index = ' + repr(index))
        context = None
        if obj_type == "device":
            context = dict(address=address, device=index)

        writable = 'FALSE'

        subondinate_list_property = get_datatype(obj_type, 'subordinateList')
        if subondinate_list_property is not None:
            self._log.debug('Processing StructuredViewObject')
            # self._process_device_object_reference(address, obj_type, index,
            #                                      'subordinateList',
            #                                      max_range_report,
            #                                      config_writer)
            return

        subondinate_list_property = get_datatype(obj_type, 'zoneMembers')
        if subondinate_list_property is not None:
            self._log.debug('Processing LifeSafetyZoneObject')
            # self._process_device_object_reference(address, obj_type, index,
            #                                      'zoneMembers',
            #                                      max_range_report,
            #                                      config_writer)
            return

        present_value_type = get_datatype(obj_type, 'presentValue')
        if present_value_type is None:
            self._log.debug('This object type has no presentValue. Skipping.')
            return

        if not issubclass(present_value_type, (Enumerated,
                                               Unsigned,
                                               Boolean,
                                               Integer,
                                               Real,
                                               Double)):
            self._log.debug(
                'presenValue is an unsupported type: ' + repr(
                    present_value_type))
            return

        try:
            object_name = self._read_prop(address, obj_type, index, "objectName")
            self._log.debug('object name = ' + object_name)
        except TypeError:
            object_name = "NO NAME! PLEASE NAME THIS."

        try:
            object_notes = self._read_prop(address, obj_type, index,
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
                    default_value = self._read_prop(address, obj_type, index,
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
                    state_count = self._read_prop(address, obj_type, index,
                                                 "numberOfStates")
                    object_units_details = 'State count: {}'.format(state_count)
                except TypeError:
                    pass

                try:
                    enum_strings = []
                    state_list = self._read_prop(address, obj_type, index,
                                                "stateText")
                    for name in state_list[1:]:
                        enum_strings.append(name)

                    object_notes = ', '.join('{}={}'.format(x, y) for x, y in
                                             enumerate(enum_strings, start=1))

                except TypeError:
                    pass

                if obj_type != 'multiStateInput':
                    try:
                        default_value = self._read_prop(address, obj_type, index,
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
                object_units = self._read_prop(address, obj_type, index, "units")
            except TypeError:
                object_units = 'UNKNOWN UNITS'

            if isinstance(object_units, (int, long)):
                object_units = 'UNKNOWN UNIT ENUM VALUE: ' + str(object_units)

            if obj_type.startswith('analog') or obj_type in (
                    'largeAnalogValue', 'integerValue', 'positiveIntegerValue'):
                # Value objects never have a resolution property in practice.
                if not object_notes and not obj_type.endswith('Value'):
                    try:
                        res_value = self._read_prop(address, obj_type, index,
                                                   "resolution")
                        object_notes = 'Resolution: {resolution:.6g}'.format(
                            resolution=res_value)
                    except (TypeError, ValueError):
                        pass

                if obj_type not in (
                        'largeAnalogValue', 'integerValue',
                        'positiveIntegerValue'):
                    try:
                        min_value = self._read_prop(address, obj_type, index,
                                                   "minPresValue")
                        max_value = self._read_prop(address, obj_type, index,
                                                   "maxPresValue")

                        has_min = (min_value is not None) and (min_value > -max_range_report)
                        has_max = (max_value is not None) and (max_value < max_range_report)

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
                        default_value = self._read_prop(address, obj_type, index,
                                                       "relinquishDefault")
                        object_units_details += ' (default {default})'.format(
                            default=default_value)
                        object_units_details = object_units_details.strip()
                        # writable = 'TRUE'
                    except (TypeError, ValueError):
                        pass

        self._log.debug('  object units = ' + str(object_units))
        self._log.debug('  object units details = ' + str(object_units_details))
        self._log.debug('  object notes = ' + str(object_notes))

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
