# pytest test cases for Actuator agent
from datetime import datetime, timedelta

import gevent
import gevent.subprocess as subprocess
import pytest
import types
from gevent.subprocess import Popen
from mock import MagicMock
from volttron.platform.messaging import topics

FAILURE = 'FAILURE'

SUCCESS = 'SUCCESS'
PLATFORM_ACTUATOR = 'platform.actuator'
TEST_AGENT = 'test-agent'
actuator_uuid = None


@pytest.fixture(scope="module")
def publish_agent(request, volttron_instance1):
    global actuator_uuid
    # Create master driver config and 2 fake devices each with 6 points
    process = Popen(['python', 'config_builder.py', '--count=2', '--publish-only-depth-all',
                     'fake', 'fake6.csv', 'null'], env=volttron_instance1.env, cwd='scripts/scalability-testing',
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = process.wait()
    print result
    assert result == 0

    # Start the master driver agent which would intern start the fake driver using the configs created above
    master_uuid = volttron_instance1.install_agent(
            agent_dir="services/core/MasterDriverAgent",
            config_file="scripts/scalability-testing/configs/master-driver.agent",
            start=True)
    print("agent id: ", master_uuid)
    gevent.sleep(2)  # wait for the agent to start and start the devices

    # Start the actuator agent through which publish agent should communicate to fake device
    # Start the master driver agent which would intern start the fake driver using the configs created above
    actuator_uuid = volttron_instance1.install_agent(
            agent_dir="services/core/ActuatorAgent",
            config_file="services/core/ActuatorAgent/tests/actuator.config",
            start=True)
    print("agent id: ", actuator_uuid)

    listener_uuid = volttron_instance1.install_agent(
            agent_dir="examples/ListenerAgent",
            config_file="examples/ListenerAgent/config",
            start=True)
    print("agent id: ", listener_uuid)

    # 3: Start a fake agent to publish to message bus
    fake_publish_agent = volttron_instance1.build_agent()
    # attach actuate method to fake_publish_agent as it needs to be a class method
    # for the call back to work
    fake_publish_agent.callback = types.MethodType(callback, fake_publish_agent)

    # 4: add a tear down method to stop sqlhistorian agent and the fake agent that published to message bus
    def stop_agent():
        print("In teardown method of module")
        volttron_instance1.stop_agent(actuator_uuid)
        volttron_instance1.stop_agent(master_uuid)
        fake_publish_agent.core.stop()

    request.addfinalizer(stop_agent)
    return fake_publish_agent


def actuate0(self, peer, sender, bus, topic, headers, message):
    print("In actuate0")
    print ("topic:", topic, 'header:', headers, 'message:', message)


def callback(self, peer, sender, bus, topic, headers, message):
    print("*************In callback")
    print ("topic:", topic, 'header:', headers, 'message:', message)


@pytest.mark.actuator
def test_schedule_response_success(publish_agent):
    """
    Test requesting a new schedule and canceling a schedule through pubsub
    Format of expected result
    Expected Header
    {
    'type': <'NEW_SCHEDULE', 'CANCEL_SCHEDULE'>
    'requesterID': <Agent ID from the request>,
    'taskID': <Task ID from the request>
    }
    Expected message
    {
    'result': <'SUCCESS', 'FAILURE', 'PREEMPTED'>,
    'info': <Failure reason, if any>,
    'data': <Data about the failure or cancellation, if any>
    }
    :param publish_agent: fixture invoked to setup all agents necessary and returns an instance
    of Agent object used for publishing
    """
    # Mock callback methods
    global actuator_uuid
    publish_agent.callback = MagicMock(name="callback")
    print("actuator uuid " + actuator_uuid)
    # subscribe to schedule response topic
    # TODO: verfy topic name - result  vs response
    print ('topic scheule response is :', topics.ACTUATOR_SCHEDULE_RESULT)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=topics.ACTUATOR_SCHEDULE_RESULT,
                                       callback=publish_agent.callback)

    print("requesting a schedule for device0")
    start = str(datetime.now() + timedelta(seconds=10))
    end = str(datetime.now() + timedelta(seconds=20))
    print ('start time for device0', start)

    header = {
        'type': 'NEW_SCHEDULE',
        'requesterID': TEST_AGENT,  # The name of the requesting agent.
        'taskID': 'task1',  # unique (to all tasks) ID for scheduled task.
        'priority': 'LOW',  # ('HIGH, 'LOW', 'LOW_PREEMPT').
    }
    msg = [
        ['fakedriver0', start, end]
    ]

    publish_agent.vip.pubsub.publish(peer='pubsub', topic=topics.ACTUATOR_SCHEDULE_REQUEST, headers=header, message=msg)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    gevent.sleep(1)
    assert publish_agent.callback.call_count == 1
    print ('call args ', publish_agent.callback.call_args[0][1])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['type'] == 'NEW_SCHEDULE'
    assert result_header['taskID'] == 'task_schedule_response'
    assert result_header['requesterID'] == TEST_AGENT
    assert result_message['result'] == SUCCESS

    # Test valid cancellation
    header = {
        'type': 'CANCEL_SCHEDULE',
        'requesterID': TEST_AGENT,  # The name of the requesting agent.
        'taskID': 'task_schedule_response'  # unique (to all tasks) ID for scheduled task.
    }
    publish_agent.vip.pubsub.publish(peer='pubsub', topic=topics.ACTUATOR_SCHEDULE_REQUEST, headers=header, message=msg)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    gevent.sleep(1)
    print ("after cancel request")
    print (publish_agent.callback.call_count)
    print (publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    # TODO verify and fix this
    # assert result_header['type'] == 'CANCEL_SCHEDULE'
    assert result_header['taskID'] == 'task_schedule_response'
    assert result_header['requesterID'] == TEST_AGENT
    assert result_message['result'] == SUCCESS


@pytest.mark.actuator
def test_schedule_error_invalid_type(publish_agent):
    """
    Test error responses for schedule request through pubsub

    :param publish_agent: fixture invoked to setup all agents necessary and returns an instance
    of Agent object used for publishing
    """
    # Mock callback methods
    global actuator_uuid
    publish_agent.callback = MagicMock(name="callback")
    publish_agent.callback.reset_mock()
    print("actuator uuid " + actuator_uuid)
    # subscribe to schedule response topic
    # TODO: verfy topic name - result  vs response
    print ('topic scheule response is :', topics.ACTUATOR_SCHEDULE_RESULT)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=topics.ACTUATOR_SCHEDULE_RESULT,
                                       callback=publish_agent.callback)

    print("requesting a schedule for device0")
    start = str(datetime.now() + timedelta(seconds=10))
    end = str(datetime.now() + timedelta(seconds=20))
    print ('start time for device0', start)

    header = {
        'type': 'NEW_SCHEDULE2',
        'requesterID': TEST_AGENT,  # The name of the requesting agent.
        'taskID': 'task1',  # unique (to all tasks) ID for scheduled task.
        'priority': 'LOW'  # ('HIGH, 'LOW', 'LOW_PREEMPT').
    }
    msg = [
        ['fakedriver0', start, end]
    ]

    publish_agent.vip.pubsub.publish(peer='pubsub', topic=topics.ACTUATOR_SCHEDULE_REQUEST, headers=header, message=msg)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    gevent.sleep(1)
    assert publish_agent.callback.call_count == 1
    print ('call args ', publish_agent.callback.call_args[0][1])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['type'] == 'NEW_SCHEDULE2'
    assert result_header['taskID'] == 'task1'
    assert result_header['requesterID'] == TEST_AGENT
    assert result_message['result'] == FAILURE
    assert result_message['info'] == 'INVALID_REQUEST_TYPE'


