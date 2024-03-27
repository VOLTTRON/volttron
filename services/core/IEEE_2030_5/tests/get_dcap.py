from datetime import datetime
import sys
import os
import time
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
        print(f'Type: {type(obj)} was passed and cannot be printed!')

dcap: m.DeviceCapability = get_as_device('dcap')
print_it('DeviceCapability', dcap)

tm: m.Time = get_as_device(dcap.TimeLink.href)
print_it('Time', tm)

edevl: m.EndDeviceList = get_as_device('edev')
print_it('EndDeviceList', edevl)
edev = edevl.EndDevice[0]
print(edev.LogEventListLink.href)

derl = get_as_device(edev.DERListLink.href)
print_it('DERList', derl)

der: m.DER = derl.DER[0]
current_program = get_as_device(der.CurrentDERProgramLink.href)
print_it('CurrentDERProgram', current_program)

config: m.Configuration = get_as_device(edev.ConfigurationLink.href)
print_it('Configuration', config)

info: m.DeviceInformation = get_as_device(edev.DeviceInformationLink.href)
print_it('DeviceInformation', info)

status: m.DeviceStatus = get_as_device(edev.DeviceStatusLink.href)
print_it('DeviceStatus', status)

fsal: m.FunctionSetAssignmentsList = get_as_device(edev.FunctionSetAssignmentsListLink.href)
print_it('FunctionSetAssignmentsList', fsal)
derpl: m.DERProgramList = get_as_device(fsal.FunctionSetAssignments[0].DERProgramListLink.href)
print_it('DERProgramList', derpl)

derp: m.DERProgram = derpl.DERProgram[0]
derca = get_as_device(derp.ActiveDERControlListLink.href)
print_it('ActiveDERControlList', derca)


dderc: m.DefaultDERControl = get_as_device(derp.DefaultDERControlLink.href)
print_it('DefaultDERControl', dderc)


dercl: m.DERControlList = get_as_device(derp.DERControlListLink.href)
print_it('DERControlList', dercl)

# No curves yet
#curvel = get_as_device(derp.DERCurveListLink.href)
#print_it("DERCurveList", curvel)

mup = m.MirrorUsagePoint()
mup.description = 'Test Mirror Usage Point'
mup.deviceLFDI = edev.lFDI
mup.mRID = '5509D69F8B3535950000000000009182'
mup.serviceCategoryKind = 0
mup.roleFlags = 49

mmr = m.MirrorMeterReading()
mmr.description = 'Real Power(W) Set'
mmr.mRID = '5509D69F8B3535950000000000009182'

mrt = m.ReadingType()
mrt.accumulationBehaviour = 12
mrt.commodity = 1
mrt.intervalLength = 300
mrt.powerOfTenMultiplier = 0
mrt.uom = 38
mmr.ReadingType = mrt
mup.MirrorMeterReading.append(mmr)

# Expect
resp = post_as_device('mup', data=dataclass_to_xml(mup))

new_mup = get_as_device(resp.headers['Location'])

print_it('New Mirror Usage Point', new_mup)
print('\n\n')
input('Press Enter to continue...')
#while True:
current_time = int(time.mktime(datetime.utcnow().timetuple()))
print(f'Time is: {current_time}')
new_ctrl = m.DERControl(mRID='b234245afff', DERControlBase=dderc.DERControlBase, description='A new control is going here')
new_ctrl.interval = m.DateTimeInterval(start=current_time + 5, duration=10)
response = post_as_admin(dercl.href, data=dataclass_to_xml(new_ctrl))

ctrl_evnt = get_as_device(response.headers['Location'])
print_it('DERControl', ctrl_evnt)

ctrll = get_as_device(derp.DERControlListLink.href)
print_it('DERControl List', ctrll)

activel = get_as_device(derp.ActiveDERControlListLink.href)
print_it('ActiveDERControl', activel)

print('Waiting for activation of control on server...')
print(print(f"{'='*20} Sleeping 6 s {'='*20}"))
time.sleep(6)

