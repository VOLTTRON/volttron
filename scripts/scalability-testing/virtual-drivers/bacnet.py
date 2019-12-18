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


#---------------------------------------------------------------------------# 
# import the various server implementations
#---------------------------------------------------------------------------# 

from bacpypes.debugging import bacpypes_debugging, ModuleLogger
from bacpypes.consolelogging import ArgumentParser

from bacpypes.core import run

from bacpypes.primitivedata import Atomic, Real, Unsigned
from bacpypes.constructeddata import Array, Any
from bacpypes.basetypes import ServicesSupported, ErrorType
from bacpypes.apdu import ReadPropertyMultipleACK, ReadAccessResult, ReadAccessResultElement, ReadAccessResultElementChoice
from bacpypes.app import BIPSimpleApplication
from bacpypes.service.device import LocalDeviceObject
from bacpypes.object import AnalogValueObject, PropertyError, get_object_class
from bacpypes.apdu import Error
from bacpypes.errors import ExecutionError

from csv import DictReader
import logging

from utils import createDaemon

#---------------------------------------------------------------------------# 
# configure the service logging
#---------------------------------------------------------------------------# 
# some debugging
_debug = 0
_log = ModuleLogger(globals())

import struct

parser = ArgumentParser(description='Run a test pymodbus driver')
parser.add_argument('config', help='device registry configuration')
parser.add_argument('interface', help='interface address and optionally the port and subnet mask for the device to listen on')
parser.add_argument('--no-daemon', help='do not create a daemon process', action='store_true')
parser.add_argument('--device-id', help='specify the BACnet device id of the device.', type=int, default=1000)
args = parser.parse_args()


class Register(object):
    def __init__(self, point_name, instance_number, object_type, property_name, read_only):
        self.read_only = read_only
        self.register_type = "byte"
        self.property_name = property_name
        self.object_type = object_type
        self.instance_number = int(instance_number)
        self.point_name = point_name
    
    def get_register_type(self):
        '''Get (type, read_only) tuple'''
        return self.register_type, self.read_only

@bacpypes_debugging
class DeviceAbstraction(object):
    def __init__(self, interface_str, config_file):
        self.build_register_map()
        self.parse_config(config_file)
        self.interface = interface_str
        
    def build_register_map(self):
        self.registers = {('byte',True):[],
                          ('byte',False):[],
                          ('bit',True):[],
                          ('bit',False):[]}
        
    def insert_register(self, register):        
        register_type = register.get_register_type()
        self.registers[register_type].append(register) 
                
    def parse_config(self, config_file):
        with open(config_file, 'rb') as f:
            configDict = DictReader(f)
            
            for regDef in configDict:            
                object_type = regDef['BACnet Object Type']
                read_only = regDef['Writable'].lower() != 'true'  
                index = int(regDef['Index'])    
                property = regDef['Property']  
                point_name = regDef['Volttron Point Name'] 
                            
                register = Register(point_name, index, object_type, property, read_only)
                    
                self.insert_register(register)
                
    
    def get_server_application(self):
        if _debug: DeviceAbstraction._debug("    - creating application")
        # make a device object
        this_device = LocalDeviceObject(
            objectName="Betelgeuse",
            objectIdentifier=args.device_id,
            maxApduLengthAccepted=1024,
            segmentationSupported="segmentedBoth",
            vendorIdentifier=15
            )
    
        # build a bit string that knows about the bit names
        pss = ServicesSupported()
        pss['whoIs'] = 1
        pss['iAm'] = 1
        pss['readProperty'] = 1
        pss['readPropertyMultiple'] = 1
        pss['writeProperty'] = 1
    
        # set the property value to be just the bits
        this_device.protocolServicesSupported = pss.value        

        # make a sample application
        this_application = ReadPropertyMultipleApplication(this_device, args.interface)
    
       
        registers= self.registers[('byte',True)]
        
        #Currently we don't actually enforce read only properties.        
        for register in registers:
            if _debug: DeviceAbstraction._debug("    - creating object of type: %s, %i", register.object_type, register.instance_number)
            klass = get_object_class(register.object_type)
            ravo = klass(objectIdentifier=(register.object_type, register.instance_number), 
                         objectName=register.point_name)
            
            ravo.WriteProperty("presentValue", 0, direct=True)
            
            this_application.add_object(ravo)
            
            
        registers= self.registers[('byte',False)]
        
        for register in registers:
            if _debug: DeviceAbstraction._debug("    - creating object of type: %s, %i", register.object_type, register.instance_number)
            klass = get_object_class(register.object_type)
            ravo = klass(objectIdentifier=(register.object_type, register.instance_number), 
                         objectName=register.point_name)
            
            ravo.WriteProperty("presentValue", 0, direct=True)
            
            this_application.add_object(ravo)
            
        return this_application