@pytest.mark.actuator
def test_schedule_error_invalid_task(publish_agent):
    # Test Error response
    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback")
    publish_agent.callback.reset_mock()
    # subscribe to schedule response topic
    # TODO: verfy topic name - result  vs response
    print ('topic scheule response is :', topics.ACTUATOR_SCHEDULE_RESULT)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=topics.ACTUATOR_SCHEDULE_RESULT,
                                       callback=publish_agent.callback)

    print("requesting a schedule for device0")
    start = str(datetime.now() + timedelta(seconds=10))
    end = str(datetime.now() + timedelta(seconds=20))
    print ('start time for device0', start)
    header = {
        'type': 'CANCEL_SCHEDULE',
        'requesterID': TEST_AGENT,  # The name of the requesting agent.
        'taskID': 'task_schedule_response-1'  # unique (to all tasks) ID for scheduled task.
    }
    msg = [
        ['fakedriver0', start, end]
    ]
    publish_agent.vip.pubsub.publish(peer='pubsub', topic=topics.ACTUATOR_SCHEDULE_REQUEST, headers=header, message=msg)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    gevent.sleep(1)
    assert publish_agent.callback.call_count == 1
    print (publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]

    assert result_header['type'] == 'CANCEL_SCHEDULE'
    assert result_header['taskID'] == 'task_schedule_response'
    assert result_header['requesterID'] == TEST_AGENT
    assert result_message['result'] == FAILURE
    assert result_message['info'] == 'TASK_ID_DOES_NOT_EXIST'


@pytest.mark.actuator
def test_schedule_error_none_taskid(publish_agent):
    # Test Error response
    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback")
    publish_agent.callback.reset_mock()
    # subscribe to schedule response topic
    # TODO: verfy topic name - result  vs response
    print ('topic scheule response is :', topics.ACTUATOR_SCHEDULE_RESULT)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=topics.ACTUATOR_SCHEDULE_RESULT,
                                       callback=publish_agent.callback)

    print("requesting a schedule for device0")
    start = str(datetime.now() + timedelta(seconds=10))
    end = str(datetime.now() + timedelta(seconds=20))
    print ('start time for device0', start)
    header = {
        'type': 'NEW_SCHEDULE',
        'requesterID': TEST_AGENT,
        'priority': 'LOW'
    }
    msg = [
        ['fakedriver0', start, end]
    ]
    publish_agent.vip.pubsub.publish(peer='pubsub', topic=topics.ACTUATOR_SCHEDULE_REQUEST, headers=header, message=msg)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    gevent.sleep(1)
    assert publish_agent.callback.call_count == 1
    print (publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]

    assert result_header['type'] == 'NEW_SCHEDULE'
    assert result_header['requesterID'] == TEST_AGENT
    assert result_message['result'] == FAILURE
    assert result_message['info'] == 'MISSING_TASK_ID'

