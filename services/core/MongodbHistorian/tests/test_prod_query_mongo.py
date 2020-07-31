import pytest
from datetime import datetime
# building name replaced. replace before testing
from volttron.platform import get_services_core
from fixtures import (ALL_TOPIC, BASE_ANALYSIS_TOPIC, BASE_DEVICE_TOPIC,
                      mongo_connection_params, mongo_agent_config,
                      mongo_connection_string)

AHU1_temp = "Economizer_RCx/PNNL/BUILDING1/AHU1/Temperature Sensor Dx/diagnostic message"
AHU2_temp = "Economizer_RCx/PNNL/BUILDING1/AHU2/Temperature Sensor Dx/diagnostic message"
AHU3_temp = "Economizer_RCx/PNNL/BUILDING1/AHU3/Temperature Sensor Dx/diagnostic message"
AHU4_temp = "Economizer_RCx/PNNL/BUILDING1/AHU4/Temperature Sensor Dx/diagnostic message"
AHU2_eco = "Economizer_RCx/PNNL/BUILDING1/AHU2/Not Economizing When Unit Should " \
           "Dx/diagnostic message"
AHU2_outdoor_air = "Economizer_RCx/PNNL/BUILDING1/AHU2/Excess Outdoor-air Intake " \
                   "Dx/diagnostic message"
AHU1_outdoor_air = "Economizer_RCx/PNNL/BUILDING1/AHU1/Excess Outdoor-air Intake " \
                   "Dx/diagnostic message"

AHU1_VAV129 = "PNNL/BUILDING1/AHU1/VAV129/ZoneOutdoorAirFlow"
AHU1_VAV127B = "PNNL/BUILDING1/AHU1/VAV127B/ZoneOutdoorAirFlow"
AHU1_VAV119 = "PNNL/BUILDING1/AHU1/VAV119/ZoneOutdoorAirFlow"
AHU1_VAV143 = "PNNL/BUILDING1/AHU1/VAV143/ZoneOutdoorAirFlow"
AHU1_VAV150 = "PNNL/BUILDING1/AHU1/VAV150/ZoneOutdoorAirFlow"
AHU1_VAV152 = "PNNL/BUILDING1/AHU1/VAV152/ZoneOutdoorAirFlow"

AHU1_VAV127A_temp = "PNNL/BUILDING1/AHU1/VAV127A/ZoneTemperature (East)"
AHU1_VAV127B_temp = "PNNL/BUILDING1/AHU1/VAV127B/ZoneTemperature (East)"

multi_topic_list2 = \
    ["Economizer_RCx/PNNL/BUILDING1/AHU2/Temperature Sensor Dx/energy impact",
     "Economizer_RCx/PNNL/BUILDING1/AHU2/Not Economizing When Unit Should Dx/"
     "energy impact",
     "Economizer_RCx/PNNL/BUILDING1/AHU2/Economizing When Unit Should Not Dx/"
     "energy impact",
     "Economizer_RCx/PNNL/BUILDING1/AHU2/Excess Outdoor-air Intake Dx/energy impact",
     "Economizer_RCx/PNNL/BUILDING1/AHU2/Insufficient Outdoor-air Intake Dx/energy "
     "impact",
     "Economizer_RCx/PNNL/BUILDING1/AHU2/Economizing When Unit Should Not "
     "Dx/diagnostic message",
     "Economizer_RCx/PNNL/BUILDING1/AHU2/Not Economizing When Unit Should "
     "Dx/diagnostic message",
     "Economizer_RCx/PNNL/BUILDING1/AHU2/Temperature Sensor Dx/diagnostic message",
     "Economizer_RCx/PNNL/BUILDING1/AHU2/Excess Outdoor-air Intake Dx/diagnostic "
     "message",
     "Economizer_RCx/PNNL/BUILDING1/AHU2/Insufficient Outdoor-air Intake "
     "Dx/diagnostic message"]

multi_topic_list1 = \
    ["Economizer_RCx/PNNL/BUILDING1/AHU1/Temperature Sensor Dx/energy impact",
     "Economizer_RCx/PNNL/BUILDING1/AHU1/Not Economizing When Unit Should Dx/"
     "energy impact",
     "Economizer_RCx/PNNL/BUILDING1/AHU1/Economizing When Unit Should Not Dx/"
     "energy impact",
     "Economizer_RCx/PNNL/BUILDING1/AHU1/Excess Outdoor-air Intake Dx/energy impact",
     "Economizer_RCx/PNNL/BUILDING1/AHU1/Insufficient Outdoor-air Intake Dx/energy "
     "impact",
     "Economizer_RCx/PNNL/BUILDING1/AHU1/Economizing When Unit Should Not "
     "Dx/diagnostic message",
     "Economizer_RCx/PNNL/BUILDING1/AHU1/Not Economizing When Unit Should "
     "Dx/diagnostic message",
     "Economizer_RCx/PNNL/BUILDING1/AHU1/Temperature Sensor Dx/diagnostic message",
     "Economizer_RCx/PNNL/BUILDING1/AHU1/Excess Outdoor-air Intake Dx/diagnostic "
     "message",
     "Economizer_RCx/PNNL/BUILDING1/AHU1/Insufficient Outdoor-air Intake "
     "Dx/diagnostic message"]

