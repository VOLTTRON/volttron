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

"""
Based on the WhoIsIAm.py sample application from the BACpypes library.
"""

import sys

from bacpypes.debugging import bacpypes_debugging, ModuleLogger
from bacpypes.consolelogging import ConfigArgumentParser
from bacpypes.consolecmd import ConsoleCmd

from bacpypes.core import run, stop

from bacpypes.pdu import Address, GlobalBroadcast
from bacpypes.app import BIPSimpleApplication
from bacpypes.service.device import LocalDeviceObject
from bacpypes.apdu import WhoIsRequest, IAmRequest
from bacpypes.basetypes import ServicesSupported
from bacpypes.errors import DecodingError

import threading
import time
import csv

# some debugging
_debug = 0
_log = ModuleLogger(globals())

# globals
this_device = None
this_application = None
this_console = None

#
#   WhoIsIAmApplication
#

this_csv_file = None

@bacpypes_debugging
class WhoIsIAmApplication(BIPSimpleApplication):

    def __init__(self, *args):
        if _debug: WhoIsIAmApplication._debug("__init__ %r", args)
        BIPSimpleApplication.__init__(self, *args)

        # keep track of requests to line up responses
        self._request = None

    def request(self, apdu):
        if _debug: WhoIsIAmApplication._debug("request %r", apdu)

        # save a copy of the request
        self._request = apdu

        # forward it along
        BIPSimpleApplication.request(self, apdu)

    def confirmation(self, apdu):
        if _debug: WhoIsIAmApplication._debug("confirmation %r", apdu)

        # forward it along
        BIPSimpleApplication.confirmation(self, apdu)

    def indication(self, apdu):
        if _debug: WhoIsIAmApplication._debug("indication %r", apdu)

        if (isinstance(self._request, WhoIsRequest)) and (isinstance(apdu, IAmRequest)):
            device_type, device_instance = apdu.iAmDeviceIdentifier
            if device_type != 'device':
                raise DecodingError("invalid object type")

            if (self._request.deviceInstanceRangeLowLimit is not None) and \
                (device_instance < self._request.deviceInstanceRangeLowLimit):
                pass
            elif (self._request.deviceInstanceRangeHighLimit is not None) and \
                (device_instance > self._request.deviceInstanceRangeHighLimit):
                pass
            else:
                # print out the contents
                sys.stdout.write('\n')
                sys.stdout.write('Device Address        = ' + repr(apdu.pduSource) + '\n')
                sys.stdout.write('Device Id             = ' + str(device_instance) + '\n')
                sys.stdout.write('maxAPDULengthAccepted = ' + str(apdu.maxAPDULengthAccepted) + '\n')
                sys.stdout.write('segmentationSupported = ' + str(apdu.segmentationSupported) + '\n')
                sys.stdout.write('vendorID              = ' + str(apdu.vendorID) + '\n')
                sys.stdout.flush()
                if this_csv_file is not None:
                    row = {"address":apdu.pduSource,
                           "device_id": device_instance,
                           "max_apdu_length": apdu.maxAPDULengthAccepted,
                           "segmentation_supported": apdu.segmentationSupported,
                           "vendor_id": apdu.vendorID}
                    this_csv_file.writerow(row)

        # forward it along
        BIPSimpleApplication.indication(self, apdu)

#
#   WhoIsIAmConsoleCmd
#

@bacpypes_debugging
class WhoIsIAmConsoleCmd(ConsoleCmd):

    def do_whois(self, args):
        """whois [ <addr>] [ <lolimit> <hilimit> ]"""
        args = args.split()
        if _debug: WhoIsIAmConsoleCmd._debug("do_whois %r", args)

        try:
            # build a request
            request = WhoIsRequest()
            if (len(args) == 1) or (len(args) == 3):
                request.pduDestination = Address(args[0])
                del args[0]
            else:
                request.pduDestination = GlobalBroadcast()

            if len(args) == 2:
                request.deviceInstanceRangeLowLimit = int(args[0])
                request.deviceInstanceRangeHighLimit = int(args[1])
            if _debug: WhoIsIAmConsoleCmd._debug("    - request: %r", request)

            # give it to the application
            this_application.request(request)

        except Exception as e:
            WhoIsIAmConsoleCmd._exception("exception: %r", e)

#
#   __main__
#


# parse the command line arguments
arg_parser = ConfigArgumentParser(description=__doc__)

arg_parser.add_argument("--address",
                        help="Target only device(s) at <address> for request" )

arg_parser.add_argument("--range", type=int, nargs=2, metavar=('LOW', 'HIGH'),
                        help="Lower and upper limit on device ID in results" )

arg_parser.add_argument("--timeout", type=int, metavar=('SECONDS'),
                        help="Time, in seconds, to wait for responses. Default: %(default)s",
                        default = 5)

arg_parser.add_argument("--csv-out", dest="csv_out",
                        help="Write results to the CSV file specified.")



args = arg_parser.parse_args()

f = None

if args.csv_out is not None:
    mode = 'wb' if sys.version_info.major == 2 else 'w'
    f = open(args.csv_out, mode)
    field_names = ["address",
                   "device_id",
                   "max_apdu_length",
                   "segmentation_supported",
                   "vendor_id"]
    this_csv_file = csv.DictWriter(f, field_names)
    this_csv_file.writeheader()

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

# build a bit string that knows about the bit names
pss = ServicesSupported()
pss['whoIs'] = 1
pss['iAm'] = 1

# set the property value to be just the bits
this_device.protocolServicesSupported = pss.value

# make a simple application
this_application = WhoIsIAmApplication(this_device, args.ini.address)
_log.debug("running")

request = WhoIsRequest()

if args.address is not None:
    request.pduDestination = Address(args.address)
else:
    request.pduDestination = GlobalBroadcast()

if args.range is not None:
    request.deviceInstanceRangeLowLimit = int(args.range[0])
    request.deviceInstanceRangeHighLimit = int(args.range[1])

try:
    #set timeout timer
    def time_out():
        time.sleep(args.timeout)
        stop()

    thread = threading.Thread(target=time_out)
    thread.start() 

    this_application.request(request)

    run()

except Exception as e:
    _log.exception("an error has occurred: %s", e)
finally:
    _log.debug("finally")
    if f is not None:
        f.close()

