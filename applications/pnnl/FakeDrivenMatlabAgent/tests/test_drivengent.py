# pytest test cases for drivenmatlabagent

import datetime
import gevent
import pytest
import gevent.subprocess as subprocess

from gevent.subprocess import Popen
from volttron.platform.agent import utils
from volttron.platform.agent import PublishMixin
from volttron.platform.vip.agent import Agent
from volttron.platform.messaging import headers as headers_mod


config_wh = {
    "agentid": "matlab",
    "application": "drivenmatlab.matlab.Application",

    "device": {
        "campus": "fakecampus",
        "building": "fakebuilding",
        "unit": {
            "fakedriver0": {
                "subdevices": []
            }
        },
        "analysis_name": "Fake_Analysis_Agent"
    },
    "output_file": "./fake_output.csv",
    "mode": "ACTIVE",
    "arguments": {
        "status_stpt": "statussetpoint",
        "temperature": "temperature"
        
    },
    "conversion_map": {
        "HPWH_Phy0_PowerState*": "int",
        "ERWH_Phy0_ValveState*": "int",
        "temperature*": "float"
    },
    "unittype_map": {
        "HPWH_Phy0_PowerState*": "On/Off",
        "ERWH_Phy0_ValveState*": "On/Off",
        "temperature*": "Farenheit"
    }
}

@pytest.mark.drivenagent
def test_drivenmatlabagent(volttron_instance):
    print("** Setting up test_drivenagent module **")
    
    wrapper = volttron_instance
    
    #Write config files for master driver
    process = Popen(['python', 'config_builder.py', 
                     '--count=1', 
                     '--publish-only-depth-all',
                     '--campus=fakecampus',
                     '--building=fakebuilding',
                     '--interval=5',
                     '--config-dir=../../applications/pnnl/FakeDrivenMatlabAgent/tests',
                     'fake', 
                     '../../applications/pnnl/FakeDrivenMatlabAgent/tests/test_fake.csv', 
                     'null'], 
                    env=volttron_instance.env, cwd='scripts/scalability-testing',
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = process.wait()
    print result
    assert result == 0
     
    #Actuator Agent
    agent_uuid = volttron_instance.install_agent(
        agent_dir="services/core/ActuatorAgent",
        config_file="services/core/ActuatorAgent/actuator-deploy.service",
        start=True)
    print("agent id: ", agent_uuid)
    assert agent_uuid
    actuator_agent = wrapper.build_agent()
     
    #Driven Matlab Agent
    agent_uuid = volttron_instance.install_agent(
        agent_dir="applications/pnnl/FakeDrivenMatlabAgent",
        config_file=config_wh,
        start=True)
    print("agent id: ", agent_uuid)
    assert agent_uuid
    driven_agent = wrapper.build_agent()
     
    #Fake Master Driver
    agent_uuid = volttron_instance.install_agent(
        agent_dir="services/core/MasterDriverAgent",
        config_file="applications/pnnl/FakeDrivenMatlabAgent/tests/master-driver.agent",
        start=True)
    print("agent id: ", agent_uuid)
    assert agent_uuid
    driver_agent = wrapper.build_agent()
     
    gevent.sleep(5)
     
    path = 'fakecampus/fakebuilding/fakedriver0/HPWH_Phy0_PowerState'
    value = driven_agent.vip.rpc.call('platform.actuator', 'get_point', path).get()
    print('The set point value is '+str(value))
    assert value == 1 
     
    path = 'fakecampus/fakebuilding/fakedriver0/ERWH_Phy0_ValveState'
    value = driven_agent.vip.rpc.call('platform.actuator', 'get_point', path).get()
    print('The set point value is '+str(value))
    assert value == 1 
