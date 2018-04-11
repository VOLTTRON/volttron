# Example file using the weather agent.
#
# Requirements
#    - A VOLTTRON instance must be started
#    - A weatheragnet must be running prior to running this code.
#
# Author: Craig Allwardt
import random
from datetime import datetime
from datetime import timedelta

import gevent
import pytest
from dateutil.tz import tzutc

from volttron.platform import get_services_core
from volttron.platform.agent import utils
from volttron.platform.agent.utils import (get_aware_utc_now, format_timestamp)
from volttron.platform.messaging import headers as headers_mod

try:
    import pymongo

    HAS_PYMONGO = True
except:
    HAS_PYMONGO = False

from fixtures import (ALL_TOPIC, BASE_ANALYSIS_TOPIC, BASE_DEVICE_TOPIC,
                      mongo_connection_params, mongo_agent_config,
                      mongo_connection_string)

query_points = {"oat_point": "Building/LAB/Device/OutsideAirTemperature",
                "mixed_point": "Building/LAB/Device/MixedAirTemperature",
                "damper_point": "Building/LAB/Device/DamperSignal"}


def clean_db(client):
    db = client[mongo_connection_params()['database']]
    db['data'].drop()
    db['topics'].drop()


# Create a mark for use within params of a fixture.
pymongo_mark = pytest.mark.skipif(not HAS_PYMONGO,
                                  reason='No pymongo client available.')

CLEANUP_CLIENT = True


@pytest.fixture(scope="function", params=[pymongo_mark(mongo_agent_config)])
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
        agent_dir=get_services_core("MongodbHistorian"), config_file=config_file,
        start=True, vip_identity="platform.historian")
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
#     # 4: add a tear down method to stop mongohistorian agent and the fake
# agent that published to message bus
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
    """ Tests whether we can connect to the mongo database at all.

    Test that we can read/write data on the database while we are at it.  This
    test assumes that the same information that is used in the mongodbhistorian
    will be able to used in this test.
    """
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
#     # Install the historian agent (after this call the agent should be
# running
#     # on the platform).
#     agent_uuid = install_historian_agent(volttron_instance, mongo_config)
#     assert agent_uuid is not None
#     assert volttron_instance.is_agent_running(agent_uuid)
#
#     # Create a publisher and publish to the message bus some fake data.  Keep
#     # track of the published data so that we can query the historian.
#     publisher = volttron_instance.build_agent()
#     assert publisher is not None
#     expected = publish_devices_fake_data(publisher)
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
def test_two_hours_of_publishing(volttron_instance, database_client):
    clean_db(database_client)
    # Install the historian agent (after this call the agent should be running
    # on the platform).
    agent_uuid = install_historian_agent(volttron_instance,
                                         mongo_agent_config())

    assert agent_uuid is not None
    assert volttron_instance.is_agent_running(agent_uuid)

    try:

        # Create a publisher and publish to the message bus some fake data.
        #  Keep
        # track of the published data so that we can query the historian.
        publisher = volttron_instance.build_agent()
        assert publisher is not None
        expected = publish_minute_data_for_two_hours(publisher)

        # The mongo historian now should have published 2 hours worth of data.
        # Based upon the structure that we expect the database to be in we
        # should
        # now have 3 topics present in the database and 2 records for each
        # of the
        # 3 data items.
        db = database_client.get_default_database()

        assert 3 == db.topics.find().count()

        topic_to_id = {}
        for row in db.topics.find():
            topic_to_id[row['topic_name']] = row['_id']

        gevent.sleep(0.5)
        for d, v in expected.items():
            print('d, v: ({}, {})'.format(d, v))
            assert db['data'].find({'ts': d}).count() == 3

            for t, _id in topic_to_id.items():
                value = db['data'].find_one({'ts': d, 'topic_id': _id})[
                    'value']
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
            # Make some random readings. round to 14 digit precision
            # as mongo only store 14 digit precision
            oat_reading = round(random.uniform(30, 100),14)
            mixed_reading = round(oat_reading + random.uniform(-5, 5),14)
            damper_reading = round(random.uniform(0, 100),14)

            # Create a message for all points.
            all_message = [{
                'OutsideAirTemperature': oat_reading,
                'MixedAirTemperature': mixed_reading,
                'DamperSignal': damper_reading},
                {
                'OutsideAirTemperature': {'units': 'F', 'tz': 'UTC',
                                          'type': 'float'},
                'MixedAirTemperature': {'units': 'F', 'tz': 'UTC',
                                        'type': 'float'},
                'DamperSignal': {'units': '%', 'tz': 'UTC', 'type': 'float'}
                }]

            now_iso_string = format_timestamp(now)
            data_by_time[now_iso_string] = {
                "oat_point": oat_reading,
                "mixed_point": mixed_reading,
                "damper_point": damper_reading}

            # now = '2015-12-02T00:00:00'
            headers = {headers_mod.DATE: now_iso_string}

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


def publish_fake_data(agent, now=None, value=None):
    """
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
    """

    except_all = ALL_TOPIC[:ALL_TOPIC.rindex('/')]

    # Make some random readings
    if value:
        oat_reading = value
        mixed_reading = value
        damper_reading = value
    else:
        oat_reading = round(random.uniform(30, 100), 14)
        mixed_reading = round(oat_reading + random.uniform(-5, 5), 14)
        damper_reading = round(random.uniform(0, 100), 14)

    # Create a message for all points.
    all_message = [{'OutsideAirTemperature': oat_reading,
                    'MixedAirTemperature': mixed_reading,
                    'DamperSignal': damper_reading}, {
                       'OutsideAirTemperature': {'units': 'F', 'tz': 'UTC',
                                                 'type': 'float'},
                       'MixedAirTemperature': {'units': 'F', 'tz': 'UTC',
                                               'type': 'float'},
                       'DamperSignal': {'units': '%', 'tz': 'UTC',
                                        'type': 'float'}}]

    # Create timestamp (no parameter to isoformat so the result is a T
    # separator) The now value is a string after this function is called.

    # now = now.replace(microsecond=random.randint(0,100))
    # now = datetime(now.year, now.month, now.day, now.hour,
    #     now.minute, now.second)
    # now = now.isoformat()
    if not now:
        now = datetime.utcnow()
    print('NOW IS: ', now)

    # now = '2015-12-02T00:00:00'
    headers = {headers_mod.DATE: now.isoformat()}

    # Publish messages
    agent.vip.pubsub.publish('pubsub', ALL_TOPIC, headers, all_message).get(
        timeout=10)

    # The keys for these should be the exact same that are in the query_points
    # dictionary.
    return {"datetime": now, "oat_point": oat_reading,
            "mixed_point": mixed_reading, "damper_point": damper_reading}


