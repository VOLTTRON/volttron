# Example file using the weather agent.
#
# Requirements
#    - A VOLTTRON instance must be started
#    - A weatheragnet must be running prior to running this code.
#
# Author: Craig Allwardt
import pytest
import sqlite3
import gevent
import random
from volttron.platform.messaging import headers as headers_mod
from datetime import datetime
from volttron.platform.agent.utils import (get_aware_utc_now,
    format_timestamp)
from dateutil import parser as dateparser

try:
    import pymongo

    HAS_PYMONGO = True
except:
    HAS_PYMONGO = False

from fixtures import (ALL_TOPIC, BASE_ANALYSIS_TOPIC, BASE_DEVICE_TOPIC, mongo_connection_params, mongo_agent_config,
                      mongo_connection_string)

query_points = {
    "oat_point": "Building/LAB/Device/OutsideAirTemperature",
    "mixed_point": "Building/LAB/Device/MixedAirTemperature",
    "damper_point": "Building/LAB/Device/DamperSignal"
}


def clean_db(client):
    db = client[mongo_connection_params()['database']]
    db['data'].drop()
    db['topics'].drop()


# Create a mark for use within params of a fixture.
pymongo_mark = pytest.mark.skipif(not HAS_PYMONGO,
                                  reason='No pymongo client available.')

CLEANUP_CLIENT = True


@pytest.fixture(scope="function",
                params=[
                    pymongo_mark(mongo_agent_config)
                ])
def database_client(request):
    print('connecting to mongo database')
    client = pymongo.MongoClient(mongo_connection_string())

    def close_client():
        if CLEANUP_CLIENT:
            print('cleansing mongodb')
            clean_db(client)

        if client is not None:
            client.close()

    request.addfinalizer(close_client)
    return client


def install_historian_agent(volttron_instance, config_file):
    agent_uuid = volttron_instance.install_agent(
            agent_dir="services/core/MongodbHistorian",
            config_file=config_file,
            start=True,
            vip_identity="platform.historian")
    return agent_uuid


#
# # Fixtures for setup and teardown
# @pytest.fixture(scope="module",
#     params=[
#         pymongo_mark(mongo_platform)
#     ])
# def mongohistorian(request, volttron_instance):
#
#     print("** Setting up test_mongohistorian module **")
#     # Make database connection
#     print("request param", request.param)
#
#     # 1: Install historian agent
#     # Install and start mongohistorian agent
#     agent_uuid = install_historian_agent(volttron_instance, request.param)
#     print("agent id: ", agent_uuid)
#
#     # 4: add a tear down method to stop mongohistorian agent and the fake agent that published to message bus
#     def stop_agent():
#         print("In teardown method of module")
#         if db_connection:
#             db_connection.close()
#             print("closed connection to db")
#
#         volttron_instance.stop_agent(agent_uuid)
#         #volttron_instance.remove_agent(agent_uuid)
#
#         publisher.core.stop()
#
#     request.addfinalizer(stop_agent)
#     return request.param

def database_name(request):
    return request.params['connection']['params']['database']


@pytest.mark.historian
@pytest.mark.mongodb
@pytest.mark.skipif(not HAS_PYMONGO, reason='No pymongo driver')
def test_can_connect(database_client):
    ''' Tests whether we can connect to the mongo database at all.

    Test that we can read/write data on the database while we are at it.  This
    test assumes that the same information that is used in the mongodbhistorian
    will be able to used in this test.
    '''
    db = database_client[mongo_connection_params()['database']]
    result = db.test.insert_one({'x': 1})
    assert result > 0
    result = db.test.insert_one({'here': 'Data to search on'})
    assert result > 0

    result = db.test.find_one({'x': 1})
    assert result['x'] == 1
    result = db.test.find_one({'here': 'Data to search on'})
    assert result['here'] == 'Data to search on'
    assert db.test.remove()
    assert db.test.find().count() == 0


