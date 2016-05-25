# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2015, Battelle Memorial Institute
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

# }}}
import gevent
import pytest
import time

from zmq import curve_keypair

from volttron.platform.vip.agent import Agent, PubSub, Core
from volttron.platform.vip.socket import encode_key
from volttrontesting.utils.platformwrapper import PlatformWrapper


@pytest.mark.wrapper
def test_can_connect_to_instance(volttron_instance):
    assert volttron_instance is not None
    assert volttron_instance.is_running()
    assert not volttron_instance.list_agents()
    message = 'Pinging Hello'
    agent = volttron_instance.build_agent()
    response = agent.vip.ping('', message).get(timeout=3)
    agent.core.stop()
    assert response[0] == message


@pytest.mark.wrapper
def test_can_install_listener(volttron_instance):
    clear_messages()
    vi = volttron_instance
    assert vi is not None
    assert vi.is_running()

    auuid = vi.install_agent(agent_dir="examples/ListenerAgent",
                             start=False)
    assert auuid is not None
    started = vi.start_agent(auuid)
    print('STARTED: ', started)
    listening = vi.build_agent()
    listening.vip.pubsub.subscribe(peer='pubsub',
                                   prefix='heartbeat/ListenerAgent',
                                   callback=onmessage)
    # sleep for 10 seconds and at least one heartbeat should have been
    # published
    # because it's set to 5 seconds.
    time_start = time.time()

    print('Awaiting heartbeat response.')
    while not messages_contains_prefix(
            'heartbeat/ListenerAgent') and time.time() < time_start + 10:
        gevent.sleep(0.2)

    assert messages_contains_prefix('heartbeat/ListenerAgent')

    stopped = vi.stop_agent(auuid)
    print('STOPPED: ', stopped)
    removed = vi.remove_agent(auuid)
    print('REMOVED: ', removed)


@pytest.mark.wrapper
def test_can_stop_vip_heartbeat(volttron_instance):
    clear_messages()
    vi = volttron_instance
    assert vi is not None
    assert vi.is_running()

    agent = vi.build_agent(heartbeat_autostart=True, heartbeat_period=5)
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
def test_can_ping_pubsub(volttron_instance):
    vi = volttron_instance
    agent = vi.build_agent()
    resp = agent.vip.ping('', 'hello').get(timeout=5)
    print('ROUTER RESP: ', resp)
    resp = agent.vip.ping('pubsub', 'hello').get(timeout=5)
    print('PUBSUB RESP: ', resp)


@pytest.mark.wrapper
def test_can_call_rpc_method(volttron_instance):
    config = dict(agentid="Central Platform", report_status_period=15)
    agent_uuid = volttron_instance.install_agent(
        agent_dir='services/core/VolttronCentralPlatform',
        config_file=config,
        start=True)
    assert agent_uuid is not None
    assert volttron_instance.is_agent_running(agent_uuid)

    agent = volttron_instance.build_agent()

    agent_list = agent.vip.rpc.call('platform.agent',
                                    method='list_agents').get(timeout=5)

    print('The agent list is: {}'.format(agent_list))
    assert agent_list is not None


@pytest.mark.wrapper
def test_can_remove_agent(volttron_instance):
    """ Confirms that 'volttron-ctl remove' removes agent as expected. """
    assert volttron_instance is not None
    assert volttron_instance.is_running()

    # Install ListenerAgent as the agent to be removed.
    agent_uuid = volttron_instance.install_agent(
        agent_dir="examples/ListenerAgent", start=False)
    assert agent_uuid is not None
    started = volttron_instance.start_agent(agent_uuid)
    assert started is not None
    assert volttron_instance.agent_status(agent_uuid) is not None

    # Now attempt removal
    volttron_instance.remove_agent(agent_uuid)

    # Confirm that it has been removed.
    assert volttron_instance.agent_status(agent_uuid) is None


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


def test_can_ping_router(volttron_instance):
    vi = volttron_instance
    agent = vi.build_agent()
    resp = agent.vip.ping('', 'router?').get(timeout=4)
    # resp = agent.vip.hello().get(timeout=1)
    print("HELLO RESPONSE!", resp)


