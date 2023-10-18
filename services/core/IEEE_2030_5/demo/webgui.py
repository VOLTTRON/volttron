#!/usr/bin/env python3
from __future__ import annotations

import calendar
from copy import deepcopy
from pprint import pformat
import os
from parser import ParserError

import re

import sys
import time
import uuid
import urllib3
from dataclasses import dataclass, field, fields
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, TypeVar
import logging
import xsdata
import yaml
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from numbers import Number
import re

from volttron.platform import get_volttron_root
from volttron.platform.agent.utils import parse_timestamp_string, process_timestamp

urllib3.disable_warnings()

sys.path.insert(0, str(Path(__file__).absolute().parent.parent.as_posix()))

import subprocess

import ieee_2030_5.models as m
import requests
from nicegui import app, background_tasks, ui

from ieee_2030_5 import dataclass_to_xml, xml_to_dataclass

logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
_log = logging.getLogger(__name__)

def uuid_2030_5() -> str:
    return str(uuid.uuid4()).replace('-', '').upper()

def datetime_from_utc_to_local(utc_datetime):
    now_timestamp = time.time()
    offset = datetime.fromtimestamp(now_timestamp) - datetime.utcfromtimestamp(now_timestamp)
    return utc_datetime + offset

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
    
# Configuration parameters from the config page
config = Configuration()
# Temp storage for changes on the config page
config_working = Configuration()

# A session for talking with the 2030.5 server
session = requests.Session()
# A file to watch for updates to output from the agent connected to volttron
# the "watch_devices_to_file.py" output.
#watch_file = WatchFileState(sys.argv[1], interval=3)
program_list = []

admin_session = requests.Session()
client_session = requests.Session()

S = TypeVar('S')
T = TypeVar('T')

class PropertyWrapper:
    """The PropertyWrapper class handles binding on behalf of the parent object.
    
    The class handles the binding from/to and formatting/applying when sending the
    object to the parent.
    """
    
    def __init__(self, backing_obj: T, parent_obj: S, parent_property: str, 
                 formatters: Dict[str, Callable] = None, applyers: Dict[str, Callable] = None):
        # The sub object that we need to provide for
        self.backing_obj = backing_obj
        # The parent object this property is wrapping
        self.parent_obj = parent_obj
        # The property this object is wrapping on the parent_obj
        self.parent_property = parent_property
        
        if formatters is None:
            formatters = {}
            
        if applyers is None:
            applyers = {}
            
        self.formatters = formatters
        self.appliers = applyers
        # Transfer the values from the parent to the backing object
        if self.parent_obj.__dict__[self.parent_property] is not None:            
            if isinstance(self.backing_obj, (m.VoltageRMS, m.ApparentPower, m.CurrentRMS,
                                                 m.ActivePower, m.FixedVar, m.FixedPointType,
                                                 m.ReactivePower, m.AmpereHour, m.WattHour)):
                self.backing_obj.__dict__["value"] = self.parent_obj.__dict__[self.parent_property].value
    
    def __setattr__(self, key: str, value: Any):
        if key in ("backing_obj", "parent_obj", "parent_property", "formatters", "appliers"):
            self.__dict__[key] = value
        else:
            if key in self.formatters:
                self.backing_obj.__dict__[key] = self.formatters[key](value)
            else:
                _log.debug(f"Setting on {type(self.backing_obj)} {key} -> {value}")
                self.backing_obj.__dict__[key] = value
            
    def __getattr__(self, key: str) -> Any:
        if key in ("data_obj", "parent_obj", "parent_property", "formatters", "appliers"):
            return self.__dict__[key]
        else:
            return self.backing_obj.__dict__[key]
                
    def apply_to_parent(self):
        other_obj = deepcopy(self.backing_obj)
        
        # if self.appliers:
        #     other_object.__dict__[]
        # for field in fields(other_obj):
        #     if field.name in self.appliers:
        #         _log.debug(f"Converting from {other_obj.__dict__[field.name]} to {self.appliers[field.name](other_obj.__dict__[field.name])}")
        #         other_obj.__dict__[field.name] = self.appliers[field.name](other_obj.__dict__[field.name])
        
        if self.should_be_none():
            setattr(self.parent_obj, self.parent_property, None)
        else:            
            _log.debug(f"Setting {self.parent_property} to {other_obj}")
            setattr(self.parent_obj, self.parent_property, other_obj)
            _log.debug(f"Parent obj is {self.parent_obj}")
    
    def should_be_none(self) -> bool:
        """Answers the question whether the parent property should be None.
        
        Loop over the backing object and if any of the fields are not None then
        the answer is False.  Otherwise the answer is True.
        
        :return: True if all fields are None, False otherwise.
        """
        for fld in fields(self.backing_obj):
            if getattr(self.backing_obj, fld.name):
                return False
        return True

