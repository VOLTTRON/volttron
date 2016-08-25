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
    }
}

offset = timedelta(seconds=3)

# Don't like declaring this global but I am not able to find a way
# to introspect this using pytest request object in the clean fixture
data_table = 'data'
topics_table = 'topics'
meta_table = 'meta'
mongo_client = None
agg_topics_table = 'aggregate_topics'
agg_meta_table = 'aggregate_meta'


def mongo_connection_string():
    mongo_conn_str = 'mongodb://{user}:{passwd}@{host}:{port}/{database}'
    params = mongo_aggregator['connection']['params']
    mongo_conn_str = mongo_conn_str.format(**params)
    return mongo_conn_str


pymongo_mark = pytest.mark.skipif(not HAS_PYMONGO,
                                  reason='No pymongo client available.')

# Don't like declaring this global but I am not able to find a way
# to introspect this using pytest request object in the clean fixture
truncate_collections = []


@pytest.fixture()
def cleanup(request):
    print('connecting to mongo database')
    cleanup_parameters = []

    def cleanup():
        global mongo_aggregator, mongo_client, truncate_collections
        db = mongo_client[mongo_aggregator['connection']['params']['database']]
        for collection in truncate_collections:
            db[collection].remove()
        for collection in cleanup_parameters:
            db[collection].remove()

    request.addfinalizer(cleanup)
    return cleanup_parameters


@pytest.fixture(scope="module")
def publish_agent(request, volttron_instance):
    # 1: Start a fake fake_agent to query the sqlhistorian in volttron_instance
    fake_agent = volttron_instance.build_agent()

    # 2: add a tear down method to stop sqlhistorian fake_agent and the fake
    # fake_agent that published to message bus
    def stop_agent():
        print("In teardown method of fake_agent")
        fake_agent.core.stop()

    request.addfinalizer(stop_agent)
    return fake_agent


# Fixtures for setup and teardown of sqlhistorian agent and aggregation agent
@pytest.fixture(scope="module",
                params=[
                    pymongo_mark(mongo_aggregator)
                ])
def aggregate_agent(request, volttron_instance):
    global data_table, \
        topics_table, meta_table, mongo_client, truncate_collections
    print("** Setting up test_sqlhistorian module **")

    # figure out db table names from config
    # Set this hear so that we can create these table after connecting to db
    if request.param.get('tables_def', None) is None:
        data_table = 'data'
        topics_table = 'topics'
        meta_table = 'meta'
        agg_topics_table = 'aggregate_topics'
        agg_meta_table = 'aggregate_meta'
    elif request.param['tables_def']['table_prefix']:
        data_table = request.param['tables_def']['table_prefix'] + "_" + \
                     request.param['tables_def']['data_table']
        topics_table = request.param['tables_def']['table_prefix'] + "_" + \
                       request.param['tables_def']['topics_table']
        meta_table = request.param['tables_def']['table_prefix'] + "_" + \
                     request.param['tables_def']['meta_table']
        agg_topics_table = request.param['tables_def']['table_prefix'] + \
                           "_" + \
                           "aggregate_" + \
                           request.param['tables_def']['topics_table']
        agg_meta_table = request.param['tables_def']['table_prefix'] + "_" + \
                         "aggregate_" + \
                         request.param['tables_def']['meta_table']
    else:
        data_table = request.param['tables_def']['data_table']
        topics_table = request.param['tables_def']['topics_table']
        meta_table = request.param['tables_def']['meta_table']
        agg_topics_table = "aggregate_" + \
                           request.param['tables_def']['topics_table']
        agg_meta_table = "aggregate_" + \
                         request.param['tables_def']['meta_table']

    truncate_collections = [data_table]

    # 2. Install agents - mongohistorian, mongoaggregatehistorian
    config = dict()
    config['agentid'] = 'mongo_historian'
    config['identity'] = 'platform.historian'
    config['connection'] = request.param['connection']
    config['tables_def'] = request.param.get('tables_def', None)

    mongo_historian_uuid = volttron_instance.install_agent(
        agent_dir="services/core/MongodbHistorian",
        config_file=config,
        vip_identity='platform.historian',
        start=True)
    print("agent id: ", mongo_historian_uuid)

    mongo_client = pymongo.MongoClient(mongo_connection_string())

    # 3: add a tear down method to stop sqlhistorian agent and the fake
    # agent that published to message bus
    def stop_agent():
        print("In teardown method of aggregate agent")
        if volttron_instance.is_running():
            volttron_instance.remove_agent(mongo_historian_uuid)

    request.addfinalizer(stop_agent)
    return request.param


