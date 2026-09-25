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
import logging
import shutil
import tempfile
import time
import os

import grequests
import gevent
import gevent.subprocess as subprocess
import pytest
from mock import MagicMock, patch
from volttrontesting.skip_if_handlers import rmq_skipif


def _assert_platform_home_under_tempdir(volttron_home):
    """PlatformWrapper builds volttron_home as <mkdtemp result>/volttron_home,
    and mkdtemp() honors TMPDIR. Check against tempfile.gettempdir() and
    tempfile.gettempprefix() directly, so the assertion moves with TMPDIR
    instead of requiring it to be unset.

    Pins the mkdtemp-under-tempdir shape and that the home itself exists.
    Does not pin freshness: a memoized or fixed-name home also satisfies
    every clause here.
    """
    mkdtemp_dir = os.path.dirname(volttron_home)
    assert os.path.dirname(mkdtemp_dir) == tempfile.gettempdir()
    assert os.path.basename(mkdtemp_dir).startswith(tempfile.gettempprefix())
    assert os.path.isdir(volttron_home)


@pytest.fixture
def _fake_tempdir(tmp_path, monkeypatch):
    """Force tempfile.gettempdir() to tmp_path without touching TMPDIR or
    the real system temp directory. This is also how the TMPDIR-unset
    fallback path is exercised below: tempfile.tempdir is forced in
    process instead of clearing the environment variable, so the test
    runs without writing to /tmp.
    """
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    return tmp_path


def _make_home(mkdtemp_parent, prefix=None):
    """Build a directory tree matching create_volttron_home()'s shape:
    a mkdtemp-created directory holding a volttron_home leaf, both
    present on disk.
    """
    mkdtemp_dir = tempfile.mkdtemp(dir=str(mkdtemp_parent), prefix=prefix)
    home = os.path.join(mkdtemp_dir, "volttron_home")
    os.makedirs(home)
    return home


def test_assert_platform_home_under_tempdir_passes_for_a_real_home(_fake_tempdir):
    _assert_platform_home_under_tempdir(_make_home(_fake_tempdir))


def test_assert_platform_home_under_tempdir_rejects_home_outside_tempdir(
        _fake_tempdir, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside")
    with pytest.raises(AssertionError):
        _assert_platform_home_under_tempdir(_make_home(outside))


def test_assert_platform_home_under_tempdir_rejects_non_mkdtemp_prefix(_fake_tempdir):
    mkdtemp_dir = os.path.join(str(_fake_tempdir), "not_a_tmp_prefix")
    home = os.path.join(mkdtemp_dir, "volttron_home")
    os.makedirs(home)
    with pytest.raises(AssertionError):
        _assert_platform_home_under_tempdir(home)


def test_assert_platform_home_under_tempdir_rejects_missing_leaf(_fake_tempdir):
    mkdtemp_dir = tempfile.mkdtemp(dir=str(_fake_tempdir))
    home = os.path.join(mkdtemp_dir, "volttron_home")
    with pytest.raises(AssertionError):
        _assert_platform_home_under_tempdir(home)


@pytest.mark.parametrize("messagebus, ssl_auth", [
    pytest.param('zmq', False),
    pytest.param('rmq', True, marks=rmq_skipif),
    pytest.param('zmq', True)
])
def test_can_create(messagebus, ssl_auth):
    p = PlatformWrapper(messagebus=messagebus, ssl_auth=ssl_auth)
    try:
        assert not p.is_running()
        _assert_platform_home_under_tempdir(p.volttron_home)

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
                                                       START_STOP_AGENTS, STOP_PLATFORM, TAG_AGENTS,
                                                       CONTROL)
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
        _assert_platform_home_under_tempdir(p.volttron_home)
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
def test_startup_skips_dynamic_agent_capability_update_when_auth_disabled():
    """Security constraint: the grant runs only when the instance has
    authentication enabled. On an auth-disabled instance, startup_platform
    must not create an auth.json or a dynamic_agent keystore: both
    KeyStore(path) and AuthFile(path) create the file at that path when
    missing, so calling the update at all is enough to fail this."""
    p = PlatformWrapper(messagebus='zmq', auth_enabled=False)
    try:
        p.startup_platform(vip_address=get_rand_tcp_address())

        auth_path = os.path.join(p.volttron_home, "auth.json")
        keystore_dir = os.path.join(p.volttron_home, "keystores", "dynamic_agent")
        assert not os.path.exists(auth_path), \
            "auth.json was created on an auth-disabled instance"
        assert not os.path.exists(keystore_dir), \
            "a dynamic_agent keystore was created on an auth-disabled instance"
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
        # volttron_home is <mkdtemp>/volttron_home; remove the mkdtemp
        # parent too, or an empty directory leaks per run.
        shutil.rmtree(os.path.dirname(p.volttron_home), ignore_errors=True)


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
        shutil.rmtree(os.path.dirname(p.volttron_home), ignore_errors=True)


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


