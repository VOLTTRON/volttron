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
Pytest test cases for SysMonAgent
"""

import json
import pytest

import gevent

from volttrontesting.utils.utils import poll_gevent_sleep

_test_config = {
    "base_topic": "test1/sysmon",
    "cpu_check_interval": 1,
    "memory_check_interval": 1,
    "disk_check_interval": 1,
    "disk_path": "/"
}


@pytest.fixture()
def sysmon_tester_agent(request, volttron_instance, tmpdir):
    """
    Fixture used for setting up SysMonAgent and tester agent
    """
    config = tmpdir.mkdir('config').join('config')
    config.write(json.dumps(_test_config))

    sysmon_uuid = volttron_instance.install_agent(
        agent_dir='services/core/SysMonAgent',
        config_file=str(config),
        start=True)

    agent = volttron_instance.build_agent()

    def stop_agent():
        volttron_instance.stop_agent(sysmon_uuid)
        volttron_instance.remove_agent(sysmon_uuid)
        agent.core.stop()

    request.addfinalizer(stop_agent)
    return agent


def listen(agent, config):
    """Assert all SysMonAgent topics have been heard"""
    base_topic = config['base_topic']
    short_topics = ['cpu_percent', 'memory_percent', 'disk_percent']
    topics = [base_topic + '/' + x for x in short_topics]
    seen_topics = set()

    def add_topic(peer, sender, bus, topic, headers, messages):
        seen_topics.add(topic)

    agent.vip.pubsub.subscribe('pubsub', base_topic,
                               callback=add_topic)

    max_wait = 1 + max([value for key, value in _test_config.items()
                        if key.endswith('_interval')])

    all_topics_seen = lambda: set(topics) <= seen_topics

    assert poll_gevent_sleep(max_wait, all_topics_seen)


def test_listen(sysmon_tester_agent):
    """Test that data is published to expected topics"""
    listen(sysmon_tester_agent, _test_config)


def test_reconfigure_then_listen(sysmon_tester_agent):
    """Test that the topic can be reconfigured"""
    new_config = _test_config.copy()
    new_config['base_topic'] = 'test2/sysmon'
    sysmon_tester_agent.vip.rpc.call('platform.sysmon', 'reconfigure',
                                     **new_config)
    listen(sysmon_tester_agent, new_config)
