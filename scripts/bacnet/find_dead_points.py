import argparse
import json
import os
import requests
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


ACE_API = "https://manager.aceiot.cloud/api"
SITE_NAME = "bernhard_lcmc_east_jefferson"
CLIENT = "bernhard"
ACE_JWT = os.getenv("ACE_JWT")


# some debugging
_debug = False
_log = ModuleLogger(globals())

# globals
this_application = None
device_address = None
object_identifier = None
property_list = None
received_points = {}

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
        # if self.property_identifier != "presentValue":
        #    return
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
        global address, object_type, object_instance, received_points
        point_index = f"{address}/{object_type}/{object_instance}"

        if iocb.ioResponse:
            try:
                apdu = iocb.ioResponse

                # find the datatype
                datatype = get_datatype(apdu.objectIdentifier[0], self.property_identifier)
                if _debug: ReadPropertyApplication._debug("    - datatype: %r", datatype)
                if not datatype:
                    raise TypeError("unknown datatype")

                # special case for array parts, others are managed by cast_out
                value = apdu.propertyValue.cast_out(datatype)
                if _debug: ReadPropertyApplication._debug("    - value: %r", value)

                # sys.stdout.write(self.property_identifier + " = " + str(value) + '\n')
                if not received_points.get(point_index):
                    if self.property_identifier == "presentValue":
                        print(f"adding {point_index} = {self.property_identifier}: {value}")
                        received_points[point_index] = {self.property_identifier: True}
                else:
                    #print(f"WARNING: value already found for {point_index=}")
                    #sys.stdout.flush()
                    pass
                # if hasattr(value, 'debug_contents'):
                #    value.debug_contents(file=sys.stdout)
                #sys.stdout.flush()
            except:
                pass

        if iocb.ioError:
            if _debug: ReadPropertyApplication._debug("    - error: %r", iocb.ioError)

            # if it is an unknown property, just skip to the next one
            if getattr(iocb.ioError, 'errorCode', '') != 'unknownProperty':
                # sys.stdout.write(self.property_identifier + "! " + str(iocb.ioError) + '\n')
                # sys.stdout.flush()
                if not received_points.get(point_index):
                    if self.property_identifier == "presentValue":
                        print(f"error reading presentValue for {point_index}")
                        received_points[point_index] = {self.property_identifier: False}
                else:
                    print(f"WARNING: non empty value when encountering error: {point_index=}")
                    #sys.stdout.flush()

        # fire off another request
        deferred(self.next_request)



def retrieve_points() -> list:
    """
    Download points in manager for current site
    """
    points_url = f"{ACE_API}/sites/{SITE_NAME}/configured_points"
    page = 1
    points = []
    while True:
        points_request = requests.get(
            points_url,
            headers={"authorization": f"Bearer {ACE_JWT}"},
            params={"per_page": 500, "page": page},
        )
        try:
            req_points = points_request.json()["items"]
        except KeyError:
            print("Is JWT/site name valid?")
            exit()
        points = points + req_points
        page += 1
        if len(req_points) < 500:
            break
    return points

def update_cache():
    points = retrieve_points()
    with open("configured_points.json", "w") as f:
        f.write(json.dumps(points, indent=4))
    return points

def find_dead_points(points):
    global this_application, device_address, object_identifier, property_list, received_points
    parser = ConfigArgumentParser()
    args = parser.parse_args()

    this_device = this_device = LocalDeviceObject(
            objectName=args.ini.objectname,
            objectIdentifier=int(args.ini.objectidentifier),
            maxApduLengthAccepted=int(args.ini.maxapdulengthaccepted),
            segmentationSupported=args.ini.segmentationsupported,
            vendorIdentifier=int(args.ini.vendoridentifier),
            )
    this_application = ReadPropertyApplication(this_device, args.ini.address)
    for point in points:
        global address, object_type, object_instance
        address, object_type, object_instance = point['name'].split('/')[-3:]
        object_instance = int(object_instance)
        # print(f"scanning {address}/{object_type}/{object_instance}")
        device_address = Address(address.split("-")[0])
        object_identifier = (object_type, object_instance)
        object_class = get_object_class(object_type)
        property_list = deque(prop.identifier for prop in object_class.properties)

        this_device.protocolServicesSupported = this_application.get_services_supported().value
        # print(f"firing off first request for {address}/{object_type}/{object_instance}")
        deferred(this_application.next_request)
        run()

    unknown = []
    for entry, value in received_points.items():
        print(f"{entry}: {value}")
        if not value['presentValue']:
            print(f"found dead value for {entry}: {value}")
            unknown.append(entry)

    with open('unknown_properties', 'w') as f:
        f.write(json.dumps(unknown, indent=4))

    print(len(received_points))


def rebuild_topic_names():
    with open('unknown_properties', 'r') as f:
        failed_points = json.loads(f.read())
    with open('configured_points.json', 'r') as f:
        points = json.loads(f.read())

    new_points = []
    for point in failed_points:
        for p in points:
            if point in p['name']:
                new_points.append(p['name'])
                print(p['name'])

    with open('unknown_points.json', 'w') as f:
        f.write(json.dumps(new_points, indent=4))
    

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh_cache", dest="refresh_cache", action="store_true")
    parser.add_argument("--rebuild_topic_names", dest="rebuild_topic_names", action="store_true")
    args = parser.parse_args()

    if args.refresh_cache:
        points = update_cache()
    else:
        try:
            with open("configured_points.json", "r") as f:
                points = json.loads(f.read())
        except FileNotFoundError:
            points = update_cache()

    if args.rebuild_topic_names:
        rebuild_topic_names()
    else:
        find_dead_points(points)

if __name__ == "__main__":
    main()