@pytest.mark.wrapper
def test_update_dynamic_agent_capabilities_matches_by_index_not_first_user_id():
    """Security constraint: the write must land on the entry that matched
    by user_id AND key, not on whatever entry AuthFile.add would find
    first by user_id alone. AuthFile.add() itself refuses to add a second
    entry sharing a user_id, so this seeds both entries directly: the
    shape a hand-written or externally modified auth.json can produce."""
    p = PlatformWrapper(messagebus='zmq', auth_enabled=True)
    try:
        with with_os_environ(p.env):
            ks = KeyStore(KeyStore.get_agent_keystore_path("dynamic_agent"))
            impostor_ks = KeyStore(KeyStore.get_agent_keystore_path("impostor"))
            foreign_capabilities = dict(edit_config_store=dict(identity="/.*/"))
            authfile = AuthFile()
            authfile._write(
                [AuthEntry(user_id="dynamic_agent", identity="dynamic_agent",
                          credentials=impostor_ks.public,
                          capabilities=dict(foreign_capabilities),
                          comments="foreign entry, seeded first"),
                 AuthEntry(user_id="dynamic_agent", identity="dynamic_agent",
                          credentials=ks.public,
                          capabilities=dict(edit_config_store=dict(identity="/.*/"),
                                            allow_auth_modifications=None),
                          comments="harness entry, seeded second")],
                [], {}, {})

            p._update_dynamic_agent_capabilities()

            entries = [e for e in AuthFile().read_allow_entries() if e.user_id == "dynamic_agent"]
        assert len(entries) == 2
        foreign = [e for e in entries if e.credentials == impostor_ks.public]
        assert len(foreign) == 1
        assert foreign[0].capabilities == foreign_capabilities
        harness = [e for e in entries if e.credentials == ks.public]
        assert len(harness) == 1
        assert harness[0].capabilities == _expected_dynamic_agent_capabilities()
    finally:
        p.skip_cleanup = True
        shutil.rmtree(os.path.dirname(p.volttron_home), ignore_errors=True)


@pytest.mark.wrapper
def test_update_dynamic_agent_capabilities_only_touches_instance_home():
    """Security constraint: the update acts on self.volttron_home, never
    on whatever VOLTTRON_HOME happens to be set in the process
    environment. Calling it with a different VOLTTRON_HOME active must
    not create or change any auth file or keystore under that other
    home, and must still correctly update the instance's own home."""
    p = PlatformWrapper(messagebus='zmq', auth_enabled=True)
    other_home = tempfile.mkdtemp(prefix="other_home_", dir=os.environ.get("TMPDIR"))
    home_was_set = "VOLTTRON_HOME" in os.environ
    home_prior_value = os.environ.get("VOLTTRON_HOME")
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

        with with_os_environ({"VOLTTRON_HOME": other_home}):
            p._update_dynamic_agent_capabilities()

            assert not os.path.exists(os.path.join(other_home, "auth.json")), \
                "auth.json was created outside the instance home"
            assert not os.path.exists(os.path.join(other_home, "keystores")), \
                "a keystore was created outside the instance home"

        # Guard the restore itself: a caller in the same process outside
        # any with_os_environ block must see VOLTTRON_HOME exactly as it
        # was before this test, set or unset.
        if home_was_set:
            assert os.environ.get("VOLTTRON_HOME") == home_prior_value, \
                "VOLTTRON_HOME was not restored to its prior value"
        else:
            assert "VOLTTRON_HOME" not in os.environ, \
                "VOLTTRON_HOME was left set after the test"

        with with_os_environ(p.env):
            entries = [e for e in AuthFile().read_allow_entries() if e.user_id == "dynamic_agent"]
        assert len(entries) == 1
        assert entries[0].capabilities == _expected_dynamic_agent_capabilities()
    finally:
        p.skip_cleanup = True
        shutil.rmtree(os.path.dirname(p.volttron_home), ignore_errors=True)
        shutil.rmtree(other_home, ignore_errors=True)