def update_sessions():
    """Update the admin and client sessions with the current configuration."""
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

def convert_local_dt_to_utc_timestamp(dt: datetime) -> int:
    """Converts a local datetime to a UTC timestamp.

    :param dt: A datetime object in local time.
    :type dt: datetime
    :return: A UTC timestamp for passing to 2030.5 server.
    :rtype: int
    """
    # Leaving these commented out as a guide to how we got the answer to the issue.
    # _log.debug(f"Start with dt: {dt} at {int(dt.timestamp())}")
    # _log.debug(f"get date from ts: {datetime.fromtimestamp(int(dt.timestamp()))}")
    gmt_date = datetime.utcfromtimestamp(int(dt.timestamp()))
    # _log.debug(f"gmtdate {gmt_date} at {int(gmt_date.timestamp())}")
    # _log.debug(f"get gmtdate back: {datetime.fromtimestamp(int(gmt_date.timestamp()))}")
    
    # _log.debug(f"Converting {dt} to epoch time gmtime")
    return int(gmt_date.timestamp())

  
update_sessions()
dcap: m.DeviceCapability = get_from_server("dcap", deserialize=True)
edl: m.EndDeviceList = get_from_server(dcap.EndDeviceListLink.href, deserialize=True)
edev = edl.EndDevice[0]
ders: m.DERList = get_from_server(edev.DERListLink.href, deserialize=True)
der = ders.DER[0]
program: m.DERProgram = get_from_server(der.CurrentDERProgramLink.href, deserialize=True)

# def update_from_server():
#     dcap: m.DeviceCapability = get_from_server("dcap", deserialize=True)
#     edl: m.EndDeviceList = get_from_server(dcap.EndDeviceListLink.href, deserialize=True)
#     edev = edl.EndDevice[0]
#     ders: m.DERList = get_from_server(edev.DERListLink.href, deserialize=True)
#     der = ders.DER[0]
#     program: m.DERProgram = get_from_server(der.CurrentDERProgramLink.href, deserialize=True)
    


def noneable_int_change(obj: object, prop: str, value):
    try:
        num = int(value.sender.value)
        setattr(obj, prop, num)
    except (ValueError, TypeError):
        ...

