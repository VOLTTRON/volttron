# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
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

import pytest
import gevent
import os
from volttron.platform import get_services_core
from volttron.platform.messaging import headers as headers_mod
from volttron.platform.agent import utils
from datetime import datetime
from mock import MagicMock


@pytest.fixture(scope="module")
def multi_messagebus_forwarder(volttron_multi_messagebus):
    from_instance, to_instance = volttron_multi_messagebus()
    to_instance.allow_all_connections()
    forwarder_config = {"custom_topic_list": ["foo"]}

    if to_instance.messagebus == 'rmq':
        remote_address = to_instance.bind_web_address
        to_instance.enable_auto_csr()
        print("REQUEST CA: {}".format(os.environ.get('REQUESTS_CA_BUNDLE')))
        os.environ['REQUESTS_CA_BUNDLE'] = to_instance.requests_ca_bundle

        forwarder_config['destination-address'] = remote_address
    else:
        remote_address = to_instance.vip_address
        forwarder_config['destination-vip'] = remote_address
        forwarder_config['destination-serverkey'] = to_instance.serverkey

    forwarder_uuid = from_instance.install_agent(
        agent_dir=get_services_core("ForwardHistorian"),
        config_file=forwarder_config,
        start=True
    )
    gevent.sleep(1)
    assert from_instance.is_agent_running(forwarder_uuid)

    yield from_instance, to_instance

    from_instance.stop_agent(forwarder_uuid)


def publish(publish_agent, topic, header, message):
    publish_agent.vip.pubsub.publish('pubsub',
                                     topic,
                                     headers=header,
                                     message=message).get(timeout=10)


def instance_reset(wrapper):
    if not wrapper.is_running():
        wrapper.restart_platform()

    wrapper.remove_all_agents()


@pytest.mark.forwarder
def test_multi_messagebus_forwarder(multi_messagebus_forwarder):
    """
    Forward Historian test with multi message bus combinations
    :return:
    """
    from_instance, to_instance = multi_messagebus_forwarder
    publish_agent = from_instance.dynamic_agent
    subscriber_agent = to_instance.dynamic_agent

    subscriber_agent.callback = MagicMock(name="callback")
    subscriber_agent.callback.reset_mock()
    subscriber_agent.vip.pubsub.subscribe(peer='pubsub',
                               prefix='devices',
                               callback=subscriber_agent.callback).get()

    subscriber_agent.analysis_callback = MagicMock(name="analysis_callback")
    subscriber_agent.analysis_callback.reset_mock()
    subscriber_agent.vip.pubsub.subscribe(peer='pubsub',
                                          prefix='analysis',
                                          callback=subscriber_agent.analysis_callback).get()
    sub_list = subscriber_agent.vip.pubsub.list('pubsub').get()
    gevent.sleep(3)

    # Create timestamp
    now = utils.format_timestamp(datetime.utcnow())
    print("now is ", now)
    headers = {
        headers_mod.DATE: now,
        headers_mod.TIMESTAMP: now
    }

    for i in range(0, 5):
        topic = "devices/PNNL/BUILDING1/HP{}/CoolingTemperature".format(i)
        value = 35
        publish(publish_agent, topic, headers, value)
        topic = "analysis/PNNL/BUILDING1/WATERHEATER{}/ILCResults".format(i)
        value = {'result': 'passed'}
        publish(publish_agent, topic, headers, value)
        gevent.sleep(0.5)

    assert subscriber_agent.callback.call_count == 5
    assert subscriber_agent.analysis_callback.call_count == 5


@pytest.mark.forwarder
def test_multi_messagebus_custom_topic_forwarder(multi_messagebus_forwarder):
    """
    Forward Historian test for custom topics with multi message bus combinations
    :return:
    """
    from_instance, to_instance = multi_messagebus_forwarder
    publish_agent = from_instance.dynamic_agent
    subscriber_agent = to_instance.dynamic_agent

    subscriber_agent.callback = MagicMock(name="callback")
    subscriber_agent.callback.reset_mock()
    subscriber_agent.vip.pubsub.subscribe(peer='pubsub',
                               prefix='foo',
                               callback=subscriber_agent.callback).get()
    #subscriber_agent.vip.pubsub.list(subscriber_agent.core.identity)
    # Create timestamp
    now = utils.format_timestamp(datetime.utcnow())
    print("now is ", now)
    headers = {
        headers_mod.DATE: now,
        headers_mod.TIMESTAMP: now
    }
    gevent.sleep(5)
    for i in range(0, 5):
        topic = "foo/grid_signal"
        value = 78.5 + i
        publish(publish_agent, topic, headers, value)
        gevent.sleep(0.1)
    gevent.sleep(1)
    assert subscriber_agent.callback.call_count == 5


@pytest.mark.forwarder
def test_multi_messagebus_forwarder_reconnection(multi_messagebus_forwarder):
    """
    Forward Historian reconnection test with multi-bus combinations
    :return:
    """
    from_instance, to_instance = multi_messagebus_forwarder
    to_instance.skip_cleanup = True

    # Restart target platform
    to_instance.shutdown_platform()
    gevent.sleep(3)
    to_instance.restart_platform()
    gevent.sleep(5)

    publish_agent = from_instance.dynamic_agent
    subscriber_agent = to_instance.dynamic_agent

    subscriber_agent.callback = MagicMock(name="callback")
    subscriber_agent.callback.reset_mock()
    subscriber_agent.vip.pubsub.subscribe(peer='pubsub',
                                          prefix='foo',
                                          callback=subscriber_agent.callback)
    gevent.sleep(1)
    # Create timestamp
    now = utils.format_timestamp(datetime.utcnow())
    print("now is ", now)
    headers = {
        headers_mod.DATE: now,
        headers_mod.TIMESTAMP: now
    }

    for i in range(0, 3):
        topic = "foo/grid_signal"
        value = 78.5 + i
        publish(publish_agent, topic, headers, value)
        gevent.sleep(0.1)

    gevent.sleep(3)
    assert subscriber_agent.callback.call_count == 3
