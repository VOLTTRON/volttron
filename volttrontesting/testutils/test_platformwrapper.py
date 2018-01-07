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
import requests

import gevent
import pytest
import time
import os

from volttron.platform import get_services_core, get_examples
from volttron.platform.agent import json as jsonapi

from volttrontesting.utils.platformwrapper import start_wrapper_platform, \
    PlatformWrapper


@pytest.fixture(scope="module")
def setup_instances():

    inst1 = PlatformWrapper()
    inst2 = PlatformWrapper()

    start_wrapper_platform(inst1)
    start_wrapper_platform(inst2)

    yield inst1, inst2

    inst1.shutdown_platform()
    inst2.shutdown_platform()


def test_can_restart_platform_without_addresses_changing(setup_instances):
    inst_forward, inst_target = setup_instances
    original_vip = inst_forward.vip_address
    assert inst_forward.is_running()
    inst_forward.stop_platform()
    assert not inst_forward.is_running()
    inst_forward.restart_platform()
    assert inst_forward.is_running()
    assert original_vip == inst_forward.vip_address



@pytest.mark.wrapper
@pytest.mark.skip("Upgrade to fix.")
def test_instance_writes_to_instances_file(volttron_instance):
    vi = volttron_instance
    assert vi is not None
    assert vi.is_running()

    instances_file = os.path.expanduser("~/.volttron_instances")

    with open(instances_file, 'r') as fp:
        result = jsonapi.loads(fp.read())

    assert result.get(vi.volttron_home)
    the_instance_entry = result.get(vi.volttron_home)
    for key in ('pid', 'vip-address', 'volttron-home', 'start-args'):
        assert the_instance_entry.get(key)

    assert the_instance_entry['pid'] == vi.p_process.pid

    assert the_instance_entry['vip-address'][0] == vi.vip_address
    assert the_instance_entry['volttron-home'] == vi.volttron_home


@pytest.mark.wrapper
@pytest.mark.skip("Upgrade to fix.")
def test_can_install_listener(volttron_instance):
    clear_messages()
    vi = volttron_instance
    assert vi is not None
    assert vi.is_running()

    auuid = vi.install_agent(agent_dir=get_examples("ListenerAgent"),
                             start=False)
    assert auuid is not None
    started = vi.start_agent(auuid)
    print('STARTED: ', started)
    listening = vi.build_agent()
    listening.vip.pubsub.subscribe(peer='pubsub',
                                   prefix='heartbeat/listeneragent',
                                   callback=onmessage)
    # sleep for 10 seconds and at least one heartbeat should have been
    # published
    # because it's set to 5 seconds.
    time_start = time.time()

    print('Awaiting heartbeat response.')
    while not messages_contains_prefix(
            'heartbeat/listeneragent') and time.time() < time_start + 10:
        gevent.sleep(0.2)

    assert messages_contains_prefix('heartbeat/listeneragent')

    stopped = vi.stop_agent(auuid)
    print('STOPPED: ', stopped)
    removed = vi.remove_agent(auuid)
    print('REMOVED: ', removed)

@pytest.mark.xfail(reason="#776 Needs updating")
@pytest.mark.timeout(1000)
def test_resinstall_agent(volttron_instance):
    mysql_config = {
        "connection": {
            "type": "mysql",
            "params": {
                "host": "localhost",
                "port": 3306,
                "database": "test_historian",
                "user": "historian",
                "passwd": "historian"
            }
        }
    }
    for i in range(0,50):
        print("Counter: {}".format(i))
        # auuid = volttron_instance.install_agent(
        #     agent_dir=get_examples("ListenerAgent",
        #     vip_identity='test_listener',
        #     start=True)
        auuid = volttron_instance.install_agent(
            agent_dir=get_services_core("SQLHistorian"),
            config_file=mysql_config,
            start=True,
            vip_identity='test_historian')
        assert volttron_instance.is_agent_running(auuid)
        volttron_instance.remove_agent(auuid)


@pytest.mark.wrapper
@pytest.mark.skip("Upgrade to fix.")
def test_can_stop_vip_heartbeat(volttron_instance):
    clear_messages()
    vi = volttron_instance
    assert vi is not None
    assert vi.is_running()

    agent = vi.build_agent(heartbeat_autostart=True,
                           heartbeat_period=1,
                           identity='Agent')
    agent.vip.pubsub.subscribe(peer='pubsub', prefix='heartbeat/Agent',
                               callback=onmessage)

    # Make sure heartbeat is recieved
    time_start = time.time()
    print('Awaiting heartbeat response.')
    while not messages_contains_prefix(
            'heartbeat/Agent') and time.time() < time_start + 10:
        gevent.sleep(0.2)

    assert messages_contains_prefix('heartbeat/Agent')

    # Make sure heartbeat is stopped

    agent.vip.heartbeat.stop()
    clear_messages()
    time_start = time.time()
    while not messages_contains_prefix(
            'heartbeat/Agent') and time.time() < time_start + 10:
        gevent.sleep(0.2)

    assert not messages_contains_prefix('heartbeat/Agent')


