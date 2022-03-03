# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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

import sys
import argparse
import traceback
from csv import DictWriter
from os.path import basename
from bacpypes.debugging import bacpypes_debugging, ModuleLogger
from bacpypes.app import BIPSimpleApplication
from bacpypes.service.device import LocalDeviceObject
from bacpypes.consolelogging import ConfigArgumentParser
from bacpypes.pdu import Address, GlobalBroadcast
from bacpypes.core import run, stop
from bacpypes.apdu import WhoIsRequest, IAmRequest, ReadPropertyRequest, ReadPropertyACK
from bacpypes.errors import DecodingError
from bacpypes.task import TaskManager
from bacpypes.object import get_datatype
from bacpypes.primitivedata import Enumerated, Unsigned, Boolean, Integer, Real, Double
from bacpypes.constructeddata import Array
from volttron.platform import jsonapi

"""
Simple utility to scrape device registers and write them to a configuration file.
"""

# Make sure the TaskManager singleton exists...
task_manager = TaskManager()
_debug = 0
_log = ModuleLogger(globals())


@bacpypes_debugging
class SynchronousApplication(BIPSimpleApplication):
    def __init__(self, *args):
        SynchronousApplication._debug("__init__ %r", args)
        BIPSimpleApplication.__init__(self, *args)
        self.expect_confirmation = True
        self.expected_device_id = ""
        self.apdu = None

    def confirmation(self, apdu):
        self.apdu = apdu
        stop()
        
    def indication(self, apdu):
        # We only care about indications if we sent out a who is request.
        if not isinstance(self._request, WhoIsRequest):
            _log.debug("Ignoring indication as we don't have an outstanding WhoIs")
            return
        
        # We only care about IAmRequest
        if not isinstance(apdu, IAmRequest):
            _log.debug("Ignoring indication as apdu is not IAm")
            return
        
        # Ignore IAmRequests that don't have the device id we care about.
        if self.expected_device_id is not None:            
            device_type, device_instance = apdu.iAmDeviceIdentifier
            
            if device_type != 'device':
                raise DecodingError("invalid object type")
            
            if device_instance != self.expected_device_id:
                _log.debug("Ignoring IAm. Expected ID: {} Received: {}".format(
                    self.expected_device_id, device_instance))
                return
            
        self.apdu = apdu
        stop()

    def make_request(self, request, expected_device_id=None):
        self.expected_device_id = expected_device_id
        self._request = request
        
        self.request(request)
        run()
        return self.apdu


def get_iam(app, device_id, target_address = None):
    request = WhoIsRequest()
    
    request.deviceInstanceRangeLowLimit = device_id
    request.deviceInstanceRangeHighLimit = device_id
    
    if target_address is not None:
        request.pduDestination = Address(target_address)
    else:
        request.pduDestination = GlobalBroadcast()
        
    result = app.make_request(request, expected_device_id=device_id)

    return result


def read_prop(app, address, obj_type, obj_inst, prop_id, index=None):
    request = ReadPropertyRequest(
                objectIdentifier=(obj_type, obj_inst),
                propertyIdentifier=prop_id,
                propertyArrayIndex=index)
    request.pduDestination = address
    
    result = app.make_request(request)
    if not isinstance(result, ReadPropertyACK):
        result.debug_contents(file=sys.stderr)
        raise TypeError("Error reading property")
    
    # find the datatype
    datatype = get_datatype(obj_type, prop_id)
    if issubclass(datatype, Array) and (result.propertyArrayIndex is not None):
        if result.propertyArrayIndex == 0:
            value = result.propertyValue.cast_out(Unsigned)
        else:
            value = result.propertyValue.cast_out(datatype.subtype)
    else:
        value = result.propertyValue.cast_out(datatype)    

    return value