@pytest.mark.actuator
def test_schedule_error_missing_taskid(publish_agent):
    # Test Error response
    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback")
    publish_agent.callback.reset_mock()
    # subscribe to schedule response topic
    # TODO: verfy topic name - result  vs response
    print ('topic scheule response is :', topics.ACTUATOR_SCHEDULE_RESULT)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=topics.ACTUATOR_SCHEDULE_RESULT,
                                       callback=publish_agent.callback)

    print("requesting a schedule for device0")
    start = str(datetime.now() + timedelta(seconds=10))
    end = str(datetime.now() + timedelta(seconds=20))
    print ('start time for device0', start)
    header = {
        'type': 'NEW_SCHEDULE',
        'requesterID': TEST_AGENT,
        'priority': 'LOW',
        'taskID': ''
    }
    msg = [
        ['fakedriver0', start, end]
    ]
    publish_agent.vip.pubsub.publish(peer='pubsub', topic=topics.ACTUATOR_SCHEDULE_REQUEST, headers=header, message=msg)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    gevent.sleep(1)
    assert publish_agent.callback.call_count == 1
    print (publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]

    assert result_header['type'] == 'NEW_SCHEDULE'
    assert result_header['requesterID'] == TEST_AGENT
    assert result_message['result'] == FAILURE
    assert result_message['info'] == 'MISSING_TASK_ID'

