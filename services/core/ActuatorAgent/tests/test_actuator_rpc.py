# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2015, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

"""
Pytest test cases for testing actuator agent using rpc calls.
"""
from datetime import datetime, timedelta

import gevent
import gevent.subprocess as subprocess
import pytest
from gevent.subprocess import Popen
from mock import MagicMock
from volttron.platform.jsonrpc import RemoteError
from volttron.platform.messaging import topics

REQUEST_CANCEL_SCHEDULE = 'request_cancel_schedule'
REQUEST_NEW_SCHEDULE = 'request_new_schedule'
PLATFORM_ACTUATOR = 'platform.actuator'
TEST_AGENT = 'test-agent'
PRIORITY_LOW = 'LOW'
SUCCESS = 'SUCCESS'
FAILURE = 'FAILURE'


@pytest.fixture(scope="module")
def publish_agent(request, volttron_instance1):
    """
    Fixture used for setting up the environment.
    1. Creates fake driver configs
    2. Starts the master driver agent with the created fake driver agents
    3. Starts the actuator agent
    4. Creates an instance Agent class for publishing and returns it

    :param request: pytest request object
    :param volttron_instance1: instance of volttron in which test cases are run
    :return: an instance of fake agent used for publishing
    """
    # Create master driver config and 2 fake devices each with 6 points
    process = Popen(['python', 'config_builder.py', '--count=4',
                     '--publish-only-depth-all', 'fake',
                     'fake_unit_testing.csv', 'null'],
                    env=volttron_instance1.env,
                    cwd='scripts/scalability-testing',
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE)
    result = process.wait()
    print result
    assert result == 0

    # Start the master driver agent which would intern start the fake driver
    #  using the configs created above
    master_uuid = volttron_instance1.install_agent(
        agent_dir="services/core/MasterDriverAgent",
        config_file="scripts/scalability-testing/configs/master-driver.agent",
        start=True)
    print("agent id: ", master_uuid)
    gevent.sleep(2)  # wait for the agent to start and start the devices

    # Start the actuator agent through which publish agent should communicate
    # to fake device. Start the master driver agent which would intern start
    # the fake driver using the configs created above
    actuator_uuid = volttron_instance1.install_agent(
        agent_dir="services/core/ActuatorAgent",
        config_file="services/core/ActuatorAgent/tests/actuator.config",
        start=True)
    print("agent id: ", actuator_uuid)

    # 3: Start a fake agent to publish to message bus
    publish_agent = volttron_instance1.build_agent()

    # 4: add a tear down method to stop sqlhistorian agent and the fake agent
    #  \that published to message bus
    def stop_agent():
        print("In teardown method of module")
        volttron_instance1.stop_agent(actuator_uuid)
        volttron_instance1.stop_agent(master_uuid)
        publish_agent.core.stop()

    request.addfinalizer(stop_agent)
    return publish_agent


@pytest.fixture(scope="function")
def cancel_schedules(request, publish_agent):
    """
    Fixture used to clean up after every test case.
    Fixture used to clean up after every test case. Cancels any active
    schedules used for a test case so that the same device and time slot can
    be used for the next test case
    :param request: pytest request object
    :param publish_agent: instance Agent class for doing the rpc calls
    :return: Array object that the test methods populates with list of tasks
    that needs to be cancelled after test. Will contain list of dictionary
    objects of the format ({'agentid': agentid, 'taskid': taskid})
    """
    cleanup_parameters = []

    def cleanup():
        for schedule in cleanup_parameters:
            print('Requesting cancel for task:', schedule['taskid'],
                  'from agent:', schedule['agentid'])
            result = publish_agent.vip.rpc.call(
                PLATFORM_ACTUATOR,
                REQUEST_CANCEL_SCHEDULE,
                schedule['agentid'],
                schedule['taskid']).get(timeout=10)
            # sleep so that the message is sent to pubsub before next
            gevent.sleep(1)
            # test monitors callback method calls
            print ("result of cancel ", result)

    request.addfinalizer(cleanup)
    return cleanup_parameters


@pytest.fixture(scope="function")
def revert_devices(request, publish_agent):
    """
    Cleanup method to revert points on device after test run
    :param request: pytest request object
    :param publish_agent: instance Agent class for doing the rpc calls
    :return: Array object that the test methods populates with list of points
    that needs to be reverted after test. Will contain list of dictionary
    objects of the format ({'agentid': agentid, 'device': point_to_revert})
    """
    cleanup_parameters = []

    def cleanup():
        for device in cleanup_parameters:
            print(
            'Requesting revert on device:', device['device'], 'from agent:',
            device['agentid'])
            publish_agent.vip.rpc.call(
                PLATFORM_ACTUATOR,  # Target agent
                'revert_device',  # Method
                device['agentid'],  # Requestor
                device['device']  # Point to revert
            ).get(timeout=10)
            # sleep so that the message is sent to pubsub before next test
            # monitors callback method calls
            gevent.sleep(1)

    request.addfinalizer(cleanup)
    return cleanup_parameters


