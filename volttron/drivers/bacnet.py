'''
Copyright (c) 2013, Battelle Memorial Institute
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met: 

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer. 
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution. 

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

The views and conclusions contained in the software and documentation are those
of the authors and should not be interpreted as representing official policies, 
either expressed or implied, of the FreeBSD Project.
'''

'''
This material was prepared as an account of work sponsored by an 
agency of the United States Government.  Neither the United States 
Government nor the United States Department of Energy, nor Battelle,
nor any of their employees, nor any jurisdiction or organization 
that has cooperated in the development of these materials, makes 
any warranty, express or implied, or assumes any legal liability 
or responsibility for the accuracy, completeness, or usefulness or 
any information, apparatus, product, software, or process disclosed,
or represents that its use would not infringe privately owned rights.

Reference herein to any specific commercial product, process, or 
service by trade name, trademark, manufacturer, or otherwise does 
not necessarily constitute or imply its endorsement, recommendation, 
r favoring by the United States Government or any agency thereof, 
or Battelle Memorial Institute. The views and opinions of authors 
expressed herein do not necessarily state or reflect those of the 
United States Government or any agency thereof.

PACIFIC NORTHWEST NATIONAL LABORATORY
operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
under Contract DE-AC05-76RL01830
'''

#!/usr/bin/python

"""
sample_http_server
"""

import os

from csv import DictReader
from collections import defaultdict

from Queue import Queue, Empty

from twisted.internet.defer import Deferred
from twisted.python.failure import Failure
from twisted.internet import reactor

from base import BaseSmapVolttron, BaseRegister, BaseInterface

from bacpypes.debugging import class_debugging, ModuleLogger

import bacpypes.core

import threading

#Tweeks to BACpypes to make it play nice with Twisted.
bacpypes.core.enable_sleeping()
bacpypes.core.SPIN = 0.1

from bacpypes.pdu import Address
from bacpypes.app import LocalDeviceObject, BIPSimpleApplication
from bacpypes.object import get_datatype

from bacpypes.apdu import (ReadPropertyRequest, 
                           WritePropertyRequest, 
                           Error, 
                           AbortPDU, 
                           ReadPropertyACK, 
                           SimpleAckPDU,
                           ReadPropertyMultipleRequest,
                           ReadPropertyMultipleACK,
                           PropertyReference,
                           ReadAccessSpecification,
                           encode_max_apdu_response)
from bacpypes.primitivedata import Enumerated, Integer, Unsigned, Real, Boolean, Double
from bacpypes.constructeddata import Array, Any
from bacpypes.basetypes import ServicesSupported
from bacpypes.task import TaskManager

import time

path = os.path.dirname(os.path.abspath(__file__))
configFile = os.path.join(path, "bacnet_example_config.csv")

#Make sure the TaskManager singleton exists...
task_manager = TaskManager()
# some debugging
_debug = 0
_log = ModuleLogger(globals())

# reference a simple application
this_application = None
server = None

#IO callback
class IOCB:

    def __init__(self, request):
        # requests and responses
        self.ioRequest = request
        self.ioDefered = Deferred()

