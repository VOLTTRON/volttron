
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


import gevent
import pytest

from volttron.platform import get_ops, get_examples, jsonapi
from volttron.platform.agent.known_identities import PLATFORM_TOPIC_WATCHER
from volttron.platform.agent.utils import get_aware_utc_now

alert_messages = {}


@pytest.mark.alert
def test_remote_alert_publish(get_volttron_instances):
    """
    Test alert to remote agent with 2 ZMQ instances
    :return:
    """

    volttron_instance1, volttron_instance2 = get_volttron_instances(2)

    volttron_instance1.allow_all_connections()
    volttron_instance2.allow_all_connections()

    gevent.sleep(3)
    agent = volttron_instance1.build_agent()

    def onmessage(peer, sender, bus, topic, headers, message):
        global alert_messages

        alert = jsonapi.loads(message)["context"]

        try:
            alert_messages[alert] += 1
        except KeyError:
            alert_messages[alert] = 1
        print("In on message: {}".format(alert_messages))

    agent.vip.pubsub.subscribe(peer='pubsub',
                               prefix='alerts',
                               callback=onmessage)

    config = {
        "group1": {
            "fakedevice": 5,
            "fakedevice2/all": {
                "seconds": 5,
                "points": ["point"]
            }
        },
        "publish-settings": {
            "publish-local": False,
            "publish-remote": True,
            "remote": {
                "identity": "remote-agent",
                "serverkey": volttron_instance1.serverkey,
                "vip-address": volttron_instance1.vip_address
            }
        }
    }

    alert_uuid = volttron_instance2.install_agent(
        agent_dir=get_ops("TopicWatcher"),
        config_file=config,
        vip_identity=PLATFORM_TOPIC_WATCHER
    )

    gevent.sleep(6)

    assert alert_messages
    alert_messages.clear()


@pytest.mark.alert
def test_alert_multi_messagebus_publish(volttron_multi_messagebus):
    """
    Test alert to remote agent with multi message bus combinations
    :return:
    """

    source_instance, destination_instance = volttron_multi_messagebus()
    destination_instance.allow_all_connections()

    if destination_instance.messagebus == 'rmq':
        remote_address = destination_instance.bind_web_address
        destination_instance.enable_auto_csr()
    else:
        remote_address = destination_instance.vip_address

    gevent.sleep(3)
    agent = destination_instance.dynamic_agent

    def onmessage(peer, sender, bus, topic, headers, message):
        global alert_messages

        alert = jsonapi.loads(message)["context"]

        try:
            alert_messages[alert] += 1
        except KeyError:
            alert_messages[alert] = 1
        print("In on message: {}".format(alert_messages))

    agent.vip.pubsub.subscribe(peer='pubsub',
                               prefix='alerts',
                               callback=onmessage)

    config = {
        "group1": {
            "fakedevice": 5,
            "fakedevice2/all": {
                "seconds": 5,
                "points": ["point"]
            }
        },
        "publish-settings": {
            "publish-local": False,
            "publish-remote": True,
            "remote": {
                "identity": "remote-agent",
                "serverkey": destination_instance.serverkey,
                "vip-address": remote_address
            }
        }
    }

    alert_uuid = source_instance.install_agent(
        agent_dir=get_ops("TopicWatcher"),
        config_file=config,
        vip_identity=PLATFORM_TOPIC_WATCHER
    )

    gevent.sleep(6)

    assert u"Topic(s) not published within time limit: ['fakedevice', " \
           u"'fakedevice2/all', ('fakedevice2/all', 'point')]" in \
           alert_messages or \
           u"Topic(s) not published within time limit: ['fakedevice', " \
           u"('fakedevice2/all', 'point'), 'fakedevice2/all']" in \
            alert_messages or \
           u"Topic(s) not published within time limit: ['fakedevice2/all', " \
           u"('fakedevice2/all', 'point'), 'fakedevice']" in \
            alert_messages or \
           u"Topic(s) not published within time limit: [('fakedevice2/all', 'point'), " \
           u"'fakedevice2/all', 'fakedevice']" in \
           alert_messages

    alert_messages.clear()