@ui.refreshable
def render_der_default_control_tab():
    def refresh_default_control_tab():
        render_der_default_control_tab.refresh()
        ui.notify("Refreshed") 
    default: m.DefaultDERControl = get_from_server(program.DefaultDERControlLink.href, deserialize=True)
    der_base: m.DERControlBase = default.DERControlBase
    if der_base is None:
        der_base = m.DERControlBase()
        default.DERControlBase = der_base
        
    wrappers: List[PropertyWrapper] = []
        
    with ui.row():
        with ui.column():
            with ui.label("DER Default Control").style("font-size: 200%;"):
                ui.button(icon="refresh", color="white", 
                      on_click=lambda: refresh_default_control_tab()).style("margin:5px; padding: 5px;")
            ui.label("Section 10.10 Distributed Energy Resources function set from 20305-2018 IEEE standard.")
            
    with ui.row().classes("pt-10"):
        with ui.column().classes("pr-15"):            
            ui.input("setESDelay (hundredth of a second)",
                                      on_change=lambda e: noneable_int_change(default, "setESDelay", e)) \
                                          .bind_value_from(default, "setESDelay").classes("w-96")
                #.bind_value_from(default, "setESDelay").classes("w-96")
            ui.input("setESHighFreq (hundredth of a hertz)",
                                      on_change=lambda e: noneable_int_change(default, "setESHighFreq", e)) \
                .bind_value_from(default, "setESHighFreq").classes("w-96")
            ui.input("setESHighVolt (hundredth of a volt)",
                                      on_change=lambda e: noneable_int_change(default, "setESHighVolt", e)) \
                .bind_value_from(default, "setESHighVolt").classes("w-96")
            
        with ui.column().classes("pr-15"):
            ui.input("setESLowFreq (hundredth of a hertz)",
                                      on_change=lambda e: noneable_int_change(default, "setESLowFreq", e)) \
                .bind_value_from(default, "setESLowFreq").classes("w-96")
            ui.input("setESLowVolt (hundredth of a volt)",
                                      on_change=lambda e: noneable_int_change(default, "setESLowVolt", e)) \
                .bind_value_from(default, "setESLowVolt").classes("w-96")
            ui.input("setESRampTms (hundredth of a second)",
                                      on_change=lambda e: noneable_int_change(default, "setESRampTms", e)) \
                .bind_value_from(default, "setESRampTms").classes("w-96")
        with ui.column():
            
            ui.input("setESRandomDelay (hundredth of a second)",
                                      on_change=lambda e: noneable_int_change(default, "setESRandomDelay", e)) \
                .bind_value_from(default, "setESRandomDelay").classes("w-96")
            ui.input("setGradW (hundredth of a watt)",
                                      on_change=lambda e: noneable_int_change(default, "setGradW", e)) \
                .bind_value_from(default, "setGradW").classes("w-96")
            ui.input("setSoftGradW (hundredth of a watt)",
                                      on_change=lambda e: noneable_int_change(default, "setSoftGradW", e)) \
                .bind_value_from(default, "setSoftGradW").classes("w-96")
    
    with ui.row().style("margin-top:15px;margin-bottom:15px;"):
        ui.label("DER Control Base").style("font-size: 150%;")
    
    with ui.row():
        with ui.column().classes("pr-20"):
            ui.checkbox("opModConnect", value=True).bind_value(der_base, "opModConnect")
            ui.checkbox("opModEnergize", value=True).bind_value(der_base, "opModEnergize")
        
        with ui.column().classes("pr-20"):
            ui.label("Power Factor Absorb Watts").style("font-size: 125%;")
            if der_base.opModFixedPFAbsorbW is None:
                der_base.opModFixedPFAbsorbW = m.PowerFactorWithExcitation()
            opModFixedPFAbsorbW_wrapper = PropertyWrapper(der_base.opModFixedPFAbsorbW, der_base, "opModFixedPFAbsorbW")
            wrappers.append(opModFixedPFAbsorbW_wrapper)
            ui.input("displacement", on_change=lambda e: noneable_int_change(opModFixedPFAbsorbW_wrapper, "displacement", e)) \
                .bind_value_from(opModFixedPFAbsorbW_wrapper, "displacement")
            ui.checkbox("excitation", value=False).bind_value(opModFixedPFAbsorbW_wrapper, "excitation")
            
            ui.label("Power Factor Inject Watts").style("font-size: 125%;")
            if der_base.opModFixedPFInjectW is None:
                der_base.opModFixedPFInjectW = m.PowerFactorWithExcitation()
            opModFixedPFInjectW_wrapper = PropertyWrapper(der_base.opModFixedPFInjectW, der_base, "opModFixedPFInjectW")
            wrappers.append(opModFixedPFInjectW_wrapper)
            ui.input("displacement", on_change=lambda e: noneable_int_change(opModFixedPFInjectW_wrapper, "displacement", e)) \
                .bind_value_from(opModFixedPFInjectW_wrapper, "displacement")
            ui.checkbox("excitation", value=False).bind_value(opModFixedPFInjectW_wrapper, "excitation")
            
                        
        with ui.column().classes("pr-20"):            
            fixedVar_wrapper = PropertyWrapper(m.FixedVar(), der_base, "opModFixedVar")
            wrappers.append(fixedVar_wrapper)
            ui.input("opModFixedVar", on_change=lambda e: noneable_int_change(fixedVar_wrapper, "value", e)) \
                .bind_value_from(fixedVar_wrapper, "value")
                
            # fixedWatt_wrapper = PropertyWrapper(m.WattHour(), der_base, "opModFixedW")
            # wrappers.append(fixedWatt_wrapper)            
            # ui.input("opModFixedW", on_change=lambda e: noneable_int_change(fixedWatt_wrapper, "value", e)) \
            #     .bind_value_from(fixedWatt_wrapper, "value")
            ui.input("opModFixedW", on_change=lambda e: noneable_int_change(der_base, "opModFixedW", e)) \
                .bind_value_from(der_base, "opModFixedW")
                
            # freqDroop_wrapper = Wrapper(m.FreqDroopType(), der_base, "openLoopTms")
            # wrappers.append(freqDroop_wrapper)
            # opModFreqDroop = ui.input("opModFreqDroop",
            #                                on_change=lambda e: noneable_int_change(freqDroop_wrapper, "openLoopTms", e)) \
            #     .bind_value_from(freqDroop_wrapper, "openLoopTms")
            
            ui.input("opModMaxLimW", on_change=lambda e: noneable_int_change(der_base, "opModMaxLimW", e)) \
                .bind_value_from(der_base, "opModMaxLimW")
                
        with ui.column().classes("pr-10"):
            opModTargetVar_wrapper = PropertyWrapper(m.ReactivePower(), der_base, "opModTargetVar")
            wrappers.append(opModTargetVar_wrapper)
            ui.input("opModTargetVar", on_change=lambda e: noneable_int_change(opModTargetVar_wrapper, "value", e)) \
                .bind_value_from(opModTargetVar_wrapper, "value")
                
            opModTargetW_wrapper = PropertyWrapper(m.ActivePower(), der_base, "opModTargetW")
            wrappers.append(opModTargetW_wrapper)
            ui.input("opModTargetW", on_change=lambda e: noneable_int_change(opModTargetW_wrapper, "value", e)) \
                .bind_value_from(opModTargetW_wrapper, "value")
                
            # opModVoltVar = ui.input("opModVoltVar",
            #                                on_change=lambda e: noneable_int_change(der_base, "opModVoltVar", e)) \
            #     .bind_value_from(der_base, "opModVoltVar")
            # opModWattPF = ui.input("opModWattPF",
            #                                on_change=lambda e: noneable_int_change(der_base, "opModWattPF", e)) \
            #     .bind_value_from(der_base, "opModWattPF")
            ui.input("rampTms", on_change=lambda e: noneable_int_change(der_base, "rampTms", e)) \
                .bind_value_from(der_base, "rampTms")
    # render_default_control(der_base)
    
    def store_default_der_control():
        try:
            _log.debug(f"Before Apply {der_base}")
            _log.debug(default)
            for wrapper in wrappers:
                _log.debug(f"Wrapper parent object {id(wrapper.parent_obj)} {wrapper.parent_obj}")
                wrapper.apply_to_parent()
                _log.debug(f"Wrapper parent object after apply {id(wrapper.parent_obj)} {wrapper.parent_obj}")
                
            _log.debug(f"After Apply {der_base}")
            base_payload = dataclass_to_xml(der_base)
            _log.warning(base_payload)
            payload = dataclass_to_xml(default)
            put_as_admin(program.DefaultDERControlLink.href, payload)
            ui.notify("Default DER Control Updated")
            render_der_default_control_tab.refresh()
        except xsdata.exceptions.ParserError as ex:
            ui.notify(ex.message, type='negative')
        
    with ui.row().classes("pt-10"):
        with ui.column():
            ui.button("Save", on_click=lambda: store_default_der_control())
    
