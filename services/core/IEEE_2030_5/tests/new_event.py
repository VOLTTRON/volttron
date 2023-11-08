from datetime import datetime
import sys
import os
import time
import uuid
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from dataclasses import asdict
from pprint import pprint
import urllib3
from request_session import get_as_admin, get_as_device, post_as_admin, post_as_device
import ieee_2030_5.models as m
from ieee_2030_5 import dataclass_to_xml, xml_to_dataclass
urllib3.disable_warnings()

def print_it(thing: str, obj: object):
    print(f"{'='*20} {thing} {'='*20}")
    try:
        pprint(asdict(obj), indent=4)
    except TypeError:
        print(f"Type: {type(obj)} was passed and cannot be printed!")
        
dcap: m.DeviceCapability = get_as_device("dcap")
print_it("DeviceCapability", dcap)

edevl: m.EndDeviceList = get_as_device("edev")
print_it("EndDeviceList", edevl)

edev = edevl.EndDevice[0]
derl = get_as_device(edev.DERListLink.href)
print_it("DERList", derl)

der: m.DER = derl.DER[0]
current_program: m.DERProgram = get_as_device(der.CurrentDERProgramLink.href)
print_it("CurrentDERProgram", current_program)

dderc: m.DefaultDERControl = get_as_device(current_program.DefaultDERControlLink.href)
print_it("DefaultDERControl", dderc)

dercl: m.DERControlList = get_as_device(current_program.DERControlListLink.href)
print_it("DERControlList", dercl)

current_time = int(time.mktime(datetime.utcnow().timetuple()))
print(f"Time is: {current_time}")
mrid = str(uuid.uuid4()).replace('-', '')
new_ctrl = m.DERControl(mRID=mrid, DERControlBase=dderc.DERControlBase, description="A new control is going here")
new_ctrl.interval = m.DateTimeInterval(start=current_time + 5, duration=30)
new_ctrl.DERControlBase.opModTargetW = m.ActivePower(3, 2000)
print_it("New Control is", new_ctrl)
print(f"{dataclass_to_xml(new_ctrl)}")
response = post_as_admin(dercl.href, data=dataclass_to_xml(new_ctrl))

print("Right before controls start")
dercl: m.DERControlList = get_as_device(current_program.DERControlListLink.href)
print_it("DERControlList", dercl)
activectl: m.DERControlList = get_as_device(current_program.ActiveDERControlListLink.href)
print("Should not have an active control.")
print_it("ActiveDERControlList", activectl)
print("Sleeping 10 seconds until control has started")
time.sleep(10)
activectl: m.DERControlList = get_as_device(current_program.ActiveDERControlListLink.href)
print("Active control should have started!")
print_it("ActiveDERControlList", activectl)
time.sleep(35)
activectl: m.DERControlList = get_as_device(current_program.ActiveDERControlListLink.href)
print("Event should be over now")
print_it("ActiveDERControlList", activectl)