@pytest.mark.actuator
def test_schedule_success(publish_agent, cancel_schedules):
    """
    Test responses for successful schedule request
 
    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end of
    test so that other tests can use the same device and time slot
    """
    print ("\n**** test_schedule_success ****")
    # used by cancel_schedules
    agentid = TEST_AGENT
    taskid = 'task_schedule_success'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})

    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=1))
    msg = [
        ['fakedriver0', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        PRIORITY_LOW,
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == SUCCESS


@pytest.mark.actuator
def test_schedule_error_int_taskid(publish_agent):
    """
    Test responses for successful schedule request with integer task id

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    """
    print ("\n**** test_schedule_error_int_taskid ****")
    agentid = TEST_AGENT
    taskid = 1234

    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=1))
    msg = [
        ['fakedriver1', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        PRIORITY_LOW,
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == FAILURE
    assert result['info'] == \
           'MALFORMED_REQUEST: TypeError: taskid must be a nonempty string'


@pytest.mark.actuator
def test_schedule_error_int_agentid(publish_agent):
    """
    Test responses for successful schedule request with integer agent id

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    """
    print ("\n**** test_schedule_error_int_agentid ****")
    agentid = 1234
    taskid = 'task_schedule_int_agentid'

    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=1))
    msg = [
        ['fakedriver1', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        PRIORITY_LOW,
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == FAILURE
    assert result['info'] == \
           'MALFORMED_REQUEST: TypeError: agentid must be a nonempty string'


@pytest.mark.actuator
def test_schedule_empty_taskid(publish_agent, cancel_schedules):
    """
    Test responses for successful schedule request when task id is an empty
    string

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end
    of test so that other tests can use the same device and time slot
    """
    print ("\n**** test_schedule_empty_taskid ****")
    # used by cancel_schedules
    agentid = TEST_AGENT
    taskid = ''
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})

    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=1))
    msg = [
        ['fakedriver1', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        PRIORITY_LOW,
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == FAILURE
    assert result['info'] == \
           'MALFORMED_REQUEST: TypeError: taskid must be a nonempty string'


@pytest.mark.actuator
def test_schedule_empty_agentid(publish_agent, cancel_schedules):
    """
    Test responses for successful schedule request when agent id is an
    empty string

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end
    of test so that other tests can use the same device and time slot
    """
    print ("\n**** test_schedule_empty_agentid ****")
    # used by cancel_schedules
    agentid = ''
    taskid = 'task_empty_str_agent'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})

    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=1))
    msg = [
        ['fakedriver0', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        PRIORITY_LOW,
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == FAILURE
    assert result['info'] == \
           'MALFORMED_REQUEST: TypeError: agentid must be a nonempty string'


@pytest.mark.actuator
def test_schedule_error_none_taskid(publish_agent):
    """
    Test error responses for  schedule request with taskid = None

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    """
    print ("\n**** test_schedule_error_none_taskid ****")
    agentid = TEST_AGENT
    taskid = None

    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=1))
    msg = [
        ['fakedriver1', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        PRIORITY_LOW,
        msg).get(timeout=10)
    print result
    assert result['result'] == FAILURE
    assert result['info'] == 'MISSING_TASK_ID'


@pytest.mark.actuator
def test_schedule_error_none_agentid(publish_agent):
    """
    Test error responses for schedule request with agentid = None

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    """
    print ("\n**** test_schedule_error_none_agentid ****")
    agentid = None
    taskid = 'task_none_agentid'

    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=1))
    msg = [
        ['fakedriver0', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        PRIORITY_LOW,
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == FAILURE
    assert result['info'] == 'MISSING_AGENT_ID'


@pytest.mark.actuator
def test_schedule_error_invalid_priority(publish_agent):
    """
    Test error responses for schedule request with an invalid priority

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    """
    print ("\n**** test_schedule_error_invalid_priority ****")
    taskid = 'task_invalid_priority'
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=1))
    msg = [
        ['fakedriver1', start, end]
    ]

    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        TEST_AGENT,
        taskid,
        'LOW2',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == FAILURE
    assert result['info'] == 'INVALID_PRIORITY'


@pytest.mark.actuator
def test_schedule_error_empty_message(publish_agent):
    """
    Test error responses for schedule request with an empty message

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    """
    print ("\n**** test_schedule_error_empty_message ****")
    taskid = 'task_empty_message'

    msg = [

    ]
    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        TEST_AGENT,
        taskid,
        PRIORITY_LOW,
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == FAILURE
    assert result['info'] == 'MALFORMED_REQUEST_EMPTY'


@pytest.mark.actuator
def test_schedule_error_duplicate_task(publish_agent, cancel_schedules):
    """
    Test error responses for schedule request with task id that is already
    in use

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end
    of test so that other tests can use the same device and time slot
    """
    print ("\n**** test_schedule_error_duplicate_task ****")
    # used by cancel_schedules
    agentid = TEST_AGENT
    taskid = 'task_schedule_duplicate_id'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})

    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=1))
    msg = [
        ['fakedriver1', start, end]
    ]

    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        PRIORITY_LOW,
        msg).get(timeout=10)
    assert result['result'] == SUCCESS
    # new request with same task id
    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        PRIORITY_LOW,
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == FAILURE
    assert result['info'] == 'TASK_ID_ALREADY_EXISTS'