@ui.refreshable
def render_der_status_tab():
    
    def do_refresh():
        render_der_status_tab.refresh()
        ui.notify("Refreshed")        
    
    settings: m.DERSettings = get_from_server(der.DERSettingsLink.href, deserialize=True)
    status: m.DERStatus = get_from_server(der.DERStatusLink.href, deserialize=True)
    capabilities: m.DERCapability = get_from_server(der.DERCapabilityLink.href, deserialize=True)
    with ui.row():
        with ui.label("DER Status").style("font-size: 200%;"):
            ui.button(icon="refresh", color="white", 
                      on_click=lambda: do_refresh()).style("margin:5px; padding: 5px;")
            # ui.icon("refresh", size="sm").style("cursor: pointer; vertical-align: center; padding-left: 5px;") \
            #     .on_click(lambda: render_der_status_tab.refresh()) 
    with ui.row():
        with ui.column():            
            ui.label("Section 10.10.4.4 DER info resources from 20305-2018 IEEE standard.")
    
    columns = [
        {'name': 'key', 'label': 'Key', 'field': 'key', 'required': True},
        {'name': 'value', 'label': 'Value', 'field': 'value', 'required': True}
    ]
    
    rows = []
    
    for fld in fields(status):
        if getattr(status, fld.name):
            rows.append(dict(key=fld.name, value=str(getattr(status, fld.name))))
    
    with ui.row():
        with ui.column():
            ui.label("DER Status").style("font-size: 150%;")
    
    with ui.row():
        with ui.column():
            ui.table(columns=columns, rows=rows)
               
    
    rows = []   
    
    for fld in fields(settings):
        if getattr(settings, fld.name):
            rows.append(dict(key=fld.name, value=getattr(settings, fld.name)))
    
    with ui.row():
        with ui.column():
            ui.label("DER Settings").style("font-size: 150%;")
    
    with ui.row():
        with ui.column():
            ui.table(columns=columns, rows=rows)
    
        
    rows = []   
    
    for fld in fields(capabilities):
        if getattr(capabilities, fld.name):
            rows.append(dict(key=fld.name, value=getattr(capabilities, fld.name)))
    
    with ui.row():
        with ui.column():
            ui.label("DER Capabilities").style("font-size: 150%;")
    
    with ui.row():
        with ui.column():
            ui.table(columns=columns, rows=rows)
    