@pytest.mark.wrapper
@pytest.mark.skip("Upgrade to fix.")
def test_can_ping_pubsub(volttron_instance):
    vi = volttron_instance
    agent = vi.build_agent()
    resp = agent.vip.ping('', 'hello').get(timeout=5)
    print('ROUTER RESP: ', resp)

@pytest.mark.wrapper
@pytest.mark.skip("Upgrade to fix.")
def test_can_remove_agent(volttron_instance):
    """ Confirms that 'volttron-ctl remove' removes agent as expected. """
    assert volttron_instance is not None
    assert volttron_instance.is_running()

    # Install ListenerAgent as the agent to be removed.
    agent_uuid = volttron_instance.install_agent(
        agent_dir=get_examples("ListenerAgent"), start=False)
    assert agent_uuid is not None
    started = volttron_instance.start_agent(agent_uuid)
    assert started is not None
    pid = volttron_instance.agent_pid(agent_uuid)
    assert pid is not None and pid > 0

    # Now attempt removal
    volttron_instance.remove_agent(agent_uuid)

    # Confirm that it has been removed.
    pid = volttron_instance.agent_pid(agent_uuid)
    assert pid is None


messages = {}


def onmessage(peer, sender, bus, topic, headers, message):
    messages[topic] = {'headers': headers, 'message': message}


def clear_messages():
    global messages
    messages = {}


def messages_contains_prefix(prefix):
    global messages
    return any(map(lambda x: x.startswith(prefix), messages.keys()))


@pytest.mark.wrapper
@pytest.mark.skip("Upgrade to fix.")
def test_can_publish(volttron_instance):
    global messages
    clear_messages()
    vi = volttron_instance
    agent = vi.build_agent()
    #    gevent.sleep(0)
    agent.vip.pubsub.subscribe(peer='pubsub', prefix='test/world',
                               callback=onmessage).get(timeout=5)

    agent_publisher = vi.build_agent()
    #    gevent.sleep(0)
    agent_publisher.vip.pubsub.publish(peer='pubsub', topic='test/world',
                                       message='got data')
    # sleep so that the message bus can actually do some work before we
    # eveluate the global messages.
    gevent.sleep(0.1)
    assert messages['test/world']['message'] == 'got data'


@pytest.mark.wrapper
@pytest.mark.skip("Upgrade to fix.")
def test_fixture_returns_single_if_one_requested(get_volttron_instances):
    wrapper = get_volttron_instances(1, False)
    assert isinstance(wrapper, PlatformWrapper)


@pytest.mark.skip("Upgrade to fix.")
def test_can_ping_router(volttron_instance):
    vi = volttron_instance
    agent = vi.build_agent()
    resp = agent.vip.ping('', 'router?').get(timeout=4)
    # resp = agent.vip.hello().get(timeout=1)
    print("HELLO RESPONSE!", resp)


@pytest.mark.wrapper
@pytest.mark.skip("Upgrade to fix.")
def test_can_install_listener_on_two_platforms(get_volttron_instances):

    wrapper1, wrapper2 = get_volttron_instances(2)

    global messages
    clear_messages()
    auuid = wrapper1.install_agent(
        agent_dir=get_examples("ListenerAgent"),
        start=False)
    assert auuid is not None
    started = wrapper1.start_agent(auuid)
    print('STARTED: ', started)
    listening = wrapper1.build_agent()
    listening.vip.pubsub.subscribe(peer='pubsub',
                                   prefix='heartbeat/listeneragent',
                                   callback=onmessage)

    # sleep for 10 seconds and at least one heartbeat should have been
    # published
    # because it's set to 5 seconds.
    time_start = time.time()

    clear_messages()
    auuid2 = wrapper2.install_agent(
        agent_dir=get_examples("ListenerAgent"),
        start=True)
    assert auuid2 is not None
    started2 = wrapper2.start_agent(auuid2)
    print('STARTED: ', started2)
    listening = wrapper2.build_agent()
    listening.vip.pubsub.subscribe(peer='pubsub',
                                   prefix='heartbeat/listeneragent',
                                   callback=onmessage)

    # sleep for 10 seconds and at least one heartbeat should have been
    # published
    # because it's set to 5 seconds.
    time_start = time.time()

    print('Awaiting heartbeat response.')
    while not messages_contains_prefix(
            'heartbeat/listeneragent') and time.time() < time_start + 10:
        gevent.sleep(0.2)

    assert messages_contains_prefix('heartbeat/listeneragent')
