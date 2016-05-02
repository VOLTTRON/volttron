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
Pytest test cases for testing actuator agent using pubsub calls. Tests 3.0
actuator agent with both 2.0 and 3.0 publish agents
"""

from datetime import datetime, timedelta

import gevent
import gevent.subprocess as subprocess
import pytest
from gevent.subprocess import Popen
from mock import MagicMock
from volttron.platform.agent import PublishMixin
from volttron.platform.messaging import topics
from volttron.platform.agent import utils

FAILURE = 'FAILURE'
SUCCESS = 'SUCCESS'
PLATFORM_ACTUATOR = 'platform.actuator'
TEST_AGENT = 'test-agent'
actuator_uuid = None
REQUEST_CANCEL_SCHEDULE = 'request_cancel_schedule'
REQUEST_NEW_SCHEDULE = 'request_new_schedule'
publish_agent_v2 = None


@pytest.fixture(scope="function")
def cancel_schedules(request, publish_agent):
    """
    Fixture used to clean up after every test case.
    Fixture used to clean up after every test case. Cancels any active
    schedules used for a test case so that the same device and time slot
    can
    be used for the next test case
    :param request: pytest request object
    :param publish_agent: instance Agent class for doing the rpc calls
    :return: Array object that the test methods populates with list of
    tasks
    that needs to be cancelled after test. Will contain list of dictionary
    objects of the format ({'agentid': agentid, 'taskid': taskid})
    """
    cleanup_parameters = []

    def cleanup():
        for schedule in cleanup_parameters:
            print(
                'Requesting cancel for task:', schedule['taskid'],
                'from agent:',
                schedule['agentid'])
            result = publish_agent.vip.rpc.call(
                PLATFORM_ACTUATOR,
                REQUEST_CANCEL_SCHEDULE,
                schedule['agentid'],
                schedule['taskid']).get(timeout=10)
            # sleep so that the message is sent to pubsub
            # before next test monitors callback method calls
            gevent.sleep(1)
            print ("result of cancel ", result)

    request.addfinalizer(cleanup)
    return cleanup_parameters


@pytest.fixture(scope="function")
def revert_devices(request, publish_agent):
    """
    Cleanup method to revert points on device after test run
    :param request: pytest request object
    :param publish_agent: instance Agent class for doing the rpc calls
    :return: Array object that the test methods populates with list of
    points
    that needs to be reverted after test. Will contain list of dictionary
    objects of the format ({'agentid': agentid, 'device': point_to_revert})
    """
    cleanup_parameters = []

    def cleanup():
        for device in cleanup_parameters:
            print(
                'Requesting revert on device:', device['device'],
                'from agent:',
                device['agentid'])
            publish_agent.vip.rpc.call(
                PLATFORM_ACTUATOR,  # Target agent
                'revert_device',  # Method
                device['agentid'],  # Requestor
                device['device']  # Point to revert
            ).get(timeout=10)
            # sleep so that the message is sent to pubsub before
            # next test monitors callback method calls
            gevent.sleep(1)

    request.addfinalizer(cleanup)
    return cleanup_parameters


# Repeat test for volttron 2.0 agent and volttron 3.0 agents
@pytest.fixture(scope="module",
                params=['volttron_2', 'volttron_3'])
def publish_agent(request, volttron_instance1):
    """
    Fixture used for setting up the environment.
    1. Creates fake driver configs
    2. Starts the master driver agent with the created fake driver agents
    3. Starts the actuator agent
    4. Creates an instance Agent class for publishing and returns it

    :param request: pytest request object
    :param volttron_instance1: instance of volttron in which test cases
    are run
    :return: an instance of fake agent used for publishing
    """
    global actuator_uuid, publish_agent_v2
    # Create master driver config and 4 fake devices each with 6 points
    process = Popen(['python', 'config_builder.py', '--count=4',
                     '--publish-only-depth-all',
                     'fake', 'fake_unit_testing.csv', 'null'],
                    env=volttron_instance1.env,
                    cwd='scripts/scalability-testing',
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = process.wait()
    print result
    assert result == 0

    # Start the master driver agent which would intern start the fake driver
    # using the configs created above
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

    listener_uuid = volttron_instance1.install_agent(
        agent_dir="examples/ListenerAgent",
        config_file="examples/ListenerAgent/config",
        start=True)
    print("agent id: ", listener_uuid)

    # 3: Start a fake agent to publish to message bus
    fake_publish_agent = volttron_instance1.build_agent()
    # Mock callback methods attach actuate method to fake_publish_agent as
    # it needs to be a class method for the call back to work
    # fake_publish_agent.callback =
    #                types.MethodType(callback, fake_publish_agent)
    fake_publish_agent.callback = MagicMock(name="callback")
    fake_publish_agent.callback.reset_mock()
    # subscribe to schedule response topic
    fake_publish_agent.vip.pubsub.subscribe(
        peer='pubsub',
        prefix=topics.ACTUATOR_SCHEDULE_RESULT,
        callback=fake_publish_agent.callback).get()
    if request.param == 'volttron_2':
        publish_agent_v2 = PublishMixin(
            volttron_instance1.opts['publish_address'])
    else:
        publish_agent_v2 = None

    # 4: add a tear down method to stop sqlhistorian agent
    # and the fake agent that published to message bus
    def stop_agent():
        print("In teardown method of module")
        volttron_instance1.stop_agent(actuator_uuid)
        volttron_instance1.stop_agent(master_uuid)
        fake_publish_agent.core.stop()

    request.addfinalizer(stop_agent)
    return fake_publish_agent


def publish(publish_agent, topic, header, message):
    """

    :param publish_agent: 3.0 agent to use for publishing
    :param topic: topic to publish to
    :param header: header to publish
    :param message: message to publish
    """
    global publish_agent_v2
    if publish_agent_v2 is None:
        publish_agent.vip.pubsub.publish('pubsub',
                                         topic,
                                         headers=header,
                                         message=message).get(timeout=10)
    else:
        publish_agent_v2.publish_json(topic, header, message)


@pytest.mark.actuator_pubsub
def test_schedule_response(publish_agent):
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
    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    """
    # Mock callback methods
    print ("\n**** test_schedule_response ****")
    global publish_agent_v2
    start = str(datetime.now() + timedelta(seconds=10))
    end = str(datetime.now() + timedelta(seconds=20))
    header = {
        'type': 'NEW_SCHEDULE',
        'requesterID': TEST_AGENT,  # The name of the requesting agent.
        'taskID': 'task_schedule_response',
        # unique (to all tasks) ID for scheduled task.
        'priority': 'LOW',  # ('HIGH, 'LOW', 'LOW_PREEMPT').
    }
    msg = [
        ['fakedriver0', start, end]
    ]
    # reset mock to ignore any previous callback
    publish_agent.callback.reset_mock()
    publish(publish_agent, topics.ACTUATOR_SCHEDULE_REQUEST, header, msg)
    gevent.sleep(1)
    assert publish_agent.callback.call_count == 1
    print ('call args ', publish_agent.callback.call_args[0][1])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == \
           topics.ACTUATOR_SCHEDULE_RESULT
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
        'taskID': 'task_schedule_response'
        # unique (to all tasks) ID for scheduled task.
    }
    # reset mock to ignore any previous callback
    publish_agent.callback.reset_mock()
    publish(publish_agent, topics.ACTUATOR_SCHEDULE_REQUEST, header, msg)
    gevent.sleep(1)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    print ("after cancel request")
    assert publish_agent.callback.call_count == 1
    print (publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == \
           topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['taskID'] == 'task_schedule_response'
    assert result_header['requesterID'] == TEST_AGENT
    assert result_message['result'] == SUCCESS
    assert result_header['type'] == 'CANCEL_SCHEDULE'


@pytest.mark.actuator_pubsub
def test_schedule_announce(publish_agent, volttron_instance1):
    """ Tests the schedule announcements of actuator.

    Waits for two announcements and checks if the right parameters
    are sent to call back method.
    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param volttron_instance1: Volttron instance on which test is run
    """
    print ("\n**** test_schedule_announce ****")
    global actuator_uuid, publish_agent_v2

    if publish_agent_v2 is not None:
        pytest.skip('No difference between 2.0 and 3.0 agent. Skip for 2.0')
    # Use a actuator that publishes frequently
    volttron_instance1.stop_agent(actuator_uuid)
    actuator_uuid = volttron_instance1.install_agent(
        agent_dir="services/core/ActuatorAgent",
        config_file="services/core/ActuatorAgent/tests/actuator2.config",
        start=True)
    try:
        # reset mock to ignore any previous callback
        publish_agent.callback.reset_mock()
        publish_agent.actuate0 = MagicMock(name="magic_actuate0")
        announce = topics.ACTUATOR_SCHEDULE_ANNOUNCE(campus='', building='',
                                                     unit='fakedriver0')
        publish_agent.vip.pubsub.subscribe(
            peer='pubsub',
            prefix=announce,
            callback=publish_agent.actuate0).get()

        start = str(datetime.now() + timedelta(seconds=1))
        end = str(datetime.now() + timedelta(seconds=6))
        msg = [
            ['fakedriver0', start, end]
        ]

        result = publish_agent.vip.rpc.call(
            'platform.actuator',
            REQUEST_NEW_SCHEDULE,
            TEST_AGENT,
            'task_schedule_announce',
            'LOW',
            msg).get(timeout=10)
        # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
        assert result['result'] == 'SUCCESS'
        gevent.sleep(5)

        # Test message on schedule/announce
        assert publish_agent.actuate0.called is True
        assert publish_agent.actuate0.call_count == 2
        args_list1 = publish_agent.actuate0.call_args_list[0][0]
        args_list2 = publish_agent.actuate0.call_args_list[1][0]
        assert args_list1[1] == args_list2[1] == 'platform.actuator'
        assert args_list1[3] == args_list2[
            3] == 'devices/actuators/schedule/announce/fakedriver0'
        assert args_list1[4]['taskID'] == args_list2[4][
            'taskID'] == 'task_schedule_announce'
        assert args_list1[4]['requesterID'] == args_list2[4][
            'requesterID'] == TEST_AGENT
        datetime1 = utils.parse_timestamp_string(args_list1[4]['time'])
        datetime2 = utils.parse_timestamp_string(args_list2[4]['time'])
        delta = datetime2 - datetime1
        assert delta.seconds == 2

        # Test message on schedule/result
        assert publish_agent.callback.call_count == 1
        print ('call args ', publish_agent.callback.call_args[0][1])
        assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
        assert publish_agent.callback.call_args[0][3] == \
               topics.ACTUATOR_SCHEDULE_RESULT
        result_header = publish_agent.callback.call_args[0][4]
        result_message = publish_agent.callback.call_args[0][5]
        assert result_header['type'] == 'NEW_SCHEDULE'
        assert result_header['taskID'] == 'task_schedule_announce'
        assert result_header['requesterID'] == TEST_AGENT
        assert result_message['result'] == SUCCESS

    finally:
        # cancel so fakedriver0 can be used by other tests
        publish_agent.vip.rpc.call(
            'platform.actuator',
            REQUEST_CANCEL_SCHEDULE,
            TEST_AGENT,
            'task_schedule_announce').get(timeout=10)
        volttron_instance1.stop_agent(actuator_uuid)
        print ("creating instance of actuator with larger publish frequency")
        actuator_uuid = volttron_instance1.install_agent(
            agent_dir="services/core/ActuatorAgent",
            config_file="services/core/ActuatorAgent/tests/actuator.config",
            start=True)


@pytest.mark.actuator_pubsub
def test_schedule_error_int_taskid(publish_agent):
    """ Test schedule request through pubsub with int task id

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    """
    print ("\n**** test_schedule_int_taskid ****")
    taskid = 1234

    start = str(datetime.now() + timedelta(seconds=10))
    end = str(datetime.now() + timedelta(seconds=20))
    header = {
        'type': 'NEW_SCHEDULE',
        'requesterID': TEST_AGENT,
        'priority': 'LOW',
        'taskID': taskid  # unique (to all tasks) ID for scheduled task
    }
    msg = [
        ['fakedriver1', start, end]
    ]
    # reset mock to ignore any previous callback
    publish_agent.callback.reset_mock()
    publish(publish_agent, topics.ACTUATOR_SCHEDULE_REQUEST, header, msg)
    gevent.sleep(1)
    print ("call args list : ", publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == \
           topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['type'] == 'NEW_SCHEDULE'
    assert result_header['requesterID'] == TEST_AGENT
    assert result_message['result'] == FAILURE
    assert result_message['info'] == \
           'MALFORMED_REQUEST: TypeError: taskid must be a nonempty string'


@pytest.mark.actuator_pubsub
def test_schedule_error_int_agentid(publish_agent):
    """
    Test responses for schedule request through pubsub with Agentid = int

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    """
    print ("\n**** test_schedule_int_agentid ****")
    taskid = 'task_schedule_int_agent'

    start = str(datetime.now() + timedelta(seconds=10))
    end = str(datetime.now() + timedelta(seconds=20))
    msg = [
        ['fakedriver1', start, end]
    ]

    header = {
        'type': 'NEW_SCHEDULE',
        'requesterID': 1234,  # The name of the requesting agent.
        'taskID': taskid,  # unique (to all tasks) ID for scheduled task.
        'priority': 'LOW'
    }

    # reset mock to ignore any previous callback
    publish_agent.callback.reset_mock()
    publish(publish_agent, topics.ACTUATOR_SCHEDULE_REQUEST, header, msg)
    gevent.sleep(1)
    print ('call args list:', publish_agent.callback.call_args_list)

    assert publish_agent.callback.call_count == 1
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == \
           topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['type'] == 'NEW_SCHEDULE'
    assert result_header['taskID'] == taskid
    assert result_message['result'] == FAILURE
    assert result_message['info'] == \
           'MALFORMED_REQUEST: TypeError: agentid must be a nonempty string'


@pytest.mark.actuator_pubsub
def test_schedule_empty_task(publish_agent, cancel_schedules):
    """
    Test responses for schedule request through pubsub. Test task=''

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end of
    test so that other tests can use the same device and time slot
    """
    print ("\n**** test_schedule_empty_task ****")
    agentid = TEST_AGENT
    taskid = ''
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})

    start = str(datetime.now() + timedelta(seconds=1))
    end = str(datetime.now() + timedelta(seconds=2))
    header = {
        'type': 'NEW_SCHEDULE',
        'requesterID': agentid,  # The name of the requesting agent.
        'taskID': taskid,  # unique (to all tasks) ID for scheduled task.
        'priority': 'LOW'
    }
    msg = [
        ['fakedriver1', start, end]
    ]
    # reset mock to ignore any previous callback
    publish_agent.callback.reset_mock()
    publish(publish_agent, topics.ACTUATOR_SCHEDULE_REQUEST, header, msg)
    gevent.sleep(1)

    print ('call args list:', publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    print (publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == \
           topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['type'] == 'NEW_SCHEDULE'
    assert result_header['taskID'] == taskid
    assert result_message['result'] == FAILURE
    assert result_message['info'] == \
           'MALFORMED_REQUEST: TypeError: taskid must be a nonempty string'


@pytest.mark.actuator_pubsub
def test_schedule_empty_agent(publish_agent, cancel_schedules):
    """ Test responses for schedule request through pubsub where Test Agent=''.
    This test case should be removed once agent id are generated by
    the volttron platform

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end of
    test so that other tests can use the same device and time slot
    """
    print ("\n**** test_schedule_empty_agent ****")
    agentid = ''
    taskid = 'task_empty_agent_id'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})

    start = str(datetime.now() + timedelta(seconds=1))
    end = str(datetime.now() + timedelta(seconds=2))
    header = {
        'type': 'NEW_SCHEDULE',
        'requesterID': agentid,  # The name of the requesting agent.
        'taskID': taskid,  # unique (to all tasks) ID for scheduled task.
        'priority': 'LOW'
    }
    msg = [
        ['fakedriver1', start, end]
    ]
    # reset mock to ignore any previous callback
    publish_agent.callback.reset_mock()
    publish(publish_agent, topics.ACTUATOR_SCHEDULE_REQUEST, header, msg)
    gevent.sleep(1)

    print ('call args list:', publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    print (publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == \
           topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['type'] == 'NEW_SCHEDULE'
    assert result_header['taskID'] == taskid
    assert result_message['result'] == FAILURE
    assert result_message['info'] == \
           'MALFORMED_REQUEST: TypeError: agentid must be a nonempty string'


@pytest.mark.actuator_pubsub
def test_schedule_error_none_taskid(publish_agent):
    """
    Test error responses for schedule request through pubsub. Test taskID=None

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    """
    print ("\n**** test_schedule_error_none_taskid ****")

    start = str(datetime.now() + timedelta(seconds=10))
    end = str(datetime.now() + timedelta(seconds=20))
    header = {
        'type': 'NEW_SCHEDULE',
        'requesterID': TEST_AGENT,
        'priority': 'LOW'
    }
    msg = [
        ['fakedriver0', start, end]
    ]
    # reset mock to ignore any previous callback
    publish_agent.callback.reset_mock()
    publish(publish_agent, topics.ACTUATOR_SCHEDULE_REQUEST, header, msg)
    print ('call args list:', publish_agent.callback.call_args_list)
    gevent.sleep(1)
    assert publish_agent.callback.call_count == 1
    print (publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == \
           topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]

    assert result_header['type'] == 'NEW_SCHEDULE'
    assert result_header['requesterID'] == TEST_AGENT
    assert result_message['result'] == FAILURE
    assert result_message['info'] == 'MISSING_TASK_ID'


@pytest.mark.actuator_pubsub
def test_schedule_error_none_agent(publish_agent):
    """
    Test error responses for schedule request through pubsub. Test Agent=None

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    """
    print ("\n**** test_schedule_error_none_agent ****")

    start = str(datetime.now() + timedelta(seconds=10))
    end = str(datetime.now() + timedelta(seconds=20))
    header = {
        'type': 'NEW_SCHEDULE',
        # 'requesterID': TEST_AGENT,  # The name of the requesting agent.
        'taskID': 'task_schedule_response-1',
        # unique (to all tasks) ID for scheduled task.
        'priority': 'LOW'
    }
    msg = [
        ['fakedriver0', start, end]
    ]
    # reset mock to ignore any previous callback
    publish_agent.callback.reset_mock()
    publish(publish_agent, topics.ACTUATOR_SCHEDULE_REQUEST, header, msg)
    gevent.sleep(1)
    print ('call args list:', publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    print (publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == \
           topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['type'] == 'NEW_SCHEDULE'
    assert result_header['taskID'] == 'task_schedule_response-1'
    assert result_message['result'] == FAILURE
    assert result_message['info'] == 'MISSING_AGENT_ID'


@pytest.mark.actuator_pubsub
def test_schedule_error_invalid_type(publish_agent):
    """
    Test error responses for schedule request through pubsub.
    Test invalid type in header

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    """
    print ("\n**** test_schedule_error_invalid_type ****")

    start = str(datetime.now() + timedelta(seconds=10))
    end = str(datetime.now() + timedelta(seconds=20))

    header = {
        'type': 'NEW_SCHEDULE2',
        'requesterID': TEST_AGENT,  # The name of the requesting agent.
        'taskID': 'task1',  # unique (to all tasks) ID for scheduled task.
        'priority': 'LOW'  # ('HIGH, 'LOW', 'LOW_PREEMPT').
    }
    msg = [
        ['fakedriver0', start, end]
    ]
    # reset mock to ignore any previous callback
    publish_agent.callback.reset_mock()
    publish(publish_agent, topics.ACTUATOR_SCHEDULE_REQUEST, header, msg)
    gevent.sleep(1)
    print ('call args list:', publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == \
           topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['type'] == 'NEW_SCHEDULE2'
    assert result_header['taskID'] == 'task1'
    assert result_header['requesterID'] == TEST_AGENT
    assert result_message['result'] == FAILURE
    assert result_message['info'] == 'INVALID_REQUEST_TYPE'


@pytest.mark.actuator_pubsub
def test_schedule_error_invalid_priority(publish_agent):
    """
    Test error responses for schedule request through pubsub.
    Test invalid type in header

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    """
    print ("\n**** test_schedule_error_invalid_type ****")

    start = str(datetime.now() + timedelta(seconds=10))
    end = str(datetime.now() + timedelta(seconds=20))

    header = {
        'type': 'NEW_SCHEDULE',
        'requesterID': TEST_AGENT,  # The name of the requesting agent.
        'taskID': 'task1',  # unique (to all tasks) ID for scheduled task.
        'priority': 'LOW2'  # ('HIGH, 'LOW', 'LOW_PREEMPT').
    }
    msg = [
        ['fakedriver0', start, end]
    ]
    # reset mock to ignore any previous callback
    publish_agent.callback.reset_mock()
    publish(publish_agent, topics.ACTUATOR_SCHEDULE_REQUEST, header, msg)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    gevent.sleep(1)
    print ('call args list:', publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    print ('call args ', publish_agent.callback.call_args[0][1])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == \
           topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['type'] == 'NEW_SCHEDULE'
    assert result_header['taskID'] == 'task1'
    assert result_header['requesterID'] == TEST_AGENT
    assert result_message['result'] == FAILURE
    assert result_message['info'] == 'INVALID_PRIORITY'


@pytest.mark.actuator_pubsub
def test_schedule_error_empty_message(publish_agent):
    """
    Test error responses for schedule request through pubsub.
    Test empty message

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    """
    print ("\n**** test_schedule_error_empty_message ****")

    header = {
        'type': 'NEW_SCHEDULE',
        'requesterID': TEST_AGENT,  # The name of the requesting agent.
        'taskID': 'task_empty_message',
        'priority': 'LOW'
    }
    msg = [

    ]
    # reset mock to ignore any previous callback
    publish_agent.callback.reset_mock()
    publish(publish_agent, topics.ACTUATOR_SCHEDULE_REQUEST, header, msg)
    gevent.sleep(1)
    print ('call args list:', publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    print (publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == \
           topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['type'] == 'NEW_SCHEDULE'
    assert result_header['taskID'] == 'task_empty_message'
    assert result_header['requesterID'] == TEST_AGENT
    assert result_message['result'] == FAILURE
    assert result_message['info'] == 'MALFORMED_REQUEST_EMPTY'


@pytest.mark.actuator_pubsub
def test_schedule_error_multiple_missing_headers(publish_agent):
    """
    Test error responses for schedule request through pubsub.
    Test multiple mising headers

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    """
    print ("\n**** test_schedule_error_multiple_missing_headers ****")

    header = {
        'type': 'NEW_SCHEDULE',
        'requesterID': TEST_AGENT,  # The name of the requesting agent.
        'taskID': 'task_schedule_response-1'
        # 'priority': 'LOW'
    }
    msg = [

    ]
    # reset mock to ignore any previous callback
    publish_agent.callback.reset_mock()
    publish(publish_agent, topics.ACTUATOR_SCHEDULE_REQUEST, header, msg)

    gevent.sleep(1)
    print ('call args list:', publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    print (publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == \
           topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['type'] == 'NEW_SCHEDULE'
    assert result_header['taskID'] == 'task_schedule_response-1'
    assert result_header['requesterID'] == TEST_AGENT
    assert result_message['result'] == FAILURE
    assert result_message['info'] == 'MALFORMED_REQUEST_EMPTY' or \
           result_message['info'] == 'MISSING_PRIORITY'


@pytest.mark.actuator_pubsub
def test_schedule_error_duplicate_task(publish_agent, cancel_schedules):
    """
    Test error response for schedule request through pubsub. Test Agent=''.
    This test case should be removed
    once agent id are generated by the volttron platform

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end of
    test so that other tests can use the same device and time slot
    """
    print ("\n**** test_schedule_error_duplicate_task ****")
    agentid = TEST_AGENT
    taskid = 'task_duplicate_task'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})

    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=4))
    msg = [
        ['fakedriver0', start, end]
    ]
    # reset mock to ignore any previous callback
    publish_agent.callback.reset_mock()
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        REQUEST_NEW_SCHEDULE,
        TEST_AGENT,
        'task_duplicate_task',
        'LOW',
        msg).get(timeout=10)
    assert result['result'] == 'SUCCESS'
    print ("Result of schedule through rpc ", result)

    header = {
        'type': 'NEW_SCHEDULE',
        'requesterID': TEST_AGENT,  # The name of the requesting agent.
        'taskID': 'task_duplicate_task',
        # unique (to all tasks) ID for scheduled task.
        'priority': 'LOW'
    }
    publish(publish_agent, topics.ACTUATOR_SCHEDULE_REQUEST, header, msg)
    gevent.sleep(1)

    print ('call args list:', publish_agent.callback.call_args_list)
    # once for rpc call and once for publish
    assert publish_agent.callback.call_count == 2
    print (publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == \
           topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['type'] == 'NEW_SCHEDULE'
    assert result_header['taskID'] == 'task_duplicate_task'
    assert result_message['result'] == FAILURE
    assert result_message['info'] == 'TASK_ID_ALREADY_EXISTS'


@pytest.mark.actuator_pubsub
def test_schedule_error_missing_priority(publish_agent):
    """
    Test error response for schedule request through pubsub.
    Test missing priority info

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    """
    print ("\n**** test_schedule_error_missing_priority ****")

    start = str(datetime.now() + timedelta(seconds=10))
    end = str(datetime.now() + timedelta(seconds=20))
    header = {
        'type': 'NEW_SCHEDULE',
        'requesterID': TEST_AGENT,  # The name of the requesting agent.
        'taskID': 'task_missing_priority'
        # unique (to all tasks) ID for scheduled task.
        # 'priority': 'LOW'
    }
    msg = [
        ['fakedriver0', start, end]
    ]
    # reset mock to ignore any previous callback
    publish_agent.callback.reset_mock()
    publish(publish_agent, topics.ACTUATOR_SCHEDULE_REQUEST, header, msg)
    gevent.sleep(1)
    print ('call args list:', publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    print (publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == \
           topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['taskID'] == 'task_missing_priority'
    assert result_message['result'] == FAILURE
    assert result_message['info'] == 'MISSING_PRIORITY'


@pytest.mark.actuator_pubsub
def test_schedule_error_malformed_request(publish_agent):
    """
    Test error response for schedule request through pubsub.
    Test malformed request by sending a message without end date.

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    """
    print ("\n**** test_schedule_error_malformed_request ****")

    start = str(datetime.now() + timedelta(seconds=10))
    # end = str(datetime.now() + timedelta(seconds=20))
    header = {
        'type': 'NEW_SCHEDULE',
        'requesterID': TEST_AGENT,  # The name of the requesting agent.
        'taskID': 'task_schedule_response-1',
        # unique (to all tasks) ID for scheduled task.
        'priority': 'LOW'
    }
    msg = [
        ['fakedriver0', start]
    ]
    # reset mock to ignore any previous callback
    publish_agent.callback.reset_mock()
    publish(publish_agent, topics.ACTUATOR_SCHEDULE_REQUEST, header, msg)
    gevent.sleep(1)
    print ('call args list:', publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    print (publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == \
           topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['type'] == 'NEW_SCHEDULE'
    assert result_header['taskID'] == 'task_schedule_response-1'
    assert result_message['result'] == FAILURE
    assert result_message['info'].startswith('MALFORMED_REQUEST')


@pytest.mark.actuator_pubsub
def test_schedule_preempt_self(publish_agent, cancel_schedules):
    """
    Test error response for schedule request through pubsub.
    Test schedule preemption by a higher priority task from the same agent.
    Expected result message
    {
    'agentID': <Agent ID of preempting task>,
    'taskID': <Task ID of preempting task>
    }
    Expected header
    {
    'type': 'CANCEL_SCHEDULE'
    'requesterID': <Agent ID from the request>,
    'taskID': <Task ID from the request>
    }
    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end of
    test so that other tests can use the same device and time slot
    """
    print ("\n**** test_schedule_preempt_self ****")

    agentid = TEST_AGENT
    taskid = 'task_high_priority'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})
    # add low prority task since it won't get cancelled till end of grace time
    cancel_schedules.append(
        {'agentid': agentid, 'taskid': 'task_low_priority'})

    start = str(datetime.now() + timedelta(seconds=10))
    end = str(datetime.now() + timedelta(seconds=20))
    header = {
        'type': 'NEW_SCHEDULE',
        'requesterID': agentid,  # The name of the requesting agent.
        'taskID': taskid,  # unique (to all tasks) ID for scheduled task.
        'priority': 'HIGH'
    }
    msg = [
        ['fakedriver1', start, end]
    ]
    # reset mock to ignore any previous callback
    publish_agent.callback.reset_mock()

    # First schedule the low priority task
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        REQUEST_NEW_SCHEDULE,
        agentid,
        'task_low_priority',
        'LOW',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    print result
    assert result['result'] == 'SUCCESS'
    gevent.sleep(1)  # wait for response on pubsub
    # reset as we don't care about the success message sent for above
    publish_agent.callback.reset_mock()

    # Now publish the higher priority task
    publish(publish_agent, topics.ACTUATOR_SCHEDULE_REQUEST, header, msg)
    # wait for 2 callbacks - success msg for task_high_priority and
    # preempt msg for task_low_priority
    gevent.sleep(5)
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

    assert cancel_header['taskID'] == 'task_low_priority'
    assert cancel_message['data']['agentID'] == agentid
    assert cancel_message['data']['taskID'] == taskid
    assert cancel_message['result'] == 'PREEMPTED'


@pytest.mark.actuator_pubsub
def test_schedule_preempt_other(publish_agent, cancel_schedules):
    """
    Test error response for schedule request through pubsub.
    Test schedule preemption by a higher priority task from a different agent.
    Expected result message
    {
    'agentID': <Agent ID of preempting task>,
    'taskID': <Task ID of preempting task>
    }
    Expected header
    {
    'type': 'CANCEL_SCHEDULE'
    'requesterID': <Agent ID from the request>,
    'taskID': <Task ID from the request>
    }
    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end of
    test so that other tests can use the same device and time slot
    """
    print ("\n**** test_schedule_preempt_other ****")

    agentid = TEST_AGENT
    taskid = 'task_high_priority2'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})
    # add low prority task since it won't get cancelled till end of grace time
    cancel_schedules.append(
        {'agentid': 'other_agent', 'taskid': 'task_low_priority2'})

    start = str(datetime.now() + timedelta(seconds=10))
    end = str(datetime.now() + timedelta(seconds=20))
    header = {
        'type': 'NEW_SCHEDULE',
        'requesterID': agentid,  # The name of the requesting agent.
        'taskID': taskid,  # unique (to all tasks) ID for scheduled task.
        'priority': 'HIGH'
    }
    msg = [
        ['fakedriver1', start, end]
    ]
    # reset mock to ignore any previous callback
    publish_agent.callback.reset_mock()

    # First schedule the low priority task
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        REQUEST_NEW_SCHEDULE,
        'other_agent',
        'task_low_priority2',
        'LOW',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    print result
    assert result['result'] == 'SUCCESS'
    gevent.sleep(1)  # wait for response on pubsub

    # reset as we don't care about the success message sent for above
    publish_agent.callback.reset_mock()
    # Now publish the higher priority task
    publish(publish_agent, topics.ACTUATOR_SCHEDULE_REQUEST, header, msg)
    # wait for 2 callbacks - success msg for task_high_priority and
    # preempt msg for task_low_priority
    gevent.sleep(5)
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
    assert cancel_header['requesterID'] == 'other_agent'
    assert cancel_message['data']['agentID'] == agentid
    assert cancel_message['data']['taskID'] == taskid
    assert cancel_message['result'] == 'PREEMPTED'


@pytest.mark.actuator_pubsub
def test_schedule_conflict(publish_agent, cancel_schedules):
    """
    Test schedule conflict with existing schdeule

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end of
    test so that other tests can use the same device and time slot
    """
    print ("\n**** test_schedule_conflict ****")
    agentid = TEST_AGENT
    taskid = 'task_conflict1'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})

    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=2))
    msg = [
        ['fakedriver0', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        'LOW',
        msg).get(timeout=10)
    print result
    assert result['result'] == 'SUCCESS'
    gevent.sleep(1)  # wait for above response on callback

    # now do second schedule expecting conflict
    header = {
        'type': 'NEW_SCHEDULE',
        'requesterID': agentid,  # The name of the requesting agent.
        'taskID': 'task_conflict2',
        # unique (to all tasks) ID for scheduled task.
        'priority': 'LOW'
    }
    # reset mock to ignore any previous callback
    publish_agent.callback.reset_mock()
    publish(publish_agent, topics.ACTUATOR_SCHEDULE_REQUEST, header, msg)
    gevent.sleep(1)  # wait for response on callback
    print ('call args list:', publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == \
           topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['type'] == 'NEW_SCHEDULE'
    assert result_header['taskID'] == 'task_conflict2'
    assert result_message['result'] == FAILURE
    assert result_message['info'] == 'CONFLICTS_WITH_EXISTING_SCHEDULES'


@pytest.mark.actuator_pubsub
def test_schedule_conflict_self(publish_agent):
    """
    Test schedule conflict within a single request

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    """
    print("requesting a schedule for device1")
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=1))
    msg = [
        ['fakedriver1', start, end],
        ['fakedriver1', start, end]
    ]
    header = {
        'type': 'NEW_SCHEDULE',
        'requesterID': TEST_AGENT,  # The name of the requesting agent.
        'taskID': 'task_conflict_self',
        # unique (to all tasks) ID for scheduled task.
        'priority': 'LOW'
    }
    # now do second schedule expecting conflict
    # reset mock to ignore any previous callback
    publish_agent.callback.reset_mock()
    publish(publish_agent, topics.ACTUATOR_SCHEDULE_REQUEST, header, msg)
    gevent.sleep(1)  # wait for response on callback
    print ('call args list:', publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == \
           topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['type'] == 'NEW_SCHEDULE'
    assert result_header['taskID'] == 'task_conflict_self'
    assert result_message['result'] == FAILURE
    assert result_message['info'] == 'REQUEST_CONFLICTS_WITH_SELF'


@pytest.mark.actuator_pubsub
def test_schedule_overlap(publish_agent, cancel_schedules):
    """
    Test successful schedule when end time of one time slot is the same as
    start time of another slot

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end of
    test so that other tests can use the same device and time slot
    """
    print ("\n**** test_schedule_overlap ****")
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
    header = {
        'type': 'NEW_SCHEDULE',
        'requesterID': agentid,  # The name of the requesting agent.
        'taskID': taskid,  # unique (to all tasks) ID for scheduled task.
        'priority': 'LOW'
    }

    # reset mock to ignore any previous callback
    publish_agent.callback.reset_mock()
    publish(publish_agent, topics.ACTUATOR_SCHEDULE_REQUEST, header, msg)
    gevent.sleep(1)  # wait for result callback

    print ('call args list:', publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == \
           topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['type'] == 'NEW_SCHEDULE'
    assert result_header['taskID'] == taskid
    assert result_message['result'] == SUCCESS


@pytest.mark.actuator_pubsub
def test_cancel_error_invalid_task(publish_agent):
    """
    Test error responses for schedule request through pubsub.
    Test invalid task id

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    """
    print ("\n**** test_schedule_error_invalid_task ****")

    start = str(datetime.now() + timedelta(seconds=10))
    end = str(datetime.now() + timedelta(seconds=20))
    header = {
        'type': 'CANCEL_SCHEDULE',
        'requesterID': TEST_AGENT,  # The name of the requesting agent.
        'taskID': 'task_invalid_task'
        # unique (to all tasks) ID for scheduled task.
    }
    msg = [
        ['fakedriver0', start, end]
    ]
    # reset mock to ignore any previous callback
    publish_agent.callback.reset_mock()
    publish(publish_agent, topics.ACTUATOR_SCHEDULE_REQUEST, header, msg)
    gevent.sleep(1)
    print ('call args list:', publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == \
           topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['requesterID'] == TEST_AGENT
    assert result_message['result'] == FAILURE
    assert result_message['info'] == 'TASK_ID_DOES_NOT_EXIST'
    assert result_header['type'] == 'CANCEL_SCHEDULE'


@pytest.mark.actuator_pubsub
def test_cancel_error_taskid_agentid_mismatch(publish_agent, cancel_schedules):
    """
    Test cancel error when there is a mismatch between the agentid used to
    schdeule and agent id used to cancel

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end of
    test so that other tests can use the same device and time slot
    """
    print ("\n**** test_cancel_error_taskid_agentid_mismatch ****")
    agentid = TEST_AGENT
    taskid = 'task_invalid_cancel'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})

    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=2))
    msg = [
        ['fakedriver0', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        'LOW',
        msg).get(timeout=10)
    print result
    assert result['result'] == 'SUCCESS'
    gevent.sleep(1)  # wait for the response of above to hit the pubsub topic

    header = {
        'type': 'CANCEL_SCHEDULE',
        'requesterID': 'invalid_agent_for_task',
        # The name of the requesting agent.
        'taskID': taskid
    }
    # reset mock to ignore any previous callback
    publish_agent.callback.reset_mock()
    publish(publish_agent, topics.ACTUATOR_SCHEDULE_REQUEST, header, msg)
    gevent.sleep(1)
    print ('call args list:', publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == \
           topics.ACTUATOR_SCHEDULE_RESULT
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['requesterID'] == 'invalid_agent_for_task'
    assert result_message['result'] == FAILURE
    assert result_message['info'] == 'AGENT_ID_TASK_ID_MISMATCH'
    assert result_header['type'] == 'CANCEL_SCHEDULE'


@pytest.mark.actuator_pubsub
def test_get_default(publish_agent):
    """
    Test getting the default value of a point through pubsub
    Format of expected result
    Expected Header
    {
     'requesterID': <Agent ID from the request>,
     }
    Expected message - contains the value of the point

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    """
    print("*** testing get_default ***")
    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback")
    # reset mock to ignore any previous callback
    publish_agent.callback.reset_mock()
    # Subscribe to result of set
    value_topic = topics.ACTUATOR_VALUE(campus='', building='',
                                        unit='fakedriver1',
                                        point='SampleWritableFloat1')
    error_topic = topics.ACTUATOR_ERROR(campus='', building='',
                                        unit='fakedriver1',
                                        point='SampleWritableFloat1')
    print ('value topic', value_topic)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=value_topic,
                                       callback=publish_agent.callback).get()
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=error_topic,
                                       callback=publish_agent.callback).get()

    # Get default value
    get_topic = topics.ACTUATOR_GET(campus='', building='', unit='fakedriver1',
                                    point='SampleWritableFloat1')
    header = {
        'requesterID': TEST_AGENT
    }
    publish_agent.vip.pubsub.publish('pubsub',
                                     get_topic,
                                     headers=header).get(timeout=10)
    gevent.sleep(1)
    print("call args list", publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    print ('call args ', publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == value_topic
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['requesterID'] == TEST_AGENT
    assert result_message == 10.0


@pytest.mark.actuator_pubsub
def test_get_value_success(publish_agent, cancel_schedules):
    """
    Test getting a float value of a point through pubsub
    Format of expected result
    Expected Header
    {
     'requesterID': <Agent ID from the request>,
     }
    Expected message - contains the value of the point

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end of
    test so that other tests can use the same device and time slot
    """
    print ("\n**** test_get_value_success ****")

    agentid = TEST_AGENT
    taskid = 'task_get_value_success'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})

    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback")
    # Subscribe to result of set
    value_topic = topics.ACTUATOR_VALUE(campus='', building='',
                                        unit='fakedriver1',
                                        point='SampleWritableFloat1')
    error_topic = topics.ACTUATOR_ERROR(campus='', building='',
                                        unit='fakedriver1',
                                        point='SampleWritableFloat1')
    print ('value topic', value_topic)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=value_topic,
                                       callback=publish_agent.callback).get()
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=error_topic,
                                       callback=publish_agent.callback).get()
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=2))
    msg = [
        ['fakedriver1', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        'LOW',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    print result
    assert result['result'] == 'SUCCESS'

    # set value
    header = {
        'requesterID': TEST_AGENT
    }

    result = publish_agent.vip.rpc.call(
        'platform.actuator',  # Target agent
        'set_point',  # Method
        agentid,  # Requestor
        'fakedriver1/SampleWritableFloat1',  # Point to set
        20.5  # New value
    ).get(timeout=10)
    print ("result of set", result)
    get_topic = topics.ACTUATOR_GET(campus='', building='', unit='fakedriver1',
                                    point='SampleWritableFloat1')
    print("set topic: ", get_topic)
    publish_agent.vip.pubsub.publish('pubsub',
                                     get_topic,
                                     headers=header).get(timeout=10)
    print("call args list", publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    print ('call args ', publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == value_topic
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['requesterID'] == agentid
    assert result_message == 20.5


@pytest.mark.actuator_pubsub
def test_get_error_invalid_point(publish_agent):
    """
    Test getting a float value of a point through pubsub with invalid
    point name
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

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    """
    print ("\n**** test_get_error_invalid_point ****")
    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback")
    # Subscribe to result of set
    value_topic = topics.ACTUATOR_VALUE(campus='', building='',
                                        unit='fakedriver1',
                                        point='SampleWritableFloat12')
    error_topic = topics.ACTUATOR_ERROR(campus='', building='',
                                        unit='fakedriver1',
                                        point='SampleWritableFloat12')
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
    get_topic = topics.ACTUATOR_GET(campus='', building='', unit='fakedriver1',
                                    point='SampleWritableFloat12')
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
    assert result_message['type'] == \
           'master_driver.interfaces.DriverInterfaceError'
    assert result_message['value'] == \
           "['Point not configured on device: SampleWritableFloat12']"
    assert result_header['requesterID'] == TEST_AGENT


@pytest.mark.actuator_pubsub
def test_set_value_bool(publish_agent, cancel_schedules, revert_devices):
    """
    Test setting a float value of a point through pubsub
    Format of expected result
    Header:
    {
    'requesterID': <Agent ID>
    }
    The message contains the value of the actuation point in JSON
    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end of
    test so that other tests can use the same device and time slot
    :param revert_devices: Cleanup method to revert device state
    """
    print ("\n**** test_set_value_bool ****")
    agentid = TEST_AGENT
    taskid = 'task_set_bool_value'
    device = 'fakedriver3'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})
    revert_devices.append({'agentid': agentid, 'device': device})

    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback")
    # Subscribe to result of set
    value_topic = topics.ACTUATOR_VALUE(campus='', building='', unit=device,
                                        point='SampleWritableBool1')
    error_topic = topics.ACTUATOR_ERROR(campus='', building='', unit=device,
                                        point='SampleWritableBool1')
    print ('value topic', value_topic)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=value_topic,
                                       callback=publish_agent.callback).get()
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=error_topic,
                                       callback=publish_agent.callback).get()
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=3))
    msg = [
        [device, start, end]
    ]
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        'LOW',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    assert result['result'] == 'SUCCESS'
    # set value
    header = {
        'requesterID': agentid
    }

    publish_agent.vip.pubsub.publish('pubsub',
                                     topics.ACTUATOR_SET(
                                         campus='',
                                         building='',
                                         unit=device,
                                         point='SampleWritableBool1'),
                                     headers=header,
                                     message=True).get(timeout=10)
    gevent.sleep(1)

    print ('call args list', publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == value_topic
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['requesterID'] == agentid
    assert result_message is True


@pytest.mark.actuator_pubsub
def test_set_value_array(publish_agent, cancel_schedules, revert_devices):
    """
    Test setting point through pubsub. Set value as array with length=1
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
    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end of
    test so that other tests can use the same device and time slot
    :param revert_devices: Cleanup method to revert device state
    """
    print ("\n**** test_set_value_array ****")
    agentid = TEST_AGENT
    taskid = 'task_set_array_value'
    device = 'fakedriver0'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})
    revert_devices.append({'agentid': agentid, 'device': device})

    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback")
    # Subscribe to result of set
    value_topic = topics.ACTUATOR_VALUE(campus='', building='', unit=device,
                                        point='SampleWritableFloat1')
    error_topic = topics.ACTUATOR_ERROR(campus='', building='', unit=device,
                                        point='SampleWritableFloat1')
    print ('value topic', value_topic)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=value_topic,
                                       callback=publish_agent.callback).get()
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=error_topic,
                                       callback=publish_agent.callback).get()
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=3))
    msg = [
        [device, start, end]
    ]
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        'LOW',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    print result
    assert result['result'] == 'SUCCESS'
    # set value
    header = {
        'requesterID': agentid
    }

    set_topic = topics.ACTUATOR_SET(campus='', building='', unit=device,
                                    point='SampleWritableFloat1')
    print("set topic: ", set_topic)
    publish_agent.vip.pubsub.publish('pubsub',
                                     set_topic,
                                     headers=header,
                                     message=[0.2]).get(timeout=10)
    gevent.sleep(1)
    print ('call args list:', publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == error_topic
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['requesterID'] == agentid
    assert result_message['type'] == 'TypeError'
    assert result_message['value'] == \
           "['float() argument must be a string or a number']"


@pytest.mark.actuator_pubsub
def test_set_value_float(publish_agent, cancel_schedules, revert_devices):
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
    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end of
    test so that other tests can use the same device and time slot
    :param revert_devices: Cleanup method to revert device state
    """
    print ("\n**** test_set_value_float ****")
    global publish_agent_v2
    agentid = TEST_AGENT
    taskid = 'task_set_float_value'
    device = 'fakedriver2'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})
    revert_devices.append({'agentid': agentid, 'device': device})

    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback")
    # Subscribe to result of set
    value_topic = topics.ACTUATOR_VALUE(campus='', building='', unit=device,
                                        point='SampleWritableFloat1')
    error_topic = topics.ACTUATOR_ERROR(campus='', building='', unit=device,
                                        point='SampleWritableFloat1')
    print ('value topic', value_topic)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=value_topic,
                                       callback=publish_agent.callback).get()
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=error_topic,
                                       callback=publish_agent.callback).get()
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=3))
    msg = [
        [device, start, end]
    ]
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        'LOW',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    # print result
    assert result['result'] == 'SUCCESS'
    # set value
    header = {
        'requesterID': TEST_AGENT
    }

    set_topic = topics.ACTUATOR_SET(campus='', building='', unit=device,
                                    point='SampleWritableFloat1')
    print("set topic: ", set_topic)
    publish(publish_agent, set_topic, header, 0.2)
    gevent.sleep(1)

    print ('call args list ', publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == value_topic
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['requesterID'] == agentid
    assert result_message == 0.2


@pytest.mark.actuator_pubsub
def test_revert_point(publish_agent, cancel_schedules):
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
    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end of
    test so that other tests can use the same device and time slot
    """
    print ("\n**** test_set_value_float ****")
    agentid = TEST_AGENT
    taskid = 'task_set_float_value'
    device = 'fakedriver2'
    point = 'SampleWritableFloat1'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})

    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback")
    # Subscribe to result of set
    value_topic = topics.ACTUATOR_VALUE(campus='', building='', unit=device,
                                        point=point)
    reverted_topic = topics.ACTUATOR_REVERTED_POINT(campus='', building='',
                                                    unit=device, point=point)
    print ('value topic', value_topic)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=value_topic,
                                       callback=publish_agent.callback).get()
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=reverted_topic,
                                       callback=publish_agent.callback).get()
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=10))
    msg = [
        [device, start, end]
    ]
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        'LOW',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    # print result
    assert result['result'] == 'SUCCESS'

    initial_value = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,  # Target agent
        'get_point',  # Method
        'fakedriver2/SampleWritableFloat1',  # Point to get
    ).get(timeout=10)

    test_value = initial_value + 1.0

    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,  # Target agent
        'set_point',  # Method
        agentid,  # Requestor
        'fakedriver2/SampleWritableFloat1',  # Point to set
        test_value  # New value
    ).get(timeout=10)

    assert result == test_value
    gevent.sleep(1)

    print ('call args list ', publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == value_topic
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['requesterID'] == agentid
    assert result_message == test_value

    publish_agent.callback.reset_mock()

    # set value
    header = {
        'requesterID': TEST_AGENT
    }

    revert_topic = topics.ACTUATOR_REVERT_POINT(campus='', building='',
                                                unit=device, point=point)
    print("revert topic: ", revert_topic)
    publish_agent.vip.pubsub.publish('pubsub',
                                     revert_topic,
                                     headers=header).get(timeout=10)
    gevent.sleep(1)

    print ('call args list ', publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == reverted_topic
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['requesterID'] == agentid
    assert result_message is None

    publish_agent.callback.reset_mock()

    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,  # Target agent
        'get_point',  # Method
        'fakedriver2/SampleWritableFloat1',  # Point to get
    ).get(timeout=10)
    # Value taken from fake_unit_testing.csv
    assert result == initial_value


@pytest.mark.actuator_pubsub
def test_revert_device(publish_agent, cancel_schedules):
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
    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end of
    test so that other tests can use the same device and time slot
    """
    print ("\n**** test_set_value_float ****")
    agentid = TEST_AGENT
    taskid = 'task_set_float_value'
    device = 'fakedriver2'
    point = 'SampleWritableFloat1'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})

    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback")
    # Subscribe to result of set
    value_topic = topics.ACTUATOR_VALUE(campus='', building='', unit=device,
                                        point=point)
    reverted_topic = topics.ACTUATOR_REVERTED_DEVICE(campus='', building='',
                                                     unit=device)
    print ('value topic', value_topic)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=value_topic,
                                       callback=publish_agent.callback).get()
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=reverted_topic,
                                       callback=publish_agent.callback).get()
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=10))
    msg = [
        [device, start, end]
    ]
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        'LOW',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    # print result
    assert result['result'] == 'SUCCESS'

    initial_value = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,  # Target agent
        'get_point',  # Method
        'fakedriver2/SampleWritableFloat1',  # Point to get
    ).get(timeout=10)

    test_value = initial_value + 1.0

    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,  # Target agent
        'set_point',  # Method
        agentid,  # Requestor
        'fakedriver2/SampleWritableFloat1',  # Point to set
        test_value  # New value
    ).get(timeout=10)

    assert result == test_value
    gevent.sleep(1)

    print ('call args list ', publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == value_topic
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['requesterID'] == agentid
    assert result_message == test_value

    publish_agent.callback.reset_mock()

    # set value
    header = {
        'requesterID': TEST_AGENT
    }

    revert_topic = topics.ACTUATOR_REVERT_DEVICE(campus='', building='',
                                                 unit=device)
    print("revert topic: ", revert_topic)
    publish_agent.vip.pubsub.publish('pubsub',
                                     revert_topic,
                                     headers=header).get(timeout=10)
    gevent.sleep(1)

    print ('call args list ', publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == reverted_topic
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['requesterID'] == agentid
    assert result_message is None

    publish_agent.callback.reset_mock()

    result = publish_agent.vip.rpc.call(
        PLATFORM_ACTUATOR,  # Target agent
        'get_point',  # Method
        'fakedriver2/SampleWritableFloat1',  # Point to get
    ).get(timeout=10)
    # Value taken from fake_unit_testing.csv
    assert result == initial_value


@pytest.mark.actuator_pubsub
def test_set_read_only_point(publish_agent, cancel_schedules):
    """
    Test setting a value of a read only point through pubsub
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

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end of
    test so that other tests can use the same device and time slot
    """
    print ("\n**** test_set_read_only_point ****")
    agentid = TEST_AGENT
    taskid = 'task_set_readonly_point'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})

    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback")
    # Subscribe to result of set
    value_topic = topics.ACTUATOR_VALUE(campus='', building='',
                                        unit='fakedriver0',
                                        point='OutsideAirTemperature1')
    error_topic = topics.ACTUATOR_ERROR(campus='', building='',
                                        unit='fakedriver0',
                                        point='OutsideAirTemperature1')
    print ('value topic', value_topic)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=value_topic,
                                       callback=publish_agent.callback).get()
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=error_topic,
                                       callback=publish_agent.callback).get()
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=3))
    msg = [
        ['fakedriver0', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        'LOW',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    # print result
    assert result['result'] == 'SUCCESS'
    # set value
    header = {
        'requesterID': TEST_AGENT
    }

    set_topic = topics.ACTUATOR_SET(campus='', building='', unit='fakedriver0',
                                    point='OutsideAirTemperature1')
    print("set topic: ", set_topic)
    publish_agent.vip.pubsub.publish('pubsub',
                                     set_topic,
                                     headers=header,
                                     message=['0.2']).get(timeout=10)
    publish_agent.vip.rpc.call(
        'platform.actuator',
        REQUEST_CANCEL_SCHEDULE,
        agentid,
        'task_set_read_only_point').get(timeout=10)
    gevent.sleep(1)

    print ('call args list:', publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    print ('call args ', publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == error_topic
    result_header = publish_agent.callback.call_args[0][4]
    assert result_header['requesterID'] == agentid
    result_message = publish_agent.callback.call_args[0][5]
    assert result_message['type'] == 'IOError'
    assert result_message['value'] == "['Trying to write to a point " \
                                      "configured read only: " \
                                      "OutsideAirTemperature1']"


@pytest.mark.actuator_pubsub
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
        'type': 'LockError'
        'value': 'caller does not have this lock'
    }
    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    """
    print ("\n**** test_set_lock_error ****")
    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback_set_lock_error")

    current_value = publish_agent.vip.rpc.call(
        'platform.actuator',  # Target agent
        'get_point',  # Method
        'fakedriver1/SampleWritableFloat1'  # point
    ).get(timeout=10)
    current_value = float(current_value)
    print ("Value of point before set without lock: ", current_value)

    # Subscribe to result of set
    value_topic = topics.ACTUATOR_VALUE(campus='', building='',
                                        unit='fakedriver1',
                                        point='SampleWritableFloat1')
    error_topic = topics.ACTUATOR_ERROR(campus='', building='',
                                        unit='fakedriver1',
                                        point='SampleWritableFloat1')
    print('error topic:', error_topic)
    print ('value topic', value_topic)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=value_topic,
                                       callback=publish_agent.callback).get()
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=error_topic,
                                       callback=publish_agent.callback).get()

    # set value
    header = {
        'requesterID': TEST_AGENT
    }

    set_topic = topics.ACTUATOR_SET(campus='', building='', unit='fakedriver1',
                                    point='SampleWritableFloat1')
    print("set topic: ", set_topic)
    set_value = current_value + 1
    print("Attempting to set value as ", set_value)
    publish_agent.vip.pubsub.publish('pubsub',
                                     set_topic,
                                     headers=header,
                                     message=set_value).get(timeout=10)
    gevent.sleep(1)
    print ('call args list:', publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    print ('call args ', publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == error_topic
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['requesterID'] == TEST_AGENT
    assert result_message['type'] == 'LockError'
    assert result_message['value'] == \
           'caller ({}) does not have this lock'.format(TEST_AGENT)

    # To test fix for bug #223
    new_value = publish_agent.vip.rpc.call(
        'platform.actuator',  # Target agent
        'get_point',  # Method
        'fakedriver1/SampleWritableFloat1'  # point
    ).get(timeout=10)
    print("Value of point after failed set:", new_value)
    assert current_value == new_value


@pytest.mark.actuator_pubsub
def test_set_value_error(publish_agent, cancel_schedules):
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

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end of
    test so that other tests can use the same device and time slot
    """
    print ("\n**** test_set_value_error ****")

    agentid = TEST_AGENT
    taskid = 'task_set_value_error'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})

    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback_value_error")
    # Subscribe to result of set
    value_topic = topics.ACTUATOR_VALUE(campus='', building='',
                                        unit='fakedriver0',
                                        point='SampleWritableFloat1')
    error_topic = topics.ACTUATOR_ERROR(campus='', building='',
                                        unit='fakedriver0',
                                        point='SampleWritableFloat1')
    print ('value topic', value_topic)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=value_topic,
                                       callback=publish_agent.callback).get()
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=error_topic,
                                       callback=publish_agent.callback).get()
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=3))
    msg = [
        ['fakedriver0', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        'LOW',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    print result
    assert result['result'] == 'SUCCESS'
    # set value
    header = {
        'requesterID': agentid
    }

    set_topic = topics.ACTUATOR_SET(campus='', building='', unit='fakedriver0',
                                    point='SampleWritableFloat1')
    print("set topic: ", set_topic)
    publish_agent.vip.pubsub.publish('pubsub',
                                     set_topic,
                                     headers=header,
                                     message='abcd').get(timeout=10)
    gevent.sleep(1)

    print ('call args list:', publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    print ('call args ', publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == error_topic
    result_header = publish_agent.callback.call_args[0][4]
    result_message = publish_agent.callback.call_args[0][5]
    assert result_header['requesterID'] == agentid
    assert result_message['type'] == 'ValueError'
    assert result_message['value'] == \
           "['could not convert string to float: abcd']"


@pytest.mark.actuator_pubsub
def test_set_error_none_agent(publish_agent, cancel_schedules):
    """
    Test setting a value of a point through pubsub without a valid agent id
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

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end of
    test so that other tests can use the same device and time slot
    """
    print ("\n**** test_set_error_none_agent ****")
    agentid = TEST_AGENT
    taskid = 'task_set_none_agent'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})

    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback_value_error")
    # Subscribe to result of set
    value_topic = topics.ACTUATOR_VALUE(campus='', building='',
                                        unit='fakedriver0',
                                        point='SampleWritableFloat1')
    error_topic = topics.ACTUATOR_ERROR(campus='', building='',
                                        unit='fakedriver0',
                                        point='SampleWritableFloat1')
    print ('value topic', value_topic)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=value_topic,
                                       callback=publish_agent.callback).get()
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=error_topic,
                                       callback=publish_agent.callback).get()
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=3))
    msg = [
        ['fakedriver0', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        'LOW',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    print result
    assert result['result'] == 'SUCCESS'
    # set value
    header = {
        'requesterID': None
    }

    set_topic = topics.ACTUATOR_SET(campus='', building='', unit='fakedriver0',
                                    point='SampleWritableFloat1')
    print("set topic: ", set_topic)
    publish_agent.vip.pubsub.publish('pubsub',
                                     set_topic,
                                     headers=header,
                                     message='abcd').get(timeout=10)
    gevent.sleep(1)

    print ('call args list:', publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    print ('call args ', publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == error_topic
    result_message = publish_agent.callback.call_args[0][5]
    assert result_message['type'] == 'TypeError'
    assert result_message['value'] == 'Agent id must be a nonempty string'


@pytest.mark.actuator_pubsub
def test_set_error_empty_header(publish_agent, cancel_schedules):
    """
    Test setting a value of a point through pubsub with an empty
    header(no agent id)
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

    :param publish_agent: fixture invoked to setup all agents necessary and
    returns an instance of Agent object used for publishing
    :param cancel_schedules: fixture used to cancel the schedule at the end of
    test so that other tests can use the same device and time slot
    """
    print ("\n**** test_set_error_empty_header ****")
    agentid = TEST_AGENT
    taskid = 'task_set_none_agent'
    cancel_schedules.append({'agentid': agentid, 'taskid': taskid})

    # Mock callback methods
    publish_agent.callback = MagicMock(name="callback_value_error")
    # Subscribe to result of set
    value_topic = topics.ACTUATOR_VALUE(campus='', building='',
                                        unit='fakedriver0',
                                        point='SampleWritableFloat1')
    error_topic = topics.ACTUATOR_ERROR(campus='', building='',
                                        unit='fakedriver0',
                                        point='SampleWritableFloat1')
    print ('value topic', value_topic)
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=value_topic,
                                       callback=publish_agent.callback).get()
    publish_agent.vip.pubsub.subscribe(peer='pubsub',
                                       prefix=error_topic,
                                       callback=publish_agent.callback).get()
    start = str(datetime.now())
    end = str(datetime.now() + timedelta(seconds=3))
    msg = [
        ['fakedriver0', start, end]
    ]
    result = publish_agent.vip.rpc.call(
        'platform.actuator',
        REQUEST_NEW_SCHEDULE,
        agentid,
        taskid,
        'LOW',
        msg).get(timeout=10)
    # expected result {'info': u'', 'data': {}, 'result': 'SUCCESS'}
    print result
    assert result['result'] == 'SUCCESS'
    # set value
    header = {
    }

    set_topic = topics.ACTUATOR_SET(campus='', building='', unit='fakedriver0',
                                    point='SampleWritableFloat1')
    print("set topic: ", set_topic)
    publish_agent.vip.pubsub.publish('pubsub',
                                     set_topic,
                                     headers=header,
                                     message='abcd').get(timeout=10)
    gevent.sleep(1)

    print ('call args list:', publish_agent.callback.call_args_list)
    assert publish_agent.callback.call_count == 1
    print ('call args ', publish_agent.callback.call_args[0])
    assert publish_agent.callback.call_args[0][1] == PLATFORM_ACTUATOR
    assert publish_agent.callback.call_args[0][3] == error_topic
    result_message = publish_agent.callback.call_args[0][5]
    assert result_message['type'] == 'TypeError'
    assert result_message['value'] == 'Agent id must be a nonempty string'