@pytest.mark.wrapper
def test_update_dynamic_agent_capabilities_drops_stale_driver_capability():
    """Criterion 5 and security constraint 3: no harness identity may
    hold driver_write. A stale entry that already carries it must end up
    holding exactly the expected set, not the expected set plus
    driver_write."""
    p = PlatformWrapper(messagebus='zmq', auth_enabled=True)
    try:
        with with_os_environ(p.env):
            ks = KeyStore(KeyStore.get_agent_keystore_path("dynamic_agent"))
            stale = dict(edit_config_store=dict(identity="/.*/"),
                        allow_auth_modifications=None,
                        driver_write=None)
            AuthFile().add(AuthEntry(
                user_id="dynamic_agent",
                identity="dynamic_agent",
                credentials=ks.public,
                capabilities=dict(stale),
                comments="stale entry holding driver_write"))

            p._update_dynamic_agent_capabilities()

            entries = [e for e in AuthFile().read_allow_entries() if e.user_id == "dynamic_agent"]
        assert len(entries) == 1
        assert entries[0].capabilities == _expected_dynamic_agent_capabilities()
        assert "driver_write" not in entries[0].capabilities
    finally:
        p.skip_cleanup = True
        shutil.rmtree(os.path.dirname(p.volttron_home), ignore_errors=True)


@pytest.mark.wrapper
def test_update_dynamic_agent_capabilities_widens_scoped_edit_config_store():
    """Criterion 1: edit_config_store must end up scoped to '/.*/'. A
    stale entry whose edit_config_store is scoped to its own identity
    (narrower than expected) must be widened to the exact expected
    value. This does not pin assign over merge: a merge that overrides
    with the expected value for keys the expected set already names
    widens edit_config_store the same way, so it also passes here.
    test_update_dynamic_agent_capabilities_drops_stale_driver_capability
    is what pins assign, through driver_write, a key expected does not
    name."""
    p = PlatformWrapper(messagebus='zmq', auth_enabled=True)
    try:
        with with_os_environ(p.env):
            ks = KeyStore(KeyStore.get_agent_keystore_path("dynamic_agent"))
            stale = dict(edit_config_store=dict(identity="dynamic_agent"),
                        allow_auth_modifications=None)
            AuthFile().add(AuthEntry(
                user_id="dynamic_agent",
                identity="dynamic_agent",
                credentials=ks.public,
                capabilities=dict(stale),
                comments="stale entry, edit_config_store scoped to its own identity"))

            p._update_dynamic_agent_capabilities()

            entries = [e for e in AuthFile().read_allow_entries() if e.user_id == "dynamic_agent"]
        assert len(entries) == 1
        assert entries[0].capabilities == _expected_dynamic_agent_capabilities()
    finally:
        p.skip_cleanup = True
        shutil.rmtree(os.path.dirname(p.volttron_home), ignore_errors=True)