@pytest.mark.wrapper
def test_can_install_listener_on_two_platforms(get_volttron_instances):
    volttron_instance1, volttron_instance2 = get_volttron_instances(2)
    global messages
    clear_messages()
    auuid = volttron_instance1.install_agent(
        agent_dir="examples/ListenerAgent",
        start=False)
    assert auuid is not None
    started = volttron_instance1.start_agent(auuid)
    print('STARTED: ', started)
    listening = volttron_instance1.build_agent()
    listening.vip.pubsub.subscribe(peer='pubsub',
                                   prefix='heartbeat/ListenerAgent',
                                   callback=onmessage)

    # sleep for 10 seconds and at least one heartbeat should have been
    # published
    # because it's set to 5 seconds.
    time_start = time.time()

    clear_messages()
    auuid2 = volttron_instance2.install_agent(
        agent_dir="examples/ListenerAgent",
        start=True)
    assert auuid2 is not None
    started2 = volttron_instance2.start_agent(auuid2)
    print('STARTED: ', started2)
    listening = volttron_instance2.build_agent()
    listening.vip.pubsub.subscribe(peer='pubsub',
                                   prefix='heartbeat/ListenerAgent',
                                   callback=onmessage)

    # sleep for 10 seconds and at least one heartbeat should have been
    # published
    # because it's set to 5 seconds.
    time_start = time.time()

    print('Awaiting heartbeat response.')
    while not messages_contains_prefix(
            'heartbeat/ListenerAgent') and time.time() < time_start + 10:
        gevent.sleep(0.2)

    assert messages_contains_prefix('heartbeat/ListenerAgent')


# def test_can_ping_control(volttron_instance2):
#     agent = volttron_instance2.build_agent()
#     res = agent.vip.ping('aip', 'hello').get(timeout=5)
#     assert res[0] == 'hello'

# def test_can_publish_messages(volttron_instance):
#     amessage = [None]
#     def onmessage(peer, sender, bus, topic, headers, message):
#         amessage[0] = message
#
#     agent_publisher = volttron_instance.build_agent()
#     response = agent_publisher.vip.ping('', 'woot').get(timeout=3)
#     assert response[0] == 'woot'
#     agent_subscriber = volttron_instance.build_agent()
#     response = agent_subscriber.vip.ping('', 'woot2').get(timeout=3)
#     assert response[0] == 'woot2'
#
#     agent_subscriber.vip.pubsub.subscribe(peer='pubsub',
#         prefix='test/data', callback=onmessage).get(timeout=5)
#     themessage = 'I am a fish!'
#     agent_publisher.vip.pubsub.publish(peer='pubsub',
#         topic='test/data', message=themessage).get(timeout=5)
#
#     agent_subscriber.core.stop()
#     agent_publisher.core.stop()
#
#     assert themessage == amessage[0]


# def test_volttron_fixtures(volttron_instance, volttron_instance2):
#     assert volttron_instance is not None
#     assert volttron_instance2 is not None
#     assert volttron_instance != volttron_instance2
#     assert volttron_instance2.is_running()
#     assert volttron_instance.is_running()
#     print('VIP ADDRESS')
#     print(volttron_instance.vip_address)
#     ipc = "ipc://"+volttron_instance.volttron_home+"/run/vip.socket"
#     agent = Agent(address='tcp://127.0.0.1:22916')
#     gevent.spawn(agent.core.run)
#     gevent.sleep(0)
#     print('AFTER SLEEPING')
#     response = agent.vip.hello('Hello World!').get(timeout=5)
#     print(response)
#     agent.core.stop()
#
#     agent = PlatormTestAgent(address=volttron_instance.vip_address,
#                              identity='Listener Found')
#     task = gevent.spawn(agent.core.run)
#     gevent.sleep(10)
#     response = agent.vip.ping('doah', 'hear me!').get(timeout=3)
#     print("PINGING")
#     print(response)
#     agent.core.stop()
#
#
#
#
#
# def test_instance_enviornment(volttron_instance, volttron_instance2):
#     assert volttron_instance.env['VOLTTRON_HOME'] != \
#         volttron_instance2.env['VOLTTRON_HOME']
#
# def test_platform_startup(volttron_instance, volttron_instance2):
#     assert volttron_instance.is_running()
#     assert volttron_instance2.is_running()
#     assert not volttron_instance.twistd_is_running()
#     assert not volttron_instance2.twistd_is_running()
#
# def test_install_listener(volttron_instance, listener_agent_wheel):
#     uuid = volttron_instance.install_agent(agent_dir='examples/ListenerAgent')
#     assert uuid
#     status = volttron_instance.agent_status(uuid)
#     assert status != (None, None)
#     assert volttron_instance.confirm_agent_running("listeneragent-3.0")

@pytest.mark.wrapper
def test_encryption():
    addr = 'tcp://127.0.0.1:55055'
    pub, sec = curve_keypair()
    publickey, secretkey = encode_key(pub), encode_key(sec)
    auth = {'allow': [{'credentials': 'CURVE:{}'.format(publickey)}]}

    plat = PlatformWrapper()
    plat.startup_platform(vip_address=addr, auth_dict=auth, encrypt=True)

    agent_addr = '{}?serverkey={}&publickey={}&secretkey=' \
                 '{}'.format(addr, plat.publickey, publickey, secretkey)

    agent1 = plat.build_agent(agent_addr, identity='agent1')
    peers = agent1.vip.peerlist.list().get(timeout=2)
    plat.shutdown_platform()
    print('PEERS: ', peers)
    assert len(peers) > 0