@pytest.mark.actuator
def test_schedule_error_empty_message(publish_agent):
    # Test Error response
    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback")
    publish_agent.callback.reset_mock()
    # subscribe to schedule response topic
    # TODO: verfy topic name - result  vs response
    print ('topic scheule response is :', topics.ACTUATOR_SCHEDULE_RESULT)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=topics.ACTUATOR_SCHEDULE_RESULT,
                                       callback=publish_agent.callback)

    print("requesting a schedule for device0")
    start = str(datetime.now() + timedelta(seconds=10))
    end = str(datetime.now() + timedelta(seconds=20))
    print ('start time for device0', start)
    header = {
        'type': 'NEW_SCHEDULE',
        'requesterID': TEST_AGENT,  # The name of the requesting agent.
        'taskID': 'task_schedule_response-1',
        'priority': 'LOW'
    }
    msg = [

    ]
    publish_agent.vip.pubsub.publish(peer='pubsub', topic=topics.ACTUATOR_SCHEDULE_REQUEST, headers=header, message=msg)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    gevent.sleep(1)
    assert publish_agent.callback.call_count == 1
    print (publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    # TODO verify and fix this
    # assert result_header['type'] == 'CANCEL_SCHEDULE'
    assert result_header['taskID'] == 'task_schedule_response-1'
    assert result_header['requesterID'] == TEST_AGENT
    assert result_message['result'] == FAILURE
    assert result_message['info'] == 'MALFORMED_REQUEST_EMPTY'


@pytest.mark.actuator
def test_schedule_error_multiple_missing(publish_agent):
    # Test Error response
    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback")
    publish_agent.callback.reset_mock()
    # subscribe to schedule response topic
    # TODO: verfy topic name - result  vs response
    print ('topic scheule response is :', topics.ACTUATOR_SCHEDULE_RESULT)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=topics.ACTUATOR_SCHEDULE_RESULT,
                                       callback=publish_agent.callback)

    print("requesting a schedule for device0")
    start = str(datetime.now() + timedelta(seconds=10))
    end = str(datetime.now() + timedelta(seconds=20))
    print ('start time for device0', start)
    header = {
        'type': 'NEW_SCHEDULE',
        'requesterID': TEST_AGENT,  # The name of the requesting agent.
        'taskID': 'task_schedule_response-1'
        # 'priority': 'LOW'
    }
    msg = [

    ]
    publish_agent.vip.pubsub.publish(peer='pubsub', topic=topics.ACTUATOR_SCHEDULE_REQUEST, headers=header, message=msg)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    gevent.sleep(1)
    assert publish_agent.callback.call_count == 1
    print (publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    # TODO verify and fix this
    # assert result_header['type'] == 'CANCEL_SCHEDULE'
    assert result_header['taskID'] == 'task_schedule_response-1'
    assert result_header['requesterID'] == TEST_AGENT
    assert result_message['result'] == FAILURE
    assert result_message['info'] == 'MALFORMED_REQUEST_EMPTY' or result_message['info'] == 'MISSING_PRIORITY'


@pytest.mark.actuator
def test_schedule_error_none_agent(publish_agent):
    # Test Error response
    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback")
    publish_agent.callback.reset_mock()
    # subscribe to schedule response topic
    # TODO: verfy topic name - result  vs response
    print ('topic scheule response is :', topics.ACTUATOR_SCHEDULE_RESULT)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=topics.ACTUATOR_SCHEDULE_RESULT,
                                       callback=publish_agent.callback)

    print("requesting a schedule for device0")
    start = str(datetime.now() + timedelta(seconds=10))
    end = str(datetime.now() + timedelta(seconds=20))
    print ('start time for device0', start)
    header = {
        'type': 'NEW_SCHEDULE',
        # 'requesterID': TEST_AGENT,  # The name of the requesting agent.
        'taskID': 'task_schedule_response-1',  # unique (to all tasks) ID for scheduled task.
        'priority': 'LOW'
    }
    msg = [
        ['fakedriver0', start, end]
    ]
    publish_agent.vip.pubsub.publish(peer='pubsub', topic=topics.ACTUATOR_SCHEDULE_REQUEST, headers=header, message=msg)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    gevent.sleep(1)
    print (publish_agent.callback.call_count)
    print (publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    # TODO verify and fix this
    # assert result_header['type'] == 'CANCEL_SCHEDULE'
    assert result_header['taskID'] == 'task_schedule_response-1'
    assert result_message['result'] == FAILURE
    assert result_message['info'] == 'MISSING_AGENT_ID'

@pytest.mark.actuator
def test_schedule_error_missing_agent(publish_agent):
    # Test Error response
    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback")
    publish_agent.callback.reset_mock()
    # subscribe to schedule response topic
    # TODO: verfy topic name - result  vs response
    print ('topic scheule response is :', topics.ACTUATOR_SCHEDULE_RESULT)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=topics.ACTUATOR_SCHEDULE_RESULT,
                                       callback=publish_agent.callback)

    print("requesting a schedule for device0")
    start = str(datetime.now() + timedelta(seconds=10))
    end = str(datetime.now() + timedelta(seconds=20))
    print ('start time for device0', start)
    header = {
        'type': 'NEW_SCHEDULE',
        'requesterID': '',  # The name of the requesting agent.
        'taskID': 'task_schedule_response-1',  # unique (to all tasks) ID for scheduled task.
        'priority': 'LOW'
    }
    msg = [
        ['fakedriver0', start, end]
    ]
    publish_agent.vip.pubsub.publish(peer='pubsub', topic=topics.ACTUATOR_SCHEDULE_REQUEST, headers=header, message=msg)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    gevent.sleep(1)
    print (publish_agent.callback.call_count)
    print (publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    # TODO verify and fix this
    # assert result_header['type'] == 'CANCEL_SCHEDULE'
    assert result_header['taskID'] == 'task_schedule_response-1'
    assert result_message['result'] == FAILURE
    assert result_message['info'] == 'MISSING_AGENT_ID'


@pytest.mark.actuator
def test_schedule_error_duplicate_task(publish_agent):
    # Test Error response
    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback")
    publish_agent.callback.reset_mock()
    # subscribe to schedule response topic
    # TODO: verfy topic name - result  vs response
    print ('topic scheule response is :', topics.ACTUATOR_SCHEDULE_RESULT)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=topics.ACTUATOR_SCHEDULE_RESULT,
                                       callback=publish_agent.callback)

    print("requesting a schedule for device0")

    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=4))
    print ('start time for device0', start)
    msg = [
        ['fakedriver0', start, end]
    ]

    result = publish_agent.vip.rpc.call(
            'platform.actuator',
            'request_new_schedule',
            TEST_AGENT,
            'task_schedule_error',
            'LOW',
            msg).get(timeout=10)
    assert result['result'] == 'SUCCESS'
    header = {
        'type': 'NEW_SCHEDULE',
        'requesterID': TEST_AGENT,  # The name of the requesting agent.
        'taskID': 'task_schedule_error',  # unique (to all tasks) ID for scheduled task.
        'priority': 'LOW'
    }
    publish_agent.vip.pubsub.publish(peer='pubsub', topic=topics.ACTUATOR_SCHEDULE_REQUEST, headers=header, message=msg)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    gevent.sleep(1)
    print (publish_agent.callback.call_count)
    print (publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    # TODO verify and fix this
    # assert result_header['type'] == 'CANCEL_SCHEDULE'
    assert result_header['taskID'] == 'task_schedule_error'
    assert result_message['result'] == FAILURE
    assert result_message['info'] == 'TASK_ID_ALREADY_EXISTS'


@pytest.mark.actuator
def test_schedule_error_missing_priority(publish_agent):
    # Test Error response
    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback")
    publish_agent.callback.reset_mock()
    # subscribe to schedule response topic
    # TODO: verfy topic name - result  vs response
    print ('topic scheule response is :', topics.ACTUATOR_SCHEDULE_RESULT)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=topics.ACTUATOR_SCHEDULE_RESULT,
                                       callback=publish_agent.callback)

    print("requesting a schedule for device0")
    start = str(datetime.now() + timedelta(seconds=10))
    end = str(datetime.now() + timedelta(seconds=20))
    print ('start time for device0', start)
    header = {
        'type': 'NEW_SCHEDULE',
        'requesterID': TEST_AGENT,  # The name of the requesting agent.
        'taskID': 'task_schedule_response-1'  # unique (to all tasks) ID for scheduled task.
        # 'priority': 'LOW'
    }
    msg = [
        ['fakedriver0', start, end]
    ]
    publish_agent.vip.pubsub.publish(peer='pubsub', topic=topics.ACTUATOR_SCHEDULE_REQUEST, headers=header, message=msg)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    gevent.sleep(1)
    print (publish_agent.callback.call_count)
    print (publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    # TODO verify and fix this
    # assert result_header['type'] == 'CANCEL_SCHEDULE'
    assert result_header['taskID'] == 'task_schedule_response-1'
    assert result_message['result'] == FAILURE
    assert result_message['info'] == 'MISSING_PRIORITY'


@pytest.mark.dev
def test_schedule_error_malformed_request(publish_agent):
    # Test Error response
    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback")
    publish_agent.callback.reset_mock()
    # subscribe to schedule response topic
    # TODO: verfy topic name - result  vs response
    print ('topic scheule response is :', topics.ACTUATOR_SCHEDULE_RESULT)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=topics.ACTUATOR_SCHEDULE_RESULT,
                                       callback=publish_agent.callback).get()

    print("requesting a schedule for device0")
    start = str(datetime.now() + timedelta(seconds=10))
    end = str(datetime.now() + timedelta(seconds=20))
    print ('start time for device0', start)
    header = {
        'type': 'NEW_SCHEDULE',
        'requesterID': TEST_AGENT,  # The name of the requesting agent.
        'taskID': 'task_schedule_response-1',  # unique (to all tasks) ID for scheduled task.
        'priority': 'LOW'
    }
    msg = [
        ['fakedriver0', start]
    ]
    publish_agent.vip.pubsub.publish(peer='pubsub', topic=topics.ACTUATOR_SCHEDULE_REQUEST, headers=header, message=msg)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    gevent.sleep(1)
    assert publish_agent.callback.call_count == 1
    print (publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    # TODO verify and fix this
    # assert result_header['type'] == 'CANCEL_SCHEDULE'
    assert result_header['taskID'] == 'task_schedule_response-1'
    assert result_message['result'] == FAILURE
    assert result_message['info'].startswith('MALFORMED_REQUEST')


@pytest.mark.actuator
def test_schedule_announce(publish_agent, volttron_instance1):
    """
    Tests the schedule announcements of actuator. waits for two announcements and checks if the right parameters
    are sent to call back method.
    :param publish_agent: fixture invoked to setup all agents necessary and returns an instance
    of Agent object used for publishing
    :param volttron_instance1: Volttron instance on which test is run
    """
    global actuator_uuid
    # Use a actuator that publishes frequently
    volttron_instance1.stop_agent(actuator_uuid)
    actuator_uuid = volttron_instance1.install_agent(
            agent_dir="services/core/ActuatorAgent",
            config_file="services/core/ActuatorAgent/tests/actuator2.config",
            start=True)
    try:
        publish_agent.actuate0 = MagicMock(name="magic_actuate0")
        announce = topics.ACTUATOR_SCHEDULE_ANNOUNCE(campus='', building='', unit='fakedriver0')
        publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                           prefix=announce,
                                           callback=publish_agent.actuate0)

        print("requesting a schedule for device0")
        start = str(datetime.now() + timedelta(seconds=1))
        end = str(datetime.now() + timedelta(seconds=6))
        print ('start time for device0', start)

        msg = [
            ['fakedriver0', start, end]
        ]

        result = publish_agent.vip.rpc.call(
                'platform.actuator',
                'request_new_schedule',
                TEST_AGENT,
                'task_schedule_announce',
                'LOW',
                msg).get(timeout=10)
        # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
        assert result['result'] == 'SUCCESS'
        gevent.sleep(5)
        assert publish_agent.actuate0.called == True
        assert publish_agent.actuate0.call_count == 2
        args_list1 = publish_agent.actuate0.call_args_list[0][0]
        args_list2 = publish_agent.actuate0.call_args_list[1][0]
        assert args_list1[1] == args_list2[1] == 'platform.actuator'
        assert args_list1[3] == args_list2[3] == 'devices/actuators/schedule/announce/fakedriver0'
        assert args_list1[4]['taskID'] == args_list2[4]['taskID'] == 'task_schedule_announce'
        assert args_list1[4]['requesterID'] == args_list2[4]['requesterID'] == TEST_AGENT
        datetime1 = datetime.strptime(args_list1[4]['time'], '%Y-%m-%d %H:%M:%S')
        datetime2 = datetime.strptime(args_list2[4]['time'], '%Y-%m-%d %H:%M:%S')
        delta = datetime2 - datetime1
        assert delta.seconds == 2
    finally:
        volttron_instance1.stop_agent(actuator_uuid)
        print ("creating instance of actuator with larger publish frequency")
        actuator_uuid = volttron_instance1.install_agent(
                agent_dir="services/core/ActuatorAgent",
                config_file="services/core/ActuatorAgent/tests/actuator.config",
                start=True)