@pytest.mark.wrapper
def test_update_dynamic_agent_capabilities_logs_when_no_entry_matches(caplog):
    """When no dynamic_agent entry matches this instance's own keystore
    key (a fresh VOLTTRON_HOME with no pre-seed run, or a regenerated
    keystore), the harness silently ran with too few privileges before
    this warning. The message names the identity and the home so the
    cause is visible instead of surfacing later as unrelated refusals.
    Searches every captured WARNING record rather than the first: an
    unrelated warning logged earlier in the block must not hide this
    one, so one is logged here on purpose."""
    p = PlatformWrapper(messagebus='zmq', auth_enabled=True)
    try:
        with with_os_environ(p.env), caplog.at_level(logging.WARNING):
            logging.getLogger(__name__).warning("unrelated warning logged first")
            p._update_dynamic_agent_capabilities()

        warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert any("dynamic_agent" in m for m in warnings), \
            "no warning naming dynamic_agent logged when no entry matched"
        assert any(p.volttron_home in m for m in warnings), \
            "no warning naming the instance home logged when no entry matched"
    finally:
        p.skip_cleanup = True
        shutil.rmtree(os.path.dirname(p.volttron_home), ignore_errors=True)


@pytest.mark.wrapper
def test_update_dynamic_agent_capabilities_warning_is_accurate_before_preseed_grant(caplog):
    """The pre-existing-auth.json startup path skips the pre-seed and
    calls this method before build_agent grants the dynamic_agent entry:
    at that point no entry has matched yet, but the grant has not
    failed, it has not happened yet. The warning text must not claim
    the grant failed on this legitimate path."""
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

            with caplog.at_level(logging.WARNING):
                p._update_dynamic_agent_capabilities()

        warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert warnings, "expected a warning when no dynamic_agent entry matches yet"
        assert not any("were not granted" in m for m in warnings), \
            "warning claimed the grant failed, though build_agent grants it later on this path"
    finally:
        p.skip_cleanup = True
        shutil.rmtree(os.path.dirname(p.volttron_home), ignore_errors=True)


@pytest.mark.wrapper
def test_update_dynamic_agent_capabilities_skips_write_when_already_exact():
    """Once the entry already holds exactly the expected capabilities
    (the fresh pre-seed path always leaves it that way), calling the
    update again must not rewrite auth.json: previously it was an
    unconditional rewrite plus a fixed sleep, on every auth-enabled
    startup, for a merge guaranteed to change nothing. Asserted through
    a patched AuthFile._write, which cannot be defeated by filesystem
    timestamp granularity the way an mtime-only check can; the mtime
    and content checks are kept alongside it."""
    p = PlatformWrapper(messagebus='zmq', auth_enabled=True)
    try:
        with with_os_environ(p.env):
            ks = KeyStore(KeyStore.get_agent_keystore_path("dynamic_agent"))
            AuthFile().add(AuthEntry(
                user_id="dynamic_agent",
                identity="dynamic_agent",
                credentials=ks.public,
                capabilities=_expected_dynamic_agent_capabilities(),
                comments="already exact"))

            auth_path = os.path.join(p.volttron_home, "auth.json")
            before = os.stat(auth_path).st_mtime_ns
            with open(auth_path, "rb") as f:
                before_content = f.read()

            with patch.object(AuthFile, "_write") as write_mock:
                p._update_dynamic_agent_capabilities()
            write_mock.assert_not_called()

        with open(auth_path, "rb") as f:
            after_content = f.read()
        assert after_content == before_content, "auth.json content changed for a no-op merge"
        assert os.stat(auth_path).st_mtime_ns == before, "auth.json was rewritten for a no-op merge"
    finally:
        p.skip_cleanup = True
        shutil.rmtree(os.path.dirname(p.volttron_home), ignore_errors=True)


@pytest.mark.wrapper
def test_dynamic_agent_start_stop_agents_capability_exercised():
    """CLEAR_AGENT_STATUS, START_STOP_AGENTS, STOP_PLATFORM and TAG_AGENTS
    are otherwise pinned only by equality against a hand-written copy of
    the expected set; only INSTALL_REMOVE_AGENTS is exercised through the
    platform. This calls a start_stop_agents-gated control method
    directly through dynamic_agent's own RPC connection, the same route
    shutdown_platform and prioritize_agent use, and asserts the call is
    not refused and the agent's running state changed."""
    p = PlatformWrapper(messagebus='zmq', auth_enabled=True)
    try:
        p.startup_platform(vip_address=get_rand_tcp_address())
        auuid = p.install_agent(agent_dir=get_examples("ListenerAgent"), start=False)
        assert not p.is_agent_running(auuid)

        p.dynamic_agent.vip.rpc(CONTROL, 'start_agent', auuid).get(timeout=10)
        gevent.sleep(3)

        assert p.is_agent_running(auuid)
    finally:
        p.shutdown_platform()