@pytest.mark.actuator
def test_schedule_error_none_priority(publish_agent):
    """
    Test error responses for schedule request with priority = None

    :param publish_agent: fixture invoked to setup all agents necessary
    and returns an instance of Agent object used for publishing
    """
    print ("\n**** test_schedule_error_none_priority ****")
    taskid = 'task_none_priority'

    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=1))
    msg = [
        ['fakedriver0', start, end]
    ]

    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        TEST_AGENT,
        taskid,
        None,
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == FAILURE
    assert result['info'] == 'MISSING_PRIORITY'


@pytest.mark.actuator
def test_schedule_error_malformed_request(publish_agent):
    """
    Test error responses for schedule request with malformed request -
    request with only a device name and start time and no stop time

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    """
    print ("\n**** test_schedule_error_malformed_request ****")
    taskid = 'task_malformed_request'

    start = str(datetime.now())
    # end = str(datetime.now() + timedelta(seconds=1))
    msg = [
        ['fakedriver0', start]
    ]

    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        TEST_AGENT,
        taskid,
        PRIORITY_LOW,
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == FAILURE
    assert result['info'].startswith('MALFORMED_REQUEST')


@pytest.mark.actuator
def test_schedule_premept_self(publish_agent, cancel_schedules):
    """
    Test error response for schedule request through pubsub.
    Test schedule preemption by a higher priority task from the same agent.

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end
    of test so that other tests can use the same device and time slot
    """
    print ("\n**** test_schedule_premept_self ****")
    # used by cancel_schedules
    agentid = TEST_AGENT
    taskid = 'task_high_priority'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})
    # add low prority task as well since it won't get cancelled till
    # end of grace time
    cancel_schedules.append(
        {'agentid': agentid, 'taskid': 'task_low_priority'})

    publish_agent.callback = MagicMock(name="callback")
    publish_agent.callback.reset_mock()
    # subscribe to schedule response topic
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=topics.ACTUATOR_SCHEDULE_RESULT,
                                       callback=publish_agent.callback).get()

    start = str(datetime.now() + timedelta(seconds=10))
    end = str(datetime.now() + timedelta(seconds=20))
    msg = [
        ['fakedriver1', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        agentid,
        'task_low_priority',
        'LOW_PREEMPT',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == SUCCESS
    # wait for above call's success response to publish_agent.callback method
    gevent.sleep(1)
    publish_agent.callback.reset_mock()

    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        'HIGH',
        msg).get(timeout=10)
    assert result['result'] == SUCCESS
    # wait for 2 callbacks - success msg for task_high_priority and preempt
    # msg for task_low_priority
    gevent.sleep(6)
    print ('call args list:', publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 2

    # Grab the args of callback and verify
    call_args1 = publish_agent.callback.call_args_list[0][0]
    call_args2 = publish_agent.callback.call_args_list[1][0]

    assert call_args1[1] == PLATFORM_ACTUATOR
    assert call_args1[3] == topics.ACTUATOR_SCHEDULE_RESULT

    # initialize 0 to schedule response and 1 to cancel response
    schedule_header = call_args1[4]
    schedule_message = call_args1[5]
    cancel_header = call_args2[4]
    cancel_message = call_args2[5]

    # check if order is reversed: 0 is cancelresponse and 1 is new schedule
    if call_args1[4]['type'] == 'CANCEL_SCHEDULE':
        assert call_args2[4]['type'] == 'NEW_SCHEDULE'
        cancel_header = call_args1[4]
        cancel_message = call_args1[5]
        schedule_header = call_args2[4]
        schedule_message = call_args2[5]
    else:
        assert call_args1[4]['type'] == 'NEW_SCHEDULE'
        assert call_args2[4]['type'] == 'CANCEL_SCHEDULE'
        # values remain as initialized above if/else

    assert schedule_header['type'] == 'NEW_SCHEDULE'
    assert schedule_header['taskID'] == taskid
    assert schedule_header['requesterID'] == TEST_AGENT
    assert schedule_message['result'] == SUCCESS

    assert cancel_header['taskID'] == 'task_low_priority'
    assert cancel_message['data']['agentID'] == TEST_AGENT
    assert cancel_message['data']['taskID'] == taskid
    assert cancel_message['result'] == 'PREEMPTED'


@pytest.mark.actuator
def test_schedule_premept_active_task(publish_agent, cancel_schedules):
    """
    Test error response for schedule request.
    Test schedule preemption of a actively running task with priority
    LOW_PREEMPT by a higher priority task from the a different agent.

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end
    of test so that other tests can use the same device and time slot
    """
    print ("\n**** test_schedule_premept_active_task ****")
    # used by cancel_schedules
    agentid = 'new_agent'
    taskid = 'task_high_priority2'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})
    # add low prority task as well since it won't get cancelled till
    # end of grace time
    cancel_schedules.append(
        {'agentid': TEST_AGENT, 'taskid': 'task_low_priority2'})

    publish_agent.callback = MagicMock(name="callback")
    publish_agent.callback.reset_mock()
    # subscribe to schedule response topic
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=topics.ACTUATOR_SCHEDULE_RESULT,
                                       callback=publish_agent.callback).get()

    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=15))
    msg = [
        ['fakedriver1', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        TEST_AGENT,
        'task_low_priority2',
        'LOW_PREEMPT',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == SUCCESS
    # wait for above call's success response to publish_agent.callback method
    gevent.sleep(1)
    publish_agent.callback.reset_mock()

    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        'HIGH',
        msg).get(timeout=10)
    assert result['result'] == SUCCESS
    # wait for 2 callbacks - success msg for task_high_priority and preempt
    # msg for task_low_priority
    gevent.sleep(6)
    print ('call args list:', publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 2

    # Grab the args of callback and verify
    call_args1 = publish_agent.callback.call_args_list[0][0]
    call_args2 = publish_agent.callback.call_args_list[1][0]

    assert call_args1[1] == PLATFORM_ACTUATOR
    assert call_args1[3] == topics.ACTUATOR_SCHEDULE_RESULT

    # initialize 0 to schedule response and 1 to cancel response
    schedule_header = call_args1[4]
    schedule_message = call_args1[5]
    print ("call args of 1 ", publish_agent.callback.call_args_list[1])
    cancel_header = call_args2[4]
    cancel_message = call_args2[5]

    # check if order is reversed: 0 is cancelresponse and 1 is new schedule
    if call_args1[4]['type'] == 'CANCEL_SCHEDULE':
        assert call_args2[4]['type'] == 'NEW_SCHEDULE'
        cancel_header = call_args1[4]
        cancel_message = call_args1[5]
        schedule_header = call_args2[4]
        schedule_message = call_args2[5]
    else:
        assert call_args1[4]['type'] == 'NEW_SCHEDULE'
        assert call_args2[4]['type'] == 'CANCEL_SCHEDULE'
        # values remain as initialized above if/else

    assert schedule_header['type'] == 'NEW_SCHEDULE'
    assert schedule_header['taskID'] == taskid
    assert schedule_header['requesterID'] == agentid
    assert schedule_message['result'] == SUCCESS

    assert cancel_header['taskID'] == 'task_low_priority2'
    assert cancel_message['data']['agentID'] == agentid
    assert cancel_message['data']['taskID'] == taskid
    assert cancel_message['result'] == 'PREEMPTED'


@pytest.mark.actuator
def test_schedule_premept_active_task_gracetime(publish_agent,
                                                cancel_schedules):
    """
    Test error response for schedule request.
    Test schedule preemption of a actively running task with priority LOW by
    a higher priority task from the a different agent. Try setting a point
    before the end of grace time of lower priority task. set operation should
    fail

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end
    of test so that other tests can use the same device and time slot
    """
    print ("\n**** test_schedule_premept_active_task_gracetime ****")
    # used by cancel_schedules
    agentid = 'new_agent'
    taskid = 'task_high_priority3'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})
    # add low prority task as well since it won't get cancelled till
    # end of grace time
    cancel_schedules.append(
        {'agentid': TEST_AGENT, 'taskid': 'task_low_priority3'})

    publish_agent.callback = MagicMock(name="callback")
    publish_agent.callback.reset_mock()
    # subscribe to schedule response topic
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=topics.ACTUATOR_SCHEDULE_RESULT,
                                       callback=publish_agent.callback).get()

    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=20))
    msg = [
        ['fakedriver1', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        TEST_AGENT,
        'task_low_priority3',
        'LOW_PREEMPT',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == SUCCESS
    # wait for above call's success response to publish_agent.callback method
    gevent.sleep(1)
    publish_agent.callback.reset_mock()

    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        'HIGH',
        msg).get(timeout=10)

    assert result['result'] == SUCCESS
    # wait for 2 callbacks - success msg for task_high_priority and preempt
    # msg for task_low_priority
    gevent.sleep(6)
    print ('call args list:', publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 2

    # Grab the args of callback and verify
    call_args1 = publish_agent.callback.call_args_list[0][0]
    call_args2 = publish_agent.callback.call_args_list[1][0]

    assert call_args1[1] == PLATFORM_ACTUATOR
    assert call_args1[3] == topics.ACTUATOR_SCHEDULE_RESULT

    # initialize 0 to schedule response and 1 to cancel response
    schedule_header = call_args1[4]
    schedule_message = call_args1[5]
    cancel_header = call_args2[4]
    cancel_message = call_args2[5]

    # check if order is reversed: 0 is cancelresponse and 1 is new schedule
    if call_args1[4]['type'] == 'CANCEL_SCHEDULE':
        assert call_args2[4]['type'] == 'NEW_SCHEDULE'
        cancel_header = call_args1[4]
        cancel_message = call_args1[5]
        schedule_header = call_args2[4]
        schedule_message = call_args2[5]
    else:
        assert call_args1[4]['type'] == 'NEW_SCHEDULE'
        assert call_args2[4]['type'] == 'CANCEL_SCHEDULE'
        # values remain as initialized above if/else

    assert schedule_header['type'] == 'NEW_SCHEDULE'
    assert schedule_header['taskID'] == taskid
    assert schedule_header['requesterID'] == agentid
    assert schedule_message['result'] == SUCCESS

    assert cancel_header['taskID'] == 'task_low_priority3'
    assert cancel_message['data']['agentID'] == agentid
    assert cancel_message['data']['taskID'] == taskid
    assert cancel_message['result'] == 'PREEMPTED'

    # High priority task's schedule request should succeed but it should not
    # be able to start write to the device till active task's (
    # 'task_low_priority3') grace time is over
    try:
        result = publish_agent.vip.rpc.call(
            PLATFORM_ACTUATOR,  # Target agent
            'set_point',  # Method
            agentid,  # Requestor
            'fakedriver1/SampleWritableFloat1',  # Point to set
            2.5  # New value
        ).get(timeout=10)
        pytest.fail('Expecting LockError. Code returned: {}'.format(result))
    except RemoteError as e:
        assert e.exc_info['exc_type'] == 'actuator.agent.LockError'
        assert e.message == 'caller ({}) does not have this lock'.format(
            agentid)


@pytest.mark.actuator
def test_schedule_premept_error_active_task(publish_agent, cancel_schedules):
    """
    Test error response for schedule request.
    Test schedule preemption of a actively running task with priority LOW by
    a higher priority task from the a different agent. It should fail as the
    LOW priority task's time window is active

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end
    of test so that other tests can use the same device and time slot
    """
    print ("\n**** test_schedule_premept_error_active_task ****")
    # used by cancel_schedules
    agentid = TEST_AGENT
    taskid = 'task_low_priority3'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})

    publish_agent.callback = MagicMock(name="callback")
    publish_agent.callback.reset_mock()
    # subscribe to schedule response topic
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=topics.ACTUATOR_SCHEDULE_RESULT,
                                       callback=publish_agent.callback).get()

    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=10))
    msg = [
        ['fakedriver1', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        PRIORITY_LOW,
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == SUCCESS
    # wait for above call's success response to publish_agent.callback method
    gevent.sleep(1)
    publish_agent.callback.reset_mock()

    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        agentid,
        'failed_high_priority_task',
        'HIGH',
        msg).get(timeout=10)

    assert result['result'] == FAILURE
    assert result['info'] == 'CONFLICTS_WITH_EXISTING_SCHEDULES'
    assert result['data'][TEST_AGENT].keys()[0] == taskid


@pytest.mark.actuator
def test_schedule_premept_future_task(publish_agent, cancel_schedules):
    """
    Test error response for schedule request.
    Test schedule preemption of a future task with priority LOW by a higher
    priority task from the a different agent.

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end
    of test so that other tests can use the same device and time slot
    """
    print ("\n**** test_schedule_premept_future_task ****")
    # used by cancel_schedules
    agentid = 'new_agent'
    taskid = 'task_high_priority4'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})
    # add low prority task as well since it won't get cancelled till end of
    # grace time
    cancel_schedules.append(
        {'agentid': TEST_AGENT, 'taskid': 'task_low_priority4'})

    publish_agent.callback = MagicMock(name="callback")
    publish_agent.callback.reset_mock()
    # subscribe to schedule response topic
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=topics.ACTUATOR_SCHEDULE_RESULT,
                                       callback=publish_agent.callback).get()

    start = str(datetime.now() + timedelta(seconds=10))
    end = str(datetime.now() + timedelta(seconds=20))
    msg = [
        ['fakedriver2', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        TEST_AGENT,
        'task_low_priority4',
        'LOW',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == SUCCESS
    # wait for above call's success response to publish_agent.callback method
    gevent.sleep(1)
    publish_agent.callback.reset_mock()

    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        'HIGH',
        msg).get(timeout=10)
    assert result['result'] == SUCCESS
    # wait for 2 callbacks - success msg for task_high_priority and preempt
    # msg for task_low_priority
    gevent.sleep(6)
    print ('call args list:', publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 2

    # Grab the args of callback and verify
    call_args1 = publish_agent.callback.call_args_list[0][0]
    call_args2 = publish_agent.callback.call_args_list[1][0]

    assert call_args1[1] == PLATFORM_ACTUATOR
    assert call_args1[3] == topics.ACTUATOR_SCHEDULE_RESULT

    # initialize 0 to schedule response and 1 to cancel response
    schedule_header = call_args1[4]
    schedule_message = call_args1[5]
    print ("call args of 1 ", publish_agent.callback.call_args_list[1])
    cancel_header = call_args2[4]
    cancel_message = call_args2[5]

    # check if order is reversed: 0 is cancelresponse and 1 is new schedule
    if call_args1[4]['type'] == 'CANCEL_SCHEDULE':
        assert call_args2[4]['type'] == 'NEW_SCHEDULE'
        cancel_header = call_args1[4]
        cancel_message = call_args1[5]
        schedule_header = call_args2[4]
        schedule_message = call_args2[5]
    else:
        assert call_args1[4]['type'] == 'NEW_SCHEDULE'
        assert call_args2[4]['type'] == 'CANCEL_SCHEDULE'
        # values remain as initialized above if/else

    assert schedule_header['type'] == 'NEW_SCHEDULE'
    assert schedule_header['taskID'] == taskid
    assert schedule_header['requesterID'] == agentid
    assert schedule_message['result'] == SUCCESS

    assert cancel_header['taskID'] == 'task_low_priority4'
    assert cancel_message['data']['agentID'] == agentid
    assert cancel_message['data']['taskID'] == taskid
    assert cancel_message['result'] == 'PREEMPTED'


@pytest.mark.actuator
def test_schedule_conflict_self(publish_agent):
    """
    Test error response for schedule request. Test schedule with conflicting
    time slots in the same request

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    """
    print ("\n**** test_schedule_conflict_self ****")
    # used by cancel_schedules
    taskid = 'task_self_conflict'
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=1))

    msg = [
        ['fakedriver1', start, end],
        ['fakedriver1', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        TEST_AGENT,
        taskid,
        PRIORITY_LOW,
        msg).get(timeout=10)

    print result
    assert result['result'] == FAILURE
    assert result['info'] == 'REQUEST_CONFLICTS_WITH_SELF'


@pytest.mark.actuator
def test_schedule_conflict(publish_agent, cancel_schedules):
    """
    Test schedule conflict with existing schdeule

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end of
    test so that other tests can use the same device and time slot
    """
    print ("\n**** test_schedule_conflict ****")
    # set agentid and task id for  cancel_schedules fixture
    agentid = TEST_AGENT
    taskid = 'task_conflict1'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})

    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=2))

    msg = [
        ['fakedriver0', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        PRIORITY_LOW,
        msg).get(timeout=10)
    print result
    assert result['result'] == SUCCESS

    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        TEST_AGENT,
        'task_conflict2',
        PRIORITY_LOW,
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == FAILURE
    assert result['info'] == 'CONFLICTS_WITH_EXISTING_SCHEDULES'


@pytest.mark.actuator
def test_schedule_overlap_success(publish_agent, cancel_schedules):
    """
    Test schedule where stop time of one requested time slot is the same as
    start time of another requested time slot.
    Expected Result : SUCCESS

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end
    of test so that other tests can use the same device and time slot
    """
    print ("\n**** test_schedule_overlap_success ****")
    # set agentid and task id for  cancel_schedules fixture
    agentid = TEST_AGENT
    taskid = 'task_overlap'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})

    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=1))
    end2 = str(datetime.now() + timedelta(seconds=2))

    msg = [
        ['fakedriver0', start, end],
        ['fakedriver0', end, end2]
    ]
    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        PRIORITY_LOW,
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == SUCCESS


