#!/usr/bin/env python

"""
This application presents a 'console' prompt to the user asking for read commands
which create ReadPropertyRequest PDUs, then lines up the coorresponding ReadPropertyACK
and prints the value.
"""

import sys
from collections import deque

from bacpypes.debugging import bacpypes_debugging, ModuleLogger
from bacpypes.consolelogging import ConfigArgumentParser
from bacpypes.consolecmd import ConsoleCmd

from bacpypes.core import run, stop, deferred
from bacpypes.iocb import IOCB

from bacpypes.pdu import Address
from bacpypes.apdu import ReadPropertyRequest, ReadPropertyACK
from bacpypes.primitivedata import Unsigned
from bacpypes.constructeddata import Array

from bacpypes.app import BIPSimpleApplication
from bacpypes.object import get_object_class, get_datatype
from bacpypes.service.device import LocalDeviceObject

# some debugging
_debug = 0
_log = ModuleLogger(globals())

# globals
this_application = None
device_address = None
object_identifier = None
property_list = None

#
#   ReadPropertyApplication
#

@bacpypes_debugging
class ReadPropertyApplication(BIPSimpleApplication):

    def __init__(self, *args):
        if _debug: ReadPropertyApplication._debug("__init__ %r", args)
        BIPSimpleApplication.__init__(self, *args)

        # current property being read
        self.property_identifier = None

    def next_request(self):
        if _debug: ReadPropertyApplication._debug("next_request")
        global device_address, object_identifier, property_list

        # check to see if we're done
        if not property_list:
            if _debug: ReadPropertyApplication._debug("    - done")
            stop()
            return

        # get the next request
        self.property_identifier = property_list.popleft()
        if _debug: ReadPropertyApplication._debug("    - property_identifier: %r", self.property_identifier)

        # build a request
        request = ReadPropertyRequest(
            destination=device_address,
            objectIdentifier=object_identifier,
            propertyIdentifier=self.property_identifier,
            )
        if _debug: ReadPropertyApplication._debug("    - request: %r", request)

        # make an IOCB
        iocb = IOCB(request)

        # set a callback for the response
        iocb.add_callback(self.complete_request)
        if _debug: ReadPropertyApplication._debug("    - iocb: %r", iocb)

        # send the request
        this_application.request_io(iocb)

    def complete_request(self, iocb):
        if _debug: ReadPropertyApplication._debug("complete_request %r", iocb)

        if iocb.ioResponse:
            apdu = iocb.ioResponse

            # find the datatype
            datatype = get_datatype(apdu.objectIdentifier[0], self.property_identifier)
            if _debug: ReadPropertyApplication._debug("    - datatype: %r", datatype)
            if not datatype:
                raise TypeError("unknown datatype")

            # special case for array parts, others are managed by cast_out
            value = apdu.propertyValue.cast_out(datatype)
            if _debug: ReadPropertyApplication._debug("    - value: %r", value)

            sys.stdout.write(self.property_identifier + " = " + str(value) + '\n')
            if hasattr(value, 'debug_contents'):
                value.debug_contents(file=sys.stdout)
            sys.stdout.flush()

        if iocb.ioError:
            if _debug: ReadPropertyApplication._debug("    - error: %r", iocb.ioError)

            # if it is an unknown property, just skip to the next one
            if getattr(iocb.ioError, 'errorCode', '') != 'unknownProperty':
                sys.stdout.write(self.property_identifier + "! " + str(iocb.ioError) + '\n')
                sys.stdout.flush()

        # fire off another request
        deferred(self.next_request)


#
#   __main__
#

def main():
    global this_application, device_address, object_identifier, property_list

    # parse the command line arguments
    parser = ConfigArgumentParser(description=__doc__)
    parser.add_argument(
        "address",
        help="device address",
        )
    parser.add_argument(
        "objtype",
        help="object types, e.g., analogInput",
        )
    parser.add_argument(
        "objinstance", type=int,
        help="object instance",
        )
    args = parser.parse_args()

    if _debug: _log.debug("initialization")
    if _debug: _log.debug("    - args: %r", args)

    # interpret the address
    device_address = Address(args.address)
    if _debug: _log.debug("    - device_address: %r", device_address)

    # build an identifier
    object_identifier = (args.objtype, args.objinstance)
    if _debug: _log.debug("    - object_identifier: %r", object_identifier)

    # get the object class
    object_class = get_object_class(args.objtype)
    if _debug: _log.debug("    - object_class: %r", object_class)

    # make a queue of the properties
    property_list = deque(prop.identifier for prop in object_class.properties)
    if _debug: _log.debug("    - property_list: %r", property_list)

    # make a device object
    this_device = LocalDeviceObject(
        objectName=args.ini.objectname,
        objectIdentifier=int(args.ini.objectidentifier),
        maxApduLengthAccepted=int(args.ini.maxapdulengthaccepted),
        segmentationSupported=args.ini.segmentationsupported,
        vendorIdentifier=int(args.ini.vendoridentifier),
        )

    # make a simple application
    this_application = ReadPropertyApplication(this_device, args.ini.address)

    # get the services supported
    services_supported = this_application.get_services_supported()
    if _debug: _log.debug("    - services_supported: %r", services_supported)

    # let the device object know
    this_device.protocolServicesSupported = services_supported.value

    # fire off a request when the core has a chance
    deferred(this_application.next_request)

    _log.debug("running")

    run()

    _log.debug("fini")

if __name__ == "__main__":
    main()