# ["Economizer_RCx/PNNL/BUILDING1/AHU1/Temperature Sensor Dx/diagnostic message","Economizer_RCx/PNNL/BUILDING1/AHU2/Temperature Sensor Dx/diagnostic message","Economizer_RCx/PNNL/BUILDING1/AHU3/Temperature Sensor Dx/diagnostic message","Economizer_RCx/PNNL/BUILDING1/AHU4/Temperature Sensor Dx/diagnostic message"]
try:
    import pymongo

    HAS_PYMONGO = True
except:
    HAS_PYMONGO = False

mongo_platform = {
    "connection": {
        "type": "mongodb",
        "params": {
            "host": "localhost",
            "port": 27017,
            "database": "performance_test",
            "user": "test",
            "passwd": "test",
            "authSource": "mongo_test"
        }
    }
}

pytestmark = pytest.mark.skip(reason="Performance test. Not for CI")


# Create a mark for use within params of a fixture.
pytestmark = pytest.mark.skip(reason="Performance test. Not for CI")
pymongo_mark = pytest.mark.skipif(not HAS_PYMONGO, reason='No pymongo client available.')


@pytest.fixture(scope="function", params=[pymongo_mark(mongo_agent_config)])
def database_client(request):
    print('connecting to mongo database')
    client = pymongo.MongoClient(mongo_connection_string())

    def close_client():
        if client is not None:
            client.close()

    request.addfinalizer(close_client)
    return client


@pytest.mark.timeout(180)
@pytest.mark.skipif(not HAS_PYMONGO, reason='No pymongo driver')
def test_basic_function_week_data(volttron_instance, database_client):
    """
    Test basic functionality of sql historian. Inserts three points as part of all topic and checks
    if all three got into the database
    :param volttron_instance: The instance against which the test is run
    """

    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_basic_function **")

    publish_agent = volttron_instance.build_agent()

    # Query the historian
    before = datetime.now()
    result = publish_agent.vip.rpc.call(
        'platform.historian',
        'query',
        topic="Economizer_RCx/PNNL/BUILDING1/AHU1/Temperature Sensor Dx/diagnostic message",
        start='2016-04-01 00:00:00.000000Z',
        end='2016-04-08 00:00:00.000000Z',
        count=35000
    ).get(timeout=100)
    print("Time taken{}".format(datetime.now() - before))
    print("result count {}".format(len(result['values'])))

    before = datetime.now()
    result = publish_agent.vip.rpc.call(
        'platform.historian',
        'query',
        topic="Economizer_RCx/PNNL/BUILDING1/AHU2/Temperature Sensor Dx/diagnostic "
              "message",
        start='2016-04-01 00:00:00.000000Z',
        end='2016-04-08 00:00:00.000000Z',
        count=35000
    ).get(timeout=100)
    print("Time taken{}".format(datetime.now() - before))
    print("result count {}".format(len(result['values'])))

    before = datetime.now()
    result = publish_agent.vip.rpc.call(
        'platform.historian',
        'query',
        topic="Economizer_RCx/PNNL/BUILDING1/AHU3/Temperature Sensor Dx/diagnostic "
              "message",
        start='2016-04-01 00:00:00.000000Z',
        end='2016-04-08 00:00:00.000000Z',
        count=35000
    ).get(timeout=100)
    print("Time taken{}".format(datetime.now() - before))
    print("result count {}".format(len(result['values'])))

    before = datetime.now()
    result = publish_agent.vip.rpc.call(
        'platform.historian',
        'query',
        topic="Economizer_RCx/PNNL/BUILDING1/AHU4/Temperature Sensor Dx/diagnostic "
              "message",
        start='2016-04-01 00:00:00.000000Z',
        end='2016-04-08 00:00:00.000000Z',
        count=35000
    ).get(timeout=100)
    print("Time taken{}".format(datetime.now() - before))
    print("result count {}".format(len(result['values'])))