@pytest.mark.actuator
def test_cancel_error_invalid_taskid(publish_agent):
    """
    Test error responses for schedule request. Test invalid task id

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance
    of Agent object used for publishing
    """
    print ("\n**** test_cancel_error_invalid_taskid ****")
    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_CANCEL_SCHEDULE,
        TEST_AGENT,
        'invalid_cancel',
    ).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == FAILURE
    assert result['info'] == 'TASK_ID_DOES_NOT_EXIST'


@pytest.mark.actuator
def test_cancel_error_taskid_agentid_mismatch(publish_agent, cancel_schedules):
    """
    Test error responses for schedule request. Test invalid task id

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end
    of test so that other tests can use the same device and time slot
    """
    print ("\n**** test_cancel_error_taskid_agentid_mismatch ****")
    agentid = TEST_AGENT
    taskid = 'invalid_cancel'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})

    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=2))
    msg = [
        ['fakedriver0', start, end]
    ]

    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        PRIORITY_LOW,
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == SUCCESS

    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_CANCEL_SCHEDULE,
        'invalid_agent_for_task',
        taskid,
    ).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == FAILURE
    assert result['info'] == 'AGENT_ID_TASK_ID_MISMATCH'


@pytest.mark.actuator
def test_cancel_success(publish_agent):
    """
    Test successful schedule cancel

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    """
    print ("\n**** test_cancel_success ****")

    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=2))
    msg = [
        ['fakedriver1', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        TEST_AGENT,
        'cancel_success',
        PRIORITY_LOW,
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == SUCCESS

    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_CANCEL_SCHEDULE,
        TEST_AGENT,
        'cancel_success',
    ).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == SUCCESS


@pytest.mark.actuator
def test_get_default(publish_agent):
    """
    Test get default value of a point

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    """
    print ("\n**** test_get_default ****")

    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,  # Target agent
        'get_point',  # Method
        'fakedriver1/SampleWritableFloat1'  # point
    ).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result == 10.0


