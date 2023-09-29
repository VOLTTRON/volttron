#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import atexit
from collections import deque
import json
import os
import platform
import re
import shlex
import sys
import time
import uuid
import urllib3
from asyncio.subprocess import Process
from dataclasses import dataclass, field, fields
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import logging
import xsdata
import yaml
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from numbers import Number

from volttron.platform import get_volttron_root
from volttron.platform.agent.utils import parse_timestamp_string, process_timestamp

urllib3.disable_warnings()

sys.path.insert(0, str(Path(__file__).parent.parent))

import subprocess

import ieee_2030_5.models as m
import requests
from nicegui import app, background_tasks, ui

from ieee_2030_5 import dataclass_to_xml, xml_to_dataclass

logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
_log = logging.getLogger(__name__)

@dataclass
class Configuration:
    agent_2030_5_identity: str = "ed1"
    volttron_home: str = Path("~/.volttron").expanduser().as_posix()
    ieee_server: str = "https://127.0.0.1:8443"
    ieee_client_pk: str = Path("~/tls/private/dev1.pem").expanduser().as_posix()
    ieee_client_cert: str = Path("~/tls/certs/dev1.crt").expanduser().as_posix()
    ieee_ca: str = Path("~/tls/certs/ca.crt").expanduser().as_posix()
    
@dataclass
class WatchFileState:
    path: str
    exists: bool = False
    interval: int = 1
    in_routing: bool = False
    
    def remove(self):
        Path(self.path).unlink(missing_ok=True)
        
    
    def check_file(self) -> bool:
        return Path(self.path).exists()
    
@dataclass
class PlottedData:
    series_labels: List[str] = field(default_factory=list)
    series_ts: List[datetime] = field(default_factory=list)
    series_values: Dict[str, List[float]] = field(default_factory=dict)
    
    def df(self) -> pd.DataFrame:
        data = {"ts": self.series_ts.copy()}
        data.update(self.series_values)
        
        my_df = pd.DataFrame(data)
        my_df.set_index(['ts'])
        return my_df
        
    
    # def add_publish(self, ts, published):
        
    #     self.series_ts.append(ts)
        
    #     if len(self.series_ts) > 10:
    #         self.series_ts.pop()
        
    #     for k in published[0]:
    #         if k not in self.series_labels:
    #             self.series_labels.append(k)
    #             self.series_values[k] = []
            
    #         self.series_values[k].append(published[0][k])
    #         if len(self.series_values[k]) > 10:
    #             self.series_values[k].pop()

    #     if self.series_ts:
    #         plot_figure.refresh()

# Data from the platform driver is plotted here.
#data_plot = PlottedData()
# Configuration parameters from the config page
config = Configuration()
# Temp storage for changes on the config page
config_working = Configuration()

# A session for talking with the 2030.5 server
session = requests.Session()
# A file to watch for updates to output from the agent connected to volttron
# the "watch_devices_to_file.py" output.
watch_file = WatchFileState(sys.argv[1], interval=3)
program_list = []

admin_session = requests.Session()
client_session = requests.Session()

def update_sessions():
    tlsdir = Path(config.ieee_client_cert).parent.parent
    admin_session.cert = (str(tlsdir.joinpath("certs/admin.crt")), str(tlsdir.joinpath("private/admin.pem")))
    client_session.cert = (config.ieee_client_cert, config.ieee_client_pk)
    admin_session.verify = config.ieee_ca
    client_session.verify = config.ieee_ca
    
def get_from_server(context: str, admin_request=False, deserialize=False):
    if admin_request:        
        session = admin_session
    else:        
        session = client_session
    
    if admin_request:
        response = session.get(config.ieee_server + f"/admin/{context}")
    else:
        response = session.get(config.ieee_server + f"/{context}")
    
    if deserialize:
        return xml_to_dataclass(response.text)
    return response.text

def admin_uri(path: str):
    path = path.replace("_", "/")
    if path.startswith("/"):
        path = path[1:]
    return f"{config.ieee_server}/admin/{path}"

def __uri__(path: str):
    if path.startswith("/"):
        path = path[1:]
    return f"{config.ieee_server}/{path}"

def post_as_admin(path, data):
    print(f"POST: {admin_uri(path)}")
    assert admin_session.cert
    return admin_session.post(admin_uri(path), data=data)