activel = get_as_device(derp.ActiveDERControlListLink.href)
print_it('ActiveDERControl', activel)

print('Waiting for deactivation of control on server...')
print(print(f"{'='*20} Sleeping 20 s {'='*20}"))
time.sleep(20)

activel = get_as_device(derp.ActiveDERControlListLink.href)
print_it('ActiveDERControl', activel)

# ctrl_str = """<DERControlList xmlns="urn:ieee:std:2030.5:ns" href="/derp_0_derc" subscribable="0" all="3">
#   <DERControl href="/derp_0_derc_0" responseRequired="00" subscribable="0">
#     <description>Control 1</description>
#     <DERControlBase>{'opModConnect': True, 'opModMaxLimW': 9500}</DERControlBase>
#   </DERControl>
#   <DERControl href="/derp_0_derc_1" responseRequired="00" subscribable="0">
#     <description>Control 2</description>
#     <DERControlBase>{'opModConnect': True, 'opModFixedW': 80}</DERControlBase>
#   </DERControl>
#   <DERControl href="/derp_0_derc_2" responseRequired="00" subscribable="0">
#     <mRID>94E46E50F4964762B94E6C24AA350CA2</mRID>
#     <interval>
#       <duration>60</duration>
#       <start>1696592892</start>
#     </interval>
#     <DERControlBase>
#       <opModConnect>true</opModConnect>
#       <opModMaxLimW>9500</opModMaxLimW>
#     </DERControlBase>
#   </DERControl>
# </DERControlList>"""




# def _change_power_factor(new_pf):
#     global inverter_pf

#     current_time = int(time.mktime(datetime.utcnow().timetuple()))

#     ctrl_base = m.DERControlBase(opModConnect=True, opModMaxLimW=9500)
#     ctrl = m.DERControl(mRID="ctrl1mrdi", description="A control for the control list")
#     ctrl.DERControlBase = ctrl_base
#     ctrl.interval = m.DateTimeInterval(start=current_time + 10, duration=20)
#     ctrl.randomizeDuration = 180
#     ctrl.randomizeStart = 180
#     ctrl.DERControlBase.opModFixedW = 500
#     ctrl.DERControlBase.opModFixedPFInjectW = m.PowerFactorWithExcitation(
#         displacement=int(pf.value))

#     posted = dataclass_to_xml(ctrl)
#     _log.debug(f"POST\n{posted}")
#     resp = session.post(get_url("derp/0/derc"), data=posted)
#     # Post will have a response with the location of the DERControl
#     der_control_uri = resp.headers.get('Location')
#     _log.debug(f"GET\n{der_control_uri}")
#     resp = session.get(der_control_uri, not_admin=True)
#     _log.debug(f"{resp.text}")
#     # pfingect: m.DERControl = resp.text)
#     # inverter_pf = pfingect.DERControlBase.opModFixedPFInjectW.displacement
#     # status.content = updated_markdown()


# def get_control_event_default():
#     derbase = m.DERControlBase(opModConnect=True, opModEnergize=False, opModFixedPFInjectW=80)

#     time_plus_10 = int(time.mktime((datetime.utcnow() + timedelta(seconds=60)).timetuple()))

#     derc = m.DERControl(mRID=str(uuid.uuid4()),
#                         description="New DER Control Event",
#                         DERControlBase=derbase,
#                         interval=m.DateTimeInterval(duration=10, start=time_plus_10))

#     return dataclass_to_xml(derc)


# def _setup_event(element):
#     derbase = m.DERControlBase(opModConnect=True, opModEnergize=False, opModFixedPFInjectW=80)

#     time_plus_60 = int(time.mktime((datetime.utcnow() + timedelta(seconds=60)).timetuple()))

#     derc = m.DERControl(mRID=str(uuid.uuid4()),
#                         description="New DER Control Event",
#                         DERControlBase=derbase,
#                         interval=m.DateTimeInterval(duration=10, start=time_plus_60))
#     element.value = dataclass_to_xml(derc)