@pytest.mark.actuator
def test_get_success(publish_agent, cancel_schedules):
    """
    Test getting a float value of a point through pubsub
    Expected Result - value of the point

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at
    the end of test so that other tests can use the same device and time slot
    """
    print ("\n**** test_get_value_success ****")
    agentid = TEST_AGENT
    taskid = 'task_set_and_get'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})

    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=2))
    msg = [
        ['fakedriver1', start, end]
    ]

    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        PRIORITY_LOW,
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == SUCCESS

    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,  # Target agent
        'set_point',  # Method
        agentid,  # Requestor
        'fakedriver1/SampleWritableFloat1',  # Point to set
        1.0  # New value
    ).get(timeout=10)
    assert result == 1.0

    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,  # Target agent
        'get_point',  # Method
        'fakedriver1/SampleWritableFloat1'  # point
    ).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result == 1.0


@pytest.mark.actuator
def test_get_error_invalid_point(publish_agent):
    """
    Test getting a float value of a point through pubsub with invalid point

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    """
    print ("\n**** test_get_error_invalid_point ****")
    try:
        result = publish_agent.vip.rpc.call(
            PLATFORM_ACTUATOR,  # Target agent
            'get_point',  # Method
            'fakedriver1/SampleWritableFloat123').get(timeout=10)
        pytest.fail('Expecting RemoteError for accessing invalid point. '
                    'Code returned {}'.format(result))
    except RemoteError as e:
        assert e.message.find(
            'Point not configured on device: SampleWritableFloat123') != -1