def publish_test_data(publish_agent, start_time, start_reading, count):
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
        publish_agent.vip.pubsub.publish(
            'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)
        reading += 1
        time = time + timedelta(minutes=1)



@pytest.mark.mongo_aggregator
@pytest.mark.aggregator
def test_single_topic(volttron_instance, aggregate_agent, publish_agent,
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
    publish_test_data(publish_agent, start_time, 0, 5)
    gevent.sleep(0.5)
    agent_uuid = None
    try:
        aggregate_agent['aggregations'] = [
            {"aggregation_period": "2m",
             "use_calendar_time_periods": True,
             "points": [
                 {
                     "topic_names": ["Building/LAB/Device/MixedAirTemperature"],
                     "aggregation_type": "sum",
                     "min_count": 2
                 },
                 {
                     "topic_names": ["Building/LAB/Device/OutsideAirTemperature"],
                     "aggregation_type": "sum",
                     "min_count": 2
                 }
             ]
             },
            {"aggregation_period": "3m",
             "use_calendar_time_periods": False,
             "points": [
                 {
                     "topic_names": ["Building/LAB/Device/MixedAirTemperature"],
                     "aggregation_type": "sum",
                     "min_count": 2
                 },
                 {
                     "topic_names": ["Building/LAB/Device/OutsideAirTemperature"],
                     "aggregation_type": "sum",
                     "min_count": 2
                 }
             ]
             }
        ]
        agent_uuid = volttron_instance.install_agent(
            agent_dir="services/core/MongodbAggregateHistorian",
            config_file=aggregate_agent,
            start=True)
        print("agent id: ", agent_uuid)
        gevent.sleep(4 * 60)  # sleep till we see two rows in aggregate table
        #gevent.sleep(60)
        result1 = publish_agent.vip.rpc.call('platform.historian',
                                             'query',
                                             topic=query_points['mixed_point'],
                                             agg_type='sum',
                                             agg_period='2m',
                                             count=20,
                                             order="FIRST_TO_LAST").get(
            timeout=100)

        print(result1)
        assert (result1['values'][0][1] == 3.0)
        assert (result1['values'][1][1] == 7.0)

        result2 = publish_agent.vip.rpc.call('platform.historian',
                                             'query',
                                             topic=query_points['oat_point'],
                                             agg_type='sum',
                                             agg_period='2m',
                                             count=20,
                                             order="FIRST_TO_LAST").get(
            timeout=100)
        assert (result2['values'][0][1] == 3.0)
        assert (result2['values'][1][1] == 7.0)

        # point1 and point2 configured within the same aggregation group should
        # be time synchronized
        assert (result2['values'][0][0] == result1['values'][0][0])
        assert (result2['values'][1][0] == result1['values'][1][0])

        result = publish_agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic=query_points['oat_point'],
            agg_type='sum',
            agg_period='3m',
            count=20,
            order="FIRST_TO_LAST").get(timeout=100)
        assert (result['values'][0][1] == 3.0)
        assert (result['values'][1][1] == 7.0)

        result = publish_agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic=query_points['mixed_point'],
            agg_type='sum',
            agg_period='3m',
            count=20,
            order="FIRST_TO_LAST").get(timeout=100)

        assert (result['values'][0][1] == 3.0)
        assert (result['values'][1][1] == 7.0)
    finally:
        cleanup.append("sum_2m")
        cleanup.append("sum_3m")
        if agent_uuid is not None:
            volttron_instance.remove_agent(agent_uuid)


@pytest.mark.mongo_aggregator
@pytest.mark.aggregator
def test_single_topic_pattern(volttron_instance, aggregate_agent,
                              publish_agent, cleanup):
    """
    Test the basic functionality of mongo historian.
    1. Publish fake data
    2. Start aggregator agent with configurtion to collect sum of data based
    on topic name pattern that would match a single topic.
    3. Sleep for 1 minutes
    4. Do an rpc call to historian to verify data
    @param volttron_instance: volttron instance on which test agents are
    installed and run
    @param aggregate_agent: the aggregate historian being test
    @param fake_agent: fake agent used to publish and query historian
    @param cleanup: fixture to clean up db records after test
    """
    # Publish fake data.
    start_time = datetime.utcnow() - timedelta(minutes=2)
    publish_test_data(publish_agent, start_time, 0, 5)
    gevent.sleep(0.5)
    agent_uuid = None
    try:
        aggregate_agent['aggregations'] = [
            {"aggregation_period": "2m",
             "use_calendar_time_periods": True,
             "points": [
                 {
                     "topic_name_pattern": "Building/LAB/Device/MixedAir.*",
                     "aggregation_topic_name":
                         "Building/LAB/Device/mixedairtemp_aggregate",
                     "aggregation_type": "sum",
                     "min_count": 2
                 },
                 {
                     "topic_name_pattern":
                         "Building/LAB/Device/Outside.*Temperature",
                     "aggregation_topic_name":
                         "Building/LAB/Device/outtemp_aggregate",
                     "aggregation_type": "sum",
                     "min_count": 2
                 }
             ]
             }
        ]
        agent_uuid = volttron_instance.install_agent(
            agent_dir="services/core/MongodbAggregateHistorian",
            config_file=aggregate_agent,
            start=True)
        print("agent id: ", agent_uuid)
        gevent.sleep(30)  # sleep till we see two rows in aggregate table

        result1 = publish_agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic="Building/LAB/Device/mixedairtemp_aggregate",
            agg_type='sum',
            agg_period='2m',
            count=20,
            order="FIRST_TO_LAST").get(timeout=100)

        print(result1)
        assert (result1['values'][0][1] == 3.0)
        # assert (result1['metadata']) == \
        #     {'units': 'F', 'tz': 'UTC', 'type': 'float'}

        result2 = publish_agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic="Building/LAB/Device/outtemp_aggregate",
            agg_type='sum',
            agg_period='2m',
            count=20,
            order="FIRST_TO_LAST").get(timeout=100)
        assert (result2['values'][0][1] == 3.0)

        # point1 and point2 configured within the same aggregation group should
        # be time synchronized
        assert (result2['values'][0][0] == result1['values'][0][0])

    finally:
        cleanup.append("sum_2m")
        if agent_uuid is not None:
            volttron_instance.remove_agent(agent_uuid)



