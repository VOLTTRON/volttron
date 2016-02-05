# pytest test cases for Actuator agent
from datetime import datetime, timedelta

import gevent
import gevent.subprocess as subprocess
import pytest
from gevent.subprocess import Popen
from volttron.platform.jsonrpc import RemoteError

TEST_AGENT = 'test-agent'


@pytest.fixture(scope="module")
def publish_agent(request, volttron_instance1):
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

    # 3: Start a fake agent to publish to message bus
    publish_agent = volttron_instance1.build_agent()

    # 4: add a tear down method to stop sqlhistorian agent and the fake agent that published to message bus
    def stop_agent():
        print("In teardown method of module")
        volttron_instance1.stop_agent(actuator_uuid)
        volttron_instance1.stop_agent(master_uuid)
        publish_agent.core.stop()

    request.addfinalizer(stop_agent)
    return publish_agent

@pytest.mark.actuator
def test_schedule_success(publish_agent):
    print("requesting a schedule for device0")
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=1))
    print ('start time for device0', start)

    msg = [
        ['fakedriver0', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        'request_new_schedule',
        TEST_AGENT,
        'task1',
        'LOW',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    print result
    assert result['result'] == 'SUCCESS'

# @pytest.mark.actuator
# def test_schedule_int_agentid(publish_agent):
#
# @pytest.mark.actuator
# def test_schedule_int_taskid(publish_agent):


@pytest.mark.actuator
def test_schedule_missing_taskid(publish_agent):
    print("requesting a schedule for device1")
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=1))
    print ('start time for device0', start)

    msg = [
        ['fakedriver1', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        'request_new_schedule',
        TEST_AGENT,
        '',
        'LOW',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    print result
    assert result['result'] == 'FAILURE'
    assert result['info'] == 'MISSING_TASK_ID'


@pytest.mark.actuator
def test_schedule_missing_agentid(publish_agent):
    print("requesting a schedule for device0")
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=1))
    print ('start time for device0', start)

    msg = [
        ['fakedriver0', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        'request_new_schedule',
        '',
        'task1',
        'LOW',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    print result
    assert result['result'] == 'FAILURE'
    assert result['info'] == 'MISSING_AGENT_ID'


@pytest.mark.actuator
def test_schedule_none_taskid(publish_agent):
    print("requesting a schedule for device1")
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=1))
    print ('start time for device0', start)

    msg = [
        ['fakedriver1', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        'request_new_schedule',
        TEST_AGENT,
        None,
        'LOW',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    print result
    assert result['result'] == 'FAILURE'
    assert result['info'] == 'MISSING_TASK_ID'


@pytest.mark.actuator
def test_schedule_none_agentid(publish_agent):
    print("requesting a schedule for device0")
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=1))
    print ('start time for device0', start)

    msg = [
        ['fakedriver0', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        'request_new_schedule',
        None,
        'task1',
        'LOW',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    print result
    assert result['result'] == 'FAILURE'
    assert result['info'] == 'MISSING_AGENT_ID'


@pytest.mark.actuator
def test_schedule_invalid_priority(publish_agent):
    print("requesting a schedule for device1")
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=1))
    print ('start time for device0', start)

    msg = [
        ['fakedriver1', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        'request_new_schedule',
        TEST_AGENT,
        'task1',
        'LOW2',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    print result
    assert result['result'] == 'FAILURE'
    assert result['info'] == 'INVALID_PRIORITY'


@pytest.mark.actuator
def test_schedule_empty_msg(publish_agent):
    print("requesting a schedule for device1")
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=1))
    print ('start time for device0', start)

    msg = [

    ]
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        'request_new_schedule',
        TEST_AGENT,
        'task1',
        'LOW',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    print result
    assert result['result'] == 'FAILURE'
    assert result['info'] == 'MALFORMED_REQUEST_EMPTY'


@pytest.mark.actuator
def test_schedule_conflict_self(publish_agent):
    print("requesting a schedule for device1")
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=1))
    print ('start time for device0', start)

    msg = [
        ['fakedriver1', start, end],
        ['fakedriver1', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        'request_new_schedule',
        TEST_AGENT,
        'task_conflict_self',
        'LOW',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    print result
    assert result['result'] == 'FAILURE'
    assert result['info'] == 'REQUEST_CONFLICTS_WITH_SELF'


@pytest.mark.actuator
def test_schedule_overlap_success(publish_agent):
    print("requesting a schedule for device1")
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=1))
    end2 = str(datetime.now() + timedelta(seconds=2))
    print ('start time for device0', start)

    msg = [
        ['fakedriver0', start, end],
        ['fakedriver0', end, end2]
    ]
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        'request_new_schedule',
        TEST_AGENT,
        'task_overlap',
        'LOW',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    print result
    assert result['result'] == 'SUCCESS'
    gevent.sleep(1)  # so that the task expires



