# pytest test cases for SQLHistorian
# For mysql test's to succeed
# 1. MySql server should be running
# 2. test database and test user should exist
# 3. Test user should have all privileges on test database
# 4. Refer to the dictionary object mysql_platform for the server configuration
from datetime import datetime, timedelta

import gevent
import pytest
from volttron.platform.agent.utils import format_timestamp
from volttron.platform.messaging import headers as headers_mod

try:
    import pymongo

    HAS_PYMONGO = True
except:
    HAS_PYMONGO = False

query_points = {
    "oat_point": "Building/LAB/Device/OutsideAirTemperature",
    "mixed_point": "Building/LAB/Device/MixedAirTemperature"
}

# Module level variables
BASE_DEVICE_TOPIC = "devices/Building/LAB/Device"
ALL_TOPIC = "{}/all".format(BASE_DEVICE_TOPIC)

mongo_aggregator = {
    "agentid": "mongodb-historian",
    "identity": "platform.historian",
    "connection": {
        "type": "mongodb",
        "params": {
            "host": "localhost",
            "port": 27017,
            "database": "mongo_test",
            "user": "test",
            "passwd": "test"
        }
    },
    "aggregations": [
        {"aggregation_period": "2m",
         "use_calendar_time_periods": True,
         "points": [
             {
                 "topic_name": "Building/LAB/Device/MixedAirTemperature",
                 "aggregation_type": "sum",
                 "min_count": 2
             },
             {
                 "topic_name": "Building/LAB/Device/OutsideAirTemperature",
                 "aggregation_type": "sum",
                 "min_count": 2
             }
         ]
         },
        {"aggregation_period": "3m",
         "use_calendar_time_periods": False,
         "points": [
             {
                 "topic_name": "Building/LAB/Device/MixedAirTemperature",
                 "aggregation_type": "sum",
                 "min_count": 2
             },
             {
                 "topic_name": "Building/LAB/Device/OutsideAirTemperature",
                 "aggregation_type": "sum",
                 "min_count": 2
             }
         ]
         }
    ]
}

offset = timedelta(seconds=3)

# Don't like declaring this global but I am not able to find a way
# to introspect this using pytest request object in the clean fixture
data_table = 'data'
topics_table = 'topics'
meta_table = 'meta'
mongo_client = None


def mongo_connection_string():
    mongo_conn_str = 'mongodb://{user}:{passwd}@{host}:{port}/{database}'
    params = mongo_aggregator['connection']['params']
    mongo_conn_str = mongo_conn_str.format(**params)
    return mongo_conn_str


pymongo_mark = pytest.mark.skipif(not HAS_PYMONGO,
                                  reason='No pymongo client available.')


@pytest.fixture()
def cleanup(request):
    print('connecting to mongo database')

    def cleanup():
        global mongo_aggregator, mongo_client
        db = mongo_client[mongo_aggregator['connection']['params']['database']]
        db[data_table].remove()
        db[topics_table].remove()
        db["sum_3m"].remove()
        db["sum_2m"].remove()

    request.addfinalizer(cleanup)


@pytest.fixture(scope="module")
def fake_agent(request, volttron_instance):
    # 1: Start a fake agent to query the sqlhistorian in volttron_instance2
    agent = volttron_instance.build_agent()

    # 2: add a tear down method to stop sqlhistorian agent and the fake
    # agent that published to message bus
    def stop_agent():
        print("In teardown method of query_agent")
        agent.core.stop()

    request.addfinalizer(stop_agent)
    return agent


# Fixtures for setup and teardown of sqlhistorian agent and aggregation agent
@pytest.fixture(scope="module",
                params=[
                    pymongo_mark(mongo_aggregator)
                ])