@pytest.mark.mongo_aggregator
@pytest.mark.aggregator
def test_multi_topic_pattern(volttron_instance, aggregate_agent,
                             publish_agent, cleanup):
    """
    Test the basic functionality of mongo historian.
    1. Publish fake data
    2. Start aggregator agent with configurtion to collect sum of data based
    on topic name pattern that would match a single topic.
    3. Sleep for 1 minutes
    4. Do an rpc call to historian to verify data
    @param volttron_instance: volttron instance on which test agents are
    installed and run
    @param aggregate_agent: the aggregate historian being test
    @param fake_agent: fake agent used to publish and query historian
    @param cleanup: fixture to clean up db records after test
    """
    # Publish fake data.
    start_time = datetime.utcnow() - timedelta(minutes=2)
    publish_test_data(publish_agent, start_time, 0, 5)
    gevent.sleep(0.5)
    agent_uuid = None
    try:
        aggregate_agent['aggregations'] = [
            {"aggregation_period": "2m",
             "use_calendar_time_periods": True,
             "points": [
                 {
                     "topic_name_pattern": "Building/LAB/Device/.*",
                     "aggregation_topic_name":
                         "Building/LAB/Device/all",
                     "aggregation_type": "sum",
                     "min_count": 2
                 }
             ]
             }
        ]
        agent_uuid = volttron_instance.install_agent(
            agent_dir="services/core/MongodbAggregateHistorian",
            config_file=aggregate_agent,
            start=True)
        print("agent id: ", agent_uuid)
        gevent.sleep(30)  # sleep till we see two rows in aggregate table

        result1 = publish_agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic="Building/LAB/Device/all",
            agg_type='sum',
            agg_period='2m',
            count=20,
            order="FIRST_TO_LAST").get(timeout=100)

        print(result1)
        assert (result1['values'][0][1] == 6.0)
        # assert (result1['metadata']) == \
        #     {'units': 'F', 'tz': 'UTC', 'type': 'float'}

    finally:
        cleanup.append("sum_2m")
        if agent_uuid is not None:
            volttron_instance.remove_agent(agent_uuid)


@pytest.mark.mongo_aggregator
@pytest.mark.aggregator
def test_multi_topic_list(volttron_instance, aggregate_agent,
                          publish_agent, cleanup):
    """
    Test the basic functionality of mongo historian.
    1. Publish fake data
    2. Start aggregator agent with configurtion to collect sum of data based
    on topic name pattern that would match a single topic.
    3. Sleep for 1 minutes
    4. Do an rpc call to historian to verify data
    @param volttron_instance: volttron instance on which test agents are
    installed and run
    @param aggregate_agent: the aggregate historian being test
    @param fake_agent: fake agent used to publish and query historian
    @param cleanup: fixture to clean up db records after test
    """
    # Publish fake data.
    start_time = datetime.utcnow() - timedelta(minutes=2)
    publish_test_data(publish_agent, start_time, 0, 5)
    gevent.sleep(0.5)
    agent_uuid = None
    try:
        aggregate_agent['aggregations'] = [
            {"aggregation_period": "2m",
             "use_calendar_time_periods": True,
             "points": [
                 {
                     "topic_names":
                         ["Building/LAB/Device/OutsideAirTemperature",
                          "Building/LAB/Device/MixedAirTemperature"],
                     "aggregation_topic_name":
                         "Building/LAB/Device/all",
                     "aggregation_type": "sum",
                     "min_count": 2
                 }
             ]
             }
        ]
        agent_uuid = volttron_instance.install_agent(
            agent_dir="services/core/MongodbAggregateHistorian",
            config_file=aggregate_agent,
            start=True)
        print("agent id: ", agent_uuid)
        gevent.sleep(30)  # sleep till we see two rows in aggregate table

        result1 = publish_agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic="Building/LAB/Device/all",
            agg_type='sum',
            agg_period='2m',
            count=20,
            order="FIRST_TO_LAST").get(timeout=100)

        print(result1)
        assert (result1['values'][0][1] == 6.0)
        # assert (result1['metadata']) == \
        #     {'units': 'F', 'tz': 'UTC', 'type': 'float'}

    finally:
        cleanup.append("sum_2m")
        if agent_uuid is not None:
            volttron_instance.remove_agent(agent_uuid)