@pytest.mark.actuator
def test_schedule_conflict(publish_agent):
    print("requesting a schedule for device1")
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=2))
    print ('start time for device0', start)

    msg = [
        ['fakedriver0', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        'request_new_schedule',
        [1234],
        'task_conflict1',
        'LOW',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    print result
    assert result['result'] == 'SUCCESS'
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        'request_new_schedule',
        TEST_AGENT,
        'task_conflict2',
        'LOW',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    print result
    assert result['result'] == 'FAILURE'
    # TODO - expect remote error
    assert result['info'] == 'CONFLICTS_WITH_EXISTING_SCHEDULES'
    gevent.sleep(1)  # so that the task expires


@pytest.mark.actuator
def test_cancel_taskid_agentid_mismatch(publish_agent):
    print("requesting a schedule for device0")
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=2))
    print ('start time for device0', start)

    msg = [
        ['fakedriver0', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        'request_new_schedule',
        TEST_AGENT,
        'invalid_cancel',
        'LOW',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    print result
    assert result['result'] == 'SUCCESS'

    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        'request_cancel_schedule',
        'invalid_agent_for_task',
        'invalid_cancel',
    ).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    print result
    assert result['result'] == 'FAILURE'
    assert result['info'] == 'AGENT_ID_TASK_ID_MISMATCH'
    gevent.sleep(2)  # so that the task expires

@pytest.mark.actuator
def test_cancel_invalid_taskid(publish_agent):
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        'request_cancel_schedule',
        TEST_AGENT,
        'invalid_cancel',
    ).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    print result
    assert result['result'] == 'FAILURE'
    assert result['info'] == 'TASK_ID_DOES_NOT_EXIST'
    gevent.sleep(2)  # so that the task expires

@pytest.mark.actuator
def test_schedule_cancel_success(publish_agent):
    print("requesting a schedule for device0")
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=2))
    print ('start time for device0', start)

    msg = [
        ['fakedriver1', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        'request_new_schedule',
        TEST_AGENT,
        'cancel_success',
        'LOW',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    print result
    assert result['result'] == 'SUCCESS'

    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        'request_cancel_schedule',
        TEST_AGENT,
        'cancel_success',
    ).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    print result
    assert result['result'] == 'SUCCESS'
    gevent.sleep(2)  # so that the task expires


@pytest.mark.actuator
def test_get_default(publish_agent):
    print("*** testing get_default ***")

    result = publish_agent.vip.rpc.call(
        'platform.actuator',  # Target agent
        'get_point',  # Method
        'fakedriver1/SampleWritableFloat1'  # point
    ).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    print result
    assert result == 10.0


@pytest.mark.actuator
def test_get_success(publish_agent):
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=2))
    print ('start time for device0', start)

    msg = [
        ['fakedriver1', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        'request_new_schedule',
        TEST_AGENT,
        'set_and_get',
        'LOW',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    print result
    assert result['result'] == 'SUCCESS'

    result = publish_agent.vip.rpc.call(
        'platform.actuator',  # Target agent
        'set_point',  # Method
        TEST_AGENT,  # Requestor
        'fakedriver1/SampleWritableFloat1',  # Point to set
        '1.0'  # New value
    ).get(timeout=10)
    result = publish_agent.vip.rpc.call(
        'platform.actuator',  # Target agent
        'get_point',  # Method
        'fakedriver1/SampleWritableFloat1'  # point
    ).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    print result
    assert result == '1.0'
    gevent.sleep(1)  # to use up task time


@pytest.mark.actuator
def test_set_success(publish_agent):
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=2))
    print ('start time for device0', start)

    msg = [
        ['fakedriver0', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        'request_new_schedule',
        TEST_AGENT,
        'set_success',
        'LOW',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    print result
    assert result['result'] == 'SUCCESS'

    result = publish_agent.vip.rpc.call(
        'platform.actuator',  # Target agent
        'set_point',  # Method
        TEST_AGENT,  # Requestor
        'fakedriver0/SampleWritableFloat1',  # Point to set
        '2.5'  # New value
    ).get(timeout=10)
    assert result == '2.5'
    gevent.sleep(1)


@pytest.mark.actuator
def test_set_lock_error(publish_agent):
    try:
        result = publish_agent.vip.rpc.call(
            'platform.actuator',  # Target agent
            'set_point',  # Method
            TEST_AGENT,  # Requestor
            'fakedriver1/SampleWritableFloat1',  # Point to set
            '2.5'  # New value
        ).get(timeout=10)
        pytest.fail("Expecting LockError. Code completed without error")
    except RemoteError as e:
        assert e.message == 'caller does not have this lock'


@pytest.mark.actuator
def test_set_value_error(publish_agent):
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=2))
    print ('start time for device0', start)

    msg = [
        ['fakedriver0', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        'request_new_schedule',
        TEST_AGENT,
        'set_success',
        'LOW',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    print result
    assert result['result'] == 'SUCCESS'
    try:
        result = publish_agent.vip.rpc.call(
            'platform.actuator',  # Target agent
            'set_point',  # Method
            TEST_AGENT,  # Requestor
            'fakedriver0/SampleWritableFloat1',  # Point to set
            'On'  # New value
        ).get(timeout=10)
        pytest.fail("Expecting value error but code completed successfully")
    except Exception as e:
        print e.message
        print e.__class__
        assert True