@class_debugging
class BACnet_application(BIPSimpleApplication):

    def __init__(self, *args):
        BIPSimpleApplication.__init__(self, *args)

        # assigning invoke identifiers
        self.nextInvokeID = 1

        # keep track of requests to line up responses
        self.iocb = {}

    def get_next_invoke_id(self, addr):
        """Called to get an unused invoke ID."""

        initialID = self.nextInvokeID
        while 1:
            invokeID = self.nextInvokeID
            self.nextInvokeID = (self.nextInvokeID + 1) % 256

            # see if we've checked for them all
            if initialID == self.nextInvokeID:
                raise RuntimeError, "no available invoke ID"

            # see if this one is used
            if (addr, invokeID) not in self.iocb:
                break

        return invokeID

    def request(self, iocb):
        apdu = iocb.ioRequest

        # assign an invoke identifier
        apdu.apduInvokeID = self.get_next_invoke_id(apdu.pduDestination)

        # build a key to reference the IOCB when the response comes back
        invoke_key = (apdu.pduDestination, apdu.apduInvokeID)

        # keep track of the request
        self.iocb[invoke_key] = iocb
        
        BIPSimpleApplication.request(self, apdu)

    def confirmation(self, apdu):
        # build a key to look for the IOCB
        invoke_key = (apdu.pduSource, apdu.apduInvokeID)

        # find the request
        iocb = self.iocb.get(invoke_key, None)
        if not iocb:
            iocb.ioDefered.errback(RuntimeError("no matching request"))
            return
        del self.iocb[invoke_key]

        if isinstance(apdu, AbortPDU):
            iocb.ioDefered.errback(RuntimeError("Device communication aborted: " + str(apdu)))
            return
        
        if isinstance(apdu, Error):
            iocb.ioDefered.errback(RuntimeError("Error during device communication: " + str(apdu)))
            return

        elif (isinstance(iocb.ioRequest, ReadPropertyRequest) and 
              isinstance(apdu, ReadPropertyACK)):
            # find the datatype
            datatype = get_datatype(apdu.objectIdentifier[0], apdu.propertyIdentifier)
            if not datatype:
                iocb.ioDefered.errback(TypeError("unknown datatype"))
                return

            # special case for array parts, others are managed by cast_out
            if issubclass(datatype, Array) and (apdu.propertyArrayIndex is not None):
                if apdu.propertyArrayIndex == 0:
                    value = apdu.propertyValue.cast_out(Unsigned)
                else:
                    value = apdu.propertyValue.cast_out(datatype.subtype)
            else:
                value = apdu.propertyValue.cast_out(datatype)
                if issubclass(datatype, Enumerated):
                    value = datatype(value).get_long()
            iocb.ioDefered.callback(value)
            
        elif (isinstance(iocb.ioRequest, WritePropertyRequest) and 
              isinstance(apdu, SimpleAckPDU)):
            iocb.ioDefered.callback(apdu)
            return
            
        elif (isinstance(iocb.ioRequest, ReadPropertyMultipleRequest) and 
              isinstance(apdu, ReadPropertyMultipleACK)):
            
            result_dict = {}
            for result in apdu.listOfReadAccessResults:
                # here is the object identifier
                objectIdentifier = result.objectIdentifier

                # now come the property values per object
                for element in result.listOfResults:
                    # get the property and array index
                    propertyIdentifier = element.propertyIdentifier
                    propertyArrayIndex = element.propertyArrayIndex

                    # here is the read result
                    readResult = element.readResult

                    # check for an error
                    if readResult.propertyAccessError is not None:
                        error_obj = readResult.propertyAccessError
                        
                        msg = 'ERROR DURRING SCRAPE (Class: {0} Code: {1})'
                        print msg.format(error_obj.errorClass, error_obj.errorCode)
                        
                    else:
                        # here is the value
                        propertyValue = readResult.propertyValue

                        # find the datatype
                        datatype = get_datatype(objectIdentifier[0], propertyIdentifier)
                        if not datatype:
                            iocb.ioDefered.errback(TypeError("unknown datatype"))
                            return

                        # special case for array parts, others are managed by cast_out
                        if issubclass(datatype, Array) and (propertyArrayIndex is not None):
                            if propertyArrayIndex == 0:
                                value = propertyValue.cast_out(Unsigned)
                            else:
                                value = propertyValue.cast_out(datatype.subtype)
                        else:
                            value = propertyValue.cast_out(datatype)
                            if issubclass(datatype, Enumerated):
                                value = datatype(value).get_long()
                        
                        result_dict[objectIdentifier[0], objectIdentifier[1], propertyIdentifier] = value
                       
            iocb.ioDefered.callback(result_dict)
            
        else:
            iocb.ioDefered.errback(TypeError('Unsupported Request Type'))

def block_for_sync(d, timeout=None):
    q = Queue()
    d.addBoth(q.put)
    try: 
        ret = q.get(True, timeout)
    except Empty:
        raise IOError('Communication with device timed out.')
    if isinstance(ret, Failure):
        ret.raiseException()
    else:
        return ret

