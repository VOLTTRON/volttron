# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2015, Battelle Memorial Institute
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
#}}}

import sys
import argparse
from csv import DictWriter
from bacpypes.debugging import bacpypes_debugging, ModuleLogger
from bacpypes.app import LocalDeviceObject, BIPSimpleApplication
from bacpypes.consolelogging import ConfigArgumentParser
from bacpypes.pdu import Address
from bacpypes.core import run, stop
from bacpypes.apdu import WhoIsRequest, IAmRequest, ReadPropertyRequest, ReadPropertyACK
from bacpypes.errors import DecodingError
from bacpypes.task import TaskManager
from bacpypes.object import get_datatype, get_object_class, DeviceObject
from bacpypes.primitivedata import Enumerated, Unsigned, Boolean, Integer, Real, Double
from bacpypes.constructeddata import Array

"""
Simple utility to scrape device registers and write them to a configuration file.
"""

#Make sure the TaskManager singleton exists...
task_manager = TaskManager()
_debug = 0
_log = ModuleLogger(globals())

@bacpypes_debugging
class SynchronousApplication(BIPSimpleApplication):
    def __init__(self, *args):
        SynchronousApplication._debug("__init__ %r", args)
        BIPSimpleApplication.__init__(self, *args)
        self.expect_confirmation = True

    def confirmation(self, apdu):
        self.apdu = apdu
        stop()
        
    def indication(self, apdu):
        if not self.expect_confirmation:
            self.apdu = apdu
            stop()

    def make_request(self, request, expect_confirmation=True):
        self.expect_confirmation = expect_confirmation
        self.request(request)
        run()
        return self.apdu

def read_prop(app, address, obj_type, obj_inst, prop_id, index=None):
    request = ReadPropertyRequest(
                objectIdentifier=(obj_type, obj_inst),
                propertyIdentifier=prop_id,
                propertyArrayIndex=index)
    request.pduDestination = address
    
    result = this_application.make_request(request)
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

