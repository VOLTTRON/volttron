# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
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

#}}}

"""
Pytest test cases for ThresholdDetectionAgent
"""

import json
import pytest

import gevent

from volttron.platform.vip.agent import Agent, PubSub
from volttrontesting.utils.utils import poll_gevent_sleep

_test_config = {
    "watch_max": [
        {
            "topic": "test1",
            "threshold": 10,
            "message": "{topic} > {threshold}",
            "enabled": True
        },
        {
            "topic": "test2",
            "threshold": 10,
            "message": "{topic} > {threshold}",
            "enabled": False
        },

    ],
    "watch_min": [
        {
            "topic": "test3",
            "threshold": 10,
            "message": "{topic} < {threshold}",
            "enabled": True
        }
    ]
}


class AlertWatcher(Agent):
    """Keep track of seen alerts"""
    def __init__(self, *args, **kwargs):
        super(AlertWatcher, self).__init__(*args, **kwargs)
        self.seen_alert_keys = set()

    @PubSub.subscribe('pubsub', 'alerts')
    def add_alert_key(self, peer, sender, bus, topic, headers, messages):
        alert_key = headers.get('alert_key')
        if alert_key:
            self.seen_alert_keys.add(alert_key)


@pytest.fixture(scope="function")
def threshold_tester_agent(request, volttron_instance, tmpdir):
    """
    Fixture used for setting up ThresholdDetectionAgent and
    tester agents
    """
    config = tmpdir.mkdir('config').join('config')
    config.write(json.dumps(_test_config))

    threshold_detection_uuid = volttron_instance.install_agent(
        agent_dir='services/core/ThresholdDetectionAgent',
        config_file=str(config),
        start=True)

    agent = volttron_instance.build_agent(agent_class=AlertWatcher)

    def stop_agent():
        volttron_instance.stop_agent(threshold_detection_uuid)
        volttron_instance.remove_agent(threshold_detection_uuid)
        agent.core.stop()

    request.addfinalizer(stop_agent)
    return agent


def publish(agent, config, operation, to_max=True):
    for entry in config['watch_max' if to_max else 'watch_min']:
        agent.vip.pubsub.publish('pubsub', entry['topic'], None,
                              operation(entry['threshold']))



def test_above_max(threshold_tester_agent):
    """Should get alert because values exceed max"""
    publish(threshold_tester_agent, _test_config, lambda x: x+1)
    # Only test1 should alert because test2 is disabled
    check = lambda: threshold_tester_agent.seen_alert_keys == set(['test1'])
    assert poll_gevent_sleep(2, check)



def test_above_min(threshold_tester_agent):
    """Should not get any alerts because values are above min"""
    publish(threshold_tester_agent, _test_config, lambda x: x+1, to_max=False)
    gevent.sleep(1)
    assert len(threshold_tester_agent.seen_alert_keys) == 0



def test_below_max(threshold_tester_agent):
    """Should not get any alerts because values are below max"""
    publish(threshold_tester_agent, _test_config, lambda x: x-1)
    gevent.sleep(1)
    assert len(threshold_tester_agent.seen_alert_keys) == 0



def test_below_min(threshold_tester_agent):
    """Should get alert because values below min"""
    publish(threshold_tester_agent, _test_config, lambda x: x-1, to_max=False)
    check = lambda: threshold_tester_agent.seen_alert_keys == set(['test3'])
    assert poll_gevent_sleep(2, check)


