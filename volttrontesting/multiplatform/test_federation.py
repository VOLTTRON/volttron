# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
# }}}
"""
pytest test cases base historian to test all_platform configuration.
By default all_platform is set to False and historian subscribes only to topics from local message bus.
When all_platforms=True, historian will subscribe to topics from all connected platforms

"""

import gevent
import pytest

from volttron.platform import get_examples
from volttron.platform.agent.known_identities import CONTROL
from volttron.platform import is_rabbitmq_available
if not is_rabbitmq_available():
    pytest.skip("Pika is not installed", allow_module_level=True)


@pytest.mark.timeout(600)
@pytest.mark.federation
def test_federation_pubsub(federated_rmq_instances):
    upstream, downstream = federated_rmq_instances
    assert upstream.is_running()
    assert downstream.is_running()

    subscription_results2 = {}
    subscription_results3 = {}
    subscriber = downstream.dynamic_agent
    publisher = upstream.dynamic_agent

    def callback2(peer, sender, bus, topic, headers, message):
        subscription_results2[topic] = {'headers': headers, 'message': message}
        print("platform2 sub results [{}] = {}".format(topic, subscription_results2[topic]))

    def callback3(peer, sender, bus, topic, headers, message):
        subscription_results3[topic] = {'headers': headers, 'message': message}
        print("platform2 sub results [{}] = {}".format(topic, subscription_results3[topic]))

    subscriber.vip.pubsub.subscribe(peer='pubsub',
                                     prefix='devices/campus/building1',
                                     callback=callback2,
                                     all_platforms=True)

    subscriber.vip.pubsub.subscribe(peer='pubsub',
                                     prefix='analysis',
                                     callback=callback3,
                                     all_platforms=True)

    gevent.sleep(1)
    for i in range(5):
        publisher.vip.pubsub.publish(peer='pubsub', topic='devices/campus/building1', message=[{'point': 'value'}])
        gevent.sleep(1)
        message = subscription_results2['devices/campus/building1']['message']
        assert message == [{'point': 'value'}]

    for i in range(5):
        publisher.vip.pubsub.publish(peer='pubsub',
                                        topic='analysis/airside/campus/building1',
                                        message=[{'result': 'pass'}])
        gevent.sleep(1)
        message = subscription_results3['analysis/airside/campus/building1']['message']
        assert message == [{'result': 'pass'}]


@pytest.mark.federation
def test_federation_rpc(two_way_federated_rmq_instances):
    instance_1, instance_2 = two_way_federated_rmq_instances
    assert instance_1.is_running()
    assert instance_2.is_running()

    auuid = None
    try:
        auuid = instance_2.install_agent(
            agent_dir=get_examples("ListenerAgent"), start=True)
        assert auuid is not None
        test_agent = instance_1.dynamic_agent
        kwargs = {"external_platform": instance_2.instance_name}
        agts = test_agent.vip.rpc.call(CONTROL,
                                       'list_agents',
                                       **kwargs).get(timeout=10)

        assert agts[0]['identity'].startswith('listener')
        listener_uuid = agts[0]['uuid']
        test_agent.vip.rpc.call(CONTROL,
                                'stop_agent',
                                listener_uuid,
                                **kwargs).get(timeout=10)
        agt_status = test_agent.vip.rpc.call(CONTROL,
                                             'agent_status',
                                             listener_uuid,
                                             **kwargs).get(timeout=10)
        assert agt_status[1] == 0
    finally:
        if instance_2.is_running:
            instance_2.remove_agent(auuid)