class BACnetRegister(BaseRegister):
    def __init__(self, instance_number, object_type, property_name, read_only, pointName, units, description = ''):
        super(BACnetRegister, self).__init__("byte", read_only, pointName, units, description = '')
        self.instance_number = int(instance_number)
        self.object_type = object_type
        self.property = property_name
        
        # find the datatype
        self.datatype = get_datatype(object_type, property_name)
        if self.datatype is None:
            raise TypeError('Invalid Register Type')
        
        if not issubclass(self.datatype, (Enumerated,
                                          Unsigned,
                                          Boolean,
                                          Integer,
                                          Real,
                                          Double)):
            raise TypeError('Invalid Register Type') 
        
        if issubclass(self.datatype, (Enumerated,
                                      Unsigned,
                                      Boolean,
                                      Integer)):
            self.python_type = int
        else:
            self.python_type = float
    
    def get_state_async(self, bac_app, address):
        request = ReadPropertyRequest(
                objectIdentifier=(self.object_type, self.instance_number),
                propertyIdentifier=self.property)        
        request.pduDestination = address
        iocb = IOCB(request)
        bac_app.request(iocb)
        return iocb.ioDefered
    
    def get_state_sync(self, bac_app, address):
        return block_for_sync(self.get_state_async(bac_app, address), 5) 
    
    def set_state_async_callback(self, result, set_value):
        if isinstance(result, SimpleAckPDU):
            return set_value
        raise RuntimeError("Failed to set value: " + str(result))
    
    def set_state_async(self, bac_app, address, value):
        if not self.read_only:   
            request = WritePropertyRequest(
                objectIdentifier=(self.object_type, self.instance_number),
                propertyIdentifier=self.property)
            # save the value
            if self.datatype is Integer:
                value = int(value)
            elif self.datatype is Real:
                value = float(value)
            bac_value = self.datatype(value)
            request.propertyValue = Any()
            request.propertyValue.cast_in(bac_value)
                
            request.pduDestination = address
            iocb = IOCB(request)
            bac_app.request(iocb)
            iocb.ioDefered.addCallback(self.set_state_async_callback, value)
            return iocb.ioDefered
        raise TypeError('This register is read only.')
    
    def set_state_sync(self, bac_app, address, value):
        r = block_for_sync(self.set_state_async(bac_app, address, value), 5)
        return r

        
class BACnetInterface(BaseInterface):
    def __init__(self, self_address, target_address, 
                 max_apdu_len=1024, seg_supported='segmentedBoth', 
                 obj_id=599, obj_name='sMap BACnet driver', 
                 ven_id=15,
                 config_file=configFile, **kwargs):
        super(BACnetInterface, self).__init__(**kwargs)
        self.reverse_point_map = {}
        self.object_property_map = defaultdict(list)
        
        self.setup_device(self_address, max_apdu_len=max_apdu_len, seg_supported=seg_supported, 
                          obj_id=obj_id, obj_name=obj_name, 
                          ven_id=ven_id)
        self.parse_config(config_file)         
        self.target_address = Address(target_address)
        
        
        
    def insert_register(self, register):
        super(BACnetInterface, self).insert_register(register)
        self.reverse_point_map[register.object_type, 
                               register.instance_number, 
                               register.property] = register.point_name  
                               
        self.object_property_map[register.object_type, 
                                 register.instance_number].append(register.property)
        
    def setup_device(self, address, 
                     max_apdu_len=1024, seg_supported='segmentedBoth', 
                     obj_id=599, obj_name='sMap BACnet driver', 
                     ven_id=15):  
        
        print 'seg_supported', seg_supported
        print 'max_apdu_len', max_apdu_len
        print 'obj_id', obj_id
        print 'obj_name', obj_name
        print 'ven_id', ven_id
        
        #Check to see if they gave a valid apdu length.
        if encode_max_apdu_response(max_apdu_len) is None:
            raise ValueError('Invalid max_apdu_len: Valid options are 50, 128, 206, 480, 1024, and 1476')
        
        this_device = LocalDeviceObject(
            objectName=obj_name,
            objectIdentifier=obj_id,
            maxApduLengthAccepted=max_apdu_len,
            segmentationSupported=seg_supported,
            vendorIdentifier=ven_id,
            )
        
        # build a bit string that knows about the bit names and leave it empty. We respond to NOTHING.
        pss = ServicesSupported()
    
        # set the property value to be just the bits
        this_device.protocolServicesSupported = pss.value
        
        self.this_application = BACnet_application(this_device, address)
        
        #We must use traditional python threads, otherwise the driver will
        # hang during startup while trying to scrape actuator values.
        # I think this is because the reactor hasn't started before we start trying
        # to use the other threads.
        #reactor.callInThread(bacpypes.core.run)
        #reactor.addSystemEventTrigger("before", "shutdown", bacpypes.core.stop)
        
        server_thread = threading.Thread(target=bacpypes.core.run)
    
        # exit the BACnet App thread when the main thread terminates
        server_thread.daemon = True
        server_thread.start()
        
    #Mostly for testing by hand and initializing actuators.
    def get_point_sync(self, point_name):    
        register = self.point_map[point_name]
        return register.get_state_sync(self.this_application, self.target_address)
    
    #Mostly for testing by hand.
    def set_point_sync(self, point_name, value):    
        register = self.point_map[point_name]
        return register.set_state_sync(self.this_application, self.target_address, value)
    
    #Getting data in a async manner
    def get_point_async(self, point_name):    
        register = self.point_map[point_name]
        return register.get_state_async(self.this_application, self.target_address)
    
    #setting data in a async manner
    def set_point_async(self, point_name, value):    
        register = self.point_map[point_name]
        return register.set_state_async(self.this_application, self.target_address, value)
    
    def scrape_all_callback(self, result):
        result_dict={}
        
        for prop_tuple, value in result.iteritems():
            name = self.reverse_point_map[prop_tuple]
            result_dict[name] = value        
        
        return result_dict
        
    def scrape_all(self):
        read_access_spec_list = []
        for obj_data, properties in self.object_property_map.iteritems():
            obj_type, obj_inst = obj_data
            prop_ref_list = []
            for prop in properties:
                prop_ref = PropertyReference(propertyIdentifier=prop)
                prop_ref_list.append(prop_ref)
            read_access_spec = ReadAccessSpecification(objectIdentifier=(obj_type, obj_inst),
                                                       listOfPropertyReferences=prop_ref_list)
            read_access_spec_list.append(read_access_spec) 
            
        request = ReadPropertyMultipleRequest(listOfReadAccessSpecs=read_access_spec_list)
        
        request.pduDestination = self.target_address
        iocb = IOCB(request)
        self.this_application.request(iocb)
        
        iocb.ioDefered.addCallback(self.scrape_all_callback)
        return iocb.ioDefered
    
    def parse_config(self, config_file):
        if config_file is None:
            return
        
        with open(config_file, 'rb') as f:
            configDict = DictReader(f)
            
            for regDef in configDict:
                #Skip lines that have no address yet.
                if not regDef['Point Name']:
                    continue
                
                io_type = regDef['BACnet Object Type']
                read_only = regDef['Writable'].lower() != 'true'
                point_name = regDef['PNNL Point Name']        
                index = int(regDef['Index'])        
                description = regDef['Notes']                 
                units = regDef['Units']       
                property_name = regDef['Property']       
                            
                register = BACnetRegister(index, 
                                          io_type, 
                                          property_name, 
                                          read_only, 
                                          point_name,
                                          units, 
                                          description = description)
                    
                self.insert_register(register)

    