@pytest.mark.historian
@pytest.mark.mongodb
@pytest.mark.skipif(not HAS_PYMONGO, reason='No pymongo driver')
def test_insert_duplicate(volttron_instance, database_client):
    clean_db(database_client)
    data_collection = database_client.get_default_database()['data']
    index_model = pymongo.IndexModel(
        [("topic_id", pymongo.DESCENDING), ("ts", pymongo.DESCENDING)],
        unique=True)
    # make sure the data collection has the unique constraint.
    data_collection.create_indexes([index_model])
    # Install the historian agent (after this call the agent should be running
    # on the platform).
    agent_uuid = install_historian_agent(volttron_instance,
                                         mongo_agent_config())
    assert agent_uuid is not None
    assert volttron_instance.is_agent_running(agent_uuid)

    try:

        oat_reading = round(random.uniform(30, 100),14)
        all_message = [{'OutsideAirTemperature': oat_reading}, {
            'OutsideAirTemperature': {'units': 'F', 'tz': 'UTC',
                                      'type': 'float'}}]

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
        headers = {headers_mod.DATE: now.isoformat()}

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
    headers = {headers_mod.DATE: now.isoformat()}

    # Publish messages
    publisher.vip.pubsub.publish('pubsub', topic, headers, message).get(
        timeout=10)

    gevent.sleep(0.5)
    return now

@pytest.mark.historian
@pytest.mark.mongodb
@pytest.mark.skipif(not HAS_PYMONGO, reason='No pymongo driver')
def test_analysis_topic(volttron_instance, database_client):
    agent_uuid = install_historian_agent(volttron_instance,
                                         mongo_agent_config())

    try:
        publisher = volttron_instance.build_agent()
        oat_reading = round(random.uniform(30, 100), 14)
        message = [{'FluffyWidgets': oat_reading}, {
            'FluffyWidgets': {'units': 'F', 'tz': 'UTC', 'type': 'float'}}]

        publisheddt = publish_data(publisher, BASE_ANALYSIS_TOPIC, message)
        gevent.sleep(0.1)

        lister = volttron_instance.build_agent()
        topic_list = lister.vip.rpc.call('platform.historian',
                                         'get_topic_list').get(timeout=5)
        assert topic_list is not None
        assert len(topic_list) == 1
        assert 'FluffyWidgets' in topic_list[0]

        result = lister.vip.rpc.call('platform.historian', 'query',
                                     topic=BASE_ANALYSIS_TOPIC[
                                           9:] + '/FluffyWidgets').get(
            timeout=5)
        assert result is not None
        assert len(result['values']) == 1
        assert isinstance(result['values'], list)
        mongoizetimestamp = publisheddt.isoformat()[:-3] + '000+00:00'
        assert result['values'][0] == [mongoizetimestamp, oat_reading]
    finally:
        volttron_instance.stop_agent(agent_uuid)
        volttron_instance.remove_agent(agent_uuid)


