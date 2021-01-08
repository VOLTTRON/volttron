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
from configparser import ConfigParser
import time
import os

import requests
import gevent
import pytest
from mock import MagicMock

from volttron.platform import get_services_core, get_examples, jsonapi
from volttrontesting.utils.platformwrapper import PlatformWrapper, with_os_environ
from volttrontesting.utils.utils import get_rand_tcp_address, get_rand_http_address


@pytest.mark.parametrize("messagebus, ssl_auth", [
    ('zmq', False)
    # , ('zmq', False)
    # , ('rmq', True)
])
def test_can_create(messagebus, ssl_auth):
    p = PlatformWrapper(messagebus=messagebus, ssl_auth=ssl_auth)
    try:
        assert not p.is_running()
        assert p.volttron_home.startswith("/tmp/tmp")

        p.startup_platform(vip_address=get_rand_tcp_address())
        assert p.is_running()
        assert p.dynamic_agent.vip.ping("").get(timeout=2)
    finally:
        if p:
            p.shutdown_platform()

    assert not p.is_running()


@pytest.mark.parametrize("messagebus, https_enabled", [
    ('zmq', False)
    # TODO: Test enable generation of certs to support https
    # , ('zmq', True)
    # , ('zmq', False)
    # , ('rmq', True)
])
def test_can_create_web_enabled(messagebus: str, https_enabled: bool):
    p = PlatformWrapper(messagebus=messagebus)
    try:
        assert not p.is_running()
        assert p.volttron_home.startswith("/tmp/tmp")
        http_address = get_rand_http_address(https=https_enabled)
        p.startup_platform(vip_address=get_rand_tcp_address(), bind_web_address=http_address)
        assert p.is_running()
        response = requests.get(http_address, verify=False)
        assert response.ok
    finally:
        if p:
            p.shutdown_platform()

    assert not p.is_running()


@pytest.mark.wrapper
def test_volttron_config_created(volttron_instance):
    config_file = os.path.join(volttron_instance.volttron_home, "config")
    assert os.path.isfile(config_file)
    parser = ConfigParser()
    # with open(config_file, 'rb') as cfg:
    parser.read(config_file)
    assert volttron_instance.instance_name == parser.get('volttron', 'instance-name')
    assert volttron_instance.vip_address == parser.get('volttron', 'vip-address')
    assert volttron_instance.messagebus == parser.get('volttron', 'message-bus')


@pytest.mark.wrapper
def test_can_restart_platform_without_addresses_changing(get_volttron_instances):
    inst_forward, inst_target = get_volttron_instances(2)

    original_vip = inst_forward.vip_address
    assert inst_forward.is_running()
    inst_forward.stop_platform()
    assert not inst_forward.is_running()
    gevent.sleep(5)
    inst_forward.restart_platform()
    assert inst_forward.is_running()
    assert original_vip == inst_forward.vip_address


@pytest.mark.wrapper
def test_can_restart_platform(volttron_instance):
    orig_vip = volttron_instance.vip_address
    orig_vhome = volttron_instance.volttron_home
    orig_bus = volttron_instance.messagebus
    orig_bind = volttron_instance.bind_web_address
    orig_proc = volttron_instance.p_process.pid

    assert volttron_instance.is_running()
    volttron_instance.stop_platform()

    assert not volttron_instance.is_running()
    volttron_instance.restart_platform()
    assert volttron_instance.is_running()
    assert orig_vip == volttron_instance.vip_address
    assert orig_vhome == volttron_instance.volttron_home
    assert orig_bus == volttron_instance.messagebus
    assert orig_bind == volttron_instance.bind_web_address
    # Expecation that we won't have the same pid after we restart the platform.
    assert orig_proc != volttron_instance.p_process.pid
    assert len(volttron_instance.dynamic_agent.vip.peerlist().get()) > 0


