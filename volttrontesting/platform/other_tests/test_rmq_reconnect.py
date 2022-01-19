# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

from __future__ import print_function

"""
Pytest test cases for testing rabbitmq reconnect cases.
"""

import gevent
import pytest
from mock import MagicMock

from volttron.utils.rmq_setup import start_rabbit, stop_rabbit
from volttron.utils.rmq_config_params import RMQConfig
from volttron.platform.vip.agent.errors import Unreachable


@pytest.fixture(scope="module")
def publisher_agent(request, volttron_instance_rmq):
    publisher_agent = volttron_instance_rmq.build_agent()

    def stop_agent():
        print("In teardown method of publisher_agent")
        publisher_agent.core.stop()

    request.addfinalizer(stop_agent)

    return publisher_agent


@pytest.fixture(scope="module")
def subscriber_agent(request, volttron_instance_rmq):
    subscriber_agent = volttron_instance_rmq.build_agent()

    subscriber_agent.callback = MagicMock(name="callback")
    subscriber_agent.callback.reset_mock()

    # subscribe to test publishes
    subscriber_agent.vip.pubsub.subscribe(
        peer='pubsub',
        prefix="test/test_message",
        callback=subscriber_agent.callback)
    gevent.sleep(0.2)

    def stop_agent():
        print("In teardown method of publisher_agent")
        subscriber_agent.core.stop()

    request.addfinalizer(stop_agent)

    return subscriber_agent


@pytest.mark.rmq_reconnect
def test_on_rmq_reconnect(volttron_instance_rmq, publisher_agent, subscriber_agent):
    """
    Test the fix for issue# 1702
    :param request:
    :param volttron_instance_rmq:
    :return:
    """
    publisher_agent.vip.pubsub.publish(peer='pubsub',
                                       topic='test/test_message',
                                       headers={},
                                       message="This is test message")
    gevent.sleep(0.5)
    assert subscriber_agent.callback.call_count == 1

    # Stop RabbitMQ server
    rmq_cfg = RMQConfig()
    stop_rabbit(rmq_cfg.rmq_home, env=volttron_instance_rmq.env)

    gevent.sleep(1)
    # Start RabbitMQ server again
    start_rabbit(rmq_cfg.rmq_home, env=volttron_instance_rmq.env)

    gevent.sleep(8)

    publisher_agent.vip.pubsub.publish(peer='pubsub',
                                       topic='test/test_message',
                                       headers={},
                                       message="This is test message after rmq reconnect")
    gevent.sleep(0.1)
    assert subscriber_agent.callback.call_count == 2


@pytest.mark.rmq_reconnect
def test_rmq_reconnect_with_publish(volttron_instance_rmq, publisher_agent, subscriber_agent):
    """
    Test the fix for issue# 1702
    :param request:
    :param volttron_instance_rmq:
    :return:
    """
    subscriber_agent.callback.reset_mock()
    gevent.sleep(0.2)
    publisher_agent.vip.pubsub.publish(peer='pubsub',
                                       topic='test/test_message',
                                       headers={},
                                       message="This is test message")
    gevent.sleep(0.2)
    assert subscriber_agent.callback.call_count == 1

    # Stop RabbitMQ server
    rmq_cfg = RMQConfig()
    stop_rabbit(rmq_cfg.rmq_home, env=volttron_instance_rmq.env)
    gevent.sleep(2)
    # Start RabbitMQ server
    start_rabbit(rmq_cfg.rmq_home, env=volttron_instance_rmq.env)
    gevent.sleep(2)

    for i in range(5):
        try:
            publisher_agent.vip.pubsub.publish(peer='pubsub',
                                               topic='test/test_message',
                                               headers={},
                                               message="This is test message")
        except Unreachable:
            # Apply back pressure and try again after sleep
            gevent.sleep(1)

    publisher_agent.vip.pubsub.publish(peer='pubsub',
                                       topic='test/test_message',
                                       headers={},
                                       message="This is test message after rmq reconnect")
    gevent.sleep(0.1)
    assert subscriber_agent.callback.call_count >= 2


@pytest.mark.rmq_reconnect
def test_resource_lock_condition(request, volttron_instance_rmq):
    agent1 = volttron_instance_rmq.build_agent(identity='agentx')
    agent2 = None
    try:
        agent2 = volttron_instance_rmq.build_agent(identity='agentx')
    except Unreachable:
        assert agent2 is None

    def stop_agent():
        print("In teardown method of publisher_agent")
        agent1.core.stop()

    request.addfinalizer(stop_agent)