@ui.refreshable
def render_der_control_list_tab():
    def do_refresh():
        render_der_control_list_tab.refresh()
        ui.notify("Refreshed") 
    
    
    control_list: m.DERControlList = get_from_server(program.DERControlListLink.href, deserialize=True)
    
    #active_list: m.DERControlList = get_from_server(program.ActiveDERControlListLink.href, deserialize=True)
    
    with ui.row():
        with ui.column():
            with ui.label("DER Control List").style("font-size: 200%;"):
                ui.button(icon="refresh", color="white", 
                      on_click=lambda: do_refresh()).style("margin:5px; padding: 5px;")
            ui.label("Section 10.10 Distributed Energy Resources function set from 20305-2018 IEEE standard.")
                
    columns = [
        {'name': 'time', 'label': 'Event Time', 'field': 'time', 'required': True},
        {'name': 'duration', 'label': 'Event Duration', 'field': 'duration', 'required': True},
        {'name': 'status', 'label': 'Event Status', 'field': 'status', 'required': True},
        {'name': 'control', 'label': 'Control', 'field': 'control', 'required': True}
        
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
        elif status == 5:
            return "Completed"
        else:
            return "Unknown"
        
    def build_list_rows(ctrl_list: m.DERControlList):
        control_list_rows = [] 
        def nonnone(control: m.DERControl):
            dct = {}
            
            for obj, val in control.DERControlBase.__dict__.items():
                if val is not None:
                    if hasattr(val, "value"):
                        val = val.value
                    elif hasattr(val, "displacement"):
                        val = val.displacement
                    dct[obj] = val
            return pformat(dct)
        
        for ctrl in sorted(ctrl_list.DERControl, key=lambda x: x.interval.start, reverse=True):
            if ctrl.interval:
                if ctrl.EventStatus is None and ctrl.interval.start and ctrl.interval.duration:
                    ctrl.EventStatus = m.EventStatus(currentStatus=0) # Scheduled.
                local_dt = datetime_from_utc_to_local(datetime.utcfromtimestamp(ctrl.interval.start))
                
                row = {
                    'time': local_dt,
                    'duration': ctrl.interval.duration,
                    'status': status_to_string(ctrl.EventStatus.currentStatus),
                    'control': nonnone(ctrl)
                }
                
                control_list_rows.append(row)
        return control_list_rows
    
    with ui.row():
        with ui.column():
            ui.label("Control Events").style("font-size: 150%")

    # with ui.row():
    #     with ui.column():
    #         ui.table(columns=columns, rows=build_list_rows(active_list, 1))
    
    # with ui.row():
    #     with ui.column():
    #         ui.label("Scheduled Controls").style("font-size: 150%")

    with ui.row():
        with ui.column():
            ui.table(columns=columns, rows=build_list_rows(control_list))
    
    # with ui.row():
    #     with ui.column():
    #         ui.label("Completed Controls").style("font-size: 150%")

    # with ui.row():
    #     with ui.column():
    #         ui.table(columns=columns, rows=build_list_rows(control_list, 5))

    
@ui.refreshable
def render_new_der_control_tab():
    # Need to start with the default control base before overwriting values from the new
    # base control.
    default: m.DefaultDERControl = get_from_server(program.DefaultDERControlLink.href, deserialize=True)
    der_base: m.DERControlBase = default.DERControlBase
    wrappers: List[PropertyWrapper] = []
    if der_base is None:
        der_base = m.DERControlBase()
        default.DERControlBase = der_base
    
    def do_refresh():
        render_new_der_control_tab.refresh()
        ui.notify("Refreshed")        
    
    with ui.row():
        with ui.column():
            with ui.label("DER Control Entry").style("font-size: 200%;"):
                ui.button(icon="refresh", color="white", 
                      on_click=lambda: do_refresh()).style("margin:5px; padding: 5px;")
            ui.label("Section 10.10 Distributed Energy Resources function set from 20305-2018 IEEE standard.")
    
    with ui.row().classes("pt-5"):
        with ui.column():
            ui.label(f"DERProgram {der.CurrentDERProgramLink.href}").style("font-size: 150%")  
    
    
    new_control = m.DERControl(mRID=uuid_2030_5())
    def submit_new_control():
        for wrapper in wrappers:
            if not wrapper.should_be_none():
                wrapper.apply_to_parent()
                
        new_control.DERControlBase = der_base
        _log.debug(f"Date Time Sending: {datetime.fromtimestamp(new_control.interval.start)}")
        # Need to modify the time to be gmt time rather than in local time.
        #new_control.interval.start = convert_datetime_to_int(new_control.interval.start)
        
        #new_ctrl = m.DERControl(mRID="b234245afff", DERControlBase=dderc.DERControlBase, description="A new control is going here")
        #new_control.interval = m.DateTimeInterval(start=current_time + 10, duration=20)
        _log.debug(dataclass_to_xml(new_control))
        response = post_as_admin(program.DERControlListLink.href, data=dataclass_to_xml(new_control))
        
        render_der_control_list_tab.refresh()
        ui.notify("New Control Complete")
        render_new_der_control_tab.refresh()
    
    def set_date(obj, prop, e):
        try:
            dt = parse_timestamp_string(e.value)
            setattr(obj, prop, e.value)
        except ParserError:
            _log.debug(f"Invalid datetime specified: {e.value}")

    with ui.row():
        with ui.column():
            interval_wrapper = PropertyWrapper(m.DateTimeInterval(duration=30, start=datetime.now() + timedelta(seconds=30)),
                                       new_control, "interval", formatters=dict(start=parse_timestamp_string),
                                       applyers=dict(start=convert_local_dt_to_utc_timestamp))
            wrappers.append(interval_wrapper)
            from_date = ui.input("Event Start", value=getattr(interval_wrapper, "start"), 
                                 on_change=lambda e: set_date(interval_wrapper, "start", e)) \
                .classes("w-96")
            duration = ui.number("Duration", min=0, value=getattr(interval_wrapper, "duration")) \
                .bind_value_from(interval_wrapper, "duration")
                
            ui.input("MRID").bind_value(new_control, "mRID").classes("w-96")
    
        with ui.column().classes("pr-20"):
            
            
            
            ui.checkbox("opModConnect", value=True).bind_value(der_base, "opModConnect")
            ui.checkbox("opModEnergize", value=True).bind_value(der_base, "opModEnergize")
       
        with ui.column().classes("pr-20"):
            ui.label("Power Factor Absorb Watts").style("font-size: 125%;")
            opModFixedPFAbsorbW_wrapper = PropertyWrapper(m.PowerFactorWithExcitation(), der_base, "opModFixedPFAbsorbW")
            wrappers.append(opModFixedPFAbsorbW_wrapper)
            ui.input("displacement", on_change=lambda e: noneable_int_change(opModFixedPFAbsorbW_wrapper, "displacement", e)) \
                .bind_value_from(opModFixedPFAbsorbW_wrapper, "displacement")
            ui.checkbox("excitation", value=False).bind_value(opModFixedPFAbsorbW_wrapper, "excitation")
            
            ui.label("Power Factor Inject Watts").style("font-size: 125%;")
            opModFixedPFInjectW_wrapper = PropertyWrapper(m.PowerFactorWithExcitation(), der_base, "opModFixedPFInjectW")
            wrappers.append(opModFixedPFInjectW_wrapper)
            ui.input("displacement", on_change=lambda e: noneable_int_change(opModFixedPFInjectW_wrapper, "displacement", e)) \
                .bind_value_from(opModFixedPFInjectW_wrapper, "displacement")
            ui.checkbox("excitation", value=False).bind_value(opModFixedPFInjectW_wrapper, "excitation")
            
                        
        with ui.column().classes("pr-20"):            
            fixedVar_wrapper = PropertyWrapper(m.FixedVar(), der_base, "opModFixedVar")
            wrappers.append(fixedVar_wrapper)
            ui.input("opModFixedVar", on_change=lambda e: noneable_int_change(fixedVar_wrapper, "value", e)) \
                .bind_value_from(fixedVar_wrapper, "value")
                
            # Note this is not using PropertyWrapper because it is defined as an int in the xsd.
            ui.input("opModFixedW", on_change=lambda e: noneable_int_change(der_base, "opModFixedW", e)) \
                .bind_value_from(der_base, "opModFixedW")
                
            # freqDroop_wrapper = Wrapper(m.FreqDroopType(), der_base, "openLoopTms")
            # wrappers.append(freqDroop_wrapper)
            # opModFreqDroop = ui.input("opModFreqDroop",
            #                                on_change=lambda e: noneable_int_change(freqDroop_wrapper, "openLoopTms", e)) \
            #     .bind_value_from(freqDroop_wrapper, "openLoopTms")
            
            ui.input("opModMaxLimW", on_change=lambda e: noneable_int_change(der_base, "opModMaxLimW", e)) \
                .bind_value_from(der_base, "opModMaxLimW")
                
        with ui.column().classes("pr-20"):
            opModTargetVar_wrapper = PropertyWrapper(m.ReactivePower(), der_base, "opModTargetVar")
            wrappers.append(opModTargetVar_wrapper)
            ui.input("opModTargetVar", on_change=lambda e: noneable_int_change(opModTargetVar_wrapper, "value", e)) \
                .bind_value_from(opModTargetVar_wrapper, "value")
                
            opModTargetW_wrapper = PropertyWrapper(m.ActivePower(), der_base, "opModTargetW")
            wrappers.append(opModTargetW_wrapper)
            ui.input("opModTargetW", on_change=lambda e: noneable_int_change(opModTargetW_wrapper, "value", e)) \
                .bind_value_from(opModTargetW_wrapper, "value")
                
            # opModVoltVar = ui.input("opModVoltVar",
            #                                on_change=lambda e: noneable_int_change(der_base, "opModVoltVar", e)) \
            #     .bind_value_from(der_base, "opModVoltVar")
            # opModWattPF = ui.input("opModWattPF",
            #                                on_change=lambda e: noneable_int_change(der_base, "opModWattPF", e)) \
            #     .bind_value_from(der_base, "opModWattPF")
            ui.input("rampTms", on_change=lambda e: noneable_int_change(der_base, "rampTms", e)) \
                .bind_value_from(der_base, "rampTms")
                
    # with ui.row().classes("pt-10"):
    #     with ui.column().classes("pr-20"):
    #         ui.label("Curve Selection")
    #         ui.label("TODO")
    
    with ui.row().classes("pt-20"):
        with ui.column():   
            ui.button("Sumbit Control", on_click=lambda: submit_new_control())
with ui.header():
    current_time_label = ui.label("Current Time")
    ui.timer(1.0, lambda: current_time_label.set_text(
        f"Local Time: {datetime.now().isoformat()} GMT TS: {convert_local_dt_to_utc_timestamp(datetime.now())}"))
with ui.tabs().classes('w-full') as tabs:
    configuration_tab = ui.tab("configuration", "Configuration")
    der_default_control_tab = ui.tab("derdefaultcontrol", "DER Default Control")
    new_der_control_tab = ui.tab("newdercontrol", "New DER Control")
    der_control_list_tab = ui.tab("dercontrollist", "DER Control List")
    der_status_tab = ui.tab("derstatus", "DER Status")
    #results_tab = ui.tab("results", "Results")
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
        ui.timer(10, lambda: render_der_control_list_tab.refresh())
        
    with ui.tab_panel(der_status_tab):
        render_der_status_tab()
        

logging.basicConfig(level=logging.INFO)

excludes = '.*, .py[cod], .sw.*, ~*,*.git,'
ui.run(reload=True, show=False, uvicorn_reload_excludes=excludes)
