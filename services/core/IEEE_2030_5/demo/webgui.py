#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import atexit
import json
import os
import platform
import re
import shlex
import sys
import time
import uuid
from asyncio.subprocess import Process
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import yaml

from volttron.platform import get_volttron_root

sys.path.insert(0, str(Path(__file__).parent.parent))

import subprocess

import ieee_2030_5.models as m
import requests
from nicegui import app, background_tasks, ui

from services.core.IEEE_2030_5.ieee_2030_5 import dataclass_to_xml, xml_to_dataclass

session = requests.Session()
tlsdir = Path("~/tls").expanduser()
session.cert = (str(tlsdir.joinpath("certs/admin.pem")), str(tlsdir.joinpath("private/admin.pem")))
session.verify = str(tlsdir.joinpath("certs/ca.pem"))

def get_url(endpoint, not_admin: bool = False) -> str:
    if endpoint.startswith('/'):
        endpoint = endpoint[1:]
    if not_admin:
        return f"https://127.0.0.1:8443/{endpoint}"
    return f"https://127.0.0.1:8443/admin/{endpoint}"

filedirectory =  Path(__file__).parent
pkfile = filedirectory.joinpath("keypair.json")
if not pkfile.exists():
    print(f"Key file not found in demo directory {pkfile}.")
    sys.exit(0)

pk_data = yaml.safe_load(pkfile.open().read())

os.environ['AGENT_PUBLICKEY'] = pk_data['public']
os.environ['AGENT_SECRETEKY'] = pk_data['secret']
os.environ['AGENT_VIP_IDENTITY'] = "inverter1"
os.environ['AGENT_CONFIG'] = str(filedirectory.parent.joinpath('example.config.yml'))
agent_py = str(filedirectory.parent.joinpath("ieee_2030_5/agent.py"))
py_launch = str(Path(get_volttron_root()).joinpath("scripts/pycharm-launch.py"))

tasks = []

def add_my_task(task):
    tasks.append(task)
    
control_status = "None"
derp = "Not Set"
inverter_pf = "Not Set"
inverter_p = "Not Set"
inverter_q = "Not Set"
in_real = False
in_reactive = False
in_control = False
def new_agent_output(line: str):
    global inverter_q, inverter_p, in_real, in_reactive, in_control, control_status
    
    if '<EventStatus>' in line:
        in_control = True
        
    if in_control:
        if "<currentStatus>" in line:
            status_value = int(re.search(r'<currentStatus>(.*?)</currentStatus>', line).group(1))
            if status_value == -1:
                control_status = "Control Complete"
            elif status_value == 0:
                control_status = "Control Scheduled"
            elif status_value == 1:
                control_status = "Active"
            else:
                control_status = "Not Set"
            in_control = False    
            
            status.content = updated_markdown()
    
    if "url: /mup_1" in line:
        in_reactive = True
    
    if in_reactive:
        if line.startswith("<value>"):
            inverter_q = re.search(r'<value>(.*?)</value>', line).group(1)
            in_reactive = False
            status.content = updated_markdown()
    
    if "url: /mup_1" in line:
        in_real = True
    
    if in_real:
        if line.startswith("<value>"):
            inverter_p = re.search(r'<value>(.*?)</value>', line).group(1)
            in_real = False
            status.content = updated_markdown()
            


def _change_power_factor(new_pf):
    global inverter_pf
    
    current_time = int(time.mktime(datetime.utcnow().timetuple()))

    ctrl_base = m.DERControlBase(opModConnect=True, opModMaxLimW=9500)
    ctrl = m.DERControl(mRID="ctrl1mrdi", description="A control for the control list")
    ctrl.DERControlBase = ctrl_base
    ctrl.interval = m.DateTimeInterval(start=current_time + 10, duration=20)
    ctrl.randomizeDuration = 180
    ctrl.randomizeStart = 180
    ctrl.DERControlBase.opModFixedW = 500
    ctrl.DERControlBase.opModFixedPFInjectW = m.PowerFactorWithExcitation(displacement=int(pf.value))

    posted = dataclass_to_xml(ctrl)
    utility_log.push(f"Event Posted to Change opModFixedPFInjectW to {pf.value}")
    utility_log.push(posted)
    resp = session.post(get_url("derp/0/derc"), data=posted)
    resp = session.get(get_url(resp.headers.get('Location'), not_admin=True))
    pfingect: m.DERControl = xml_to_dataclass(resp.text)
    inverter_pf = pfingect.DERControlBase.opModFixedPFInjectW.displacement
    status.content = updated_markdown()
    
    

    
    
    