# Issue #3283: build_agent's readiness loop retried agent.vip.peerlist()
# .get(timeout=.2), but peerlist() sends before it returns the AsyncResult
# that .get() waits on, so a send that blocks (the VIP send lock, #3280)
# defeated the retry count and the .get(timeout) entirely and ran until the
# suite's 300s pytest timeout.

class _BlockingSendAgent:
    """Stand-in for agent_class in build_agent(): its vip.peerlist() blocks
    the way a real client-side stall on the VIP send lock would, inside the
    call that produces the AsyncResult rather than inside .get(). core.run
    sets the ready event immediately so build_agent's own spawn/wait step
    is not what is under test here."""

    def __init__(self, *args, **kwargs):
        self.core = MagicMock()
        self.core.run = lambda event: event.set()
        self.vip = MagicMock()
        self.vip.peerlist.side_effect = lambda: gevent.sleep(3600)


class _ReadinessWatchdogTimeout(Exception):
    """Raised only by this test's own outer watchdog, never by
    build_agent. Kept distinct from the Exception build_agent raises on a
    real deadline so the two are told apart after pytest.raises catches
    either of them."""
    pass


@pytest.mark.wrapper
def test_build_agent_readiness_loop_bounded_by_wall_clock_deadline():
    """Issue #3283, criteria 1-3: build_agent's readiness loop must be
    bounded end to end, including the peerlist send, by a wall clock
    deadline, and raise naming identity/address/elapsed time rather than
    keep retrying. A 15s watchdog turns an unbounded wait into a fast,
    unambiguous failure instead of the 300s pytest timeout: before the
    fix, the watchdog's own _ReadinessWatchdogTimeout is what pytest.raises
    catches, which the assertion below tells apart from a real deadline
    exception."""
    p = PlatformWrapper(messagebus='zmq', auth_enabled=False)
    try:
        start = time.time()
        with pytest.raises(Exception) as excinfo:
            with gevent.Timeout(15, _ReadinessWatchdogTimeout(
                    "build_agent's readiness loop was not bounded by a "
                    "wall clock deadline within 15s")):
                p.build_agent(agent_class=_BlockingSendAgent,
                              address=p.vip_address, should_spawn=True)
        elapsed = time.time() - start

        assert not isinstance(excinfo.value, _ReadinessWatchdogTimeout), (
            f"watchdog fired after {elapsed:.1f}s: {excinfo.value}")
        assert elapsed < 15, f"took {elapsed:.1f}s, expected well under the 15s watchdog"
        message = str(excinfo.value)
        assert "identity=" in message and "elapsed=" in message, (
            f"exception did not name identity and elapsed time: {message}")
    finally:
        p.skip_cleanup = True
        shutil.rmtree(os.path.dirname(p.volttron_home), ignore_errors=True)


@pytest.mark.wrapper
def test_build_agent_returns_connected_agent_within_deadline():
    """Issue #3283, criterion 4: the new wall clock deadline must not
    change the successful path. A normal build_agent against a real,
    already-running platform still returns a connected agent."""
    p = PlatformWrapper(messagebus='zmq', auth_enabled=True)
    try:
        p.startup_platform(vip_address=get_rand_tcp_address())
        agent = p.build_agent()
        assert CONTROL in agent.vip.peerlist().get(timeout=5)
    finally:
        p.shutdown_platform()


# Issue #3282: shutdown_platform wrapped the whole dynamic-agent teardown
# in a bare except that only logged str(e), so an exception raised by
# list_agents(), remove_all_agents() or the control-shutdown RPC skipped
# both dynamic_agent.core.stop() and dynamic_agent = None, since they were
# the last two statements inside the same try.

