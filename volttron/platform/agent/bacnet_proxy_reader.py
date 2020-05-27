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


import logging
import weakref
import gevent
from collections import defaultdict
from bacpypes.basetypes import EngineeringUnits
from bacpypes.object import get_datatype
from bacpypes.primitivedata import Enumerated, Unsigned, Boolean, Integer, Real, Double

from volttron.platform.jsonrpc import RemoteError
from volttron.platform.messaging import topics

# Deals with the largest numbers that can be reported.
# see proxy_grab_bacnet_config.py
MAX_RANGE_REPORT = 1.0e+20

_log = logging.getLogger(__name__)


class BACnetReader(object):
    """
    The BACnetReader
    """
    def __init__(self, vip, bacnet_proxy_identity,
                 iam_response_fn=None, config_response_fn=None, batch_size=20):

        if batch_size < 1:
            raise ValueError("batch_size must be larger than 0")
        self._batch_size = batch_size
        self._pubsub = weakref.ref(vip.pubsub)
        self._rpc = weakref.ref(vip.rpc)
        self._proxy_identity = bacnet_proxy_identity
        self._response_function = iam_response_fn
        self._iam_response_fn = iam_response_fn
        self._config_response_fn = config_response_fn
        self._iam_callbacks = {}
        self._send_iam_responses = False
        self._caller_callback = {}

    def start_whois(self, low_device_id=None, high_device_id=None,
                    target_address=None):
        _log.info("Starting WHOIS")
        self._pubsub().subscribe(peer='pubsub', prefix=topics.BACNET_I_AM,
                                 callback=self._iam_handler).get(timeout=3)

        self._send_iam_responses = True
        self._rpc().call(self._proxy_identity, "who_is",
                         low_device_id=low_device_id,
                         high_device_id=high_device_id,
                         target_address=target_address).get(timeout=5.0)

    def stop_iam_responses(self):
        _log.info("Stopping WHOIS")
        self._pubsub().unsubscribe(peer='pubsub', prefix=topics.BACNET_I_AM,
                                   callback=self._iam_handler).get(timeout=3)

        self._send_iam_responses = False

    def get_iam(self, device_id, callback, address=None, timeout=10):
        _log.debug("Getting iam callback")
        self._caller_callback[device_id] = callback
        self._pubsub().subscribe(peer='pubsub', prefix=topics.BACNET_I_AM,
                                 callback=self._iam_handler).get(timeout=3)
        self._rpc().call(self._proxy_identity, "who_is",
                         low_device_id=device_id,
                         high_device_id=device_id,
                         target_address=address).get(timeout=5.0)

    def _iam_handler(self, peer, sender, bus, topic, headers, message):
        """ Handle publishes from who_is.

        There are two different modes that this handler supports.  The first
        is a sending of a single device_id which was started through a call
        to get_iam.  This allows the caller to retrieve only the single device's
        information.  This method is meant to be run from the
        scripts/bacnet/proxy_grab_bacnet_config.py script.

        The second method is when the user calls start_whois.  This will keep
        open the whois publish for the specified number of seconds before
        unsubscribing.  In this method we respond each time any information
        comes into the system.

        These two methods are mutually exclusive.
        """

        device_id = message["device_id"]
        if device_id in self._caller_callback:
            callback = self._caller_callback.pop(device_id)
            _log.info("Received iam for device_id {}".format(device_id))
            _log.debug("Callback received: {}".format(message))
            callback(message)

            # Not 100% sure this won't have issues, but it didn't throw
            # any errors during scripts nor from the vc/vcp combinations.
            gevent.spawn_later(3, self._pubsub().unsubscribe, peer='pubsub',
                               prefix=topics.BACNET_I_AM,
                               callback=self._iam_handler)
            return

        if self._iam_response_fn is None:
            _log.error("No handler set for iam responses.")
            _log.error("IAM response was {}".format(message))
            return

        if self._send_iam_responses:
            _log.info("Received iam for device_id {}".format(device_id))
            _log.debug("iam message is: {}".format(message))
            self._iam_response_fn(message)
        else:
            _log.debug("IAM response not processed {}".format(device_id))

    def read_device_name(self, address, device_id):
        """ Reads the device name from the specified address and device_id

            :param address: Address of the bacnet device
            :param device_id: The device id of the bacnet device.
            :return: The device name or the string "MISSING DEVICE NAME"
        """
        try:
            _log.debug("Reading device name.")
            device_name = self._read_prop(address, "device", device_id,
                                         "objectName")
            _log.debug('device_name = ' + str(device_name))
        except TypeError:
            _log.debug("device missing objectName")
            device_name = "MISSING DEVICE NAME"
        except gevent.Timeout:
            device_name = "Device Timeout"
        except RemoteError as ex:
            device_name = repr(ex)
        except Exception as ex:
            device_name = repr(ex)

        return device_name

    def read_device_description(self, address, device_id):
        """ Reads the device name from the specified address and device_id

            :param address: Address of the bacnet device
            :param device_id: The device id of the bacnet device.
            :return: The device desciption or an empty string
        """
        try:
            _log.debug("Reading device description.")
            device_description = self._read_prop(address, "device", device_id,
                                                "description")
            _log.debug('description = ' + str(device_description))
        except TypeError:
            _log.debug('device missing description')
            device_description = ""
        except RemoteError as e:
            _log.error("REMOTE ERROR")
            _log.error(e.args)
            device_description = ""
        except Exception as ex:
            device_description = repr(ex)

        return device_description

    def read_device_properties(self, target_address, device_id, filter=None):
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
        _log.info('read_device_properties called target_address: {} device_id: {}'.format(
                  target_address, device_id))
        try:
            _log.debug("Reading objectList from device index 0")
            object_count = self._read_prop(target_address, "device", device_id, "objectList", index=0)
            list_property = "objectList"
        except TypeError:
            _log.debug("Type error so reading structuredObjectList of index 0")
            object_count = self._read_prop(target_address, "device", device_id,
                                           "structuredObjectList", index=0)
            list_property = "structuredObjectList"
        except RemoteError as e:
            _log.error("REMOTE ERROR read_device_properties")
            _log.error(e.args)
        except RuntimeError as ex:
            _log.error(repr(ex))

        _log.debug('object_count = ' + str(object_count))

        query_map = {}
        count = 0

        # type_map contains a dictionary keyed off of the bacnet_type string
        # each value holds a list of the lines in the csv file that contains
        # that specific datatype.

        _log.debug("query_map: {}".format(query_map))
        # Loop over each of the objects and interrogate the device for the
        # properties types and indexes.  After this for loop type_map will
        # hold the readable properties from the bacnet device ordered by
        # the type i.e. type_map['analogInput'] = [300324,304050]
        for object_index in range(1, object_count + 1):
            count += 1

            query_map[object_index] = [
                "device", device_id, list_property, object_index
            ]

            if count >= self._batch_size:
                _log.debug("query_map: {}".format(query_map))
                results = self._read_props(target_address, query_map)
                present_values = self._filter_present_value_from_results(
                    results)
                self._process_input(target_address, device_id, present_values)
                query_map = {}
                count = 0

        if count > 0:
            _log.debug("query_map: {}".format(query_map))
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

    def _build_results(self, query_map, result_map):
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
        from pprint import pprint
        objects = defaultdict(dict)
        for key in query_map:
            if key not in result_map:
                _log.debug("MISSING KEY {}".format(key))
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
                obj['object_type'] = query_map[key][0]
        _log.debug("Built objects")
        return objects

    def _process_enumerated(self, object_type, obj):
        units = 'Enum'
        notes = obj.get('description', '').strip()

        present_value_type = get_datatype(object_type, 'presentValue')
        values = list(present_value_type.enumerations.values())
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
            if "relinquishDefault" in obj:
                default_value = obj['relinquishDefault']
                _log.debug('DEFAULT VALUE IS: {}'.format(default_value))
                _log.debug('ENUMERATION VALUES: {}'.format(present_value_type.enumerations))
                for k, v in present_value_type.enumerations.items():
                    if v == default_value:
                        units_details += ' (default {default})'.format(
                            default=default_value)
                        break

        if not notes:
            enum_strings = []
            enum_items = sorted(present_value_type(0).enumerations.items())
            for name, value in enum_items:
                enum_strings.append(str(value) + '=' + name)

            notes = present_value_type.__name__ + ': ' + ', '.join(enum_strings)

        return units, units_details, notes

    def _process_units(self, object_type, obj):
        units_details = ''
        notes = obj.get('description', '').strip()

        if object_type.startswith('multiState'):
            units = 'State'
            state_count = obj.get('numberOfStates')
            if state_count:
                units_details = 'State count: {}'.format(state_count)

            enum_strings = []
            state_list = obj.get('stateText')
            if state_list:
                for name in state_list[1:]:
                    enum_strings.append(name)
                notes = ', '.join('{}={}'.format(x, y) for x, y in enumerate(enum_strings, start=1))

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

        obj_units = "UNKNOWN UNIT ENUM VALUE"
        try:
            obj_units = EngineeringUnits(obj.get('units')).value
            if isinstance(obj_units, int):
                obj_units = 'UNKNOWN UNIT ENUM VALUE: ' + str(obj.get('units'))
        except ValueError:
            if obj.get('units'):
                obj_units += ": " + str(obj.get('units'))
        units_details = ''
        notes = obj.get('description', '').strip()

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
                if 'relinquishDefault' in obj:
                    units_details += ' (default {default})'.format(
                        default=obj.get('relinquishDefault'))

                    units_details = units_details.strip()

        return obj_units, units_details, notes

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

        _log.debug('emit_responses: objects: {}'.format(objects))
        for index, obj in objects.items():
            object_type = obj['object_type']
            present_value_type = get_datatype(object_type, 'presentValue')

            object_units_details = ''
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
        _log.debug('process_input: items: {}'.format(input_items))
        query_mapping = {}
        count = 0
        processed = {}

        for item in input_items:
            index = item['index']
            object_type = item['bacnet_type']
            key = (target_address, device_id, object_type, index)
            if key in processed:
                _log.debug("Duplicate detected continuing")
                continue

            processed[key] = 1

            new_map = self._build_query_map_for_type(object_type, index)
            query_mapping.update(new_map)

            if count >= self._batch_size:
                try:

                    results = self._read_props(target_address, query_mapping)
                    objects = self._build_results(query_mapping, results)
                    _log.debug('Built bacnet Objects 1: {}'.format(objects))
                    self._emit_responses(device_id, target_address, objects)
                    count = 0
                except Exception as ex:
                    _log.error(repr(ex))
                except RemoteError as e:
                    _log.error('REMOTE ERROR: {}'.format(e))
                query_mapping = {}
            count += 1

        if query_mapping:
            try:
                results = self._read_props(target_address, query_mapping)
                objects = self._build_results(query_mapping, results)
            except RemoteError as e:
                _log.error("REMOTE ERROR 2:")
                _log.error(e.args)
            except Exception as ex:
                _log.error(repr(ex))
            else:
                _log.debug('Built bacnet Objects 2: {}'.format(objects))
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
        _log.debug("_read_props for address: {} params: {}".format(address, parameters))
        return self._rpc().call(self._proxy_identity, "read_properties", address, parameters).get(timeout=20)

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

        for object_index in range(1, object_count + 1):
            _log.debug('property_name index = ' + repr(object_index))

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
        _log.debug('obj_type = ' + repr(obj_type))
        _log.debug('bacnet_index = ' + repr(index))
        context = None
        if obj_type == "device":
            context = dict(address=address, device=index)

        writable = 'FALSE'

        subondinate_list_property = get_datatype(obj_type, 'subordinateList')
        if subondinate_list_property is not None:
            _log.debug('Processing StructuredViewObject')
            # self._process_device_object_reference(address, obj_type, index,
            #                                      'subordinateList',
            #                                      max_range_report,
            #                                      config_writer)
            return

        subondinate_list_property = get_datatype(obj_type, 'zoneMembers')
        if subondinate_list_property is not None:
            _log.debug('Processing LifeSafetyZoneObject')
            # self._process_device_object_reference(address, obj_type, index,
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
            object_name = self._read_prop(address, obj_type, index, "objectName")
            _log.debug('object name = ' + object_name)
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
            values = list(present_value_type.enumerations.values())
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
                    default_value = self._read_prop(address, obj_type, index, "relinquishDefault")
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
                enum_items = sorted(present_value_type(0).enumerations.items())
                for name, value in enum_items:
                    enum_strings.append(str(value) + '=' + name)

                object_notes = present_value_type.__name__ + ': ' + ', '.join(enum_strings)

        elif issubclass(present_value_type, Boolean):
            object_units = 'Boolean'

        elif get_datatype(obj_type, 'units') is None:
            if obj_type.startswith('multiState'):
                object_units = 'State'
                try:
                    state_count = self._read_prop(address, obj_type, index, "numberOfStates")
                    object_units_details = 'State count: {}'.format(state_count)
                except TypeError:
                    pass

                try:
                    enum_strings = []
                    state_list = self._read_prop(address, obj_type, index, "stateText")
                    for name in state_list[1:]:
                        enum_strings.append(name)

                    object_notes = ', '.join('{}={}'.format(x, y) for x, y in enumerate(enum_strings, start=1))

                except TypeError:
                    pass

                if obj_type != 'multiStateInput':
                    try:
                        default_value = self._read_prop(address, obj_type, index, "relinquishDefault")
                        object_units_details += ' (default {default})'.format(default=default_value)
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

            if isinstance(object_units, int):
                object_units = 'UNKNOWN UNIT ENUM VALUE: ' + str(object_units)

            if obj_type.startswith('analog') or obj_type in (
                    'largeAnalogValue', 'integerValue', 'positiveIntegerValue'):
                # Value objects never have a resolution property in practice.
                if not object_notes and not obj_type.endswith('Value'):
                    try:
                        res_value = self._read_prop(address, obj_type, index, "resolution")
                        object_notes = 'Resolution: {resolution:.6g}'.format(
                            resolution=res_value)
                    except (TypeError, ValueError):
                        pass

                if obj_type not in (
                        'largeAnalogValue', 'integerValue',
                        'positiveIntegerValue'):
                    try:
                        min_value = self._read_prop(address, obj_type, index, "minPresValue")
                        max_value = self._read_prop(address, obj_type, index, "maxPresValue")

                        has_min = (min_value is not None) and (min_value > -max_range_report)
                        has_max = (max_value is not None) and (max_value < max_range_report)

                        if has_min and has_max:
                            object_units_details = '{min:.2f} to {max:.2f}'.format(min=min_value, max=max_value)
                        elif has_min:
                            object_units_details = 'Min: {min:.2f}'.format(min=min_value)
                        elif has_max:
                            object_units_details = 'Max: {max:.2f}'.format(max=max_value)
                        else:
                            object_units_details = 'No limits.'
                    except (TypeError, ValueError):
                        pass

                if obj_type != 'analogInput':
                    try:
                        default_value = self._read_prop(address, obj_type, index, "relinquishDefault")
                        object_units_details += ' (default {default})'.format(default=default_value)
                        object_units_details = object_units_details.strip()
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
