#!/usr/bin/env python

"""
This application presents a 'console' prompt to the user asking for commands.

For 'read' commands it will create ReadPropertyRequest PDUs, then lines up the
coorresponding ReadPropertyACK and prints the value.  For 'write' commands it
will create WritePropertyRequst PDUs and prints out a simple acknowledgement.
"""

import sys

from bacpypes.debugging import bacpypes_debugging, ModuleLogger
from bacpypes.consolelogging import ConfigArgumentParser
from bacpypes.consolecmd import ConsoleCmd

from bacpypes.core import run, enable_sleeping
from bacpypes.iocb import IOCB

from bacpypes.pdu import Address
from bacpypes.object import get_object_class, get_datatype

from bacpypes.apdu import SimpleAckPDU, \
    ReadPropertyRequest, ReadPropertyACK, WritePropertyRequest
from bacpypes.primitivedata import Null, Atomic, Integer, Unsigned, Real
from bacpypes.constructeddata import Array, Any

from bacpypes.app import BIPSimpleApplication
from bacpypes.service.device import LocalDeviceObject

# some debugging
_debug = 0
_log = ModuleLogger(globals())

# globals
this_application = None

#
#   ReadWritePropertyConsoleCmd
#

@bacpypes_debugging
class ReadWritePropertyConsoleCmd(ConsoleCmd):

    def do_read(self, args):
        """read <addr> <type> <inst> <prop> [ <indx> ]"""
        args = args.split()
        if _debug: ReadWritePropertyConsoleCmd._debug("do_read %r", args)

        try:
            addr, obj_type, obj_inst, prop_id = args[:4]

            if obj_type.isdigit():
                obj_type = int(obj_type)
            elif not get_object_class(obj_type):
                raise ValueError("unknown object type")

            obj_inst = int(obj_inst)

            datatype = get_datatype(obj_type, prop_id)
            if not datatype:
                raise ValueError("invalid property for object type")

            # build a request
            request = ReadPropertyRequest(
                objectIdentifier=(obj_type, obj_inst),
                propertyIdentifier=prop_id,
                )
            request.pduDestination = Address(addr)

            if len(args) == 5:
                request.propertyArrayIndex = int(args[4])
            if _debug: ReadWritePropertyConsoleCmd._debug("    - request: %r", request)

            # make an IOCB
            iocb = IOCB(request)
            if _debug: ReadWritePropertyConsoleCmd._debug("    - iocb: %r", iocb)

            # give it to the application
            this_application.request_io(iocb)

            # wait for it to complete
            iocb.wait()

            # do something for success
            if iocb.ioResponse:
                apdu = iocb.ioResponse

                # should be an ack
                if not isinstance(apdu, ReadPropertyACK):
                    if _debug: ReadWritePropertyConsoleCmd._debug("    - not an ack")
                    return

                # find the datatype
                datatype = get_datatype(apdu.objectIdentifier[0], apdu.propertyIdentifier)
                if _debug: ReadWritePropertyConsoleCmd._debug("    - datatype: %r", datatype)
                if not datatype:
                    raise TypeError("unknown datatype")

                # special case for array parts, others are managed by cast_out
                if issubclass(datatype, Array) and (apdu.propertyArrayIndex is not None):
                    if apdu.propertyArrayIndex == 0:
                        value = apdu.propertyValue.cast_out(Unsigned)
                    else:
                        value = apdu.propertyValue.cast_out(datatype.subtype)
                else:
                    value = apdu.propertyValue.cast_out(datatype)
                if _debug: ReadWritePropertyConsoleCmd._debug("    - value: %r", value)

                sys.stdout.write(str(value) + '\n')
                if hasattr(value, 'debug_contents'):
                    value.debug_contents(file=sys.stdout)
                sys.stdout.flush()

            # do something for error/reject/abort
            if iocb.ioError:
                sys.stdout.write(str(iocb.ioError) + '\n')

        except Exception as error:
            ReadWritePropertyConsoleCmd._exception("exception: %r", error)

    def do_write(self, args):
        """write <addr> <type> <inst> <prop> <value> [ <indx> ] [ <priority> ]"""
        args = args.split()
        ReadWritePropertyConsoleCmd._debug("do_write %r", args)

        try:
            addr, obj_type, obj_inst, prop_id = args[:4]
            if obj_type.isdigit():
                obj_type = int(obj_type)
            obj_inst = int(obj_inst)
            value = args[4]

            indx = None
            if len(args) >= 6:
                if args[5] != "-":
                    indx = int(args[5])
            if _debug: ReadWritePropertyConsoleCmd._debug("    - indx: %r", indx)

            priority = None
            if len(args) >= 7:
                priority = int(args[6])
            if _debug: ReadWritePropertyConsoleCmd._debug("    - priority: %r", priority)

            # get the datatype
            datatype = get_datatype(obj_type, prop_id)
            if _debug: ReadWritePropertyConsoleCmd._debug("    - datatype: %r", datatype)

            # change atomic values into something encodeable, null is a special case
            if (value == 'null'):
                value = Null()
            elif issubclass(datatype, Atomic):
                if datatype is Integer:
                    value = int(value)
                elif datatype is Real:
                    value = float(value)
                elif datatype is Unsigned:
                    value = int(value)
                value = datatype(value)
            elif issubclass(datatype, Array) and (indx is not None):
                if indx == 0:
                    value = Integer(value)
                elif issubclass(datatype.subtype, Atomic):
                    value = datatype.subtype(value)
                elif not isinstance(value, datatype.subtype):
                    raise TypeError("invalid result datatype, expecting %s" % (datatype.subtype.__name__,))
            elif not isinstance(value, datatype):
                raise TypeError("invalid result datatype, expecting %s" % (datatype.__name__,))
            if _debug: ReadWritePropertyConsoleCmd._debug("    - encodeable value: %r %s", value, type(value))

            # build a request
            request = WritePropertyRequest(
                objectIdentifier=(obj_type, obj_inst),
                propertyIdentifier=prop_id
                )
            request.pduDestination = Address(addr)

            # save the value
            request.propertyValue = Any()
            try:
                request.propertyValue.cast_in(value)
            except Exception as error:
                ReadWritePropertyConsoleCmd._exception("WriteProperty cast error: %r", error)

            # optional array index
            if indx is not None:
                request.propertyArrayIndex = indx

            # optional priority
            if priority is not None:
                request.priority = priority

            if _debug: ReadWritePropertyConsoleCmd._debug("    - request: %r", request)

            # make an IOCB
            iocb = IOCB(request)
            if _debug: ReadWritePropertyConsoleCmd._debug("    - iocb: %r", iocb)

            # give it to the application
            this_application.request_io(iocb)

            # wait for it to complete
            iocb.wait()

            # do something for success
            if iocb.ioResponse:
                # should be an ack
                if not isinstance(iocb.ioResponse, SimpleAckPDU):
                    if _debug: ReadWritePropertyConsoleCmd._debug("    - not an ack")
                    return

                sys.stdout.write("ack\n")

            # do something for error/reject/abort
            if iocb.ioError:
                sys.stdout.write(str(iocb.ioError) + '\n')

        except Exception as error:
            ReadWritePropertyConsoleCmd._exception("exception: %r", error)

    def do_rtn(self, args):
        """rtn <addr> <net> ... """
        args = args.split()
        if _debug: ReadWritePropertyConsoleCmd._debug("do_rtn %r", args)

        # safe to assume only one adapter
        adapter = this_application.nsap.adapters[0]
        if _debug: ReadWritePropertyConsoleCmd._debug("    - adapter: %r", adapter)

        # provide the address and a list of network numbers
        router_address = Address(args[0])
        network_list = [int(arg) for arg in args[1:]]

        # pass along to the service access point
        this_application.nsap.add_router_references(adapter, router_address, network_list)


#
#   __main__
#

def main():
    global this_application

    # parse the command line arguments
    args = ConfigArgumentParser(description=__doc__).parse_args()

    if _debug: _log.debug("initialization")
    if _debug: _log.debug("    - args: %r", args)

    # make a device object
    this_device = LocalDeviceObject(
        objectName=args.ini.objectname,
        objectIdentifier=int(args.ini.objectidentifier),
        maxApduLengthAccepted=int(args.ini.maxapdulengthaccepted),
        segmentationSupported=args.ini.segmentationsupported,
        vendorIdentifier=int(args.ini.vendoridentifier),
        )

    # make a simple application
    this_application = BIPSimpleApplication(this_device, args.ini.address)

    # get the services supported
    services_supported = this_application.get_services_supported()
    if _debug: _log.debug("    - services_supported: %r", services_supported)

    # let the device object know
    this_device.protocolServicesSupported = services_supported.value

    # make a console
    this_console = ReadWritePropertyConsoleCmd()
    if _debug: _log.debug("    - this_console: %r", this_console)

    # enable sleeping will help with threads
    enable_sleeping()

    _log.debug("running")

    run()

    _log.debug("fini")

if __name__ == "__main__":
    main()