def process_object(app, address, obj_type, index, max_range_report, config_writer):
    _log.debug('obj_type = ' + repr(obj_type))
    _log.debug('bacnet_index = ' + repr(index))
    
    writable = 'FALSE'
    
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
        _log.debug('presentValue is an unsupported type: ' + repr(present_value_type))
        return

    object_name = "NO NAME! PLEASE NAME THIS."
    try:
        object_name = read_prop(app, address, obj_type, index, "objectName")
        _log.debug('object name = ' + object_name)
    except TypeError:
        pass
    except Exception:
        _log.debug(traceback.format_exc())

    object_notes = ''
    try:
        object_notes = read_prop(app, address, obj_type, index, "description")
    except TypeError:
        pass
    except Exception:
        _log.debug(traceback.format_exc())
        
    object_units_details = ''
    
    if issubclass(present_value_type, Enumerated):
        object_units = 'Enum'
        values = list(present_value_type.enumerations.values())
        min_value = min(values)
        max_value = max(values)
        
        vendor_range = ''
        if hasattr(present_value_type, 'vendor_range'):
            vendor_min, vendor_max = present_value_type.vendor_range
            vendor_range = ' (vendor {min}-{max})'.format(min=vendor_min, max=vendor_max)
            
        object_units_details = '{min}-{max}{vendor}'.format(min=min_value, max=max_value, vendor=vendor_range)
        
        if not obj_type.endswith('Input'):
            try:
                default_value = read_prop(app, address, obj_type, index, "relinquishDefault")
                object_units_details += ' (default {default})'.format(
                    default=present_value_type.enumerations[default_value])
                # writable = 'TRUE'
            except TypeError:
                pass
            except ValueError:
                pass
            except Exception:
                _log.debug(traceback.format_exc())
    
        if not object_notes:
            enum_strings = []
            try:
                for name in Enumerated.keylist(present_value_type(0)):
                    value = present_value_type.enumerations[name]
                    enum_strings.append(str(value) + '=' + name)
                
                object_notes = present_value_type.__name__ + ': ' + ', '.join(enum_strings)
            except AttributeError:
                pass

    elif issubclass(present_value_type, Boolean):
        object_units = 'Boolean'
        
    elif get_datatype(obj_type, 'units') is None:
        if obj_type.startswith('multiState'):
            object_units = 'State'
            try:
                state_count = read_prop(app, address, obj_type, index, "numberOfStates")
                object_units_details = 'State count: {}'.format(state_count)
            except TypeError:
                pass
            except Exception:
                _log.debug(traceback.format_exc())
            
            try:
                enum_strings = []
                state_list = read_prop(app, address, obj_type, index, "stateText")
                for name in state_list[1:]:
                    enum_strings.append(name)
                    
                object_notes = ', '.join('{}={}'.format(x,y) for x,y in enumerate(enum_strings, start=1))
                    
            except TypeError:
                pass
            
            if obj_type != 'multiStateInput':
                try:
                    default_value = read_prop(app, address, obj_type, index, "relinquishDefault")
                    object_units_details += ' (default {default})'.format(default=default_value)
                    object_units_details = object_units_details.strip()
                    # writable = 'TRUE'
                except TypeError:
                    pass
                except ValueError:
                    pass
                except Exception:
                    _log.debug(traceback.format_exc())
                
        elif obj_type == 'loop':
            object_units = 'Loop'
        else:
            object_units = 'UNKNOWN UNITS'        
    else:
        object_units = 'UNKNOWN UNITS'
        try:
            object_units = read_prop(app, address, obj_type, index, "units")
        except TypeError:
            pass
        except Exception:
            _log.debug(traceback.format_exc())
            
        if isinstance(object_units, int):
            object_units = 'UNKNOWN UNIT ENUM VALUE: ' + str(object_units)
            
        if obj_type.startswith('analog') or obj_type in ('largeAnalogValue', 'integerValue', 'positiveIntegerValue'):
            # Value objects never have a resolution property in practice.
            if not object_notes and not obj_type.endswith('Value'):
                try:
                    res_value = read_prop(app, address, obj_type, index, "resolution")
                    object_notes = 'Resolution: {resolution:.6g}'.format(resolution=res_value)
                except TypeError:
                    pass
            
            if obj_type not in ('largeAnalogValue', 'integerValue', 'positiveIntegerValue'):    
                try:
                    min_value = read_prop(app, address, obj_type, index, "minPresValue")
                    max_value = read_prop(app, address, obj_type, index, "maxPresValue")

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
                    # object_units_details = '{min} to {max}'.format(min=min_value, max=max_value)
                except TypeError:
                    pass
                except Exception:
                    _log.debug(traceback.format_exc())
            
            if obj_type != 'analogInput':
                try:
                    default_value = read_prop(app, address, obj_type, index, "relinquishDefault")
                    object_units_details += ' (default {default})'.format(default=default_value)
                    object_units_details = object_units_details.strip()
                    # writable = 'TRUE'
                except TypeError:
                    pass
                except ValueError:
                    pass
                except Exception:
                    _log.debug(traceback.format_exc())
   
    _log.debug('  object units = ' + str(object_units))
    _log.debug('  object units details = ' + str(object_units_details))
    _log.debug('  object notes = ' + object_notes)    
    
    results = {
        'Reference Point Name': object_name,
        'Volttron Point Name': object_name,
        'Units': object_units,
        'Unit Details': object_units_details,
        'BACnet Object Type': obj_type,
        'Property': 'presentValue',
        'Writable': writable,
        'Index': index,
        'Notes': object_notes
    }

    config_writer.writerow(results)