#Most of this stuff is copied from the example here: 
#https://github.com/JoelBender/bacpypes/blob/master/samples/ReadPropertyMultipleServer.py


@bacpypes_debugging
def ReadPropertyToAny(obj, propertyIdentifier, propertyArrayIndex=None):
    """Read the specified property of the object, with the optional array index,
    and cast the result into an Any object."""
    if _debug: ReadPropertyToAny._debug("ReadPropertyToAny %s %r %r", obj, propertyIdentifier, propertyArrayIndex)

    # get the datatype
    datatype = obj.get_datatype(propertyIdentifier)
    if _debug: ReadPropertyToAny._debug("    - datatype: %r", datatype)
    if datatype is None:
        raise ExecutionError(errorClass='property', errorCode='datatypeNotSupported')

    # get the value
    value = obj.ReadProperty(propertyIdentifier, propertyArrayIndex)
    if _debug: ReadPropertyToAny._debug("    - value: %r", value)
    if value is None:
        raise ExecutionError(errorClass='property', errorCode='unknownProperty')

    # change atomic values into something encodeable
    if issubclass(datatype, Atomic):
        value = datatype(value)
    elif issubclass(datatype, Array) and (propertyArrayIndex is not None):
        if propertyArrayIndex == 0:
            value = Unsigned(value)
        elif issubclass(datatype.subtype, Atomic):
            value = datatype.subtype(value)
        elif not isinstance(value, datatype.subtype):
            raise TypeError("invalid result datatype, expecting %s and got %s" \
                % (datatype.subtype.__name__, type(value).__name__))
    elif not isinstance(value, datatype):
        raise TypeError("invalid result datatype, expecting %s and got %s" \
            % (datatype.__name__, type(value).__name__))
    if _debug: ReadPropertyToAny._debug("    - encodeable value: %r", value)

    # encode the value
    result = Any()
    result.cast_in(value)
    if _debug: ReadPropertyToAny._debug("    - result: %r", result)

    # return the object
    return result

#
#   ReadPropertyToResultElement
#

@bacpypes_debugging
def ReadPropertyToResultElement(obj, propertyIdentifier, propertyArrayIndex=None):
    """Read the specified property of the object, with the optional array index,
    and cast the result into an Any object."""
    if _debug: ReadPropertyToResultElement._debug("ReadPropertyToResultElement %s %r %r", obj, propertyIdentifier, propertyArrayIndex)

    # save the result in the property value
    read_result = ReadAccessResultElementChoice()

    try:
        read_result.propertyValue = ReadPropertyToAny(obj, propertyIdentifier, propertyArrayIndex)
        if _debug: ReadPropertyToResultElement._debug("    - success")
    except PropertyError as error:
        if _debug: ReadPropertyToResultElement._debug("    - error: %r", error)
        read_result.propertyAccessError = ErrorType(errorClass='property', errorCode='unknownProperty')
    except ExecutionError as error:
        if _debug: ReadPropertyToResultElement._debug("    - error: %r", error)
        read_result.propertyAccessError = ErrorType(errorClass=error.errorClass, errorCode=error.errorCode)

    # make an element for this value
    read_access_result_element = ReadAccessResultElement(
        propertyIdentifier=propertyIdentifier,
        propertyArrayIndex=propertyArrayIndex,
        readResult=read_result,
        )
    if _debug: ReadPropertyToResultElement._debug("    - read_access_result_element: %r", read_access_result_element)

    # fini
    return read_access_result_element

#
#   ReadPropertyMultipleApplication
#