@pytest.mark.actuator
def test_set_value_float(publish_agent, cancel_schedules, revert_devices):
    """
    Test setting a float value of a point through rpc
    Expected result = value of the actuation point

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end
    of test so that other tests can use the same device and time slot
    """
    print ("\n**** test_set_float_value ****")
    taskid = 'task_set_float_value'
    agentid = TEST_AGENT
    device = 'fakedriver0'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})
    revert_devices.append({'agentid': agentid, 'device': device})

    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=2))
    msg = [
        [device, start, end]
    ]
    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        PRIORITY_LOW,
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == SUCCESS

    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,  # Target agent
        'set_point',  # Method
        agentid,  # Requestor
        'fakedriver0/SampleWritableFloat1',  # Point to set
        2.5  # New value
    ).get(timeout=10)
    assert result == 2.5


@pytest.mark.actuator
def test_revert_point(publish_agent, cancel_schedules):
    """
    Test setting a float value of a point through rpc
    Expected result = value of the actuation point

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end
    of test so that other tests can use the same device and time slot
    """
    print ("\n**** test_set_float_value ****")
    taskid = 'test_revert_point'
    agentid = TEST_AGENT
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})

    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=2))
    msg = [
        ['fakedriver0', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        PRIORITY_LOW,
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == SUCCESS

    initial_value = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,  # Target agent
        'get_point',  # Method
        'fakedriver0/SampleWritableFloat1',  # Point to get
    ).get(timeout=10)

    test_value = initial_value + 1.0

    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,  # Target agent
        'set_point',  # Method
        agentid,  # Requestor
        'fakedriver0/SampleWritableFloat1',  # Point to set
        test_value  # New value
    ).get(timeout=10)
    assert result == test_value

    publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,  # Target agent
        'revert_point',  # Method
        agentid,  # Requestor
        'fakedriver0/SampleWritableFloat1'  # Point to revert
    ).get(timeout=10)

    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,  # Target agent
        'get_point',  # Method
        'fakedriver0/SampleWritableFloat1',  # Point to get
    ).get(timeout=10)
    # Value taken from fake_unit_testing.csv
    assert result == initial_value