class BACnet(BaseSmapVolttron):
    def setup(self, opts):
        super(BACnet, self).setup(opts)
        self.set_metadata('/', {'Extra/Driver' : 'volttron.drivers.bacnet.BACnet'})
             
    def get_interface(self, opts):
        target_ip_address = opts['target_address']
        self_ip_address = opts['self_address']
        config = opts.get('register_config', configFile)
        
        max_apdu_len = int(opts.get('max_apdu_length', 1024))
        
        seg_supported  = opts.get('segmented_supported', 'segmentedBoth')
        obj_id  = int(opts.get('object_id', 599))
        obj_name  = opts.get('object_name', 'sMap BACnet driver')
        ven_id  = int(opts.get('vendor_id', 15))
        
        return BACnetInterface(self_ip_address, target_ip_address, 
                               max_apdu_len=max_apdu_len, seg_supported=seg_supported, 
                               obj_id=obj_id, obj_name=obj_name, 
                               ven_id=ven_id,
                               config_file=config)
        
if __name__ == "__main__":
    from pprint import pprint    
    from time import sleep
    import sys
    
    iface = BACnetInterface(sys.argv[1], sys.argv[2], config_file='test2.csv')
    
    def run_tests():    
        print 'Test'
        r = iface.get_point_sync('RoomRealTemp2')
        print 'RoomRealTemp2', r
        r = iface.get_point_sync('RoomRealTemp1')
        print 'RoomRealTemp1', r
        r = iface.get_point_sync('OutsideAir')
        print 'OutsideAir', r
        r = iface.get_point_sync('Current1')
        print 'Current1', r
        r = iface.get_point_sync('Occupied')
        print 'Occupied', r
        
        r = iface.get_point_sync('Volt1')
        print 'Volt1', r
        
        new_value = 55.0 if r != 55.0 else 65.0
        print 'Writing to Volt1:', new_value
        r = iface.set_point_sync('Volt1', new_value)
        print 'Volt1 change result', r
        
        #For some reason on the test device if we try to read what
        # we just wrote too quickly we'll get back the old value.
        sleep(1)
        r = iface.get_point_sync('Volt1')
        print 'Volt1', r
        
        def printvalue(value, name):
            print name,':'
            pprint(value)
            
        d = iface.get_point_async('ProgrammingAnalogVariable1')
        d.addCallback(printvalue, 'ProgrammingAnalogVariable1')
        
        d = iface.get_point_async('Cool1')
        d.addCallback(printvalue, 'Cool1')
        
        d = iface.scrape_all()
        d.addCallback(printvalue, 'all')
        
        def end():        
            reactor.stop()
            
        
        reactor.callLater(2, end)
        
    reactor.callLater(0, run_tests)
    reactor.run()
    
