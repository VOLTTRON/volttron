# pytest test cases for drivenmatlabagent

import datetime
import gevent
import pytest

from volttron.platform.agent import utils
from volttron.platform.agent import PublishMixin
from volttron.platform.vip.agent import Agent
from volttron.platform.messaging import headers as headers_mod

config_wh = {
    "agentid": "matlab",
    "application": "drivenmatlab.matlab.Application",

    "device": {
        "campus": "PNNL",
        "building": "2400_STEVENS",
        "unit": {
            "HEATER1": {
                "subdevices": []
            }
        },
        "analysis_name": "WaterHeater_Agent"
    },
    "output_file": "./waterheater_output.csv",
    "mode": "ACTIVE",
    "arguments": {
        "status_stpt": "statussetpoint",
        "temperature": "temperature",
        
        "config_url": "tcp://130.20.104.75:5556",
        "data_url": "tcp://130.20.104.75:5557",
        "recv_timeout": 50000
    },
    "conversion_map": {
        "statussetpoint*": "bool",
        "temperature*": "float"
    },
    "unittype_map": {
        "statussetpoint*": "On/Off",
        "temperature*": "Farenheit"
    }
}

@pytest.mark.drivenagent
def test_drivenmatlabagent(volttron_instance1):
    print("** Setting up test_drivenagent module **")
    
    wrapper = volttron_instance1
    
    #Actuator Agent
    agent_uuid = volttron_instance1.install_agent(
        agent_dir="services/core/ActuatorAgent",
        config_file="services/core/ActuatorAgent/actuator-deploy.service",
        start=True)
    print("agent id: ", agent_uuid)
    assert agent_uuid
    actuator_agent = wrapper.build_agent()
    
    #Driven Matlab Agent
    agent_uuid = volttron_instance1.install_agent(
        agent_dir="applications/pnnl/FakeDrivenMatlabAgent",
        config_file=config_wh,
        start=True)
    print("agent id: ", agent_uuid)
    assert agent_uuid
    driven_agent = wrapper.build_agent()
    
    #Fake Master Driver
    agent_uuid = volttron_instance1.install_agent(
        agent_dir="services/core/MasterDriverAgent",
        config_file="services/core/MasterDriverAgent/fake-master-driver.agent",
        start=True)
    print("agent id: ", agent_uuid)
    assert agent_uuid
    driver_agent = wrapper.build_agent()
    
    gevent.sleep(5)
    
    path = 'PNNL/2400_STEVENS/HEATER1/HPWH_Phy0_PowerState'
    value = driven_agent.vip.rpc.call('platform.actuator', 'get_point', path).get()
    print('The set point value is '+str(value))
    assert value == 1 
    
    path = 'PNNL/2400_STEVENS/HEATER1/ERWH_Phy0_ValveState'
    value = driven_agent.vip.rpc.call('platform.actuator', 'get_point', path).get()
    print('The set point value is '+str(value))
    assert value == 1 