try:
    # parse the command line arguments
    arg_parser = ConfigArgumentParser(description=__doc__)
    
    arg_parser.add_argument("address",
                            help="Address of target device" )
    arg_parser.add_argument("out_file", nargs='?', type=argparse.FileType('wb'),
                            help="Optional output file for configuration",
                            default=sys.stdout )
    
    arg_parser.add_argument("--max_range_report", nargs='?', type=float,
                            help='Affects how very large numbers are reported in the "Unit Details" column of the output. ' 
                            'Does not affect sMap driver behavior.',
                            default=1.0e+20 )
    
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
    
    target_address = Address(args.address)
    
    request = WhoIsRequest()
    request.pduDestination = target_address
    result = this_application.make_request(request, expect_confirmation = False)
    
    if not isinstance(result, IAmRequest):
        result.debug_contents()
        raise TypeError("Error making WhoIs request")
        
    
    device_type, device_instance = result.iAmDeviceIdentifier
    if device_type != 'device':
        raise DecodingError("invalid object type")
    
    _log.debug('pduSource = ' + repr(result.pduSource))
    _log.debug('iAmDeviceIdentifier = ' + str(result.iAmDeviceIdentifier))
    _log.debug('maxAPDULengthAccepted = ' + str(result.maxAPDULengthAccepted))
    _log.debug('segmentationSupported = ' + str(result.segmentationSupported))
    _log.debug('vendorID = ' + str(result.vendorID))
    
    device_id = result.iAmDeviceIdentifier[1]
    
    device_name = read_prop(this_application, target_address, "device", device_id, "objectName")
    _log.debug('device_name = ' + str(device_name))
    device_description = read_prop(this_application, target_address, "device", device_id, "description")
    _log.debug('description = ' + str(device_description))
    
    objectCount = read_prop(this_application, target_address, "device", device_id, "objectList", index=0)
    
    _log.debug('objectCount = ' + str(objectCount))
    
    config_writer = DictWriter(args.out_file, 
                               ('Reference Point Name',
                                'Volttron Point Name',
                                'Units',
                                'Unit Details',
                                'BACnet Object Type',
                                'Property',
                                'Writable',
                                'Index',
                                'Notes'))
    
    config_writer.writeheader()
    
    for object_index in xrange(1,objectCount+1):
        
        bac_object = read_prop(this_application, 
                                    target_address, 
                                    "device", 
                                    device_id, 
                                    "objectList",
                                    index=object_index)
        
        obj_type, index = bac_object
        
        writable = 'FALSE'
        
        present_value_type = get_datatype(obj_type, 'presentValue')
        if present_value_type is None:
            continue
        
        if not issubclass(present_value_type, (Enumerated,
                                               Unsigned,
                                               Boolean,
                                               Integer,
                                               Real,
                                               Double)):
            continue 
        
        try:
            object_name = read_prop(this_application, target_address, obj_type, index, "objectName")
            _log.debug('object name = ' + object_name)
        except TypeError:
            object_name = "NO NAME! PLEASE NAME THIS."
            
        _log.debug('  object type = ' + obj_type)
        _log.debug('  object index = ' + str(index))
        
        try:
            object_notes = read_prop(this_application, target_address, obj_type, index, "description")
            
        except TypeError:
            object_notes = ''
            
        object_units_details = ''
        
        if issubclass(present_value_type, Enumerated):
            object_units = 'Enum'
            values=present_value_type.enumerations.values()
            min_value = min(values)
            max_value = max(values)
            
            vendor_range = ''
            if hasattr(present_value_type, 'vendor_range'):
                vendor_min, vendor_max = present_value_type.vendor_range
                vendor_range = ' (vendor {min}-{max})'.format(min=vendor_min, max=vendor_max)
                
            object_units_details = '{min}-{max}{vendor}'.format(min=min_value, max=max_value, vendor=vendor_range)
            
            if not obj_type.endswith('Input'):
                try:
                    default_value = read_prop(this_application, target_address, obj_type, index, "relinquishDefault")
                    object_units_details += ' (default {default})'.format(default=present_value_type.enumerations[default_value])
                    #writable = 'TRUE'
                except TypeError:
                    pass
                except ValueError:
                    pass
        
            if not object_notes:
                enum_strings=[]
                for name in Enumerated.keylist(present_value_type(0)):
                    value = present_value_type.enumerations[name]
                    enum_strings.append(str(value)+'='+name)
                    
                object_notes = present_value_type.__name__ + ': ' + ', '.join(enum_strings)
            
            
        elif issubclass(present_value_type, Boolean):
            object_units = 'Boolean'
            
        elif get_datatype(obj_type, 'units') is None:
            if obj_type.startswith('multiState'):
                object_units = 'State'
                try:
                    state_count = read_prop(this_application, target_address, obj_type, index, "numberOfStates")
                    object_units_details = 'State count: {}'.format(state_count)
                except TypeError:
                    pass
                
                try:
                    enum_strings=[]
                    state_list = read_prop(this_application, target_address, obj_type, index, "stateText")
                    for name in state_list.value[1:]:
                        enum_strings.append(name)
                        
                    object_notes = ', '.join('{}={}'.format(x,y) for x,y in enumerate(enum_strings, start=1))
                        
                except TypeError:
                    pass
                
                if obj_type != 'multiStateInput':
                    try:
                        default_value = read_prop(this_application, target_address, obj_type, index, "relinquishDefault")
                        object_units_details += ' (default {default})'.format(default=default_value)
                        object_units_details = object_units_details.strip()
                        #writable = 'TRUE'
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
                object_units = read_prop(this_application, target_address, obj_type, index, "units")
            except TypeError:
                object_units = 'UNKNOWN UNITS'
                
            if isinstance(object_units, (int, long)):
                object_units = 'UNKNOWN UNIT ENUM VALUE: ' + str(object_units)
                
            if obj_type.startswith('analog') or obj_type in ('largeAnalogValue', 'integerValue', 'positiveIntegerValue'):
                # Value objects never have a resolution property in practice.
                if not object_notes and not obj_type.endswith('Value'):
                    try:
                        res_value = read_prop(this_application, target_address, obj_type, index, "resolution")
                        object_notes = 'Resolution: {resolution:.6g}'.format(resolution=res_value)
                    except TypeError:
                        pass
                
                if obj_type not in ('largeAnalogValue', 'integerValue', 'positiveIntegerValue'):    
                    try:
                        min_value = read_prop(this_application, target_address, obj_type, index, "minPresValue")
                        max_value = read_prop(this_application, target_address, obj_type, index, "maxPresValue")
                        
                        has_min = min_value > -args.max_range_report
                        has_max = max_value <  args.max_range_report
                        
                        if has_min and has_max:
                            object_units_details = '{min:.2f} to {max:.2f}'.format(min=min_value, max=max_value)
                        elif has_min:
                            object_units_details = 'Min: {min:.2f}'.format(min=min_value)
                        elif has_max:
                            object_units_details = 'Max: {max:.2f}'.format(max=max_value)
                        else:
                            object_units_details = 'No limits.'
                        #object_units_details = '{min} to {max}'.format(min=min_value, max=max_value)            
                    except TypeError:
                        pass
                
                if obj_type != 'analogInput':
                    try:
                        default_value = read_prop(this_application, target_address, obj_type, index, "relinquishDefault")
                        object_units_details += ' (default {default})'.format(default=default_value)
                        object_units_details = object_units_details.strip()
                        #writable = 'TRUE'
                    except TypeError:
                        pass
                    except ValueError:
                        pass
       
        _log.debug('  object units = ' + str(object_units))
        _log.debug('  object units details = ' + str(object_units_details))
        _log.debug('  object notes = ' + object_notes)    
        
        results = {}     
        results['Reference Point Name'] = results['Volttron Point Name'] = object_name
        results['Units'] = object_units
        results['Unit Details'] = object_units_details
        results['BACnet Object Type'] = obj_type
        results['Property'] = 'presentValue'
        results['Writable'] = writable
        results['Index'] = index
        results['Notes'] = object_notes
        
        config_writer.writerow(results)

except Exception as e:
    _log.exception("an error has occurred: %s", e)
finally:
    _log.debug("finally")