def put_as_admin(path, data):
    print(f"PUT: {admin_uri(path)}")
    assert admin_session.cert
    return admin_session.put(admin_uri(path), data=data)

def post_as_device(path, data):
    print(f"POST: {__uri__(path)}")
    return client_session.post(__uri__(path), data=data)


def save_config():
    paths_needed = ('volttron_home', 'ieee_client_pk', 'ieee_client_cert', 'ieee_ca')
    path_text = ('VOLTTRON home', 'Client PK', 'Client Cert', 'CA')
    paths_unavailable = []
    
    for index, p in enumerate(paths_needed):
        if not Path(getattr(config_working, p)).exists():
            paths_unavailable.append(path_text[index])
    
    if paths_unavailable:
        ui.notify(f"Missing: {';'.join(paths_unavailable)}", type="warning", position='center')
    else:
        for fld in fields(config):
            setattr(config, fld.name, getattr(config_working, fld.name))
            
        update_sessions()
        
        ui.notify("Configuration Updated")

def reset_config():
    for fld in fields(config):
        setattr(config_working, fld.name, getattr(config, fld.name))
    
cards = []

  
update_sessions()
dcap: m.DeviceCapability = get_from_server("dcap", deserialize=True)
edl: m.EndDeviceList = get_from_server(dcap.EndDeviceListLink.href, deserialize=True)
edev = edl.EndDevice[0]
ders: m.DERList = get_from_server(edev.DERListLink.href, deserialize=True)
der = ders.DER[0]
program: m.DERProgram = get_from_server(der.CurrentDERProgramLink.href, deserialize=True)

def noneable_int_change(obj: object, prop: str, value):
    if value.sender.value == "" or value.sender.value is None:
        setattr(obj, prop, None)
    else:
        try:
            num = int(value.sender.value)
            setattr(obj, prop, num)
        except ValueError:
            ...

@ui.refreshable
def render_der_default_control_tab():
    default: m.DefaultDERControl = get_from_server(program.DefaultDERControlLink.href, deserialize=True)
    with ui.row():
        with ui.column():
            ui.label("DER Default Control").style("font-size: 200%;")
            ui.label("Section 10.10 Distributed Energy Resources function set from 20305-2018 IEEE standard.")
            
    with ui.row().classes("pt-10"):
        with ui.column().classes("pr-20"):            
            esdelay_input = ui.input("setESDelay (hundredth of a second)",
                                      on_change=lambda e: noneable_int_change(default, "setESDelay", e)) \
                                          .bind_value_from(default, "setESDelay").classes("w-96")
                #.bind_value_from(default, "setESDelay").classes("w-96")
            setESHighFreq = ui.input("setESHighFreq (hundredth of a hertz)",
                                      on_change=lambda e: noneable_int_change(default, "setESHighFreq", e)) \
                .bind_value_from(default, "setESHighFreq").classes("w-96")
            setESHighVolt = ui.input("setESHighVolt (hundredth of a volt)",
                                      on_change=lambda e: noneable_int_change(default, "setESHighVolt", e)) \
                .bind_value_from(default, "setESHighVolt").classes("w-96")
            setESLowFreq = ui.input("setESLowFreq (hundredth of a hertz)",
                                      on_change=lambda e: noneable_int_change(default, "setESHighVolt", e)) \
                .bind_value_from(default, "setESLowFreq").classes("w-96")
            setESLowVolt = ui.input("setESLowVolt (hundredth of a volt)",
                                      on_change=lambda e: noneable_int_change(default, "setESLowFreq", e)) \
                .bind_value_from(default, "setESLowVolt").classes("w-96")
        with ui.column():
            setESRampTms = ui.input("setESRampTms (hundredth of a second)",
                                      on_change=lambda e: noneable_int_change(default, "setESRampTms", e)) \
                .bind_value_from(default, "setESRampTms").classes("w-96")
            setESRandomDelay = ui.input("setESRandomDelay (hundredth of a second)",
                                      on_change=lambda e: noneable_int_change(default, "setESRandomDelay", e)) \
                .bind_value_from(default, "setESRandomDelay").classes("w-96")
            setGradW = ui.input("setGradW (hundredth of a watt)",
                                      on_change=lambda e: noneable_int_change(default, "setGradW", e)) \
                .bind_value_from(default, "setGradW").classes("w-96")
            setSoftGradW = ui.input("setSoftGradW (hundredth of a watt)",
                                      on_change=lambda e: noneable_int_change(default, "setSoftGradW", e)) \
                .bind_value_from(default, "setSoftGradW").classes("w-96")
    
    def store_default_der_control():
        try:
            put_as_admin(program.DefaultDERControlLink.href, dataclass_to_xml(default))
            ui.notify("Default DER Control Updated")
        except xsdata.exceptions.ParserError as ex:
            ui.notify(ex.message, type='negative')
        
    with ui.row().classes("pt-10"):
        with ui.column():
            ui.button("Save", on_click=lambda: store_default_der_control())
    
    