def main():
    # parse the command line arguments
    arg_parser = ConfigArgumentParser(description=__doc__)
        
    arg_parser.add_argument("device_id", type=int,
                            help="Device ID of the target device")
    
    arg_parser.add_argument("--address",
                            help="Address of target device, may be needed to help route initial request to device.")
    
    arg_parser.add_argument("--registry-out-file", type=argparse.FileType('w'),
                            help="Output registry to CSV file",
                            default=sys.stdout)

    arg_parser.add_argument("--driver-out-file", type=argparse.FileType('w'),
                            help="Output driver configuration to JSON file.",
                            default=sys.stdout)
    
    arg_parser.add_argument("--max-range-report", nargs='?', type=float,
                            help='Affects how very large numbers are reported in the "Unit Details" column of the '
                                 'output. Does not affect driver behavior.',
                            default=1.0e+20)
    
    args = arg_parser.parse_args()

    _log.debug("initialization")
    _log.debug("    - args: %r", args)

    # make a device object
    this_device = LocalDeviceObject(
        objectName=args.ini.objectname,
        objectIdentifier=int(args.ini.objectidentifier),
        maxApduLengthAccepted=int(args.ini.maxapdulengthaccepted),
        segmentationSupported=args.ini.segmentationsupported,
        vendorIdentifier=int(args.ini.vendoridentifier),
        )

    # make a simple application
    this_application = SynchronousApplication(this_device, args.ini.address)

    _log.debug("starting build")
    
    result = get_iam(this_application, args.device_id, args.address)

    target_address = result.pduSource
    device_id = result.iAmDeviceIdentifier[1]
    
    _log.debug('pduSource = ' + repr(result.pduSource))
    _log.debug('iAmDeviceIdentifier = ' + str(result.iAmDeviceIdentifier))
    _log.debug('maxAPDULengthAccepted = ' + str(result.maxAPDULengthAccepted))
    _log.debug('segmentationSupported = ' + str(result.segmentationSupported))
    _log.debug('vendorID = ' + str(result.vendorID))

    config_file_name = basename(args.registry_out_file.name)

    config = {
        "driver_config": {"device_address": str(target_address),
                          "device_id": device_id},
        "driver_type": "bacnet",
        "registry_config": "config://registry_configs/{}".format(config_file_name)
    }

    jsonapi.dump(config, args.driver_out_file, indent=4)
    
    try:
        device_name = read_prop(this_application, target_address, "device", device_id, "objectName")
        _log.debug('device_name = ' + str(device_name))
    except TypeError:
        _log.debug('device missing objectName')
    
    try:
        device_description = read_prop(this_application, target_address, "device", device_id, "description")
        _log.debug('description = ' + str(device_description))
    except TypeError:
        _log.debug('device missing description')
    
    config_writer = DictWriter(args.registry_out_file,
                               ('Reference Point Name',
                                'Volttron Point Name',
                                'Units',
                                'Unit Details',
                                'BACnet Object Type',
                                'Property',
                                'Writable',
                                'Index',
                                'Write Priority',
                                'Notes'))
    
    config_writer.writeheader()

    try:
        object_count = read_prop(this_application, target_address, "device", device_id, "objectList", index=0)
        list_property = "objectList"
    except TypeError:
        object_count = read_prop(this_application, target_address, "device", device_id, "structuredObjectList", index=0)
        list_property = "structuredObjectList"
    
    _log.debug('objectCount = ' + str(object_count))
    
    for object_index in range(1, object_count + 1):
        _log.debug('object_device_index = ' + repr(object_index))
        
        bac_object = read_prop(this_application, target_address, "device", device_id, list_property, index=object_index)
        
        obj_type, index = bac_object

        try:
            process_object(this_application, target_address, obj_type, index, args.max_range_report, config_writer)
        except Exception:
            _log.debug("Unexpected error processing object: {} {}".format(obj_type, index))
            _log.debug(traceback.format_exc())


try:
    main()
except Exception as e:
    _log.exception("an error has occurred: %s", e)
finally:
    _log.debug("finally")
    

    