@pytest.mark.wrapper
def test_shutdown_platform_clears_dynamic_agent_when_teardown_raises(caplog):
    """Issue #3282, criteria 1-3: an exception during dynamic_agent
    teardown (here, the control-shutdown RPC) must not prevent
    dynamic_agent.core.stop() from running or dynamic_agent from being
    cleared, and must be logged with its traceback and type rather than
    only str(e)."""
    p = PlatformWrapper(messagebus='zmq', auth_enabled=True)
    p._instance_shutdown = False
    p.skip_cleanup = True
    p.p_process = None

    fake_agent = MagicMock()
    fake_agent.vip.rpc.return_value.get.side_effect = RuntimeError("control shutdown boom")
    p.dynamic_agent = fake_agent

    try:
        with patch.object(PlatformWrapper, 'is_running', return_value=True), \
             patch.object(PlatformWrapper, 'list_agents', return_value=[]), \
             caplog.at_level(logging.ERROR):
            p.shutdown_platform()

        fake_agent.core.stop.assert_called_once()
        assert p.dynamic_agent is None, "dynamic_agent survived a raising teardown"

        error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert error_records, "no error-level record logged for the teardown exception"
        assert any(r.exc_info and r.exc_info[0] is RuntimeError for r in error_records), \
            "logged record did not carry the exception's traceback and type"
    finally:
        shutil.rmtree(os.path.dirname(p.volttron_home), ignore_errors=True)


@pytest.mark.wrapper
def test_shutdown_platform_kills_a_process_that_outlives_terminate(caplog):
    """Issue #3282, criterion 4: the terminate path must wait for the
    platform process to exit with a bound, and kill and report a process
    that is still alive after that bound, rather than only sending
    SIGTERM and moving on after a fixed sleep."""
    p = PlatformWrapper(messagebus='zmq', auth_enabled=True)
    p._instance_shutdown = False
    p.skip_cleanup = True
    p.dynamic_agent = None

    fake_process = MagicMock()
    fake_process.pid = 999999
    fake_process.wait.side_effect = [subprocess.TimeoutExpired(cmd="volttron", timeout=10), None]
    p.p_process = fake_process

    try:
        with patch.object(PlatformWrapper, 'is_running', return_value=True), \
             caplog.at_level(logging.ERROR):
            p.shutdown_platform()

        fake_process.terminate.assert_called_once()
        fake_process.kill.assert_called_once()
        assert fake_process.wait.call_count == 2
        assert any("did not exit" in r.getMessage() for r in caplog.records), \
            "no record reported the surviving process"
    finally:
        shutil.rmtree(os.path.dirname(p.volttron_home), ignore_errors=True)


@pytest.mark.wrapper
def test_dynamic_agent_core_greenlet_does_not_survive_a_raising_teardown():
    """Issue #3282, criterion 5: the dynamic_agent's core greenlet, spawned
    against this platform's own ZMQ context, must be stopped even when the
    control-shutdown RPC raises, so it cannot survive into a second
    PlatformWrapper started afterward in the same process. Before the fix,
    core_greenlet.ready() stays False here because the bare except skips
    core.stop() whenever the RPC raises."""
    p = PlatformWrapper(messagebus='zmq', auth_enabled=True)
    core_greenlet = None
    try:
        p.startup_platform(vip_address=get_rand_tcp_address())
        core_greenlet = p.dynamic_agent.core.greenlet
        assert core_greenlet is not None and not core_greenlet.ready()

        original_rpc = p.dynamic_agent.vip.rpc

        def _raise_on_shutdown(peer, method, *args, **kwargs):
            if method == 'shutdown':
                raise RuntimeError("simulated control-shutdown failure")
            return original_rpc(peer, method, *args, **kwargs)

        p.dynamic_agent.vip.rpc = _raise_on_shutdown
    finally:
        p.skip_cleanup = True
        p.shutdown_platform()

    assert p.dynamic_agent is None
    assert core_greenlet.ready(), "dynamic_agent's core greenlet survived a raising teardown"

    second = PlatformWrapper(messagebus='zmq', auth_enabled=True)
    try:
        second.startup_platform(vip_address=get_rand_tcp_address())
        assert second.is_running(), \
            "a second platform could not start after the first's raising teardown"
    finally:
        second.shutdown_platform()