@ui.refreshable
def render_der_control_list_tab():
    control_list: m.DERControlList = get_from_server(program.DERControlListLink.href, deserialize=True)
    active_listl: m.DERControlList = get_from_server(program.ActiveDERControlListLink.href, deserialize=True)
    curve_list: m.DERCurveList = get_from_server(program.DERCurveListLink.href, deserialize=True)
    default: m.DefaultDERControl = get_from_server(program.DefaultDERControlLink.href, deserialize=True)  
    
    with ui.row():
        with ui.column():
            ui.label("DER Control List").style("font-size: 200%;")
            ui.label("Section 10.10 Distributed Energy Resources function set from 20305-2018 IEEE standard.")
    
    columns = [
        {'name': 'time', 'label': 'Event Time', 'field': 'time', 'required': True},
        {'name': 'duration', 'label': 'Event Duration', 'field': 'duration', 'required': True},
        {'name': 'status', 'label': 'Event Status', 'field': 'status', 'required': True}
        
    ]
    
    def status_to_string(status: int):
        if status == 0:
            return "Scheduled"
        elif status == 1:
            return "Active"
        elif status == 2:
            return "Cancelled"
        elif status == 3:
            return "Supersceded"
        else:
            return "Unknown"
    control_list_rows = []    
    for ctrl in control_list.DERControl:
        if ctrl.interval:
            row = {
                'time': ctrl.interval.start,
                'duration': ctrl.interval.duration,
                'status': status_to_string(ctrl.EventStatus.currentStatus)
            }
            control_list_rows.append(row)
    
    with ui.row():
        with ui.column():
            ui.label("Active Controls").style("font-size: 150%")

    with ui.row():
        with ui.column():
            ui.table(columns=columns, rows=control_list_rows)
    
    with ui.row():
        with ui.column():
            ui.label("Scheduled Controls").style("font-size: 150%")

    with ui.row():
        with ui.column():
            ui.label("Insert table here!")
            
    with ui.row():
        with ui.column():
            ui.label("Completed Controls").style("font-size: 150%")

    with ui.row():
        with ui.column():
            ui.label("Insert table here!")
    