@pytest.mark.wrapper
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
def test_can_install_listener(volttron_instance):
    vi = volttron_instance
    assert vi is not None
    assert vi.is_running()

    # agent identity should be
    auuid = vi.install_agent(agent_dir=get_examples("ListenerAgent"),
                             start=False)
    assert auuid is not None
    started = vi.start_agent(auuid)

    assert started
    assert vi.is_agent_running(auuid)
    listening = vi.build_agent()
    listening.callback = MagicMock(name="callback")
    listening.callback.reset_mock()

    assert listening.core.identity
    listening.vip.pubsub.subscribe(peer='pubsub',
                                   prefix='heartbeat/{}'.format(vi.get_agent_identity(auuid)),
                                   callback=listening.callback)

    # default heartbeat for core listener is 5 seconds.
    # sleep for 10 just in case we miss one.
    gevent.sleep(10)

    assert listening.callback.called
    call_args = listening.callback.call_args[0]
    # peer, sender, bus, topic, headers, message
    assert call_args[0] == 'pubsub'
    # TODO: This hard coded value should be changed with a platformwrapper call to a function
    # get_agent_identity(uuid)
    assert call_args[1] == vi.get_agent_identity(auuid)
    assert call_args[2] == ''
    assert call_args[3].startswith('heartbeat/listeneragent')
    assert 'max_compatible_version' in call_args[4]
    assert 'min_compatible_version' in call_args[4]
    assert 'TimeStamp' in call_args[4]
    assert 'GOOD' in call_args[5]

    stopped = vi.stop_agent(auuid)
    print('STOPPED: ', stopped)
    removed = vi.remove_agent(auuid)
    print('REMOVED: ', removed)
    listening.core.stop()


@pytest.mark.wrapper
def test_reinstall_agent(volttron_instance):
    sqlite_config = {
        "connection": {
            "type": "sqlite",
            "params": {
                "database": "data/historian.sqlite"
            }
        }
    }
    auuid = volttron_instance.install_agent(
        agent_dir=get_services_core("SQLHistorian"),
        config_file=sqlite_config,
        start=True,
        vip_identity='test_historian')
    assert volttron_instance.is_agent_running(auuid)

    newuuid = volttron_instance.install_agent(
        agent_dir=get_services_core("SQLHistorian"),
        config_file=sqlite_config,
        start=True,
        force=True,
        vip_identity='test_historian')

    assert volttron_instance.is_agent_running(newuuid)
    assert auuid != newuuid and auuid is not None
    volttron_instance.remove_agent(newuuid)


@pytest.mark.wrapper
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
def test_get_peerlist(volttron_instance):
    vi = volttron_instance
    agent = vi.build_agent()
    assert agent.core.identity
    resp = agent.vip.peerlist().get(timeout=5)
    assert isinstance(resp, list)
    assert len(resp) > 1


@pytest.mark.wrapper
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
    return any([x.startswith(prefix) for x in list(messages.keys())])


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


@pytest.mark.wrapper
def test_can_install_multiple_listeners(volttron_instance):
    assert volttron_instance.is_running()
    uuids = []
    agent_list = volttron_instance.dynamic_agent.vip.rpc('control', 'list_agents').get(timeout=5)
    num_agents_before = len(agent_list)
    num_listeners = 3

    try:
        for x in range(num_listeners):
            identity = "listener_" + str(x)
            auuid = volttron_instance.install_agent(
                agent_dir=get_examples("ListenerAgent"), config_file={
                    "agentid": identity,
                    "message": "So Happpy"})
            assert auuid
            uuids.append(auuid)
            gevent.sleep(4)

        for u in uuids:
            assert volttron_instance.is_agent_running(u)

        agent_list = volttron_instance.dynamic_agent.vip.rpc('control', 'list_agents').get(timeout=5)
        print('Agent List: {}'.format(agent_list))
        assert len(agent_list) - num_agents_before == num_listeners
    finally:
        for x in uuids:
            try:
                volttron_instance.remove_agent(x)
            except:
                print('COULDN"T REMOVE AGENT')


def test_will_update_throws_typeerror():
    # Note dictionary for os.environ must be string=string for key=value

    to_update = dict(bogus=35)
    with pytest.raises(TypeError):
        with with_os_environ(to_update):
            print("Should not reach here")

    to_update = dict(shanty=dict(holy="cow"))
    with pytest.raises(TypeError):
        with with_os_environ(to_update):
            print("Should not reach here")


def test_will_update_environ():
    to_update = dict(farthing="50")
    with with_os_environ(to_update):
        assert os.environ.get("farthing") == "50"

    assert "farthing" not in os.environ

