from __future__ import annotations
import json
from pathlib import Path

import random
from dataclasses import dataclass, field
import time
from typing import Any, Dict, List

import gevent
import pytest
import yaml


from volttron.platform import get_services_core
from volttron.platform.agent.known_identities import CONFIGURATION_STORE, PLATFORM_DRIVER
from volttron.platform.agent.utils import execute_command, is_auth_enabled
from volttron.platform.scheduling import periodic
from volttron.platform.vip.agent import Agent
from volttron.platform.vip.agent.core import Core
from volttron.platform.vip.agent.subsystems.rpc import RPC
from volttrontesting.utils.platformwrapper import PlatformWrapper
from requests import Session

from ieee_2030_5 import xml_to_dataclass
import ieee_2030_5.models as m





@dataclass
class AllPoints:
    points: Dict = field(default_factory=dict)
    meta: Dict = field(default_factory=dict)

    def add(self, name: str, value: Any, meta: Dict = {}):
        self.points[name] = value
        self.meta[name] = meta

    def forbus(self) -> List:
        return [self.points, self.meta]


def test_inverter_agent_starts(volttron_instance: PlatformWrapper):
    
    vip_identity = "test_inverter"
    test_config_file = Path(__file__).parent.joinpath("fixtures/test_config.yml")
    test_config_file_data = yaml.safe_load(test_config_file.open("rt").read())
    config_name = test_config_file_data['point_map'][10:]
    test_inverter_csv = Path(__file__).parent.joinpath("fixtures/test_inverter.csv")
    volttron_instance.config_store_store(vip_identity, config_name, test_inverter_csv, "csv")
    
    agnt = volttron_instance.install_agent(agent_dir=get_services_core("IEEE_2030_5"), config_file=test_config_file.as_posix(), 
                                           start=True, vip_identity=vip_identity)
    assert volttron_instance.is_agent_running(agnt)
    
    request_session = Session()
    request_base_uri = f"https://{test_config_file_data['server_hostname']}:{test_config_file_data['server_ssl_port']}"
    tls_path = Path(test_config_file_data["certfile"]).expanduser().parent.parent
    request_session.cert = (tls_path.joinpath("certs/admin.crt"), tls_path.joinpath("private/admin.pem"))
    request_session.verify = Path(test_config_file_data["cacertfile"]).expanduser().as_posix()
    
    # Note this was originally csv, but dictionaries are easier to deal with.
    resp = volttron_instance.config_store_get(vip_identity, config_name)
    points = json.loads(resp)
    
    assert points
    
    class MyActuator(Agent):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            
        @RPC.export
        def set_point(self, requester_id, topic, value, point=None):
            print(f"{self.__class__.__name__} Set point called")
            
        
        @RPC.export
        def get_point(self, topic, point=None):
            print(f"{self.__class__.__name__} Get point called")

    
    class MyPlatformDriver(Agent):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.running_greenlets: List = []
            self.point_config = points
            self.things_i_publish = [x for x in test_config_file_data["subscriptions"]]
            self.things_i_published = []
        
            self.point_values = {}
        
        @RPC.export
        def set_point(self, path, point_name, value):
            print(f"{self.__class__.__name__} Set point called")
        
        @RPC.export
        def get_point(self, path, point_name):
            print(f"{self.__class__.__name__} Get point called")
            
            
        def do_a_publish(self):
            for p in self.things_i_publish:
                self.vip.pubsub.publish(peer="pubsub",
                                topic=p,
                                message=self.point_config)
    
    driver_agent = volttron_instance.build_agent(identity="platform.driver", agent_class=MyPlatformDriver)
    actuator_agent = volttron_instance.build_agent(identity="platform.actuator", agent_class=MyActuator)
    
    def admin_uri(path):
        return f"{request_base_uri}/admin/{path}"
    
    def uri(path):
        return f"{request_base_uri}/{path}"
    
    resp = request_session.get(uri("mup"))
    
    mup_list: m.MirrorUsagePointList = xml_to_dataclass(resp.text)

    assert isinstance(mup_list, m.MirrorUsagePointList)
    assert len(test_config_file_data['MirrorUsagePointList']) == mup_list.all 

    resp = request_session.get(uri("upt"))
    upt_list: m.UsagePointList = xml_to_dataclass(resp.text)
    assert isinstance(upt_list, m.UsagePointList)
    assert mup_list.all == upt_list.all