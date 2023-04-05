#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import os.path
import platform
import shlex
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import ieee_2030_5.models as m
from nicegui import background_tasks, ui

from services.core.IEEE_2030_5.ieee_2030_5 import dataclass_to_xml, xml_to_dataclass

tasks = []

def add_my_task(task):
    tasks.append(task)

    
def _send_control_event():
    default_pf = 0.99
    import requests
    session = requests.Session()
    session.cert = ('/home/os2004/tls/certs/admin.pem', '/home/os2004/tls/private/admin.pem')
    session.verify = "/home/os2004/tls/certs/ca.pem"

    control_path = Path('inverter.ctl')
    derc: m.DERControl = xml_to_dataclass(xml_text.value)
       
    
    time_now = int(time.mktime((datetime.utcnow()).timetuple()))
    
    while time_now < derc.interval.start:
        time.sleep(0.1)
        time_now = int(time.mktime((datetime.utcnow()).timetuple()))
        
    with open(str(control_path), 'wt') as fp:
        fp.write(json.dumps(dict(pf=derc.DERControlBase.opModFixedPFInjectW)))
    
    while time_now < derc.interval.start + derc.interval.duration:
        time.sleep(0.1)
        time_now = int(time.mktime((datetime.utcnow()).timetuple()))
        
    control_path.write(json.dump(dict(pf=default_pf)))
    
    
    
def get_control_event_default():
    derbase = m.DERControlBase(opModConnect=True, opModEnergize=False, opModFixedPFInjectW=80)
    
    time_plus_10 = int(time.mktime((datetime.utcnow() + timedelta(seconds=60)).timetuple()))

    derc = m.DERControl(mRID=str(uuid.uuid4()),
                description="New DER Control Event",                
                DERControlBase=derbase,
                interval=m.DateTimeInterval(duration=10, start=time_plus_10))
                            

                # setESLowVolt=0.917,
                # setESHighVolt=1.05,
                # setESLowFreq=59.5,
                # setESHighFreq=60.1,
                # setESRampTms=300,
                # setESRandomDelay=0,
                #DERControlBase=derbase)
    # dderc = m.DefaultDERControl(href=hrefs.get_dderc_href(),
    #                             mRID=str(uuid.uuid4()),
    #                             description="Default DER Control Mode",
    #                             setESDelay=300,
    #                             setESLowVolt=0.917,
    #                             setESHighVolt=1.05,
    #                             setESLowFreq=59.5,
    #                             setESHighFreq=60.1,
    #                             setESRampTms=300,
    #                             setESRandomDelay=0,
    #                             DERControlBase=derbase)
    return dataclass_to_xml(derc)


def _setup_event(element):
    derbase = m.DERControlBase(opModConnect=True, opModEnergize=False, opModFixedPFInjectW=80)
    
    time_plus_60 = int(time.mktime((datetime.utcnow() + timedelta(seconds=60)).timetuple()))

    derc = m.DERControl(mRID=str(uuid.uuid4()),
                description="New DER Control Event",                
                DERControlBase=derbase,
                interval=m.DateTimeInterval(duration=10, start=time_plus_60))
    element.value=dataclass_to_xml(derc)
    

async def _reset_tasks():
    for task in tasks:
        print(task.cancel())

        await asyncio.sleep(0.1)
    
        # while not task.cancelled():
        #     asyncio.sleep(0.1)
        #     print(task.cancelled())
        
        
    tasks.clear()
    agent_log.clear()
    proxy_log.clear()
    inverter_log.clear()
    
    #background_tasks.running_tasks.clear()

async def run_command(command: LabeledCommand) -> None:
    '''Run a command in the background and display the output in the pre-created dialog.'''
    
    process = await asyncio.create_subprocess_exec(
        *shlex.split(command.command),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        cwd=command.working_dir
    )
    
    # NOTE we need to read the output in chunks, otherwise the process will block
    output = ''
    while True:
        new = await process.stdout.readline()
        if not new:
            break
        output = new.decode()
        
        try:
            jsonparsed = json.loads(output)
            if command.output_element is not None:
                command.output_element().push(output.strip())
        except json.decoder.JSONDecodeError:
            if not command.output_only_json:
                command.output_element().push(output.strip())
        
        # NOTE the content of the markdown element is replaced every time we have new output
        #result.content = f'```\n{output}\n```'

with ui.dialog() as dialog, ui.card():
    result = ui.markdown()

@dataclass
class LabeledCommand:
    label: str
    command: str
    output_element: Any
    working_dir: str = str(Path(__file__).parent)
    output_only_json: bool = True

commands = [
    LabeledCommand("Start Inverter", f'{sys.executable} inverter_runner.py', lambda: inverter_log),
    LabeledCommand("Start Proxy", f'/home/os2004/repos/gridappsd-2030_5/.venv/bin/python -m ieee_2030_5.basic_proxy config.yml ', lambda: proxy_log, "/home/os2004/repos/gridappsd-2030_5",
                   output_only_json=False),
    LabeledCommand("Start Agent", f'{sys.executable} -m ieee_2030_5.agent', lambda: agent_log, "/home/os2004/repos/volttron/services/core/IEEE_2030_5",
                   output_only_json=False),
]

with ui.column():
    # commands = [f'{sys.executable} inverter_runner.py']
    with ui.row():
        
        for command in commands:
            ui.button(command.label, on_click=lambda _, c=command: add_my_task(background_tasks.create(run_command(c)))).props('no-caps')
            
        ui.button("Reset", on_click=lambda: _reset_tasks()).props('no-caps')
        #ui.button("Update Control Time", on_click=lambda: _setup_event(xml_text)).props('no-caps')
        #ui.button("Send Control", on_click=lambda: _send_control_event()).props('no-caps')
    # with ui.row():
    #     xml_text = ui.textarea(label="xml", value=get_control_event_default()).props('rows=20').props('cols=120').classes('w-full, h-80')
    with ui.row():
        ui.label("Inverter Log")
        inverter_log = ui.log(10).props('rows=5').props('cols=120').classes('w-full h-80')
    with ui.row():
        ui.label("Proxy Log")
        proxy_log = ui.log(10).props('rows=5').props('cols=120').classes('w-full h-80')
    with ui.row():
        ui.label("Agent Log")
        agent_log = ui.log(10).props('rows=5').props('cols=120').classes('w-full h-80')
    
    
# NOTE on windows reload must be disabled to make asyncio.create_subprocess_exec work (see https://github.com/zauberzeug/nicegui/issues/486)
ui.run(reload=platform.system() != "Windows")