@ui.refreshable
def render_new_der_control_tab():
        
    with ui.row():
        with ui.column():
            ui.label("DER Control Entry").style("font-size: 200%;")
            ui.label("Section 10.10 Distributed Energy Resources function set from 20305-2018 IEEE standard.")
    
    with ui.row().classes("pt-5"):
        with ui.column():
            ui.label(f"DERProgram {der.CurrentDERProgramLink.href}").style("font-size: 150%")  
    
    new_control = m.DERControl(EventStatus=m.EventStatus())
    der_base = m.DERControlBase()
    def submit_new_control():
        new_control.DERControlBase = der_base
        ui.notify("Doing good stuff but not much here!")
        render_der_control_list_tab.refresh()
    
    def combine_datetime():
        print(from_date.value)
    with ui.row():
        with ui.column():
            from_date = ui.input("Event Start", value=datetime.now(), 
                                 on_change=lambda: combine_datetime()).classes("w-96")
            duration = ui.number("Duration", min=0) \
                .bind_value_from(new_control.EventStatus, "duration")

    disable_curves = True         
    
    with ui.row():
        with ui.column().classes("pr-10"):
            ui.label("DERControlBase")
            
            opModConnect = ui.checkbox("opModConnect") \
                .bind_value(der_base, "opModConnect")
            opModEnergize = ui.checkbox("opModEnergize") \
                .bind_value(der_base, "opModEnergize")
            opModFixedPFAbsorbW = ui.input("opModFixedPFAbsorbW",
                                           on_change=lambda e: noneable_int_change(der_base, "opModFixedPFAbsorbW", e)) \
                .bind_value_from(der_base, "opModFixedPFAbsorbW")
            opModFixedPFInjectW = ui.input("opModFixedPFInjectW",
                                           on_change=lambda e: noneable_int_change(der_base, "opModFixedPFInjectW", e)) \
                .bind_value_from(der_base, "opModFixedPFInjectW")
                        
        with ui.column().classes("pr-10"):            
            opModFixedVar = ui.input("opModFixedVar",
                                           on_change=lambda e: noneable_int_change(der_base, "opModFixedVar", e)) \
                .bind_value_from(der_base, "opModFixedVar")
            opModFixedW = ui.input("opModFixedW",
                                           on_change=lambda e: noneable_int_change(der_base, "opModFixedW", e)) \
                .bind_value_from(der_base, "opModFixedW")
            opModFreqDroop = ui.input("opModFreqDroop",
                                           on_change=lambda e: noneable_int_change(der_base, "opModFreqDroop", e)) \
                .bind_value_from(der_base, "opModFreqDroop")
            opModMaxLimW = ui.input("opModMaxLimW",
                                           on_change=lambda e: noneable_int_change(der_base, "opModMaxLimW", e)) \
                .bind_value_from(der_base, "opModMaxLimW")
                
        with ui.column().classes("pr-10"):
            opModTargetVar = ui.input("opModTargetVar",
                                           on_change=lambda e: noneable_int_change(der_base, "opModTargetVar", e)) \
                .bind_value_from(der_base, "opModTargetVar")
            opModTargetW = ui.input("opModTargetW",
                                           on_change=lambda e: noneable_int_change(der_base, "opModTargetW", e)) \
                .bind_value_from(der_base, "opModTargetW")
            opModVoltVar = ui.input("opModVoltVar",
                                           on_change=lambda e: noneable_int_change(der_base, "opModVoltVar", e)) \
                .bind_value_from(der_base, "opModVoltVar")
            opModWattPF = ui.input("opModWattPF",
                                           on_change=lambda e: noneable_int_change(der_base, "opModWattPF", e)) \
                .bind_value_from(der_base, "opModWattPF")
            rampTms: ui.input("rampTms",
                                           on_change=lambda e: noneable_int_change(der_base, "rampTms", e)) \
                .bind_value_from(der_base, "rampTms")
                
    with ui.row().classes("pt-10"):
        with ui.column().classes("pr-20"):
            ui.label("Curve Selection")
            ui.label("TODO")
    
    with ui.row().classes("pt-20"):
        with ui.column():   
            ui.button("Sumbit Control", on_click=lambda: submit_new_control())

with ui.tabs().classes('w-full') as tabs:
    configuration_tab = ui.tab("configuration", "Configuration")
    der_default_control_tab = ui.tab("derdefaultcontrol", "DER Default Control")
    new_der_control_tab = ui.tab("newdercontrol", "New DER Control")
    der_control_list_tab = ui.tab("dercontrollist", "DER Control List")
    results_tab = ui.tab("results", "Results")
line_plot = None
with ui.tab_panels(tabs, value=configuration_tab).classes("w-full"):
    with ui.tab_panel(configuration_tab):
        with ui.row():
            with ui.column():
                ui.input("2030.5 Identity").classes("w-96").bind_value(config_working, "agent_2030_5_identity")
                ui.input("VOLTTRON home").classes("w-96").bind_value(config_working, "volttron_home")
                ui.input("EndDevice private").classes("w-96").bind_value(config_working, "ieee_client_pk")
                ui.input("EndDevice cert").classes("w-96").bind_value(config_working, "ieee_client_cert")
                ui.input("CA cert").classes("w-96").bind_value(config_working, "ieee_ca")
                
        with ui.row().classes("p-10"):
            ui.button("Save", on_click=lambda: save_config())
            ui.button("Reset", on_click=lambda: reset_config())
    
    with ui.tab_panel(new_der_control_tab):
        render_new_der_control_tab()
        
    with ui.tab_panel(der_default_control_tab):
        render_der_default_control_tab()
        
    with ui.tab_panel(der_control_list_tab):
        render_der_control_list_tab()
        