def aggregate_agent(request, volttron_instance):
    global data_table, \
        topics_table, meta_table, mongo_aggregator, mongo_client
    print("** Setting up test_sqlhistorian module **")

    # figure out db table names from config
    # Set this hear so that we can create these table after connecting to db
    if mongo_aggregator.get('tables_def', None) is None:
        data_table = 'data'
        topics_table = 'topics'
        meta_table = 'meta'
    elif mongo_aggregator['tables_def']['table_prefix']:
        data_table = mongo_aggregator['tables_def']['table_prefix'] + "_" + \
            mongo_aggregator['tables_def']['data_table']
        topics_table = mongo_aggregator['tables_def']['table_prefix'] + "_" + \
            mongo_aggregator['tables_def']['topics_table']
        meta_table = mongo_aggregator['tables_def']['table_prefix'] + "_" + \
            mongo_aggregator['tables_def']['meta_table']
    else:
        data_table = mongo_aggregator['tables_def']['data_table']
        topics_table = mongo_aggregator['tables_def']['topics_table']
        meta_table = mongo_aggregator['tables_def']['meta_table']

    # 2. Install agents - mongohistorian, mongoaggregatehistorian
    config = dict()
    config['agentid'] = 'mongo_historian'
    config['identity'] = 'platform.historian'
    config['connection'] = mongo_aggregator['connection']
    config['tables_def'] = mongo_aggregator.get('tables_def', None)

    mongo_historian_uuid = volttron_instance.install_agent(
        agent_dir="services/core/MongodbHistorian",
        config_file=config,
        start=True)
    print("agent id: ", mongo_historian_uuid)

    agent_uuid = volttron_instance.install_agent(
        agent_dir="services/core/MongoAggregateHistorian",
        config_file=mongo_aggregator,
        start=False)
    print("agent id: ", agent_uuid)

    mongo_client = pymongo.MongoClient(mongo_connection_string())

    # 3: add a tear down method to stop sqlhistorian agent and the fake
    # agent that published to message bus
    def stop_agent():
        print("In teardown method of aggregate agent")
        if volttron_instance.is_running():
            volttron_instance.remove_agent(agent_uuid)
            volttron_instance.remove_agent(mongo_historian_uuid)

    request.addfinalizer(stop_agent)
    return agent_uuid


def publish_test_data(start_time, start_reading, count, fake_agent):
    global data_table

    reading = start_reading
    time = start_time
    print ("publishing test data starttime is {} utcnow is {}".format(
        start_time, datetime.utcnow()))
    print ("publishing test data value string {} at {}".format(reading,
                                                               datetime.now()))
    for i in range(0, count):
        headers = {
            headers_mod.DATE: format_timestamp(time)
        }
        all_message = [{
            'OutsideAirTemperature': reading,
            'MixedAirTemperature': reading,
        },
            {'OutsideAirTemperature':
                {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                'MixedAirTemperature': {'units': 'F', 'tz': 'UTC',
                                     'type': 'float'}
             }]
        # Publish messages
        fake_agent.vip.pubsub.publish(
            'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)
        reading += 1
        time = time + timedelta(minutes=1)


@pytest.mark.dev
@pytest.mark.aggregator
def test_basic_function(volttron_instance, aggregate_agent, fake_agent,
                        cleanup):
    """
    Test the basic functionality of mongo historian.
    1. Publish fake data
    2. Start aggregator agent with configurtion to collect sum of data in
    two different intervals.
    3. Sleep for 4 minutes
    4. Do an rpc call to historian to verify data
    @param volttron_instance: volttron instance on which test agents are
    installed and run
    @param aggregate_agent: the aggregate historian being test
    @param fake_agent: fake agent used to publish and query historian
    @param cleanup: fixture to clean up db records after test
    """

    # Publish fake data.
    start_time = datetime.utcnow() - timedelta(minutes=2)
    publish_test_data(start_time, 0, 5, fake_agent)
    gevent.sleep(0.5)
    volttron_instance.start_agent(aggregate_agent)
    # gevent.sleep(2)
    gevent.sleep(4 * 60)  # sleep till we see two rows in aggregate table

    result = fake_agent.vip.rpc.call('platform.historian',
                                     'query',
                                     topic=query_points['mixed_point'],
                                     agg_type='sum',
                                     agg_period='2m',
                                     count=20,
                                     order="FIRST_TO_LAST").get(timeout=100)

    print(result)
    assert (result['values'][0][1] == 3.0)
    assert (result['values'][1][1] == 7.0)

    result = fake_agent.vip.rpc.call('platform.historian',
                                     'query',
                                     topic=query_points['oat_point'],
                                     agg_type='sum',
                                     agg_period='2m',
                                     count=20,
                                     order="FIRST_TO_LAST").get(timeout=100)
    assert (result['values'][0][1] == 3.0)
    assert (result['values'][1][1] == 7.0)

    result = fake_agent.vip.rpc.call('platform.historian',
                                     'query',
                                     topic=query_points['oat_point'],
                                     agg_type='sum',
                                     agg_period='3m',
                                     count=20,
                                     order="FIRST_TO_LAST").get(timeout=100)
    assert (result['values'][0][1] == 3.0)
    assert (result['values'][1][1] == 7.0)

    result = fake_agent.vip.rpc.call('platform.historian',
                                     'query',
                                     topic=query_points['mixed_point'],
                                     agg_type='sum',
                                     agg_period='3m',
                                     count=20,
                                     order="FIRST_TO_LAST").get(timeout=100)

    assert (result['values'][0][1] == 3.0)
    assert (result['values'][1][1] == 7.0)