@pytest.mark.actuator
def test_revert_device(publish_agent, cancel_schedules):
    """
    Test setting a float value of a point through rpc
    Expected result = value of the actuation point

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end
    of test so that other tests can use the same device and time slot
    """
    print ("\n**** test_set_float_value ****")
    taskid = 'test_revert_point'
    agentid = TEST_AGENT
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})

    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=2))
    msg = [
        ['fakedriver0', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        PRIORITY_LOW,
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == SUCCESS

    initial_value = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,  # Target agent
        'get_point',  # Method
        'fakedriver0/SampleWritableFloat1',  # Point to get
    ).get(timeout=10)

    test_value = initial_value + 1.0

    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,  # Target agent
        'set_point',  # Method
        agentid,  # Requestor
        'fakedriver0/SampleWritableFloat1',  # Point to set
        test_value  # New value
    ).get(timeout=10)
    assert result == test_value

    publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,  # Target agent
        'revert_device',  # Method
        agentid,  # Requestor
        'fakedriver0'  # Point to revert
    ).get(timeout=10)

    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,  # Target agent
        'get_point',  # Method
        'fakedriver0/SampleWritableFloat1',  # Point to get
    ).get(timeout=10)
    # Value taken from fake_unit_testing.csv
    assert result == initial_value


