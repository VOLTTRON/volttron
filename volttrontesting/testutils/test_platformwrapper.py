# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
# }}}
from configparser import ConfigParser
import shutil
import time
import os

import grequests
import gevent
import pytest
from mock import MagicMock
from volttrontesting.skip_if_handlers import rmq_skipif

@pytest.mark.parametrize("messagebus, ssl_auth", [
    pytest.param('zmq', False),
    pytest.param('rmq', True, marks=rmq_skipif),
    pytest.param('zmq', True)
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
from volttron.platform import get_services_core, get_examples, jsonapi
from volttrontesting.utils.platformwrapper import PlatformWrapper, with_os_environ
from volttron.platform.agent.known_identities import (CLEAR_AGENT_STATUS, INSTALL_REMOVE_AGENTS,
                                                       START_STOP_AGENTS, STOP_PLATFORM, TAG_AGENTS)
from volttron.platform.auth import AuthEntry, AuthFile
from volttron.platform.keystore import KeyStore


from volttrontesting.utils.utils import get_rand_tcp_address, get_rand_http_address


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
        result = grequests.get(http_address, verify=False).send()
        assert result
        response = result.response
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
def test_can_install_listener(volttron_instance: PlatformWrapper):
    vi = volttron_instance
    assert vi is not None
    assert vi.is_running()

    # agent identity should be
    auuid = vi.install_agent(agent_dir=get_examples("ListenerAgent"),
                             start=False)
    assert auuid is not None
    time.sleep(1)
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
def test_web_wrapper(volttron_instance_web):
    vi = volttron_instance_web
    agent = vi.build_agent()
    assert agent.core.identity
    resp = agent.vip.peerlist().get(timeout=5)
    assert isinstance(resp, list)
    assert len(resp) > 1


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
    volttron_instance.remove_all_agents()
    uuids = []
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
            time.sleep(4)

        for u in uuids:
            assert volttron_instance.is_agent_running(u)

        agent_list = volttron_instance.dynamic_agent.vip.rpc('control', 'list_agents').get(timeout=5)
        print('Agent List: {}'.format(agent_list))
        assert len(agent_list) == num_listeners
    finally:
        for x in uuids:
            try:
                volttron_instance.remove_agent(x)
            except:
                print('COULDN"T REMOVE AGENT')


def test_will_update_throws_typeerror():
    # Note dictionary for os.environ must be string=string for key=value

    to_update = dict(shanty=dict(holy="cow"))
    #with pytest.raises(TypeError):
    with with_os_environ(to_update):
        print("Should not reach here")

    to_update = dict(bogus=35)
#    with pytest.raises(TypeError):
    with with_os_environ(to_update):
        print("Should not reach here")


def test_will_update_environ():
    to_update = dict(farthing="50")
    with with_os_environ(to_update):
        assert os.environ.get("farthing") == "50"

    assert "farthing" not in os.environ


# Issue 3238: the harness identity dynamic_agent drives the platform
# lifecycle (remove_all_agents, stop_platform, shutdown_platform, and
# prioritize_agent in tests) but was only granted edit_config_store and
# allow_auth_modifications, so those calls were refused once ControlService
# started requiring capabilities.

def _expected_dynamic_agent_capabilities():
    return {
        'edit_config_store': {'identity': '/.*/'},
        'allow_auth_modifications': None,
        CLEAR_AGENT_STATUS: None,
        INSTALL_REMOVE_AGENTS: None,
        START_STOP_AGENTS: None,
        STOP_PLATFORM: None,
        TAG_AGENTS: None,
    }


def _dynamic_agent_entry(platform_wrapper):
    with with_os_environ(platform_wrapper.env):
        entries = [e for e in AuthFile().read_allow_entries() if e.user_id == "dynamic_agent"]
    assert len(entries) == 1
    return entries[0]


@pytest.mark.wrapper
def test_dynamic_agent_entry_has_control_capabilities():
    """On a fresh auth-enabled instance (the pre-seed grant path), the
    dynamic_agent entry holds exactly the capabilities the harness needs to
    drive the platform lifecycle, named through known_identities."""
    p = PlatformWrapper(messagebus='zmq', auth_enabled=True)
    try:
        p.startup_platform(vip_address=get_rand_tcp_address())
        entry = _dynamic_agent_entry(p)
        assert entry.capabilities == _expected_dynamic_agent_capabilities()
    finally:
        p.shutdown_platform()


@pytest.mark.wrapper
def test_dynamic_agent_entry_created_when_auth_file_preexists():
    """The pre-seed grant only runs on a brand new auth.json. When the file
    already has an allow entry for another identity, startup_platform still
    ends with a correctly capable dynamic_agent entry, through the
    build_agent(identity="dynamic_agent") grant path."""
    p = PlatformWrapper(messagebus='zmq', auth_enabled=True)
    try:
        with with_os_environ(p.env):
            other_ks = KeyStore(KeyStore.get_agent_keystore_path("other_identity"))
            AuthFile().add(AuthEntry(
                user_id="other_identity",
                identity="other_identity",
                credentials=other_ks.public,
                capabilities=dict(edit_config_store=dict(identity="other_identity")),
                comments="seeded so the auth file is not brand new"))

        p.startup_platform(vip_address=get_rand_tcp_address())
        entry = _dynamic_agent_entry(p)
        assert entry.capabilities == _expected_dynamic_agent_capabilities()
    finally:
        p.shutdown_platform()


@pytest.mark.wrapper
def test_update_dynamic_agent_capabilities_merges_stale_entry():
    """A dynamic_agent entry already on disk under this harness's own
    keystore key, but missing the control capabilities, is merged up to
    the full set. This exercises _update_dynamic_agent_capabilities
    directly; no platform process needs to be running for it."""
    p = PlatformWrapper(messagebus='zmq', auth_enabled=True)
    try:
        with with_os_environ(p.env):
            ks = KeyStore(KeyStore.get_agent_keystore_path("dynamic_agent"))
            AuthFile().add(AuthEntry(
                user_id="dynamic_agent",
                identity="dynamic_agent",
                credentials=ks.public,
                capabilities=dict(edit_config_store=dict(identity="/.*/"),
                                  allow_auth_modifications=None),
                comments="stale entry seeded for test"))

            p._update_dynamic_agent_capabilities()

            entries = [e for e in AuthFile().read_allow_entries() if e.user_id == "dynamic_agent"]
        assert len(entries) == 1
        assert entries[0].capabilities == _expected_dynamic_agent_capabilities()
    finally:
        p.skip_cleanup = True
        shutil.rmtree(p.volttron_home, ignore_errors=True)


@pytest.mark.wrapper
def test_update_dynamic_agent_capabilities_leaves_different_key_entry_untouched():
    """Security constraint: the stale-entry update matches by user_id AND
    by this harness's own dynamic_agent keystore key. An entry with the
    same user_id but a different key (not this harness's own agent) is
    left unchanged."""
    p = PlatformWrapper(messagebus='zmq', auth_enabled=True)
    try:
        with with_os_environ(p.env):
            impostor_ks = KeyStore(KeyStore.get_agent_keystore_path("impostor"))
            stale_capabilities = dict(edit_config_store=dict(identity="/.*/"),
                                      allow_auth_modifications=None)
            AuthFile().add(AuthEntry(
                user_id="dynamic_agent",
                identity="dynamic_agent",
                credentials=impostor_ks.public,
                capabilities=dict(stale_capabilities),
                comments="different key, must not be updated"))

            p._update_dynamic_agent_capabilities()

            entries = [e for e in AuthFile().read_allow_entries() if e.user_id == "dynamic_agent"]
        assert len(entries) == 1
        assert entries[0].capabilities == stale_capabilities
        assert entries[0].credentials == impostor_ks.public
    finally:
        p.skip_cleanup = True
        shutil.rmtree(p.volttron_home, ignore_errors=True)


@pytest.mark.wrapper
def test_build_agent_default_capabilities_unchanged():
    """build_agent() without an explicit capabilities argument still grants
    only edit_config_store scoped to the agent's own identity: the
    dynamic_agent grant paths must not widen the default for other
    identities."""
    p = PlatformWrapper(messagebus='zmq', auth_enabled=True)
    try:
        p.startup_platform(vip_address=get_rand_tcp_address())
        agent = p.build_agent()
        identity = agent.core.identity
        with with_os_environ(p.env):
            entries = [e for e in AuthFile().read_allow_entries() if e.user_id == identity]
        assert len(entries) == 1
        assert entries[0].capabilities == {'edit_config_store': {'identity': identity}}
    finally:
        p.shutdown_platform()


@pytest.mark.wrapper
def test_remove_all_agents_removes_installed_agent():
    """remove_all_agents (used for cleanup between tests) calls
    control.remove_agent through dynamic_agent. Fails at d68dff037 with
    "requires capabilities {'install_remove_agents'}"."""
    p = PlatformWrapper(messagebus='zmq', auth_enabled=True)
    try:
        p.startup_platform(vip_address=get_rand_tcp_address())
        auuid = p.install_agent(agent_dir=get_examples("ListenerAgent"), start=False)
        assert auuid is not None

        p.remove_all_agents()

        assert p.list_agents() == []
    finally:
        p.shutdown_platform()
