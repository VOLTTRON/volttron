# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

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
#}}}

"""
Pytest test cases for SysMonAgent
"""

import os
import pytest

from volttron.platform import jsonapi, get_ops
from volttrontesting.utils.utils import poll_gevent_sleep

_test_config = {
    "base_topic": "test1/sysmon",
    "cpu_check_interval": 1,
    "memory_check_interval": 1,
    "disk_check_interval": 1,
    "disk_path": "/"
}

config_path = os.path.join(get_ops("SysMonAgent"), "sysmonagent.config")
with open(config_path, "r") as config_file:
    default_config_json = jsonapi.load(config_file)
assert isinstance(default_config_json, dict)


@pytest.fixture()
def sysmon_tester_agent(request, volttron_instance, tmpdir):
    """
    Fixture used for setting up SysMonAgent and tester agent
    """
    config = tmpdir.mkdir('config').join('config')
    config.write(jsonapi.dumps(_test_config))

    sysmon_uuid = volttron_instance.install_agent(
        agent_dir=get_ops("SysMonAgent"),
        config_file=_test_config,
        start=True)

    agent = volttron_instance.build_agent()

    def stop_agent():
        volttron_instance.stop_agent(sysmon_uuid)
        volttron_instance.remove_agent(sysmon_uuid)
        agent.core.stop()

    request.addfinalizer(stop_agent)
    return agent


def listen(agent, config):
    """
    Assert all SysMonAgent topics have been heard
    """
    base_topic = config['base_topic']
    short_topics = ['cpu_percent', 'memory_percent', 'disk_percent']
    topics = [base_topic + '/' + x for x in short_topics]
    seen_topics = set()

    def add_topic(peer, sender, bus, topic, headers, messages):
        seen_topics.add(topic)

    agent.vip.pubsub.subscribe('pubsub', base_topic, callback=add_topic)

    max_wait = 1 + max(value for key, value in _test_config.items() if key.endswith('_interval')) + 8
    print(f"Max wait: {max_wait}, topics: {topics}, seen_topics: {seen_topics}")
    assert poll_gevent_sleep(max_wait, lambda: set(topics) <= seen_topics)


def test_listen(sysmon_tester_agent):
    """
    Test that data is published to expected topics
    """
    listen(sysmon_tester_agent, _test_config)


def test_reconfigure_then_listen(sysmon_tester_agent):
    """
    Test that the topic can be reconfigured
    """
    new_config = _test_config.copy()
    new_config['base_topic'] = 'test2/sysmon'
    sysmon_tester_agent.vip.rpc.call('platform.sysmon', 'reconfigure', **new_config)
    listen(sysmon_tester_agent, new_config)


@pytest.mark.dev
def test_default_config(sysmon_tester_agent):
    """
    Test that the topic can be reconfigured
    """
    sysmon_tester_agent.vip.rpc.call('platform.sysmon', 'reconfigure', **default_config_json)
    listen(sysmon_tester_agent, default_config_json)