@pytest.mark.timeout(180)
@pytest.mark.skipif(not HAS_PYMONGO, reason='No pymongo driver')
def test_basic_function_month_data(volttron_instance, database_client):
    """
    Test basic functionality of sql historian. Inserts three points as part of all topic and checks
    if all three got into the database
    :param volttron_instance: The instance against which the test is run
    """

    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_basic_function **")

    publish_agent = volttron_instance.build_agent()

    # Query the historian
    before = datetime.now()
    result = publish_agent.vip.rpc.call(
        'platform.historian',
        'query',
        topic=AHU1_VAV129,
        start='2016-04-01 00:00:00.000000Z',
        end='2016-05-01 00:00:00.000000Z',
        count=35000
    ).get(timeout=100)
    print("Time taken{}".format(datetime.now() - before))
    print("result count {}".format(len(result['values'])))

    before = datetime.now()
    result = publish_agent.vip.rpc.call(
        'platform.historian',
        'query',
        topic=AHU1_VAV127B,
        start='2016-04-01 00:00:00.000000Z',
        end='2016-05-01 00:00:00.000000Z',
        count=35000
    ).get(timeout=100)
    print("Time taken{}".format(datetime.now() - before))
    print("result count {}".format(len(result['values'])))

    before = datetime.now()
    result = publish_agent.vip.rpc.call(
        'platform.historian',
        'query',
        topic=AHU1_VAV127A_temp,
        start='2016-04-01 00:00:00.000000Z',
        end='2016-05-01 00:00:00.000000Z',
        count=35000
    ).get(timeout=100)
    print("Time taken{}".format(datetime.now() - before))
    print("result count {}".format(len(result['values'])))

    before = datetime.now()
    result = publish_agent.vip.rpc.call(
        'platform.historian',
        'query',
        topic=AHU1_VAV127B_temp,
        start='2016-04-01 00:00:00.000000Z',
        end='2016-05-01 00:00:00.000000Z',
        count=35000
    ).get(timeout=100)
    print("Time taken{}".format(datetime.now() - before))
    print("result count {}".format(len(result['values'])))

    before = datetime.now()
    result = publish_agent.vip.rpc.call(
        'platform.historian',
        'query',
        topic=AHU1_VAV119,
        start='2016-04-01 00:00:00.000000Z',
        end='2016-05-01 00:00:00.000000Z',
        count=35000
    ).get(timeout=100)
    print("Time taken{}".format(datetime.now() - before))
    print("result count {}".format(len(result['values'])))

    before = datetime.now()
    result = publish_agent.vip.rpc.call(
        'platform.historian',
        'query',
        topic=AHU1_VAV143,
        start='2016-04-01 00:00:00.000000Z',
        end='2016-05-01 00:00:00.000000Z',
        count=35000
    ).get(timeout=100)
    print("Time taken{}".format(datetime.now() - before))
    print("result count {}".format(len(result['values'])))

    before = datetime.now()
    result = publish_agent.vip.rpc.call(
        'platform.historian',
        'query',
        topic=AHU1_VAV150,
        start='2016-04-01 00:00:00.000000Z',
        end='2016-05-01 00:00:00.000000Z',
        count=35000
    ).get(timeout=100)
    print("Time taken{}".format(datetime.now() - before))
    print("result count {}".format(len(result['values'])))


@pytest.mark.timeout(180)
@pytest.mark.skipif(not HAS_PYMONGO, reason='No pymongo driver')
def test_basic_function_week_multi_topic(volttron_instance, database_client):
    """
    Test basic functionality of sql historian. Inserts three points as part of all topic and checks
    if all three got into the database
    :param volttron_instance: The instance against which the test is run
    """

    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_basic_function **")

    publish_agent = volttron_instance.build_agent()

    # Query the historian
    before = datetime.now()
    result = publish_agent.vip.rpc.call(
        'platform.historian',
        'query',
        topic=multi_topic_list1,
        start='2016-04-01 00:00:00.000000Z',
        end='2016-04-08 00:00:00.000000Z',
        count=35000
    ).get(timeout=100)
    print("Time taken{}".format(datetime.now() - before))
    print("result count {}".format(len(result['values'])))

    before = datetime.now()
    result = publish_agent.vip.rpc.call(
        'platform.historian',
        'query',
        topic=multi_topic_list2,
        start='2016-04-01 00:00:00.000000Z',
        end='2016-04-08 00:00:00.000000Z',
        count=35000
    ).get(timeout=100)
    print("Time taken{}".format(datetime.now() - before))
    print("result count {}".format(len(result['values'])))


@pytest.mark.timeout(180)
@pytest.mark.skipif(not HAS_PYMONGO, reason='No pymongo driver')
def test_basic_function_2week_multi_topic(volttron_instance, database_client):
    """
    Test basic functionality of sql historian. Inserts three points as part of all topic and checks
    if all three got into the database
    :param volttron_instance: The instance against which the test is run
    """

    # print('HOME', volttron_instance.volttron_home)
    print("\n** test_basic_function **")

    publish_agent = volttron_instance.build_agent()

    # Query the historian
    before = datetime.now()
    result = publish_agent.vip.rpc.call(
        'platform.historian',
        'query',
        topic=multi_topic_list1,
        start='2016-04-01 00:00:00.000000Z',
        end='2016-04-15 00:00:00.000000Z',
        count=35000
    ).get(timeout=100)
    print("Time taken{}".format(datetime.now() - before))
    print("result count {}".format(len(result['values'])))

    before = datetime.now()
    result = publish_agent.vip.rpc.call(
        'platform.historian',
        'query',
        topic=multi_topic_list2,
        start='2016-04-01 00:00:00.000000Z',
        end='2016-04-15 00:00:00.000000Z',
        count=35000
    ).get(timeout=100)
    print("Time taken{}".format(datetime.now() - before))
    print("result count {}".format(len(result['values'])))