def watch_for_file():
    if not watch_file.in_routing:
        watch_file.in_routing = True
        if watch_file.check_file():
            with open(watch_file.path) as rd:
                for line in rd.read().split("\n"):
                    if line.strip():
                        data = json.loads(line.strip())
                        from volttron.platform.messaging.headers import TIMESTAMP
                        ts = data["headers"][TIMESTAMP]
                        #data_plot.add_publish(parse_timestamp_string(ts), data['message'])
                        
        watch_file.remove()
        watch_file.in_routing = False
    


logging.basicConfig(level=logging.DEBUG)
#ui.timer(watch_file.interval, watch_for_file)
ui.run(reload=True, show=False)
#ui.run(reload=True, uvicorn_reload_dirs='services/core/IEEE_2030_5/demo')

# session = requests.Session()
# tlsdir = Path("~/tls").expanduser()
# session.cert = (str(tlsdir.joinpath("certs/admin.pem")), str(tlsdir.joinpath("private/admin.pem")))
# session.verify = str(tlsdir.joinpath("certs/ca.pem"))


# def get_url(endpoint, not_admin: bool = False) -> str:
#     if endpoint.startswith('/'):
#         endpoint = endpoint[1:]
#     if not_admin:
#         return f"https://127.0.0.1:8443/{endpoint}"
#     return f"https://127.0.0.1:8443/admin/{endpoint}"


# filedirectory = Path(__file__).parent
# pkfile = filedirectory.joinpath("keypair.json")
# if not pkfile.exists():
#     print(f"Key file not found in demo directory {pkfile}.")
#     sys.exit(0)

# pk_data = yaml.safe_load(pkfile.open().read())

# os.environ['AGENT_PUBLICKEY'] = pk_data['public']
# os.environ['AGENT_SECRETEKY'] = pk_data['secret']
# os.environ['AGENT_VIP_IDENTITY'] = "inverter1"
# os.environ['AGENT_CONFIG'] = str(filedirectory.parent.joinpath('example.config.yml'))
# agent_py = str(filedirectory.parent.joinpath("ieee_2030_5/agent.py"))
# py_launch = str(Path(get_volttron_root()).joinpath("scripts/pycharm-launch.py"))

# tasks = []


# def add_my_task(task):
#     tasks.append(task)


# control_status = "None"
# derp = "Not Set"
# inverter_pf = "Not Set"
# inverter_p = "Not Set"
# inverter_q = "Not Set"
# in_real = False
# in_reactive = False
# in_control = False


# def new_agent_output(line: str):
#     global inverter_q, inverter_p, in_real, in_reactive, in_control, control_status

#     if '<EventStatus>' in line:
#         in_control = True

#     if in_control:
#         if "<currentStatus>" in line:
#             status_value = int(re.search(r'<currentStatus>(.*?)</currentStatus>', line).group(1))
#             if status_value == -1:
#                 control_status = "Control Complete"
#             elif status_value == 0:
#                 control_status = "Control Scheduled"
#             elif status_value == 1:
#                 control_status = "Active"
#             else:
#                 control_status = "Not Set"
#             in_control = False

#             status.content = updated_markdown()

#     if "url: /mup_1" in line:
#         in_reactive = True

#     if in_reactive:
#         if line.startswith("<value>"):
#             inverter_q = re.search(r'<value>(.*?)</value>', line).group(1)
#             in_reactive = False
#             status.content = updated_markdown()

#     if "url: /mup_1" in line:
#         in_real = True

#     if in_real:
#         if line.startswith("<value>"):
#             inverter_p = re.search(r'<value>(.*?)</value>', line).group(1)
#             in_real = False
#             status.content = updated_markdown()


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
#     utility_log.push(f"Event Posted to Change opModFixedPFInjectW to {pf.value}")
#     utility_log.push(posted)
#     resp = session.post(get_url("derp/0/derc"), data=posted)
#     resp = session.get(get_url(resp.headers.get('Location'), not_admin=True))
#     pfingect: m.DERControl = xml_to_dataclass(resp.text)
#     inverter_pf = pfingect.DERControlBase.opModFixedPFInjectW.displacement
#     status.content = updated_markdown()


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

#     #background_tasks.running_tasks.clear()


