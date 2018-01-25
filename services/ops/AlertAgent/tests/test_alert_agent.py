# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
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
import json

from volttron.platform import get_ops
from volttron.platform.agent.known_identities import PLATFORM_ALERTER

ALERT_CONFIG = {
    "group1": {
        "fakedevice": 5,
        "fakedevice2": {
            "seconds": 5,
            "points": ["point"]
        }
    }
}

alert_messages = {}

@pytest.fixture(scope='module')
def agent(request, volttron_instance1):

    alert_uuid = volttron_instance1.install_agent(
        agent_dir=get_ops("AlertAgent"),
        config_file=ALERT_CONFIG)
    gevent.sleep(2)

    agent = volttron_instance1.build_agent()

    def onmessage(peer, sender, bus, topic, headers, message):
        global alert_messages

        alert = json.loads(message)["context"]

        try:
            alert_messages[alert] += 1
        except KeyError:
            alert_messages[alert] = 1

    agent.vip.pubsub.subscribe(peer='pubsub',
                               prefix='alert',
                               callback=onmessage)

    def stop():
        volttron_instance1.stop_agent(alert_uuid)
        agent.core.stop()

    request.addfinalizer(stop)
    return agent


def test_alert_agent(agent):
    global alert_messages
    for _ in range(10):
        agent.vip.pubsub.publish(peer='pubsub',
                                 topic='fakedevice')
        agent.vip.pubsub.publish(peer='pubsub',
                                 topic='fakedevice2',
                                 message=[{'point': 'value'}])
        gevent.sleep(1)

    assert not alert_messages
    gevent.sleep(6)

    assert len(alert_messages) == 1


def test_ignore_topic(agent):
    global alert_messages

    agent.vip.rpc.call(PLATFORM_ALERTER, 'ignore_topic', 'group1', 'fakedevice2').get()
    alert_messages.clear()
    gevent.sleep(6)

    assert len(alert_messages) == 1
    assert u"Topic(s) not published within time limit: ['fakedevice']" in alert_messages


def test_watch_topic(agent):
    global alert_messages

    agent.vip.rpc.call(PLATFORM_ALERTER, 'watch_topic', 'group1', 'newtopic', 5).get()
    gevent.sleep(6)

    assert u"Topic(s) not published within time limit: ['newtopic']" in alert_messages


def test_watch_device(agent):
    global alert_messages

    agent.vip.rpc.call(PLATFORM_ALERTER, 'watch_device', 'group1', 'newdevice', 5, ['point']).get()
    gevent.sleep(6)

    assert u"Topic(s) not published within time limit: ['newdevice', ('newdevice', 'point')]" in alert_messages
