# Example file using the weather agent.
#
# Requirements
#    - A VOLTTRON instance must be started
#    - A weatheragnet must be running prior to running this code.
#
# Author: Craig Allwardt
import pytest
import sqlite3
from volttron.platform.vip.agent import Agent
from volttron.platform.agent import utils
import gevent
import random
from volttron.platform.messaging import headers as headers_mod
from datetime import datetime

##Module level variables
sqlite_platform = {
    "agentid": "sqlhistorian-sqlite",
    "identity": "platform.historian",
    "connection": {
        "type": "sqlite",
        "params": {
            "database": 'test.sqlite'
        }
    }
}

points = {
    "oat_point": "devices/Building/LAB/Device/OutsideAirTemperature",
    "mixed_point": "devices/Building/LAB/Device/MixedAirTemperature",
    "damper_point": "devices/Building/LAB/Device/DamperSignal",
    "all_topic": "devices/Building/LAB/Device/all"
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

db_connection=None
publish_agent = None

## Fixtures for setup and teardown
@pytest.fixture(scope="module",params=[sqlite_platform])
def sqlhistorian(request,volttron_instance1):
    global db_connection,publish_agent
    # Make database connection
    print request.param

    #Install and start sqlhistorian agent
    agent_uuid = volttron_instance1.install_agent(
                  agent_dir="services/core/SQLHistorian",
                  config_file=request.param,
                  start=True)
    gevent.sleep(1)
    # if request.param['connection']['type'] == "sqlite":
    #     from os import path
    #     db_name = request.param['connection']['params']['database']
    #     database_path = path.join(volttron_instance1.volttron_home,
    #         'agents', agent_uuid,
    #         'sqlhistorianagent-3.0.1/sqlhistorianagent-3.0.1.agent-data',
    #          db_name)
    #     print(database_path)
    #     assert path.exists(database_path)
    #
    #     try:
    #         print "connecting to sqlite path " + database_path
    #         db_connection = sqlite3.connect(database_path)
    #         print "successfully connected to sqlite"
    #     except sqlite3.Error, e:
    #         pytest.skip(msg="Unable to connect to sqlite databse: " +
    #                         database_path +
    #                         " Exception:" + e.args[0])
    # elif request.param['connection']['type'] == "mysql":
    #     print "connect to mysql"
    #     #db_connection = sqlite3.connect('example.db')
    # else:
    #     pytest.skip(msg="Invalid database type specified "+request.param['connection']['type'] )

    #Start a fake agent to publish to message bus
    publish_agent = volttron_instance1.build_agent()

    #add a tear down method to stop sqlhistorian agent and the fake agent that published to message bus
    # def stop_agent():
    #     print("##########In teardown method of module")
    #     if db_connection:
    #         db_connection.close()
    #     volttron_instance1.stop_agent(agent_uuid)
    #     publish_agent.core.stop()
    # request.addfinalizer(stop_agent)



@pytest.fixture(params=[sqlite_platform])
def clean(request,volttron_instance1,sqlhistorian):
    pass
    # def delete_row_sqlite():
    #     global db_connection
    #     print("###Sqlite delete test records")
    #     cursor = db_connection.cursor()
    #     cursor.execute("DELETE FROM data")
    #     cursor.execute("DELETE FROM topics;")
    #     db_connection.commit()
    #
    # if request.param['connection']['type'] == "sqlite":
    #     print("####### Adding sqlite finalizer")
    #     request.addfinalizer(delete_row_sqlite)
    # else:
    #     print ("### Adding mysql finalizer")

@pytest.mark.historian
def test_basic_function(volttron_instance1, sqlhistorian, clean):
    """
    Test basic functionality of sql historian. Inserts three points as part of all topic and checks
    if all three got into the database
    :param volttron_instance1: The instance against which the test is run
    :param sqlhistorian: instance of the sql historian tested
    :param clean: teardown function
    """
    print("################### 1 " + __name__)
    print('HOME', volttron_instance1.volttron_home)

    #Publish fake data. The format mimics the format used by VOLTTRON drivers.
    #Make some random readings
    oat_reading = random.uniform(30,100)
    mixed_reading = oat_reading + random.uniform(-5,5)
    damper_reading = random.uniform(0,100)

    # Create a message for all points.
    all_message = [{'OutsideAirTemperature': oat_reading, 'MixedAirTemperature': mixed_reading,
                'DamperSignal': damper_reading},
               {'OutsideAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                'MixedAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                'DamperSignal': {'units': '%', 'tz': 'UTC', 'type': 'float'}
                }]



    #Create timestamp
    now = datetime.utcnow().isoformat(' ') + 'Z'
    headers = {
        headers_mod.DATE: now
    }
    print("################### 2 " + __name__)
    #Publish messages
    result = publish_agent.vip.pubsub.publish(
        'pubsub', "devices/Building/LAB/Device/all", headers, all_message).get(timeout=10)

    print("###################testing insert")
    gevent.sleep(5)

    print("################### 3 " + __name__)
    result = publish_agent.vip.rpc.call('platform.historian',
                   'query',
                    topic= "devices/Building/LAB/Device/OutsideAirTemperature",
                    #start= now,
                    count = 20,
                    order = "LAST_TO_FIRST").get(timeout=10)
    print('###########Query Result', result)
    assert 1


# @pytest.mark.historian
# def test_insert_zero_timestamp(request,volttron_instance1, sqlhistorian, clean):
#     print("###################" + __name__)
#     try:
#
#         #Publish fake data. The format mimics the format used by VOLTTRON drivers.
#         #Make some random readings
#         oat_reading = random.uniform(30,100)
#         mixed_reading = oat_reading + random.uniform(-5,5)
#         damper_reading = random.uniform(0,100)
#
#         # Create a message for all points.
#         all_message = [{'OutsideAirTemperature': oat_reading, 'MixedAirTemperature': mixed_reading,
#                     'DamperSignal': damper_reading},
#                    {'OutsideAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
#                     'MixedAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
#                     'DamperSignal': {'units': '%', 'tz': 'UTC', 'type': 'float'}
#                     }]
#
#
#
#         #Create timestamp
#         now = '2015-12-02T00:00:00'
#         headers = {
#             headers_mod.DATE: now
#         }
#         print("###################" + __name__)
#         #Publish messages
#         result = publish_agent.vip.pubsub.publish(
#             'pubsub', request.param['all_topic'], headers, all_message).get(timeout=10)
#
#         print("###################testing insert")
#         gevent.sleep(5)
#
#         print("###################" + __name__)
#         result = publish_agent.vip.rpc.call('platform.historian',
#                        'query',
#                         topic= request.param['oat_point'],
#                         start= "2015-12-02T00:00:00",
#                         end= "2015-12-03T00:00:01",
#                        count = 20,
#                        order = "LAST_TO_FIRST").get(timeout=10)
#         print('###########Query Result', result)
#         assert 1
#     except Exception as e:
#         print ("Exception testing insert: ", e)
#         assert 0

# import dateutil.parser
# from volttron.platform.vip.agent import Agent
#
# from gevent.core import callback
# import random
# from volttron.platform.messaging import headers as headers_mod
# import pytest

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