@pytest.mark.actuator
def test_set_error_array(publish_agent, cancel_schedules):
    """
    Test setting a array of single float value of a point. Should return
    type error

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end
    of test so that other tests can use the same device and time slot
    """
    print ("\n**** test_set_error_array ****")
    # set agentid and task id for  cancel_schedules fixture
    agentid = TEST_AGENT
    taskid = 'task_set_float_array_value'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})

    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=2))
    msg = [
        ['fakedriver0', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        PRIORITY_LOW,
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == SUCCESS
    try:
        result = publish_agent.vip.rpc.call(
            PLATFORM_ACTUATOR,  # Target agent
            'set_point',  # Method
            agentid,  # Requestor
            'fakedriver0/SampleWritableFloat1',  # Point to set
            [2.5]  # New value
        ).get(timeout=10)
        pytest.fail('Expecting RemoteError for trying to set array on point '
                    'that expects float. Code returned {}'.format(result))
    except RemoteError as e:
        assert e.message == \
               "TypeError('float() argument must be a string or a number')"


@pytest.mark.actuator
def test_set_lock_error(publish_agent):
    """
    Test setting a float value of a point through rpc without an allocation
    Expected result
    Remote Error with message 'caller does not have this lock'
        'type': 'LockError'
        'value':
    }
    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    """
    try:
        result = publish_agent.vip.rpc.call(
            PLATFORM_ACTUATOR,  # Target agent
            'set_point',  # Method
            TEST_AGENT,  # Requestor
            'fakedriver1/SampleWritableFloat1',  # Point to set
            '2.5'  # New value
        ).get(timeout=10)
        pytest.fail('Expecting LockError. Code returned: {}'.format(result))
    except RemoteError as e:
        assert e.exc_info['exc_type'] == 'actuator.agent.LockError'
        assert e.message == 'caller ({}) does not have this lock'.format(
            TEST_AGENT)


@pytest.mark.actuator
def test_set_value_error(publish_agent, cancel_schedules):
    """
    Test setting a wrong type value of a point through rpc


    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end
    of test so that other tests can use the same device and time slot
    """
    print ("\n**** test_set_value_error ****")
    agentid = TEST_AGENT
    taskid = 'task_set_value_error'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})

    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=2))

    msg = [
        ['fakedriver0', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        PRIORITY_LOW,
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == SUCCESS
    try:
        result = publish_agent.vip.rpc.call(
            'platform.actuator',  # Target agent
            'set_point',  # Method
            agentid,  # Requestor
            'fakedriver0/SampleWritableFloat1',  # Point to set
            'On').get(timeout=10)
        pytest.fail(
            "Expecting ValueError but code returned: {}".format(result))
    except RemoteError as e:
        assert e.message == "ValueError('could not convert string to float: " \
                            "On')"


@pytest.mark.actuator
def test_set_error_none_agent(publish_agent, cancel_schedules):
    """
    Test setting a value of a point through rpc with agentid=None


    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end
    of test so that other tests can use the same device and time slot
    """
    print ("\n**** test_set_error_none_agent ****")
    agentid = TEST_AGENT
    taskid = 'task_set_none_agent'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})

    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=2))

    msg = [
        ['fakedriver0', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        PRIORITY_LOW,
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == SUCCESS

    try:
        result = publish_agent.vip.rpc.call(
            'platform.actuator',  # Target agent
            'set_point',  # Method
            None,  # Requestor
            'fakedriver0/SampleWritableFloat1',  # Point to set
            'On'  # New value
        ).get(timeout=10)
        pytest.fail(
            "Expecting value error but code returned: {}".format(result))
    except RemoteError as e:
        assert e.message == 'Agent id must be a nonempty string'
        assert e.exc_info['exc_type'] == 'TypeError'


@pytest.mark.actuator
def test_set_error_read_only_point(publish_agent, cancel_schedules):
    """
    Test setting a value of a read only point through pubsub

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end
    of test so that other tests can use the same device and time slot
    """
    print ("\n**** test_set_read_only_point ****")
    agentid = TEST_AGENT
    taskid = 'task_set_readonly_point'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})

    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=2))

    msg = [
        ['fakedriver0', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        PRIORITY_LOW,
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': SUCCESS}
    print result
    assert result['result'] == SUCCESS

    try:
        result = publish_agent.vip.rpc.call(
            'platform.actuator',  # Target agent
            'set_point',  # Method
            agentid,  # Requestor
            'fakedriver0/OutsideAirTemperature1',  # Point to set
            1.2  # New value
        ).get(timeout=10)
        pytest.fail(
            'Expecting RemoteError but code returned: {}'.format(result))
    except RemoteError as e:
        assert e.message == "IOError('Trying to write to a point configured " \
                            "read only: OutsideAirTemperature1')"