@pytest.mark.historian
@pytest.mark.mongodb
@pytest.mark.skipif(not HAS_PYMONGO, reason='No pymongo driver')
def test_get_topic_map(volttron_instance, database_client):
    agent_uuid = install_historian_agent(volttron_instance,
                                         mongo_agent_config())

    try:
        oat_reading = round(random.uniform(30, 100), 14)
        all_message = [{'OutsideAirTemperature': oat_reading}, {
            'OutsideAirTemperature': {'units': 'F', 'tz': 'UTC',
                                      'type': 'float'}}]

        publisher = volttron_instance.build_agent()
        publisheddt = publish_data(publisher, ALL_TOPIC, all_message)

        db = database_client.get_default_database()
        assert db.topics.count() == 1

        lister = volttron_instance.build_agent()
        topic_list = lister.vip.rpc.call('platform.historian',
                                         'get_topic_list').get(timeout=5)
        assert topic_list is not None
        assert len(topic_list) == 1

        # Publish data again for the next point.
        publisheddt = publish_data(publisher, ALL_TOPIC, all_message)
        topic_list = lister.vip.rpc.call('platform.historian',
                                         'get_topic_list').get(timeout=5)

        # Same topic shouldn't add anything else.
        assert topic_list is not None
        assert len(topic_list) == 1
        assert topic_list[0] == BASE_DEVICE_TOPIC[
                                8:] + '/OutsideAirTemperature'

        mixed_reading = round(random.uniform(30, 100), 14)
        all_message = [{'MixedAirTemperature': mixed_reading}, {
            'MixedAirTemperature': {'units': 'F', 'tz': 'UTC',
                                    'type': 'float'}}]

        publisheddt = publish_data(publisher, ALL_TOPIC, all_message)
        topic_list = lister.vip.rpc.call('platform.historian',
                                         'get_topic_list').get(timeout=5)

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
    Test basic functionality of sql historian. Inserts three points as part
    of all topic and checks
    if all three got into the database
    :param database_client:
    :param volttron_instance: The instance against which the test is run
    """
    global query_points

    agent_uuid = install_historian_agent(volttron_instance,
                                         mongo_agent_config())

    try:
        # print('HOME', volttron_instance.volttron_home)
        print("\n** test_basic_function **")

        publish_agent = volttron_instance.build_agent()

        # Publish data to message bus that should be recorded in the mongo
        # database.
        expected = publish_fake_data(publish_agent)
        expected = publish_fake_data(publish_agent)
        gevent.sleep(0.5)

        # Query the historian
        result = publish_agent.vip.rpc.call('platform.historian', 'query',
                                            topic=query_points['oat_point'],
                                            count=20,
                                            order="LAST_TO_FIRST").get(
            timeout=100)
        assert expected['datetime'].isoformat()[:-3] + '000+00:00' == \
            result['values'][0][0]
        assert result['values'][0][1] == expected['oat_point']

        result = publish_agent.vip.rpc.call('platform.historian', 'query',
                                            topic=query_points['mixed_point'],
                                            count=20,
                                            order="LAST_TO_FIRST").get(
            timeout=100)

        assert expected['datetime'].isoformat()[:-3] + '000+00:00' == \
            result['values'][0][0]
        assert result['values'][0][1] == expected['mixed_point']

        result = publish_agent.vip.rpc.call('platform.historian', 'query',
                                            topic=query_points['damper_point'],
                                            count=20,
                                            order="LAST_TO_FIRST").get(
            timeout=100)

        assert expected['datetime'].isoformat()[:-3] + '000+00:00' == \
            result['values'][0][0]
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
    agent_uuid = install_historian_agent(volttron_instance,
                                         mongo_agent_config())
    try:
        publisher = volttron_instance.build_agent()
        oat_reading = round(random.uniform(30, 100), 14)
        message = [{'FluffyWidgets': oat_reading}, {
            'FluffyWidgets': {'units': 'F', 'tz': 'UTC', 'type': 'float'}}]

        publisheddt = publish_data(publisher, BASE_ANALYSIS_TOPIC, message)
        gevent.sleep(0.1)

        lister = volttron_instance.build_agent()
        topic_list = lister.vip.rpc.call('platform.historian',
                                         'get_topic_list').get(timeout=5)
        assert topic_list is not None
        assert len(topic_list) == 1
        assert 'FluffyWidgets' in topic_list[0]

        result = lister.vip.rpc.call('platform.historian', 'query',
                                     topic=BASE_ANALYSIS_TOPIC[
                                           9:] + '/FluffyWidgets').get(
            timeout=5)
        assert result is not None
        assert len(result['values']) == 1
        assert isinstance(result['values'], list)
        mongoizetimestamp = publisheddt.isoformat()[:-3] + '000+00:00'

        assert result['values'][0] == [mongoizetimestamp, oat_reading]

        message = [{'Fluffywidgets': oat_reading}, {
            'Fluffywidgets': {'units': 'F', 'tz': 'UTC', 'type': 'float'}}]
        publisheddt = publish_data(publisher, BASE_ANALYSIS_TOPIC, message)
        gevent.sleep(0.1)
        topic_list = lister.vip.rpc.call('platform.historian',
                                         'get_topic_list').get(timeout=5)
        assert topic_list is not None
        assert len(topic_list) == 1
        assert 'Fluffywidgets' in topic_list[0]

        result = lister.vip.rpc.call(
            'platform.historian', 'query',
            topic=BASE_ANALYSIS_TOPIC[9:] + '/Fluffywidgets',
            order="LAST_TO_FIRST").get(timeout=5)
        assert result is not None
        assert len(result['values']) == 2
        assert isinstance(result['values'], list)
        mongoizetimestamp = publisheddt.isoformat()[:-3] + '000+00:00'
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
    agent_uuid = install_historian_agent(volttron_instance,
                                         mongo_agent_config())
    try:

        lister = volttron_instance.build_agent()

        result = lister.vip.rpc.call(
            'platform.historian', 'query',
            topic=BASE_ANALYSIS_TOPIC[9:] + '/FluffyWidgets').get(timeout=5)
        print ("query result:", result)
        assert result == {}
    finally:
        volttron_instance.stop_agent(agent_uuid)
        volttron_instance.remove_agent(agent_uuid)


@pytest.mark.mongodb
@pytest.mark.skipif(not HAS_PYMONGO, reason='No pymongo driver')
def test_multi_topic(volttron_instance, database_client):
    """
    Test basic functionality of sql historian. Inserts three points as part
    of all topic and checks
    if all three got into the database
    :param database_client:
    :param volttron_instance: The instance against which the test is run
    """
    global query_points

    agent_uuid = install_historian_agent(volttron_instance,
                                         mongo_agent_config())

    try:
        # print('HOME', volttron_instance.volttron_home)
        print("\n** test_basic_function **")

        publish_agent = volttron_instance.build_agent()

        # Publish data to message bus that should be recorded in the mongo
        # database.
        expected_result = {}
        values_dict = {query_points['oat_point']: [],
                       query_points['mixed_point']: []}
        for x in range(0, 5):
            expected = publish_fake_data(publish_agent)
            gevent.sleep(0.5)
            if x < 3:
                values_dict[query_points['oat_point']].append(
                    [expected["datetime"].isoformat()[:-3] + '000+00:00',
                     expected["oat_point"]])
                values_dict[query_points['mixed_point']].append(
                    [expected["datetime"].isoformat()[:-3] + '000+00:00',
                     expected["mixed_point"]])
        expected_result["values"] = values_dict
        expected_result["metadata"] = {}

        # Query the historian
        result = publish_agent.vip.rpc.call(
            'platform.historian', 'query',
            topic=[query_points['mixed_point'], query_points['oat_point']],
            count=3, order="FIRST_TO_LAST").get(timeout=100)

        # print("expected result {}".format(expected_result))
        # print("result {}".format(result))
        assert result["metadata"] == expected_result["metadata"]
        assert result["values"][query_points['mixed_point']] == \
            expected_result["values"][query_points['mixed_point']]
        assert result["values"][query_points['oat_point']] == \
            expected_result["values"][query_points['oat_point']]
    finally:
        volttron_instance.stop_agent(agent_uuid)
        volttron_instance.remove_agent(agent_uuid)

@pytest.mark.historian
@pytest.mark.mongodb
@pytest.mark.skipif(not HAS_PYMONGO, reason='No pymongo driver')
def test_data_rollup_insert(volttron_instance, database_client):
    """
    Test the creation of rolled up data in hourly, daily and monthly data
    tables when data is published for new or existing topics
    :param database_client:
    :param volttron_instance: The instance against which the test is run
    """
    global query_points
    agent_uuid = None
    try:
        # print('HOME', volttron_instance.volttron_home)
        print("\n** test_data_rollup_insert **")

        # Clean data and roll up tables
        db = database_client.get_default_database()
        db['data'].drop()
        db['topics'].drop()
        db['meta'].drop()
        db['hourly_data'].drop()
        db['daily_data'].drop()
        db['monthly_data'].drop()
        gevent.sleep(0.5)
        config = mongo_agent_config()
        config['periodic_rollup_initial_wait'] = 0.1
        config['rollup_query_end'] = 0
        config['periodic_rollup_frequency'] = 2
        agent_uuid = install_historian_agent(volttron_instance, config)

        publish_agent = volttron_instance.build_agent()

        version = publish_agent.vip.rpc.call('platform.historian',
                                   'get_version').get(timeout=5)

        version_nums = version.split(".")
        if int(version_nums[0]) < 2:
            pytest.skip("Only version >= 2.0 support rolled up data.")



        # ###################
        # Initialization test
        # ###################
        # Publish data to message bus that should be
        # recorded in the mongo
        # database. All topics are new
        now = datetime(year=2016, month=03, day=01, hour= 01, minute=01,
                       second=01, microsecond=123, tzinfo=tzutc())
        expected1 = publish_fake_data(publish_agent, now)
        expected2 = publish_fake_data(publish_agent, now + timedelta(
            minutes=1))

        # publish again. this time topic is not new. rolled up data should
        # get append in the array initialized during last publish
        expected3 = publish_fake_data(publish_agent,
                                      now + timedelta(minutes=4))
        gevent.sleep(0.5)
        result = publish_agent.vip.rpc.call('platform.historian', 'query',
            topic=query_points['oat_point'], count=20,
            order="FIRST_TO_LAST").get(timeout=10)
        print result
        gevent.sleep(6) #allow for periodic rollup function to catchup
        compare_query_results(db, expected1, expected2, expected3,
                              'oat_point', result)

    finally:
        if agent_uuid:
            volttron_instance.stop_agent(agent_uuid)
            volttron_instance.remove_agent(agent_uuid)

@pytest.mark.historian
@pytest.mark.mongodb
@pytest.mark.skipif(not HAS_PYMONGO, reason='No pymongo driver')
def test_rollup_query_with_topic_pattern(volttron_instance, database_client):
    """
    Test the query of rolled up data from hourly, daily and monthly data
    tables
    :param database_client:
    :param volttron_instance: The instance against which the test is run
    """
    global query_points
    agent_uuid = None
    try:
        # Clean data and roll up tables
        db = database_client.get_default_database()
        db['data'].drop()
        db['topics'].drop()
        db['meta'].drop()
        db['hourly_data'].drop()
        db['daily_data'].drop()

        publish_t1 = datetime(year=2016, month=3, day=1, hour=1, minute=10,
                       second=1, microsecond=0, tzinfo=tzutc())
        publish_t2 = publish_t1 + timedelta(minutes=1)
        publish_t3 = publish_t2 + timedelta(minutes=3)
        query_end = publish_t3 + timedelta(seconds=2)
        #query time period should be greater than 3 hours for historian to use
        # hourly_data collection and  >= 1 day to use daily_data table
        query_start = query_end - timedelta(hours=4)
        query_start_day = query_end - timedelta(days=2)

        config = mongo_agent_config()
        config['periodic_rollup_initial_wait'] = 0.1
        config['rollup_query_end'] = 0
        config['periodic_rollup_frequency'] = 2
        config['rollup_query_start'] = query_start_day.strftime(
            '%Y-%m-%dT%H:%M:%S.%f')
        config['initial_rollup_start_time'] = query_start_day.strftime(
            '%Y-%m-%dT%H:%M:%S.%f')
        config['rollup_topic_pattern'] = \
            ".*/OutsideAirTemperature|.*/MixedAirTemperature"

        agent_uuid = install_historian_agent(volttron_instance, config)
        # print('HOME', volttron_instance.volttron_home)
        print("\n** test_data_rollup_insert **")

        publish_agent = volttron_instance.build_agent()

        version = publish_agent.vip.rpc.call('platform.historian',
                                             'get_version').get(timeout=5)

        version_nums = version.split(".")
        if int(version_nums[0]) < 2:
            pytest.skip("Only version >= 2.0 support rolled up data.")

        expected1 = publish_fake_data(publish_agent, publish_t1)
        expected2 = publish_fake_data(publish_agent, publish_t2)
        expected3 = publish_fake_data(publish_agent, publish_t3)
        gevent.sleep(6)

        #test query from data table for damper_point - point not in
        # rollup_topic_pattern configured
        result = publish_agent.vip.rpc.call('platform.historian', 'query',
            topic=query_points['damper_point'], count=20,
            start=query_start.isoformat(), end=query_end.isoformat(),
            order="FIRST_TO_LAST").get(timeout=10)
        print result
        compare_query_results(db, expected1, expected2, expected3,
                              'damper_point', result)

        # test query from hourly_data table
        # db['data'].drop()
        # result = publish_agent.vip.rpc.call(
        #     'platform.historian',
        #     'query',
        #     topic=query_points['oat_point'],
        #     count=20,
        #     start = query_start.isoformat(),
        #     end = query_end.isoformat(),
        #     order="FIRST_TO_LAST").get(timeout=10)
        # print result
        # compare_query_results(db, expected1, expected2, expected3,
        #                       'oat_point', result)
        # verify_hourly_collection(db, expected1, expected2, expected3)
        #
        # # test damper_point result don't come back from hourly_table. Result
        # # should be empty since we dropped damper_point
        # result = publish_agent.vip.rpc.call('platform.historian', 'query',
        #     topic=query_points['damper_point'], count=20,
        #     start=query_start.isoformat(), end=query_end.isoformat(),
        #     order="FIRST_TO_LAST").get(timeout=10)
        # assert result == {}
        #
        # # Check query from daily_data
        # db['hourly_data'].drop()
        # result = publish_agent.vip.rpc.call('platform.historian', 'query',
        #     topic=query_points['oat_point'], count=20,
        #     start=query_start_day.isoformat(),
        #     end= query_end.isoformat(),
        #     order="FIRST_TO_LAST").get(timeout=10)
        # print result
        #
        # compare_query_results(db, expected1, expected2, expected3,
        #                       'oat_point', result)
        # verify_daily_collection(db, expected1, expected2, expected3)
        # # test damper_point result don't come back from daily_data. Result
        # # should be empty since we dropped damper_point
        # result = publish_agent.vip.rpc.call(
        #     'platform.historian', 'query',
        #     topic=query_points['damper_point'],
        #     count=20,
        #     start=query_start.isoformat(),
        #     end=query_end.isoformat(),
        #     order="FIRST_TO_LAST").get(timeout=10)
        # assert result == {}


    finally:
        if agent_uuid:
            volttron_instance.stop_agent(agent_uuid)
            volttron_instance.remove_agent(agent_uuid)


@pytest.mark.historian
@pytest.mark.mongodb
@pytest.mark.skipif(not HAS_PYMONGO, reason='No pymongo driver')
def test_rollup_query(volttron_instance, database_client):
    """
    Test the query of rolled up data from hourly, daily and monthly data
    tables
    :param database_client:
    :param volttron_instance: The instance against which the test is run
    """
    global query_points
    agent_uuid = None
    try:
        # Clean data and roll up tables
        db = database_client.get_default_database()
        db['data'].drop()
        db['topics'].drop()
        db['meta'].drop()
        db['hourly_data'].drop()
        db['daily_data'].drop()

        publish_t1 = datetime(year=2016, month=3, day=1, hour=1, minute=10,
                       second=1, microsecond=0, tzinfo=tzutc())
        publish_t2 = publish_t1 + timedelta(minutes=1)
        publish_t3 = publish_t2 + timedelta(minutes=3)
        query_end = publish_t3 + timedelta(seconds=2)
        #query time period should be greater than 3 hours for historian to use
        # hourly_data collection and  >= 1 day to use daily_data table
        query_start = query_end - timedelta(hours=4)
        query_start_day = query_end - timedelta(days=2)

        config = mongo_agent_config()
        config['periodic_rollup_initial_wait'] = 0.1
        config['rollup_query_end'] = 0
        config['periodic_rollup_frequency'] = 2
        config['rollup_query_start'] = query_start_day.strftime(
            '%Y-%m-%dT%H:%M:%S.%f')
        config['initial_rollup_start_time'] = query_start_day.strftime(
            '%Y-%m-%dT%H:%M:%S.%f')

        agent_uuid = install_historian_agent(volttron_instance, config)
        # print('HOME', volttron_instance.volttron_home)
        print("\n** test_data_rollup_insert **")

        publish_agent = volttron_instance.build_agent()

        version = publish_agent.vip.rpc.call('platform.historian',
                                             'get_version').get(timeout=5)

        version_nums = version.split(".")
        if int(version_nums[0]) < 2:
            pytest.skip("Only version >= 2.0 support rolled up data.")

        expected1 = publish_fake_data(publish_agent, publish_t1)
        expected2 = publish_fake_data(publish_agent, publish_t2)
        expected3 = publish_fake_data(publish_agent, publish_t3)
        gevent.sleep(6)

        # test query from hourly_data table
        db['data'].drop()
        result = publish_agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic=query_points['oat_point'],
            count=20,
            start = query_start.isoformat(),
            end = query_end.isoformat(),
            order="FIRST_TO_LAST").get(timeout=10)
        print result
        compare_query_results(db, expected1, expected2, expected3,
                              'oat_point', result)
        verify_hourly_collection(db, expected1, expected2, expected3)

        # Check query from daily_data
        db['hourly_data'].drop()
        result = publish_agent.vip.rpc.call('platform.historian', 'query',
            topic=query_points['oat_point'], count=20,
            start=query_start_day.isoformat(),
            end= query_end.isoformat(),
            order="LAST_TO_FIRST").get(timeout=10)
        print result

        compare_query_results(db, expected3, expected2, expected1,
                              'oat_point', result)
        verify_daily_collection(db, expected3, expected2, expected1)


    finally:
        if agent_uuid:
            volttron_instance.stop_agent(agent_uuid)
            volttron_instance.remove_agent(agent_uuid)

@pytest.mark.historian
@pytest.mark.mongodb
@pytest.mark.skipif(not HAS_PYMONGO, reason='No pymongo driver')
def test_combined_results_from_rollup_and_raw_data(volttron_instance,
                                            database_client):
    """
    Test querying data with start date earlier than available rollup data
    and query end date greater than available rollup data. Historian should 
    query available data from rolled up collection and get the rest 
    from raw data collection
    :param database_client:
    :param volttron_instance: The instance against which the test is run
    """
    global query_points
    agent_uuid = None
    try:
        # Clean data and roll up tables
        db = database_client.get_default_database()
        db['data'].drop()
        db['topics'].drop()
        db['meta'].drop()
        db['hourly_data'].drop()
        db['daily_data'].drop()

        publish_t1 = datetime(year=2016, month=3, day=1, hour=1, minute=10,
                       second=1, microsecond=0, tzinfo=tzutc())
        publish_t2 = publish_t1 + timedelta(minutes=1)
        publish_t3 = utils.get_aware_utc_now()
        #query time period should be greater than 3 hours for historian to use
        # hourly_data collection and  >= 1 day to use daily_data table
        query_start_day = publish_t1 - timedelta(days=35)
        query_end = publish_t3 + timedelta(seconds=2)

        config = mongo_agent_config()
        config['periodic_rollup_initial_wait'] = 0.1
        config['rollup_query_end'] = 1
        config['periodic_rollup_frequency'] = 1
        config['rollup_query_start'] = publish_t2.strftime(
            '%Y-%m-%dT%H:%M:%S.%f')
        config['initial_rollup_start_time'] = publish_t2.strftime(
            '%Y-%m-%dT%H:%M:%S.%f')

        agent_uuid = install_historian_agent(volttron_instance, config)
        # print('HOME', volttron_instance.volttron_home)
        print("\n** test_data_rollup_insert **")

        publish_agent = volttron_instance.build_agent()

        version = publish_agent.vip.rpc.call('platform.historian',
                                             'get_version').get(timeout=5)

        version_nums = version.split(".")
        if int(version_nums[0]) < 2:
            pytest.skip("Only version >= 2.0 support rolled up data.")

        expected1 = publish_fake_data(publish_agent, publish_t1)
        expected2 = publish_fake_data(publish_agent, publish_t2)
        expected3 = publish_fake_data(publish_agent, publish_t3)
        gevent.sleep(6)

        #Only publish_t2 should have gone into rollup collection.
        # Remove publish_t2 entry from data collection
        print("removing {}".format(publish_t2))
        db['data'].remove({'ts':publish_t2})
        db['daily_data'].remove({'ts':publish_t3.replace(hour=0,
                                                         minute=0,
                                                         second=0,
                                                         microsecond=0)})

        # Check query
        result = publish_agent.vip.rpc.call('platform.historian', 'query',
            topic=query_points['oat_point'], count=20,
            start=query_start_day.isoformat(),
            end= query_end.isoformat(),
            order="LAST_TO_FIRST").get(timeout=10)
        print(result)
        compare_query_results(db, expected3, expected2, expected1,
                              'oat_point', result)

    finally:
        if agent_uuid:
            volttron_instance.stop_agent(agent_uuid)
            volttron_instance.remove_agent(agent_uuid)


@pytest.mark.historian
@pytest.mark.mongodb
@pytest.mark.skipif(not HAS_PYMONGO, reason='No pymongo driver')
def test_combined_results_from_rollup_and_raw_data(volttron_instance,
                                            database_client):
    """
    Test querying data with start date earlier than available rollup data
    and query end date greater than available rollup data. Historian should 
    query available data from rolled up collection and get the rest 
    from raw data collection
    :param database_client:
    :param volttron_instance: The instance against which the test is run
    """
    global query_points
    agent_uuid = None
    try:
        # Clean data and roll up tables
        db = database_client.get_default_database()
        db['data'].drop()
        db['topics'].drop()
        db['meta'].drop()
        db['hourly_data'].drop()
        db['daily_data'].drop()

        publish_t1 = datetime(year=2016, month=3, day=1, hour=1, minute=10,
                       second=1, microsecond=0, tzinfo=tzutc())
        publish_t2 = publish_t1 + timedelta(minutes=1)
        publish_t3 = utils.get_aware_utc_now()
        #query time period should be greater than 3 hours for historian to use
        # hourly_data collection and  >= 1 day to use daily_data table
        query_start_day = publish_t1 - timedelta(days=35)
        query_end = publish_t3 + timedelta(seconds=2)

        config = mongo_agent_config()
        config['periodic_rollup_initial_wait'] = 0.1
        config['rollup_query_end'] = 1
        config['periodic_rollup_frequency'] = 1
        config['rollup_query_start'] = publish_t2.strftime(
            '%Y-%m-%dT%H:%M:%S.%f')
        config['initial_rollup_start_time'] = publish_t2.strftime(
            '%Y-%m-%dT%H:%M:%S.%f')

        agent_uuid = install_historian_agent(volttron_instance, config)
        # print('HOME', volttron_instance.volttron_home)
        print("\n** test_data_rollup_insert **")

        publish_agent = volttron_instance.build_agent()

        version = publish_agent.vip.rpc.call('platform.historian',
                                             'get_version').get(timeout=5)

        version_nums = version.split(".")
        if int(version_nums[0]) < 2:
            pytest.skip("Only version >= 2.0 support rolled up data.")

        expected1 = publish_fake_data(publish_agent, publish_t1)
        expected2 = publish_fake_data(publish_agent, publish_t2)
        expected3 = publish_fake_data(publish_agent, publish_t3)
        gevent.sleep(6)

        #Only publish_t2 should have gone into rollup collection.
        # Remove publish_t2 entry from data collection
        print("removing {}".format(publish_t2))
        db['data'].remove({'ts':publish_t2})
        db['daily_data'].remove({'ts':publish_t3.replace(hour=0,
                                                         minute=0,
                                                         second=0,
                                                         microsecond=0)})

        # Check query
        result = publish_agent.vip.rpc.call('platform.historian', 'query',
            topic=query_points['oat_point'], count=20,
            start=query_start_day.isoformat(),
            end= query_end.isoformat(),
            order="LAST_TO_FIRST").get(timeout=10)
        print(result)
        compare_query_results(db, expected3, expected2, expected1,
                              'oat_point', result)

    finally:
        if agent_uuid:
            volttron_instance.stop_agent(agent_uuid)
            volttron_instance.remove_agent(agent_uuid)


@pytest.mark.historian
@pytest.mark.mongodb
@pytest.mark.skipif(not HAS_PYMONGO, reason='No pymongo driver')
def test_combined_results_rollup_and_raw_data_with_count(volttron_instance,
                                            database_client):
    """
    Test querying data with start date earlier than available rollup data
    and query end date greater than available rollup data. Historian should 
    query available data from rolled up collection and get the rest 
    from raw data collection
    :param database_client:
    :param volttron_instance: The instance against which the test is run
    """
    global query_points
    agent_uuid = None
    try:
        # Clean data and roll up tables
        db = database_client.get_default_database()
        db['data'].drop()
        db['topics'].drop()
        db['meta'].drop()
        db['hourly_data'].drop()
        db['daily_data'].drop()

        publish_t1 = datetime(year=2016, month=3, day=1, hour=1, minute=10,
                       second=1, microsecond=0, tzinfo=tzutc())
        publish_t2 = publish_t1 + timedelta(minutes=1)
        publish_t3 = utils.get_aware_utc_now() - timedelta(minutes=1)
        publish_t4 = utils.get_aware_utc_now()
        #query time period should be greater than 3 hours for historian to use
        # hourly_data collection and  >= 1 day to use daily_data table
        query_start_day = publish_t1 - timedelta(days=35)
        query_end = publish_t4 + timedelta(seconds=2)

        config = mongo_agent_config()
        config['periodic_rollup_initial_wait'] = 0.1
        config['rollup_query_end'] = 1
        config['periodic_rollup_frequency'] = 1
        config['rollup_query_start'] = publish_t2.strftime(
            '%Y-%m-%dT%H:%M:%S.%f')
        config['initial_rollup_start_time'] = publish_t2.strftime(
            '%Y-%m-%dT%H:%M:%S.%f')

        agent_uuid = install_historian_agent(volttron_instance, config)
        # print('HOME', volttron_instance.volttron_home)
        print("\n** test_data_rollup_insert **")

        publish_agent = volttron_instance.build_agent()

        version = publish_agent.vip.rpc.call('platform.historian',
                                             'get_version').get(timeout=5)

        version_nums = version.split(".")
        if int(version_nums[0]) < 2:
            pytest.skip("Only version >= 2.0 support rolled up data.")

        expected1 = publish_fake_data(publish_agent, publish_t1)
        expected2 = publish_fake_data(publish_agent, publish_t2)
        expected3 = publish_fake_data(publish_agent, publish_t3)
        expected4 = publish_fake_data(publish_agent, publish_t4)
        gevent.sleep(6)

        #Only publish_t2 should have gone into rollup collection.
        # Remove publish_t2 entry from data collection so that is is only
        # available in hourly and daily  collections
        print("removing {}".format(publish_t2))
        db['data'].remove({'ts':publish_t2})
        db['daily_data'].remove({'ts':publish_t3.replace(hour=0,
                                                         minute=0,
                                                         second=0,
                                                         microsecond=0)})

        # result from data table alone
        result = publish_agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic=query_points['oat_point'],
            count=1,
            start=query_start_day.isoformat(),
            end= query_end.isoformat(),
            order="LAST_TO_FIRST").get(timeout=10)
        print("Case 1: {}".format(result))
        compare_query_results(db, expected4, None, None,
                              'oat_point', result)

        # result from data table alone
        result = publish_agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic=query_points['oat_point'],
            count=1,
            start=query_start_day.isoformat(),
            end=query_end.isoformat(),
            order="FIRST_TO_LAST").get(timeout=10)
        print("Case 2: {}".format(result))
        compare_query_results(db, expected1, None, None, 'oat_point', result)

        # result from rollup table alone
        result = publish_agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic=query_points['oat_point'],
            count=1,
            start=publish_t2.isoformat(),
            end=query_end.isoformat(),
            order="FIRST_TO_LAST").get(timeout=10)
        print("Case 3: {}".format(result))
        compare_query_results(db, expected2, None, None, 'oat_point', result)

        # combined result
        result = publish_agent.vip.rpc.call(
            'platform.historian', 'query',
            topic=query_points['oat_point'], count=2,
            start=query_start_day.isoformat(), end=query_end.isoformat(),
            order="FIRST_TO_LAST").get(timeout=10)
        print("Case 4: {}".format(result))
        compare_query_results(db, expected1, expected2, None, 'oat_point',
                              result)

        # combined result
        result = publish_agent.vip.rpc.call(
            'platform.historian', 'query',
            topic=query_points['oat_point'], count=3,
            start=query_start_day.isoformat(), end=query_end.isoformat(),
            order="LAST_TO_FIRST").get(timeout=10)
        print("Case 5: {}".format(result))
        compare_query_results(db, expected4, expected3, expected2, 'oat_point',
                              result)

        # results only from raw data
        result = publish_agent.vip.rpc.call(
            'platform.historian', 'query',
            topic=query_points['oat_point'],
            count=2,
            start=query_start_day.isoformat(),
            end=query_end.isoformat(),
            order="LAST_TO_FIRST").get(timeout=10)
        print("Case 6: {}".format(result))
        compare_query_results(db, expected4, expected3, None, 'oat_point',
                              result)

    finally:
        if agent_uuid:
            volttron_instance.stop_agent(agent_uuid)
            volttron_instance.remove_agent(agent_uuid)


@pytest.mark.historian
@pytest.mark.mongodb
@pytest.mark.skipif(not HAS_PYMONGO, reason='No pymongo driver')
def test_dict_insert_special_character(volttron_instance, database_client):
    """
    Test the inserting special characters
    :param database_client:
    :param volttron_instance: The instance against which the test is run
    """
    global query_points
    agent_uuid = None
    try:
        # Clean data and roll up tables
        db = database_client.get_default_database()
        db['data'].drop()
        db['topics'].drop()
        db['meta'].drop()
        db['hourly_data'].drop()
        db['daily_data'].drop()

        publish_t1 = datetime(year=2016, month=3, day=1, hour=1, minute=10,
                       second=1, microsecond=0, tzinfo=tzutc())
        publish_t2 = publish_t1 + timedelta(minutes=1)

        query_end = publish_t2 + timedelta(seconds=2)
        #query time period should be greater than 3 hours for historian to use
        # hourly_data collection and  >= 1 day to use daily_data table
        query_start = query_end - timedelta(hours=4)
        query_start_day = query_end - timedelta(days=2)

        config = mongo_agent_config()
        config['periodic_rollup_initial_wait'] = 0.1
        config['rollup_query_end'] = 0
        config['periodic_rollup_frequency'] = 2
        config['rollup_query_start'] = query_start_day.strftime(
            '%Y-%m-%dT%H:%M:%S.%f')
        config['initial_rollup_start_time'] = query_start_day.strftime(
            '%Y-%m-%dT%H:%M:%S.%f')

        agent_uuid = install_historian_agent(volttron_instance, config)
        # print('HOME', volttron_instance.volttron_home)
        print("\n** test_dict_insert_special_character **")

        publish_agent = volttron_instance.build_agent()

        version = publish_agent.vip.rpc.call('platform.historian',
                                             'get_version').get(timeout=5)

        version_nums = version.split(".")
        if int(version_nums[0]) < 2:
            pytest.skip("Only version >= 2.0 support rolled up data.")

        dict1 = {"key.1":"value1", "$":1}
        expected1 = publish_fake_data(publish_agent, publish_t1, dict1)
        expected2 = publish_fake_data(publish_agent, publish_t2, dict1)
        gevent.sleep(6)

        # test query from hourly_data table
        db['data'].drop()
        result = publish_agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic=query_points['oat_point'],
            count=20,
            start = query_start.isoformat(),
            end = query_end.isoformat(),
            order="FIRST_TO_LAST").get(timeout=10)
        print(result)
        compare_query_results(db, expected1, expected2, None,
                              'oat_point', result)

        # Check query from daily_data
        db['hourly_data'].drop()
        result = publish_agent.vip.rpc.call('platform.historian', 'query',
            topic=query_points['oat_point'], count=20,
            start=query_start_day.isoformat(),
            end= query_end.isoformat(),
            order="LAST_TO_FIRST").get(timeout=10)
        print(result)

        compare_query_results(db, expected2, expected1, None,
                              'oat_point', result)
    finally:
        if agent_uuid:
            volttron_instance.stop_agent(agent_uuid)
            volttron_instance.remove_agent(agent_uuid)

@pytest.mark.mongodb
@pytest.mark.skipif(not HAS_PYMONGO, reason='No pymongo driver')
def test_insert_multiple_data_per_minute(volttron_instance,
                                            database_client):
    """
    Test the query of rolled up data from hourly, daily and monthly data
    tables
    :param database_client:
    :param volttron_instance: The instance against which the test is run
    """
    global query_points
    agent_uuid = None
    try:
        # Clean data and roll up tables
        db = database_client.get_default_database()
        db['data'].drop()
        db['topics'].drop()
        db['meta'].drop()
        db['hourly_data'].drop()
        db['daily_data'].drop()

        publish_t1 = datetime(year=2016, month=3, day=1, hour=1, minute=10,
                       second=1, microsecond=0, tzinfo=tzutc())
        # test insert and query when there is more than 1 record in the
        # same minute
        publish_t2 = publish_t1 + timedelta(seconds=5)
        query_end = publish_t2 + timedelta(seconds=2)
        #query time period should be greater than 3 hours for historian to use
        # hourly_data collection and  >= 1 day to use daily_data table
        query_start = query_end - timedelta(hours=4)
        query_start_day = query_end - timedelta(days=2)

        config = mongo_agent_config()
        config['periodic_rollup_initial_wait'] = 0.1
        config['rollup_query_end'] = 0
        config['periodic_rollup_frequency'] = 2
        config['rollup_query_start'] = query_start_day.strftime(
            '%Y-%m-%dT%H:%M:%S.%f')
        config['initial_rollup_start_time'] = query_start_day.strftime(
            '%Y-%m-%dT%H:%M:%S.%f')

        agent_uuid = install_historian_agent(volttron_instance, config)
        # print('HOME', volttron_instance.volttron_home)
        print("\n** test_data_rollup_insert **")

        publish_agent = volttron_instance.build_agent()

        version = publish_agent.vip.rpc.call('platform.historian',
                                             'get_version').get(timeout=5)

        version_nums = version.split(".")
        if int(version_nums[0]) < 2:
            pytest.skip("Only version >= 2.0 support rolled up data.")

        expected1 = publish_fake_data(publish_agent, publish_t1)
        expected2 = publish_fake_data(publish_agent, publish_t2)
        gevent.sleep(6)

        # test query from hourly_data table
        db['data'].drop()
        result = publish_agent.vip.rpc.call(
            'platform.historian',
            'query',
            topic=query_points['oat_point'],
            count=20,
            start = query_start.isoformat(),
            end = query_end.isoformat(),
            order="FIRST_TO_LAST").get(timeout=10)
        print result
        compare_query_results(db, expected1, expected2, None,
                              'oat_point', result)
        verify_hourly_collection(db, expected1, expected2)

        # Check query from daily_data
        db['hourly_data'].drop()
        result = publish_agent.vip.rpc.call('platform.historian', 'query',
            topic=query_points['oat_point'], count=20,
            start=query_start_day.isoformat(),
            end= query_end.isoformat(),
            order="FIRST_TO_LAST").get(timeout=10)
        print result

        compare_query_results(db, expected1, expected2, None,
                              'oat_point', result)
        verify_daily_collection(db, expected1, expected2)


    finally:
        if agent_uuid:
            volttron_instance.stop_agent(agent_uuid)
            volttron_instance.remove_agent(agent_uuid)


def compare_query_results(db, expected1, expected2,
                          expected3, query_point,
                          result):
    expected_t1 = format_expected_time(expected1)
    assert expected_t1 == result['values'][0][0]
    assert result['values'][0][1] == expected1[query_point]
    if expected2:
        expected_t2 = format_expected_time(expected2)
        assert expected_t2 == result['values'][1][0]
        assert result['values'][1][1] == expected2[query_point]
    if expected3:
        expected_t3 = format_expected_time(expected3)
        assert expected_t3 == result['values'][2][0]
        assert result['values'][2][1] == expected3[query_point]


def verify_daily_collection(db, expected1, expected2, expected3=None):
    # verify daily data
    expected_t1 = format_expected_time(expected1)
    expected_t2 = format_expected_time(expected2)
    t1_hour_min = expected1['datetime'].replace(second=0, microsecond=0)
    t2_hour_min = expected2['datetime'].replace(second=0, microsecond=0)
    if expected3:
        expected_t3 = format_expected_time(expected3)
    cursor = db['topics'].find({'topic_name': query_points['oat_point']})
    rows = list(cursor)
    id = rows[0]['_id']
    cursor = db['daily_data'].find({'topic_id': id})
    rows = list(cursor)
    assert len(rows[0]['data']) == 24 * 60
    # print rows[0]['data']
    # if it is same day and same minute
    if t1_hour_min == t2_hour_min:
        rolled_up_data1 = rows[0]['data'][
            expected1['datetime'].hour * 60 + expected1['datetime'].minute][0]
        rolled_up_data2 = rows[0]['data'][
            expected2['datetime'].hour * 60 + expected1['datetime'].minute][1]
    else:
        rolled_up_data1 = rows[0]['data'][
            expected1['datetime'].hour * 60 + expected1['datetime'].minute][0]
        rolled_up_data2 = rows[0]['data'][
            expected2['datetime'].hour * 60 + expected2['datetime'].minute][0]
    compare_rolled_up_data(rolled_up_data1, expected_t1,
                           expected1['oat_point'])
    compare_rolled_up_data(rolled_up_data2, expected_t2,
                           expected2['oat_point'])
    if expected3:
        rolled_up_data3 = rows[0]['data'][
            expected3['datetime'].hour * 60 + expected3['datetime'].minute][0]
        compare_rolled_up_data(rolled_up_data3, expected_t3,
                               expected3['oat_point'])


def verify_hourly_collection(db, expected1, expected2, expected3=None):
    # verify hourly rollup
    expected_t1 = format_expected_time(expected1)
    expected_t2 = format_expected_time(expected2)
    t1_hour = expected1['datetime'].replace(second=0, microsecond=0)
    t2_hour = expected2['datetime'].replace(second=0, microsecond=0)
    if expected3:
        expected_t3 = format_expected_time(expected3)
    cursor = db['topics'].find({'topic_name': query_points['oat_point']})
    rows = list(cursor)
    id = rows[0]['_id']
    cursor = db['hourly_data'].find({'topic_id': id})
    rows = list(cursor)
    assert len(rows[0]['data']) == 60
    print rows[0]['data']
    if t1_hour == t2_hour:
        rolled_up_data1 = rows[0]['data'][expected1['datetime'].minute][0]
        rolled_up_data2 = rows[0]['data'][expected1['datetime'].minute][1]
    else:
        rolled_up_data1 = rows[0]['data'][expected1['datetime'].minute][0]
        rolled_up_data2 = rows[0]['data'][expected2['datetime'].minute][0]

    compare_rolled_up_data(rolled_up_data1, expected_t1,
                           expected1['oat_point'])
    compare_rolled_up_data(rolled_up_data2, expected_t2,
                           expected2['oat_point'])
    if expected3 and expected_t3:
        rolled_up_data3 = rows[0]['data'][expected3['datetime'].minute][0]
        compare_rolled_up_data(rolled_up_data3, expected_t3,
                               expected3['oat_point'])


def format_expected_time(expected1):
    expected_t1 = utils.format_timestamp(expected1['datetime'])
    expected_t1 = expected_t1[:-9] + '000+00:00'
    return expected_t1


def compare_rolled_up_data(data_from_db_query, expected_time, expected_value):
    assert utils.format_timestamp(data_from_db_query[0])+'+00:00' == \
           expected_time
    assert data_from_db_query[1] == expected_value

@pytest.mark.historian
@pytest.mark.mongodb
@pytest.mark.skipif(not HAS_PYMONGO, reason='No pymongo driver')
def test_manage_db_size(volttron_instance, database_client):
    clean_db(database_client)

    # set config parameter to automatically delete data
    config = dict(mongo_agent_config())
    config["history_limit_days"] = 6

    # start up the angent
    agent_uuid = install_historian_agent(volttron_instance,
                                         config)

    assert agent_uuid is not None
    assert volttron_instance.is_agent_running(agent_uuid)

    # put some fake data in the database
    db = database_client.get_default_database()
    collection_names = ("data", "hourly_data", "daily_data")
    doc = {"ts": datetime(1970, 1, 1), "message": "testdata"}
    for collection_name in collection_names:
        db[collection_name].insert_one(doc)

    for collection_name in collection_names:
        assert db[collection_name].find_one({"message": "testdata"}) is not None

    # publish something that the database should see
    publisher = volttron_instance.build_agent()
    assert publisher is not None
    publish_fake_data(publisher)

    gevent.sleep(6)
    # make sure that the database deletes old data
    for collection_name in collection_names:
        assert db[collection_name].find_one({"message": "testdata"}) is None

    # clean up
    volttron_instance.stop_agent(agent_uuid)
    volttron_instance.remove_agent(agent_uuid)