@bacpypes_debugging
class ReadPropertyMultipleApplication(BIPSimpleApplication):

    def __init__(self, *args, **kwargs):
        if _debug: ReadPropertyMultipleApplication._debug("__init__ %r %r", args, kwargs)
        BIPSimpleApplication.__init__(self, *args, **kwargs)

    def do_ReadPropertyMultipleRequest(self, apdu):
        """Respond to a ReadPropertyMultiple Request."""
        if _debug: ReadPropertyMultipleApplication._debug("do_ReadPropertyMultipleRequest %r", apdu)

        # response is a list of read access results (or an error)
        resp = None
        read_access_result_list = []

        # loop through the request
        for read_access_spec in apdu.listOfReadAccessSpecs:
            # get the object identifier
            objectIdentifier = read_access_spec.objectIdentifier
            if _debug: ReadPropertyMultipleApplication._debug("    - objectIdentifier: %r", objectIdentifier)

            # check for wildcard
            if (objectIdentifier == ('device', 4194303)):
                if _debug: ReadPropertyMultipleApplication._debug("    - wildcard device identifier")
                objectIdentifier = self.localDevice.objectIdentifier

            # get the object
            obj = self.get_object_id(objectIdentifier)
            if _debug: ReadPropertyMultipleApplication._debug("    - object: %r", obj)

            # make sure it exists
            if not obj:
                resp = Error(errorClass='object', errorCode='unknownObject', context=apdu)
                if _debug: ReadPropertyMultipleApplication._debug("    - unknown object error: %r", resp)
                break

            # build a list of result elements
            read_access_result_element_list = []

            # loop through the property references
            for prop_reference in read_access_spec.listOfPropertyReferences:
                # get the property identifier
                propertyIdentifier = prop_reference.propertyIdentifier
                if _debug: ReadPropertyMultipleApplication._debug("    - propertyIdentifier: %r", propertyIdentifier)

                # get the array index (optional)
                propertyArrayIndex = prop_reference.propertyArrayIndex
                if _debug: ReadPropertyMultipleApplication._debug("    - propertyArrayIndex: %r", propertyArrayIndex)

                # check for special property identifiers
                if propertyIdentifier in ('all', 'required', 'optional'):
                    for propId, prop in obj._properties.items():
                        if _debug: ReadPropertyMultipleApplication._debug("    - checking: %r %r", propId, prop.optional)

                        if (propertyIdentifier == 'all'):
                            pass
                        elif (propertyIdentifier == 'required') and (prop.optional):
                            if _debug: ReadPropertyMultipleApplication._debug("    - not a required property")
                            continue
                        elif (propertyIdentifier == 'optional') and (not prop.optional):
                            if _debug: ReadPropertyMultipleApplication._debug("    - not an optional property")
                            continue

                        # read the specific property
                        read_access_result_element = ReadPropertyToResultElement(obj, propId, propertyArrayIndex)

                        # check for undefined property
                        if read_access_result_element.readResult.propertyAccessError \
                            and read_access_result_element.readResult.propertyAccessError.errorCode == 'unknownProperty':
                            continue

                        # add it to the list
                        read_access_result_element_list.append(read_access_result_element)

                else:
                    # read the specific property
                    read_access_result_element = ReadPropertyToResultElement(obj, propertyIdentifier, propertyArrayIndex)

                    # add it to the list
                    read_access_result_element_list.append(read_access_result_element)

            # build a read access result
            read_access_result = ReadAccessResult(
                objectIdentifier=objectIdentifier,
                listOfResults=read_access_result_element_list
                )
            if _debug: ReadPropertyMultipleApplication._debug("    - read_access_result: %r", read_access_result)

            # add it to the list
            read_access_result_list.append(read_access_result)

        # this is a ReadPropertyMultiple ack
        if not resp:
            resp = ReadPropertyMultipleACK(context=apdu)
            resp.listOfReadAccessResults = read_access_result_list
            if _debug: ReadPropertyMultipleApplication._debug("    - resp: %r", resp)

        # return the result
        self.response(resp)

#
#   __main__
#

try:
    abstraction = DeviceAbstraction(args.interface, args.config)
    
    #Create the deamon as soon as we've loaded the device configuration.
    if not args.no_daemon:
        createDaemon()
    
    application = abstraction.get_server_application()

    _log.debug("running")

    run()

except Exception as e:
    _log.exception("an error has occurred: %s", e)
finally:
    _log.debug("finally")