@pytest.mark.actuator
def test_set_value_success1(publish_agent):
    """
    Test setting a float value of a point through pubsub
    Format of expected result
    Header:
    {
    'requesterID': <Agent ID>
    }
    The message contains the value of the actuation point in JSON
    :param publish_agent: fixture invoked to setup all agents necessary and returns an instance
    of Agent object used for publishing
    """
    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback")
    # Subscribe to result of set
    value_topic = topics.ACTUATOR_VALUE(campus='', building='', unit='fakedriver1', point='SampleWritableBool1')
    error_topic = topics.ACTUATOR_ERROR(campus='', building='', unit='fakedriver1', point='SampleWritableBool1')
    print ('value topic', value_topic)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=value_topic,
                                       callback=publish_agent.callback)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=error_topic,
                                       callback=publish_agent.callback)
    print("requesting a schedule for device1")
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=3))
    print ('start time for device1', start)

    msg = [
        ['fakedriver1', start, end]
    ]
    result = publish_agent.vip.rpc.call(
            'platform.actuator',
            'request_new_schedule',
            TEST_AGENT,
            'task_set_value_success1',
            'LOW',
            msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    assert result['result'] == 'SUCCESS'
    # set value
    header = {
        'requesterID': TEST_AGENT
    }

    publish_agent.vip.pubsub.publish('pubsub',
                                     topics.ACTUATOR_SET(campus='', building='', unit='fakedriver1',
                                                         point='SampleWritableBool1'),
                                     headers=header,
                                     message=['On']).get(timeout=10)
    gevent.sleep(1)
    assert publish_agent.callback.call_count == 1
    print ('call args ', publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == value_topic
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['requesterID'] == TEST_AGENT
    assert result_message == ['On']


@pytest.mark.actuator
def test_set_value_success2(publish_agent):
    """
    Test setting a float value of a point through pubsub
    Format of expected result
    Expected Header
    {
    'type': <'NEW_SCHEDULE', 'CANCEL_SCHEDULE'>
    'requesterID': <Agent ID from the request>,
    'taskID': <Task ID from the request>
    }
    Expected message
    {
    'result': <'SUCCESS', 'FAILURE', 'PREEMPTED'>,
    'info': <Failure reason, if any>,
    'data': <Data about the failure or cancellation, if any>
    }
    :param publish_agent: fixture invoked to setup all agents necessary and returns an instance
    of Agent object used for publishing
    """
    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback")
    # Subscribe to result of set
    value_topic = topics.ACTUATOR_VALUE(campus='', building='', unit='fakedriver1', point='SampleWritableFloat1')
    error_topic = topics.ACTUATOR_ERROR(campus='', building='', unit='fakedriver1', point='SampleWritableFloat1')
    print ('value topic', value_topic)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=value_topic,
                                       callback=publish_agent.callback)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=error_topic,
                                       callback=publish_agent.callback)
    print("requesting a schedule for device1")
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=3))
    print ('start time for device1', start)

    msg = [
        ['fakedriver1', start, end]
    ]
    result = publish_agent.vip.rpc.call(
            'platform.actuator',
            'request_new_schedule',
            TEST_AGENT,
            'task_set_value_success2',
            'LOW',
            msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    # print result
    assert result['result'] == 'SUCCESS'
    # set value
    header = {
        'requesterID': TEST_AGENT
    }

    set_topic = topics.ACTUATOR_SET(campus='', building='', unit='fakedriver1', point='SampleWritableFloat1')
    print("set topic: ", set_topic)
    publish_agent.vip.pubsub.publish('pubsub',
                                     set_topic,
                                     headers=header,
                                     message=['0.2']).get(timeout=10)
    gevent.sleep(1)
    assert publish_agent.callback.call_count == 1
    print ('call args ', publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == value_topic
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['requesterID'] == TEST_AGENT
    assert result_message == ['0.2']

@pytest.mark.actuator
def test_set_value_success3(publish_agent):
    """
    Test setting a float value of a point  through pubsub.
    Value is set without enclosing it in an list
    Format of expected result
    Expected Header
    {
    'type': <'NEW_SCHEDULE', 'CANCEL_SCHEDULE'>
    'requesterID': <Agent ID from the request>,
    'taskID': <Task ID from the request>
    }
    Expected message
    {
    'result': <'SUCCESS', 'FAILURE', 'PREEMPTED'>,
    'info': <Failure reason, if any>,
    'data': <Data about the failure or cancellation, if any>
    }
    :param publish_agent: fixture invoked to setup all agents necessary and returns an instance
    of Agent object used for publishing
    """
    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback")
    # Subscribe to result of set
    value_topic = topics.ACTUATOR_VALUE(campus='', building='', unit='fakedriver0', point='SampleWritableFloat1')
    error_topic = topics.ACTUATOR_ERROR(campus='', building='', unit='fakedriver0', point='SampleWritableFloat1')
    print ('value topic', value_topic)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=value_topic,
                                       callback=publish_agent.callback)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=error_topic,
                                       callback=publish_agent.callback)
    print("requesting a schedule for device1")
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=3))
    print ('start time for device1', start)

    msg = [
        ['fakedriver0', start, end]
    ]
    result = publish_agent.vip.rpc.call(
            'platform.actuator',
            'request_new_schedule',
            TEST_AGENT,
            'task_set_value_success2',
            'LOW',
            msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    # print result
    assert result['result'] == 'SUCCESS'
    # set value
    header = {
        'requesterID': TEST_AGENT
    }

    set_topic = topics.ACTUATOR_SET(campus='', building='', unit='fakedriver0', point='SampleWritableFloat1')
    print("set topic: ", set_topic)
    publish_agent.vip.pubsub.publish('pubsub',
                                     set_topic,
                                     headers=header,
                                     message='0.2').get(timeout=10)
    gevent.sleep(1)
    assert publish_agent.callback.call_count == 1
    print ('call args ', publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == value_topic
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['requesterID'] == TEST_AGENT
    assert result_message == '0.2'

@pytest.mark.actuator
def test_set_read_only_point(publish_agent):
    """
    Test setting a value of a point through pubsub
    Format of expected result
    header:
    {
        'requesterID': <Agent ID>
    }
    message:
    {
        'type': <Error Type or name of the exception raised by the request>
        'value': <Specific info about the error>
    }

    :param publish_agent: fixture invoked to setup all agents necessary and returns an instance
    of Agent object used for publishing
    """
    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback")
    # Subscribe to result of set
    value_topic = topics.ACTUATOR_VALUE(campus='', building='', unit='fakedriver0', point='OutsideAirTemperature1')
    error_topic = topics.ACTUATOR_ERROR(campus='', building='', unit='fakedriver0', point='OutsideAirTemperature1')
    print ('value topic', value_topic)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=value_topic,
                                       callback=publish_agent.callback)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=error_topic,
                                       callback=publish_agent.callback)
    print("requesting a schedule for device1")
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=3))
    print ('start time for device1', start)

    msg = [
        ['fakedriver0', start, end]
    ]
    result = publish_agent.vip.rpc.call(
            'platform.actuator',
            'request_new_schedule',
            TEST_AGENT,
            'task_set_read_only_point',
            'LOW',
            msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    # print result
    assert result['result'] == 'SUCCESS'
    # set value
    header = {
        'requesterID': TEST_AGENT
    }

    set_topic = topics.ACTUATOR_SET(campus='', building='', unit='fakedriver0', point='OutsideAirTemperature1')
    print("set topic: ", set_topic)
    publish_agent.vip.pubsub.publish('pubsub',
                                     set_topic,
                                     headers=header,
                                     message=['0.2']).get(timeout=10)
    gevent.sleep(3)
    assert publish_agent.callback.call_count == 1
    print ('call args ', publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == error_topic
    result_header = publish_agent.callback.call_args[0][4]
    # result_message =  publish_agent.callback.call_args[0][5]
    assert result_header['requesterID'] == TEST_AGENT


@pytest.mark.actuator
def test_set_lock_error(publish_agent):
    """
    Test setting a float value of a point through pubsub without an allocation
    Format of expected result
    header:
    {
        'requesterID': <Agent ID>
    }
    message:
    {
        'type': <Error Type or name of the exception raised by the request>
        'value': <Specific info about the error>
    }
    :param publish_agent: fixture invoked to setup all agents necessary and returns an instance
    of Agent object used for publishing
    """
    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback_set_lock_error")
    # Subscribe to result of set
    value_topic = topics.ACTUATOR_VALUE(campus='', building='', unit='fakedriver1', point='SampleWritableFloat1')
    error_topic = topics.ACTUATOR_ERROR(campus='', building='', unit='fakedriver1', point='SampleWritableFloat1')
    print('error topic:', error_topic)
    print ('value topic', value_topic)
    # publish_agent.vip.pubsub.subscribe(peer='pubsub',
    #                            prefix = value_topic,
    #                            callback=publish_agent.callback)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=error_topic,
                                       callback=publish_agent.callback)

    # set value
    header = {
        'requesterID': TEST_AGENT
    }

    set_topic = topics.ACTUATOR_SET(campus='', building='', unit='fakedriver1', point='SampleWritableFloat1')
    print("set topic: ", set_topic)
    publish_agent.vip.pubsub.publish('pubsub',
                                     set_topic,
                                     headers=header,
                                     message=['0.2']).get(timeout=10)
    gevent.sleep(5)
    assert publish_agent.callback.call_count == 1
    print ('call args ', publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == error_topic
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['requesterID'] == TEST_AGENT
    assert result_message[0]['type'] == 'LockError'
    assert result_message[0]['value'] == 'caller does not have this lock'


@pytest.mark.actuator
def test_set_value_error(publish_agent):
    """
    Test setting a value of a point through pubsub
    Format of expected result
    header:
    {
        'requesterID': <Agent ID>
    }
    message:
    {
        'type': <Error Type or name of the exception raised by the request>
        'value': <Specific info about the error>
    }

    :param publish_agent: fixture invoked to setup all agents necessary and returns an instance
    of Agent object used for publishing
    """
    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback_value_error")
    # Subscribe to result of set
    value_topic = topics.ACTUATOR_VALUE(campus='', building='', unit='fakedriver0', point='SampleWritableFloat1')
    error_topic = topics.ACTUATOR_ERROR(campus='', building='', unit='fakedriver0', point='SampleWritableFloat1')
    print ('value topic', value_topic)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=value_topic,
                                       callback=publish_agent.callback)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=error_topic,
                                       callback=publish_agent.callback)
    print("requesting a schedule for device1")
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=3))
    print ('start time for device1', start)

    msg = [
        ['fakedriver0', start, end]
    ]
    result = publish_agent.vip.rpc.call(
            'platform.actuator',
            'request_new_schedule',
            TEST_AGENT,
            'task_value_error',
            'LOW',
            msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    # print result
    assert result['result'] == 'SUCCESS'
    # set value
    header = {
        'requesterID': TEST_AGENT
    }

    set_topic = topics.ACTUATOR_SET(campus='', building='', unit='fakedriver0', point='SampleWritableFloat1')
    print("set topic: ", set_topic)
    publish_agent.vip.pubsub.publish('pubsub',
                                     set_topic,
                                     headers=header,
                                     message='abcd').get(timeout=10)
    gevent.sleep(3)
    assert publish_agent.callback.call_count == 1
    print ('call args ', publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == error_topic
    result_header = publish_agent.callback.call_args[0][4]
    # result_message =  publish_agent.callback.call_args[0][5]
    assert result_header['requesterID'] == TEST_AGENT


# callback happens twice
@pytest.mark.actuator
def test_get_value_success(publish_agent):
    """
    Test getting a float value of a point through pubsub
    Format of expected result
    Expected Header
    {
     'requesterID': <Agent ID from the request>,
     }
    Expected message - contains the value of the point

    :param publish_agent: fixture invoked to setup all agents necessary and returns an instance
    of Agent object used for publishing
    """
    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback")
    # Subscribe to result of set
    value_topic = topics.ACTUATOR_VALUE(campus='', building='', unit='fakedriver1', point='SampleWritableFloat1')
    error_topic = topics.ACTUATOR_ERROR(campus='', building='', unit='fakedriver1', point='SampleWritableFloat1')
    print ('value topic', value_topic)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=value_topic,
                                       callback=publish_agent.callback)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=error_topic,
                                       callback=publish_agent.callback)
    print("requesting a schedule for device1")
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=2))
    print ('start time for device1', start)

    msg = [
        ['fakedriver1', start, end]
    ]
    result = publish_agent.vip.rpc.call(
            'platform.actuator',
            'request_new_schedule',
            TEST_AGENT,
            'task_set_value_success2',
            'LOW',
            msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    # print result
    assert result['result'] == 'SUCCESS'

    # set value
    header = {
        'requesterID': TEST_AGENT
    }

    result = publish_agent.vip.rpc.call(
            'platform.actuator',  # Target agent
            'set_point',  # Method
            TEST_AGENT,  # Requestor
            'fakedriver1/SampleWritableFloat1',  # Point to set
            '20.5'  # New value
    ).get(timeout=10)
    print ("result of set", result)
    get_topic = topics.ACTUATOR_GET(campus='', building='', unit='fakedriver1', point='SampleWritableFloat1')
    print("set topic: ", get_topic)
    publish_agent.vip.pubsub.publish('pubsub',
                                     get_topic,
                                     headers=header).get(timeout=10)
    gevent.sleep(1)
    publish_agent.callback.reset_mock()
    print("call args list", publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    print ('call args ', publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == value_topic
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['requesterID'] == TEST_AGENT
    assert result_message == ['20.5']


# error gets sent to value topic

@pytest.mark.actuator
def test_get_invalid_point(publish_agent):
    """
    Test getting a float value of a point through pubsub with invalid header
    Format of expected result
    Expected Header
    {
     'requesterID': <Agent ID from the request>,
    }
    Expected message
    {
    'type': <Error Type or name of the exception raised by the request>
    'value': <Specific info about the error>
    }

    :param publish_agent: fixture invoked to setup all agents necessary and returns an instance
    of Agent object used for publishing
    """
    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback")
    # Subscribe to result of set
    value_topic = topics.ACTUATOR_VALUE(campus='', building='', unit='fakedriver1', point='SampleWritableFloat12')
    error_topic = topics.ACTUATOR_ERROR(campus='', building='', unit='fakedriver1', point='SampleWritableFloat12')
    print ('value topic', value_topic)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=value_topic,
                                       callback=publish_agent.callback).get()
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=error_topic,
                                       callback=publish_agent.callback).get()

    header = {
        'requesterID': TEST_AGENT
    }
    get_topic = topics.ACTUATOR_GET(campus='', building='', unit='fakedriver1', point='SampleWritableFloat12')
    print("set topic: ", get_topic)
    publish_agent.vip.pubsub.publish('pubsub',
                                     get_topic,
                                     headers=header).get(timeout=10)
    gevent.sleep(1)
    print("call args list", publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    print ('call args ', publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == error_topic
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['requesterID'] == TEST_AGENT
    assert result_message == ['20.5']
