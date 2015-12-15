# Example file using the weather agent.
#
# Requirements
#    - A VOLTTRON instance must be started
#    - A weatheragnet must be running prior to running this code.
#
# Author: Craig Allwardt
import pytest

sqlite_platform = {
    "agentid": "sqlhistorian-sqlite",
    "identity": "platform.historian",
    "connection": {
        "type": "sqlite",
        "params": {
            "database": "~/.volttron/data/platform.historian.sqlite"
        }
    }
}

mysql_platform={
    "agentid": "sqlhistorian-mysql",
    "identity": "platform.historian",
    "connection": {
        "type": "mysql",
        "params": {
            "host": "localhost",
            "port": 3306,
            "database": "historian",
            "user": "historian",
            "passwd": "historian"
        }
    }
}

@pytest.fixture(scope="module",params=[sqlite_platform])
def sqlhistorian(request,volttron_instance1):
    agent_uuid = volttron_instance1.install_agent(
                  agent_dir="services/core/SQLHistorian", 
                  config_file=request.param,
                  start=True)
    print("##########3In setup method 1")
    def stop_agent():
        print("##########In teardown method of module")
        volttron_instance1.stop_agent(agent_uuid)
    request.addfinalizer(stop_agent)
     

@pytest.fixture(params=[sqlite_platform])
def clean(request,volttron_instance1,sqlhistorian):
    def delete_row():
        #sqlhistorian._connection.cursor.execute("DELETE FROM DATA")
        #sqlhistorian._connection.cursor.execute("DELETE FROM TOPIC")
        print("##########In teardown method of function")
        #print(request.param)
        #request.param
    request.addfinalizer(delete_row)
    
    
    

def test_insert(volttron_instance1, sqlhistorian, clean):
    print("###################testing insert")
    assert 0
    

# import dateutil.parser
# from volttron.platform.vip.agent import Agent
# import gevent
# from gevent.core import callback
# import random
# from volttron.platform.messaging import headers as headers_mod
# import pytest
# 
# 
#           
# 
#     
# a = Agent()
# gevent.spawn(a.core.run).join(0)
#                        
# try: 
#     
# 
#     ''' This method publishes fake data for use by the rest of the agent.
#     The format mimics the format used by VOLTTRON drivers.
#     
#     This method can be removed if you have real data to work against.
#     '''
#     
#     #Make some random readings
#     oat_reading = random.uniform(30,100)
#     mixed_reading = oat_reading + random.uniform(-5,5)
#     damper_reading = random.uniform(0,100)
#     
#     # Create a message for all points.
#     all_message = [{'OutsideAirTemperature': oat_reading, 'MixedAirTemperature': mixed_reading, 
#                 'DamperSignal': damper_reading},
#                {'OutsideAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
#                 'MixedAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'}, 
#                 'DamperSignal': {'units': '%', 'tz': 'UTC', 'type': 'float'}
#                 }]
#     
#     
#     
#     #Create timestamp
#     now = '2015-12-02T00:00:00'
#     headers = {
#         headers_mod.DATE: now
#     }
#     
#     #Publish messages
#     result = a.vip.pubsub.publish(
#         'pubsub', 'devices/Building/LAB/Device/all', headers, all_message).get(timeout=10)
#             
#     
#     gevent.sleep(5)
#     
# 
#     result = a.vip.rpc.call('platform.historian', 
#                    'query', 
#                     topic='Building/LAB/Device/OutsideAirTemperature',
#                     #start= "2015-12-02T00:00:00",
#                     #end= "2015-12-03T00:00:00",
#                    count = 20,
#                    order = "LAST_TO_FIRST").get(timeout=10)
#     print('Query Result', result)
# except Exception as e:
#     print ("Could not contact historian. Is it running?")
#     print(e)
#                  
# gevent.sleep(5)
# a.core.stop()