# async def _exit_background_tasks():
#     for item in tasks:
#         if isinstance(item, Process):
#             try:
#                 item.kill()    # .cancel()
#             except ProcessLookupError:
#                 pass
#         else:
#             item.cancel()
#     # async for proc, command in tasks:
#     #     print(f"Stoping {command.label}")
#     #     proc.cancel()

#     tasks.clear()
#     agent_log.clear()
#     inverter_log.clear()
#     utility_log.clear()


# async def run_command(command: LabeledCommand) -> None:
#     '''Run a command in the background and display the output in the pre-created dialog.'''

#     process = await asyncio.create_subprocess_exec(*shlex.split(command.command),
#                                                    stdout=asyncio.subprocess.PIPE,
#                                                    stderr=asyncio.subprocess.STDOUT,
#                                                    cwd=command.working_dir,
#                                                    env=dict(os.environ))

#     add_my_task(process)

#     # NOTE we need to read the output in chunks, otherwise the process will block
#     output = ''
#     while True:
#         new = await process.stdout.readline()
#         if not new:
#             break
#         output = new.decode()
#         if command.agent_output:
#             new_agent_output(output.strip())

#         try:
#             jsonparsed = json.loads(output)
#             if command.output_element is not None:
#                 command.output_element().push(output.strip())
#         except json.decoder.JSONDecodeError:
#             if not command.output_only_json:
#                 command.output_element().push(output.strip())

#         # NOTE the content of the markdown element is replaced every time we have new output
#         #result.content = f'```\n{output}\n```'


# @dataclass
# class LabeledCommand:
#     label: str
#     command: str
#     output_element: Any
#     working_dir: str = str(Path(__file__).parent)
#     output_only_json: bool = True
#     agent_output: bool = False


# commands = [
#     LabeledCommand("Start Inverter", f'{sys.executable} inverter_runner.py', lambda: inverter_log),
#     LabeledCommand("Start Agent",
#                    f"{sys.executable} {py_launch} {agent_py}",
#                    lambda: agent_log,
#                    filedirectory.parent,
#                    output_only_json=False,
#                    agent_output=True)
# ]


# def updated_markdown() -> str:
#     return f"""#### Status
#                     Control: {control_status}
#                     Real Power (p): {inverter_p}
#                     Reactive Power (q): {inverter_q}
#                     Power Factor (pf): {inverter_pf}
#                     """


# with ui.column():
#     # commands = [f'{sys.executable} inverter_runner.py']
#     with ui.row():

#         for command in commands:
#             ui.button(command.label,
#                       on_click=lambda _, c=command: add_my_task(
#                           background_tasks.create(run_command(c)))).props('no-caps')

#         pf = ui.select(options=[70, 80, 90], value=70, label="Power Factor").classes('w-32')
#         ui.button("Change Power Factor",
#                   on_click=lambda: _change_power_factor(pf.value)).props('no-caps')
#         ui.button("Reset", on_click=_exit_background_tasks).props('no-caps')

#     with ui.row():
#         status = ui.markdown(updated_markdown())
#         #ui.button("Update Control Time", on_click=lambda: _setup_event(xml_text)).props('no-caps')
#         #ui.button("Send Control", on_click=lambda: _send_control_event()).props('no-caps')
#     # with ui.row():
#     #     xml_text = ui.textarea(label="xml", value=get_control_event_default()).props('rows=20').props('cols=120').classes('w-full, h-80')
#     with ui.row():
#         ui.label("Inverter Log")
#         inverter_log = ui.log(max_lines=2000).props('cols=120').classes('w-full h-20')
#     # with ui.row():
#     #     ui.label("Proxy Log")
#     #     proxy_log = ui.log().props('cols=120').classes('w-full h-80')
#     with ui.row():
#         ui.label("Agent Log")
#         agent_log = ui.log(max_lines=2000).props('cols=120').classes('w-full h-80')

#     with ui.row():
#         ui.label("Utility Log")
#         utility_log = ui.log(max_lines=2000).props('cols=120').classes('w-full h-20')

# #atexit.register(_exit_background_tasks)
# app.on_shutdown(_exit_background_tasks)

# # NOTE on windows reload must be disabled to make asyncio.create_subprocess_exec work
# # (see https://github.com/zauberzeug/nicegui/issues/486)
# ui.run(reload=platform.system() != "Windows", )