def get_control_event_default():
    derbase = m.DERControlBase(opModConnect=True, opModEnergize=False, opModFixedPFInjectW=80)
    
    time_plus_10 = int(time.mktime((datetime.utcnow() + timedelta(seconds=60)).timetuple()))

    derc = m.DERControl(mRID=str(uuid.uuid4()),
                description="New DER Control Event",                
                DERControlBase=derbase,
                interval=m.DateTimeInterval(duration=10, start=time_plus_10))
                 
    return dataclass_to_xml(derc)


def _setup_event(element):
    derbase = m.DERControlBase(opModConnect=True, opModEnergize=False, opModFixedPFInjectW=80)
    
    time_plus_60 = int(time.mktime((datetime.utcnow() + timedelta(seconds=60)).timetuple()))

    derc = m.DERControl(mRID=str(uuid.uuid4()),
                description="New DER Control Event",                
                DERControlBase=derbase,
                interval=m.DateTimeInterval(duration=10, start=time_plus_60))
    element.value=dataclass_to_xml(derc)
    
    #background_tasks.running_tasks.clear()
    
async def _exit_background_tasks():
    for item in tasks:
        if isinstance(item, Process):
            try:
                item.kill() # .cancel()
            except ProcessLookupError:
                pass
        else:
            item.cancel()
    # async for proc, command in tasks:
    #     print(f"Stoping {command.label}")
    #     proc.cancel()
    
    tasks.clear()
    agent_log.clear()
    inverter_log.clear()
    utility_log.clear()
        
async def run_command(command: LabeledCommand) -> None:
    '''Run a command in the background and display the output in the pre-created dialog.'''
    
    process = await asyncio.create_subprocess_exec(
        *shlex.split(command.command),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        cwd=command.working_dir
    )
    
    add_my_task(process)
    
    # NOTE we need to read the output in chunks, otherwise the process will block
    output = ''
    while True:
        new = await process.stdout.readline()
        if not new:
            break
        output = new.decode()
        if command.agent_output:
            new_agent_output(output.strip())
        
        try:
            jsonparsed = json.loads(output)
            if command.output_element is not None:
                command.output_element().push(output.strip())
        except json.decoder.JSONDecodeError:
            if not command.output_only_json:
                command.output_element().push(output.strip())
        
        # NOTE the content of the markdown element is replaced every time we have new output
        #result.content = f'```\n{output}\n```'

@dataclass
class LabeledCommand:
    label: str
    command: str
    output_element: Any
    working_dir: str = str(Path(__file__).parent)
    output_only_json: bool = True
    agent_output: bool = False

commands = [
    LabeledCommand("Start Inverter", 
                   f'{sys.executable} inverter_runner.py', 
                   lambda: inverter_log),
    LabeledCommand("Start Agent", 
                   f"{sys.executable} {py_launch} {agent_py}", 
                   lambda: agent_log, filedirectory.parent,
                   output_only_json=False,
                   agent_output=True)
]

def updated_markdown() -> str:
    return f"""#### Status
                    Control: {control_status}
                    Real Power (p): {inverter_p}
                    Reactive Power (q): {inverter_q}
                    Power Factor (pf): {inverter_pf}
                    """

with ui.column():
    # commands = [f'{sys.executable} inverter_runner.py']
    with ui.row():
        
        for command in commands:
            ui.button(command.label, on_click=lambda _, c=command: add_my_task(background_tasks.create(run_command(c)))).props('no-caps')
        
        pf = ui.select(options=[70, 80, 90], value=70, label="Power Factor").classes('w-32')
        ui.button("Change Power Factor", on_click=lambda: _change_power_factor(pf.value)).props('no-caps')    
        ui.button("Reset", on_click=_exit_background_tasks).props('no-caps')
        
    with ui.row():
        status = ui.markdown(updated_markdown())
        #ui.button("Update Control Time", on_click=lambda: _setup_event(xml_text)).props('no-caps')
        #ui.button("Send Control", on_click=lambda: _send_control_event()).props('no-caps')
    # with ui.row():
    #     xml_text = ui.textarea(label="xml", value=get_control_event_default()).props('rows=20').props('cols=120').classes('w-full, h-80')
    with ui.row():
        ui.label("Inverter Log")
        inverter_log = ui.log(max_lines=2000).props('cols=120').classes('w-full h-20')
    # with ui.row():
    #     ui.label("Proxy Log")
    #     proxy_log = ui.log().props('cols=120').classes('w-full h-80')
    with ui.row():
        ui.label("Agent Log")
        agent_log = ui.log(max_lines=2000).props('cols=120').classes('w-full h-80')
    
    with ui.row():
        ui.label("Utility Log")
        utility_log = ui.log(max_lines=2000).props('cols=120').classes('w-full h-20')
            

    
        
#atexit.register(_exit_background_tasks)
app.on_shutdown(_exit_background_tasks)

# NOTE on windows reload must be disabled to make asyncio.create_subprocess_exec work 
# (see https://github.com/zauberzeug/nicegui/issues/486)
ui.run(reload=platform.system() != "Windows", )
