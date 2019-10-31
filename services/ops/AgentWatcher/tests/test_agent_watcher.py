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


from volttron.platform import get_ops, get_examples, jsonapi

WATCHER_CONFIG = {
    "watchlist": ["listener"],
    "check-period": 1
}

alert_messages = {}
listener_uuid = None

@pytest.fixture(scope='module')
def platform(request, volttron_instance):
    global listener_uuid

    listener_uuid = volttron_instance.install_agent(
        agent_dir=get_examples("ListenerAgent"),
        vip_identity="listener",
        start=True)
    gevent.sleep(2)

    watcher_uuid = volttron_instance.install_agent(
        agent_dir=get_ops("AgentWatcher"),
        config_file=WATCHER_CONFIG)
    gevent.sleep(2)

    agent = volttron_instance.build_agent()

    def onmessage(peer, sender, bus, topic, headers, message):
        global alert_messages

        alert = jsonapi.loads(message)["context"]

        try:
            alert_messages[alert] += 1
        except KeyError:
            alert_messages[alert] = 1

    agent.vip.pubsub.subscribe(peer='pubsub',
                               prefix='alerts',
                               callback=onmessage)

    def stop():
        volttron_instance.stop_agent(listener_uuid)
        volttron_instance.stop_agent(watcher_uuid)
        agent.core.stop()
        alert_messages.clear()

    request.addfinalizer(stop)
    return volttron_instance


def test_agent_watcher(platform):
    global alert_messages
    global listener_uuid

    gevent.sleep(2)
    assert not alert_messages

    platform.stop_agent(listener_uuid)
    gevent.sleep(2)
    assert alert_messages
    assert "Agent(s) expected but but not running ['listener']" in alert_messages

    platform.start_agent(listener_uuid)
    alert_messages.clear()
    gevent.sleep(2)

    assert not alert_messages