# @pytest.mark.historian
# @pytest.mark.mongodb
# def test_agent_publish_and_query(request, volttron_instance, mongo_config,
#     database_client):
#     ''' Test the normal operation of the MongodbHistorian agent.
#
#     This test will publish some data on the message bus and determine if it
#     was written and can be queried back.
#     '''
#     clean_db(database_client)
#
#     # Install the historian agent (after this call the agent should be running
#     # on the platform).
#     agent_uuid = install_historian_agent(volttron_instance, mongo_config)
#     assert agent_uuid is not None
#     assert volttron_instance.is_agent_running(agent_uuid)
#
#     # Create a publisher and publish to the message bus some fake data.  Keep
#     # track of the published data so that we can query the historian.
#     publisher = volttron_instance.build_agent()
#     assert publisher is not None
#     expected = publish_fake_data(publisher)
#
#     # Query the historian
#     for qp in query_points.keys():
#         print("POINT {}".format(qp))
#         result = publisher.vip.rpc.call('platform.historian',
#                                     'query',
#                                     topic=query_points[qp],
#                                     count=20,
#                                     order="LAST_TO_FIRST").get(timeout=100)
#         print("RESULT ", result)
#         assert expected['datetime'] == result['values'][0][0]
#         assert expected[qp] == result['values'][0][1]
#
#     publisher.core.stop()
#     if agent_uuid is not None:
#         volttron_instance.remove_agent(agent_uuid)

@pytest.mark.historian
@pytest.mark.mongodb
@pytest.mark.skipif(not HAS_PYMONGO, reason='No pymongo driver')
def test_two_hours_of_publishing(request, volttron_instance, database_client):
    clean_db(database_client)
    # Install the historian agent (after this call the agent should be running
    # on the platform).
    agent_uuid = install_historian_agent(volttron_instance, mongo_agent_config())


    assert agent_uuid is not None
    assert volttron_instance.is_agent_running(agent_uuid)

    try:

        # Create a publisher and publish to the message bus some fake data.  Keep
        # track of the published data so that we can query the historian.
        publisher = volttron_instance.build_agent()
        assert publisher is not None
        expected = publish_minute_data_for_two_hours(publisher)

        # The mongo historian now should have published 2 hours worth of data.
        # Based upon the structure that we expect the database to be in we should
        # now have 3 topics present in the database and 2 records for each of the
        # 3 data items.
        db = database_client.get_default_database()

        assert 3 == db.topics.find().count()

        topic_to_id = {}
        for row in db.topics.find():
            topic_to_id[row['topic_name']] = row['_id']

        gevent.sleep(0.5)
        for d, v in expected.items():
            print('d, v: ({}, {})'.format(d,v))
            assert db['data'].find({'ts': d}).count() == 3

            for t, _id in topic_to_id.items():
                value = db['data'].find_one({'ts': d, 'topic_id': _id})['value']
                assert value == v[t]
    finally:
        volttron_instance.stop_agent(agent_uuid)
        volttron_instance.remove_agent(agent_uuid)

def publish_minute_data_for_two_hours(agent):
    now = get_aware_utc_now()
    # expection[datetime]={oat:b,mixed:c,damper:d}
    expectation = {}

    for h in xrange(2):
        data_by_time = {}

        for m in xrange(60):
            # Because timestamps in mongo are only concerned with the first
            #  three digits after the decimal we do this to give some
            # randomness here.
            micro = str(random.randint(0, 999999))

            now = datetime(now.year, now.month, now.day, h, m,
                           random.randint(0, 59), int(micro))
            # Make some random readings
            oat_reading = random.uniform(30, 100)
            mixed_reading = oat_reading + random.uniform(-5, 5)
            damper_reading = random.uniform(0, 100)

            # Create a message for all points.
            all_message = [{
                'OutsideAirTemperature': oat_reading,
                'MixedAirTemperature': mixed_reading,
                'DamperSignal': damper_reading},
                {'OutsideAirTemperature':
                     {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                 'MixedAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                 'DamperSignal': {'units': '%', 'tz': 'UTC', 'type': 'float'}
                 }]

            now_iso_string = format_timestamp(now)
            data_by_time[now_iso_string] = {
                "oat_point": oat_reading,
                "mixed_point": mixed_reading,
                "damper_point": damper_reading
            }

            # now = '2015-12-02T00:00:00'
            headers = {
                headers_mod.DATE: now_iso_string
            }

            # Publish messages
            agent.vip.pubsub.publish(
                    'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)

            expectation[now] = {
                query_points['oat_point']: oat_reading,
                query_points['mixed_point']: mixed_reading,
                query_points['damper_point']: damper_reading
            }
    gevent.sleep(0.1)
    return expectation


def publish_fake_data(agent):
    '''
    Publishes an all message to the passed instances of volttron's message bus.

    The format mimics the format used by VOLTTRON drivers. Uses the passed
    agent's vip pubsub to publish an all message.

    returns a dictionary of random readings
        {
            "datetime": isoformatted string,
            "oat_reading": number,
            "mixed_reading": number,
            "damper_reading": number
        }
    '''

    except_all = ALL_TOPIC[:ALL_TOPIC.rindex('/')]

    # Make some random readings
    oat_reading = random.uniform(30, 100)
    mixed_reading = oat_reading + random.uniform(-5, 5)
    damper_reading = random.uniform(0, 100)

    # Create a message for all points.
    all_message = [{'OutsideAirTemperature': oat_reading, 'MixedAirTemperature': mixed_reading,
                    'DamperSignal': damper_reading},
                   {'OutsideAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                    'MixedAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'},
                    'DamperSignal': {'units': '%', 'tz': 'UTC', 'type': 'float'}
                    }]

    # Create timestamp (no parameter to isoformat so the result is a T
    # separator) The now value is a string after this function is called.
    now = datetime.utcnow()
    # now = now.replace(microsecond=random.randint(0,100))
    # now = datetime(now.year, now.month, now.day, now.hour,
    #     now.minute, now.second)
    # now = now.isoformat()
    print('NOW IS: ', now)

    # now = '2015-12-02T00:00:00'
    headers = {
        headers_mod.DATE: now.isoformat()
    }

    # Publish messages
    agent.vip.pubsub.publish(
            'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)

    # The keys for these should be the exact same that are in the query_points
    # dictionary.
    return {
        "datetime": now,
        "oat_point": oat_reading,
        "mixed_point": mixed_reading,
        "damper_point": damper_reading
    }

@pytest.mark.historian
@pytest.mark.mongodb
@pytest.mark.skipif(not HAS_PYMONGO, reason='No pymongo driver')
def test_insert_duplicate(volttron_instance, database_client):
    clean_db(database_client)
    data_collection = database_client.get_default_database()['data']
    index_model = pymongo.IndexModel([("topic_id", pymongo.DESCENDING),
                                      ("ts", pymongo.DESCENDING)],
                                     unique=True)
    # make sure the data collection has the unique constraint.
    data_collection.create_indexes([index_model])
    # Install the historian agent (after this call the agent should be running
    # on the platform).
    agent_uuid = install_historian_agent(volttron_instance, mongo_agent_config())
    assert agent_uuid is not None
    assert volttron_instance.is_agent_running(agent_uuid)

    try:

        oat_reading = random.uniform(30, 100)
        all_message = [{'OutsideAirTemperature': oat_reading},
                       {'OutsideAirTemperature':
                         {'units': 'F', 'tz': 'UTC', 'type': 'float'}}]

        publisher = volttron_instance.build_agent()
        # Create timestamp (no parameter to isoformat so the result is a T
        # separator) The now value is a string after this function is called.
        now = get_aware_utc_now()
        # now = now.replace(microsecond=random.randint(0,100))
        # now = datetime(now.year, now.month, now.day, now.hour,
        #     now.minute, now.second)
        # now = now.isoformat()
        print('NOW IS: ', now)

        # now = '2015-12-02T00:00:00'
        headers = {
            headers_mod.DATE: now.isoformat()
        }

        # Publish messages
        publisher.vip.pubsub.publish(
                'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)

        gevent.sleep(0.5)

        publisher.vip.pubsub.publish(
                'pubsub', ALL_TOPIC, headers, all_message).get(timeout=10)

    finally:
        volttron_instance.stop_agent(agent_uuid)
        volttron_instance.remove_agent(agent_uuid)

def publish_data(publisher, topic, message, now=None):
    if now is None:
        now = datetime.now()
    headers = {
        headers_mod.DATE: now.isoformat()
    }

    # Publish messages
    publisher.vip.pubsub.publish(
            'pubsub', topic, headers, message).get(timeout=10)

    gevent.sleep(0.5)
    return now

@pytest.mark.historian
@pytest.mark.mongodb
@pytest.mark.skipif(not HAS_PYMONGO, reason='No pymongo driver')
def test_analysis_topic(volttron_instance, database_client):
    agent_uuid = install_historian_agent(volttron_instance, mongo_agent_config())

    try:
        publisher = volttron_instance.build_agent()
        oat_reading = random.uniform(30, 100)
        message = [{'FluffyWidgets': oat_reading},
                       {'FluffyWidgets':
                         {'units': 'F', 'tz': 'UTC', 'type': 'float'}}]

        publisheddt = publish_data(publisher, BASE_ANALYSIS_TOPIC, message)
        gevent.sleep(0.1)

        lister = volttron_instance.build_agent()
        topic_list = lister.vip.rpc.call('platform.historian', 'get_topic_list').get(timeout=5)
        assert topic_list is not None
        assert len(topic_list) == 1
        assert 'FluffyWidgets' in topic_list[0]

        result = lister.vip.rpc.call('platform.historian',
                                            'query',
                                            topic=BASE_ANALYSIS_TOPIC[9:]+'/FluffyWidgets').get(timeout=5)
        assert result is not None
        assert len(result['values']) == 1
        assert isinstance(result['values'], list)
        mongoizetimestamp = publisheddt.isoformat()[:-3]+'000'
        assert result['values'][0] == [mongoizetimestamp, oat_reading]
    finally:
        volttron_instance.stop_agent(agent_uuid)
        volttron_instance.remove_agent(agent_uuid)


@pytest.mark.historian
@pytest.mark.mongodb
@pytest.mark.skipif(not HAS_PYMONGO, reason='No pymongo driver')
def test_get_topic_map(volttron_instance, database_client):

    agent_uuid = install_historian_agent(volttron_instance, mongo_agent_config())

    try:
        oat_reading = random.uniform(30, 100)
        all_message = [{'OutsideAirTemperature': oat_reading},
                       {'OutsideAirTemperature':
                         {'units': 'F', 'tz': 'UTC', 'type': 'float'}}]

        publisher = volttron_instance.build_agent()
        publisheddt = publish_data(publisher, ALL_TOPIC, all_message)

        db = database_client.get_default_database()
        assert db.topics.count() == 1

        lister = volttron_instance.build_agent()
        topic_list = lister.vip.rpc.call('platform.historian', 'get_topic_list').get(timeout=5)
        assert topic_list is not None
        assert len(topic_list) == 1

        # Publish data again for the next point.
        publisheddt = publish_data(publisher, ALL_TOPIC, all_message)
        topic_list = lister.vip.rpc.call('platform.historian', 'get_topic_list').get(timeout=5)

        # Same topic shouldn't add anything else.
        assert topic_list is not None
        assert len(topic_list) == 1
        assert topic_list[0] == BASE_DEVICE_TOPIC[8:] + '/OutsideAirTemperature'

        mixed_reading = random.uniform(30, 100)
        all_message = [{'MixedAirTemperature': mixed_reading},
                       {'MixedAirTemperature': {'units': 'F', 'tz': 'UTC', 'type': 'float'}}]

        publisheddt = publish_data(publisher, ALL_TOPIC, all_message)
        topic_list = lister.vip.rpc.call('platform.historian', 'get_topic_list').get(timeout=5)

        assert topic_list is not None
        assert len(topic_list) == 2
    finally:
        volttron_instance.stop_agent(agent_uuid)
        volttron_instance.remove_agent(agent_uuid)






@pytest.mark.historian
@pytest.mark.mongodb
@pytest.mark.skipif(not HAS_PYMONGO, reason='No pymongo driver')
def test_basic_function(volttron_instance, database_client):
    """
    Test basic functionality of sql historian. Inserts three points as part of all topic and checks
    if all three got into the database
    :param volttron_instance: The instance against which the test is run
    """
    global query_points, db_connection

    agent_uuid = install_historian_agent(volttron_instance, mongo_agent_config())

    try:
        # print('HOME', volttron_instance.volttron_home)
        print("\n** test_basic_function **")

        publish_agent = volttron_instance.build_agent()

        # Publish data to message bus that should be recorded in the mongo database.
        expected = publish_fake_data(publish_agent)
        expected = publish_fake_data(publish_agent)
        gevent.sleep(0.5)

        # Query the historian
        result = publish_agent.vip.rpc.call('platform.historian',
                                            'query',
                                            topic=query_points['oat_point'],
                                            count=20,
                                            order="LAST_TO_FIRST").get(timeout=100)
        assert expected['datetime'].isoformat()[:-3] + '000' == result['values'][0][0]
        assert result['values'][0][1] == expected['oat_point']

        result = publish_agent.vip.rpc.call('platform.historian',
                                            'query',
                                            topic=query_points['mixed_point'],
                                            count=20,
                                            order="LAST_TO_FIRST").get(timeout=100)

        assert expected['datetime'].isoformat()[:-3] + '000' == result['values'][0][0]
        assert result['values'][0][1] == expected['mixed_point']

        result = publish_agent.vip.rpc.call('platform.historian',
                                            'query',
                                            topic=query_points['damper_point'],
                                            count=20,
                                            order="LAST_TO_FIRST").get(timeout=100)

        assert expected['datetime'].isoformat()[:-3] + '000' == result['values'][0][0]
        assert result['values'][0][1] == expected['damper_point']
    finally:
        volttron_instance.stop_agent(agent_uuid)
        volttron_instance.remove_agent(agent_uuid)


@pytest.mark.historian
@pytest.mark.mongodb
@pytest.mark.skipif(not HAS_PYMONGO, reason='No pymongo driver')
def test_topic_name_case_change(volttron_instance, database_client):
    """
    When case of a topic name changes check if they are saved as two topics
    Expected result: query result should be cases insensitive
    """
    clean_db(database_client)
    agent_uuid = install_historian_agent(volttron_instance, mongo_agent_config())
    try:
        publisher = volttron_instance.build_agent()
        oat_reading = random.uniform(30, 100)
        message = [{'FluffyWidgets': oat_reading},
                       {'FluffyWidgets':
                         {'units': 'F', 'tz': 'UTC', 'type': 'float'}}]

        publisheddt = publish_data(publisher, BASE_ANALYSIS_TOPIC, message)
        gevent.sleep(0.1)

        lister = volttron_instance.build_agent()
        topic_list = lister.vip.rpc.call('platform.historian', 'get_topic_list').get(timeout=5)
        assert topic_list is not None
        assert len(topic_list) == 1
        assert 'FluffyWidgets' in topic_list[0]

        result = lister.vip.rpc.call('platform.historian',
                                            'query',
                                            topic=BASE_ANALYSIS_TOPIC[9:]+'/FluffyWidgets').get(timeout=5)
        assert result is not None
        assert len(result['values']) == 1
        assert isinstance(result['values'], list)
        mongoizetimestamp = publisheddt.isoformat()[:-3]+'000'

        assert result['values'][0] == [mongoizetimestamp, oat_reading]

        message = [{'Fluffywidgets': oat_reading},
                       {'Fluffywidgets':
                         {'units': 'F', 'tz': 'UTC', 'type': 'float'}}]
        publisheddt = publish_data(publisher,
                                   BASE_ANALYSIS_TOPIC, message)
        gevent.sleep(0.1)
        topic_list = lister.vip.rpc.call('platform.historian', 'get_topic_list').get(timeout=5)
        assert topic_list is not None
        assert len(topic_list) == 1
        assert 'Fluffywidgets' in topic_list[0]

        result = lister.vip.rpc.call(
            'platform.historian',
            'query',
            topic=BASE_ANALYSIS_TOPIC[9:]+'/Fluffywidgets',
            order="LAST_TO_FIRST").get(timeout=5)
        assert result is not None
        assert len(result['values']) == 2
        assert isinstance(result['values'], list)
        mongoizetimestamp = publisheddt.isoformat()[:-3]+'000'
        assert result['values'][0] == [mongoizetimestamp, oat_reading]


    finally:
        volttron_instance.stop_agent(agent_uuid)
        volttron_instance.remove_agent(agent_uuid)


@pytest.mark.historian
@pytest.mark.mongodb
@pytest.mark.skipif(not HAS_PYMONGO, reason='No pymongo driver')
def test_empty_result(volttron_instance, database_client):
    """
    When case of a topic name changes check if they are saved as two topics
    Expected result: query result should be cases insensitive
    """
    agent_uuid = install_historian_agent(volttron_instance, mongo_agent_config())
    try:

        lister = volttron_instance.build_agent()

        result = lister.vip.rpc.call(
            'platform.historian',
            'query',
            topic=BASE_ANALYSIS_TOPIC[9:]+'/FluffyWidgets').get(timeout=5)
        print ("query result:" ,result)
        assert result == {}
    finally:
        volttron_instance.stop_agent(agent_uuid)
        volttron_instance.remove_agent(agent_uuid)
