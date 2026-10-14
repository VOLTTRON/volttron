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
"""The auth service maps each user that connects with a platform's listed key
to that platform's name, and sends the map to the router with every
capabilities update: at start, first in every refresh, and on the hub."""

import json
import logging
import threading
from types import SimpleNamespace

import gevent
import pytest
from mock import MagicMock

from volttron.platform import jsonapi
from volttron.platform.agent.known_identities import AUTH
from volttron.platform.auth import AuthEntry, AuthService
from volttron.platform.auth import auth as auth_module
from volttron.platform.auth.auth_protocols import auth_zmq
from volttron.platform.keystore import KeyStore

AUTH_LOGGER = auth_module.__name__
DISCOVERY = "external_platform_discovery.json"
KEY_B = "B" * 43
KEY_C = "C" * 43
KEY_D = "D" * 43


@pytest.fixture
def service(tmp_path, monkeypatch):
    """A real AuthService after its onsetup signal, with the pieces that need
    a running platform stubbed and the router socket recorded."""
    monkeypatch.setenv("VOLTTRON_HOME", str(tmp_path))
    (tmp_path / "config").write_text("[volttron]\ninstance-name = inst-a\n")
    monkeypatch.setattr(auth_module, "watch_file", lambda *a, **k: None)
    monkeypatch.setattr(auth_zmq.ZMQServerAuthentication,
                        "setup_authentication", lambda self: None)
    built = AuthService(str(tmp_path / "auth.json"),
                        str(tmp_path / "protected_topics.json"), False,
                        None, address="inproc://unused", identity=AUTH,
                        enable_store=False, message_bus="zmq",
                        enable_auth=True)
    built.core.socket = MagicMock()
    built.core.spawn = lambda *args, **kwargs: None
    pubsub = built.vip.pubsub
    try:
        built.core.onsetup.send(built.core)
        yield built
    finally:
        processor = getattr(pubsub, "_processgreenlet", None)
        if processor is not None:
            processor.kill()


def entry(user, key, identity=None):
    return AuthEntry(user_id=user, credentials=key, mechanism="CURVE",
                     identity=identity)


def write_discovery(tmp_path, platforms):
    """platforms: file key -> (instance name, serverkey)."""
    body = {file_key: {"instance-name": name, "serverkey": key,
                       "vip-address": "tcp://127.0.0.1:22916"}
            for file_key, (name, key) in platforms.items()}
    (tmp_path / DISCOVERY).write_text(json.dumps(body))


def sent_updates(service):
    """The auth_update messages sent to the router, parsed."""
    updates = []
    for call in service.core.socket.send_vip.call_args_list:
        frames = call[0][2]
        if frames[0].bytes == b"auth_update":
            updates.append(jsonapi.loads(frames[1].bytes))
    return updates


def platform_map(service, entries):
    service.auth_entries = entries
    service.core.socket.send_vip.reset_mock()
    service.authorization_server.update_user_capabilites(
        service.get_user_to_capabilities())
    (update,) = sent_updates(service)
    return update["platforms"]


def discovery_warnings(caplog):
    return [r.getMessage() for r in caplog.records
            if r.name == AUTH_LOGGER and r.levelno == logging.WARNING
            and DISCOVERY in r.getMessage()]


@pytest.fixture
def listed(service, tmp_path):
    write_discovery(tmp_path, {"inst-b": ("inst-b", KEY_B),
                               "inst-c": ("inst-c", KEY_C)})


def test_the_update_carries_the_capabilities_and_the_map(service, listed):
    service.auth_entries = [entry("peer.b", KEY_B)]
    service.core.socket.send_vip.reset_mock()
    service.authorization_server.update_user_capabilites({"u": ["c"]})
    (update,) = sent_updates(service)
    assert update["capabilities"] == {"u": ["c"]}
    assert update["platforms"] == {"peer.b": ["inst-b"]}


def test_an_exact_key_entry_maps_to_the_listed_instance_name(service, listed):
    assert platform_map(service, [entry("peer.b", KEY_B)]) == {
        "peer.b": ["inst-b"]}


def test_the_name_is_the_instance_name_field_not_the_file_key(
        service, tmp_path):
    write_discovery(tmp_path, {"file-key": ("inst-b", KEY_B)})
    assert platform_map(service, [entry("peer.b", KEY_B)]) == {
        "peer.b": ["inst-b"]}


def test_two_entries_that_share_a_key_under_two_users_both_map(
        service, listed):
    assert platform_map(service, [entry("peer.b", KEY_B),
                                  entry("peer.b2", KEY_B)]) == {
        "peer.b": ["inst-b"], "peer.b2": ["inst-b"]}


def test_a_regex_credential_maps_to_nothing(service, listed):
    assert platform_map(service, [entry("peer.any", "/.*/")]) == {}


def test_a_regex_credential_equal_to_a_listed_key_text_maps_to_nothing(
        service, tmp_path):
    pattern = "/" + "B" * 41 + "/"
    write_discovery(tmp_path, {"inst-b": ("inst-b", pattern)})
    assert platform_map(service, [entry("peer.b", pattern)]) == {}


def test_an_entry_with_other_credentials_maps_to_nothing(service, listed):
    assert platform_map(service, [entry("peer.x", KEY_D)]) == {}


@pytest.mark.parametrize("user", ["platform", "control.connection", AUTH, "volttron.central"])
def test_a_reserved_user_id_maps_to_nothing(service, listed, user):
    assert platform_map(service, [entry(user, KEY_B)]) == {}


def test_a_user_id_also_on_an_entry_with_other_credentials_maps_to_nothing(
        service, listed):
    assert platform_map(service, [entry("peer.b", KEY_B),
                                  entry("peer.b", KEY_D)]) == {}


def test_a_user_on_entries_for_two_platforms_maps_to_nothing(service, listed):
    assert platform_map(service, [entry("peer.b", KEY_B),
                                  entry("peer.b", KEY_C)]) == {}


def test_an_entry_with_an_identity_maps_to_nothing(service, listed):
    assert platform_map(service, [entry("agent.b", KEY_B,
                                        identity="agent.b")]) == {}


def test_an_agent_key_copied_into_the_discovery_file_does_not_make_it_a_platform(
        service, tmp_path):
    write_discovery(tmp_path, {"inst-x": ("inst-x", KEY_D)})
    entries = [entry("agent.d", KEY_D, identity="agent.d")]
    assert platform_map(service, entries) == {}


def test_the_platforms_own_instance_name_maps_to_nothing(service, tmp_path):
    write_discovery(tmp_path, {"inst-a": ("inst-a", KEY_B)})
    assert platform_map(service, [entry("peer.b", KEY_B)]) == {}


def test_the_platforms_own_key_maps_to_nothing(service, tmp_path):
    own = KeyStore().public
    write_discovery(tmp_path, {"inst-b": ("inst-b", own)})
    assert platform_map(service, [entry("peer.b", own)]) == {}


def test_a_key_listed_under_two_names_maps_to_nothing_with_one_warning(
        service, tmp_path, caplog):
    write_discovery(tmp_path, {"inst-b": ("inst-b", KEY_B),
                               "inst-b2": ("inst-b2", KEY_B),
                               "inst-c": ("inst-c", KEY_C)})
    entries = [entry("peer.b", KEY_B), entry("peer.c", KEY_C)]
    with caplog.at_level(logging.WARNING, logger=AUTH_LOGGER):
        first = platform_map(service, entries)
        second = platform_map(service, entries)
    assert first == second == {"peer.c": ["inst-c"]}
    (warning,) = discovery_warnings(caplog)
    assert "inst-b" in warning and "inst-b2" in warning


def test_a_warning_is_logged_again_after_its_cause_clears(
        service, tmp_path, caplog):
    entries = [entry("peer.b", KEY_B)]
    twice = {"inst-b": ("inst-b", KEY_B), "inst-b2": ("inst-b2", KEY_B)}
    with caplog.at_level(logging.WARNING, logger=AUTH_LOGGER):
        write_discovery(tmp_path, twice)
        platform_map(service, entries)
        write_discovery(tmp_path, {"inst-b": ("inst-b", KEY_B)})
        assert platform_map(service, entries) == {"peer.b": ["inst-b"]}
        write_discovery(tmp_path, twice)
        platform_map(service, entries)
    assert len(discovery_warnings(caplog)) == 2


def test_a_missing_discovery_file_gives_an_empty_map_and_one_warning(
        service, tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger=AUTH_LOGGER):
        assert platform_map(service, [entry("peer.b", KEY_B)]) == {}
        platform_map(service, [entry("peer.b", KEY_B)])
    assert len(discovery_warnings(caplog)) == 1


@pytest.mark.parametrize("text", ["{not json", "[]", '"x"', ""])
def test_an_unreadable_discovery_file_gives_an_empty_map_and_one_warning(
        service, tmp_path, caplog, text):
    (tmp_path / DISCOVERY).write_text(text)
    with caplog.at_level(logging.WARNING, logger=AUTH_LOGGER):
        assert platform_map(service, [entry("peer.b", KEY_B)]) == {}
    assert len(discovery_warnings(caplog)) == 1


@pytest.mark.parametrize("info", [
    {"instance-name": "inst-b"}, {"serverkey": KEY_B},
    {"instance-name": 5, "serverkey": KEY_B},
    {"instance-name": "inst-b", "serverkey": ["x"]}, "text"], ids=repr)
def test_an_entry_without_a_name_or_key_is_skipped_with_a_warning(
        service, tmp_path, caplog, info):
    body = {"bad": info,
            "inst-c": {"instance-name": "inst-c", "serverkey": KEY_C}}
    (tmp_path / DISCOVERY).write_text(json.dumps(body))
    entries = [entry("peer.b", KEY_B), entry("peer.c", KEY_C)]
    with caplog.at_level(logging.WARNING, logger=AUTH_LOGGER):
        assert platform_map(service, entries) == {"peer.c": ["inst-c"]}
    (warning,) = discovery_warnings(caplog)
    assert "'bad'" in warning


def test_setup_mode_gives_an_empty_map_whatever_the_file_holds(
        service, listed, caplog):
    service._setup_mode = True
    with caplog.at_level(logging.WARNING, logger=AUTH_LOGGER):
        assert platform_map(service, [entry("peer.b", KEY_B)]) == {}
    (warning,) = [r.getMessage() for r in caplog.records
                  if r.name == AUTH_LOGGER and r.levelno == logging.WARNING
                  and "setup mode" in r.getMessage()]
    assert "restart" in warning


def test_a_map_that_cannot_be_built_is_sent_empty_not_skipped(
        service, listed, monkeypatch):
    def broken():
        raise KeyError("no instance name")
    monkeypatch.setattr(auth_module, "get_platform_instance_name", broken)
    assert platform_map(service, [entry("peer.b", KEY_B)]) == {}


# The push: at start, first in every refresh, on the hub, and a failure is
# logged with its trigger.

class _StopLoop(Exception):
    pass


def run_start(service, events):
    def poll(timeout):
        events.append("poll")
        raise _StopLoop()
    service.authentication_server.zap_socket = SimpleNamespace(poll=poll)
    service.core.socket.send_vip.side_effect = (
        lambda peer, subsystem, frames, **kw: events.append(
            frames[0].bytes.decode()))
    with pytest.raises(_StopLoop):
        service.authentication_server.handle_authentication({})


def test_the_map_is_pushed_once_at_start_before_the_first_zap_reply(
        service, listed):
    service.auth_entries = [entry("peer.b", KEY_B)]
    events = []
    run_start(service, events)
    assert events == ["protected_update", "auth_update", "poll"]


def test_the_start_push_carries_the_map(service, listed):
    service.auth_entries = [entry("peer.b", KEY_B)]
    service.core.socket.send_vip.side_effect = None
    service.authentication_server.zap_socket = SimpleNamespace(
        poll=MagicMock(side_effect=_StopLoop()))
    with pytest.raises(_StopLoop):
        service.authentication_server.handle_authentication({})
    (update,) = sent_updates(service)
    assert update["platforms"] == {"peer.b": ["inst-b"]}


def test_a_failed_start_push_is_logged_as_an_error_naming_the_trigger(
        service, listed, caplog):
    def refuse(peer, subsystem, frames, **kw):
        if frames[0].bytes == b"auth_update":
            raise RuntimeError("router unreachable")
    service.core.socket.send_vip.side_effect = refuse
    service.authentication_server.zap_socket = SimpleNamespace(
        poll=MagicMock(side_effect=_StopLoop()))
    with caplog.at_level(logging.ERROR, logger=AUTH_LOGGER):
        with pytest.raises(_StopLoop):
            service.authentication_server.handle_authentication({})
    (error,) = [r.getMessage() for r in caplog.records
                if r.name == AUTH_LOGGER and r.levelno == logging.ERROR]
    assert "start" in error and "router" in error


def make_refresh(service, peers):
    """_send_update with a peer list; the order of the push and the peer
    calls is recorded."""
    order = []
    listing = MagicMock()
    if peers is None:
        listing.return_value.get.side_effect = Exception("no answer")
        listing.peers_list = []
    else:
        listing.return_value.get.return_value = peers
    service.vip = SimpleNamespace(
        peerlist=listing,
        rpc=SimpleNamespace(call=lambda *a, **k: order.append("rpc")))
    service.core.socket.send_vip.side_effect = (
        lambda *a, **k: order.append("push"))
    service._is_connected = True
    return order


def test_a_refresh_whose_peer_loop_raises_still_pushes_the_map(
        service, listed):
    service.auth_entries = [entry("peer.b", KEY_B)]
    make_refresh(service, peers=None)
    with pytest.raises(BaseException, match="No peers"):
        service._send_update([])
    (update,) = sent_updates(service)
    assert update["platforms"] == {"peer.b": ["inst-b"]}


def test_the_push_comes_before_the_peer_loop_and_is_not_repeated_after_it(
        service, listed):
    service.auth_entries = [entry("peer.b", KEY_B)]
    order = make_refresh(service, peers=["agent.one"])
    service._send_update([])
    assert order == ["push", "rpc"]
    assert len(sent_updates(service)) == 1


def test_a_failed_refresh_push_is_logged_as_an_error_naming_the_trigger(
        service, listed, caplog):
    service.auth_entries = [entry("peer.b", KEY_B)]
    make_refresh(service, peers=["agent.one"])
    service.core.socket.send_vip.side_effect = RuntimeError("router gone")
    with caplog.at_level(logging.ERROR, logger=AUTH_LOGGER):
        service._send_update([])
    (error,) = [r.getMessage() for r in caplog.records
                if r.name == AUTH_LOGGER and r.levelno == logging.ERROR]
    assert "auth file reload" in error


def test_the_auth_file_watcher_is_given_the_hand_off_to_the_hub(service):
    registered = []
    service.core.spawn = lambda func, *args: registered.append((func, args))
    service.setup_authentication_server(None)
    watched = {args[0]: args[1] for func, args in registered}
    assert watched[service.auth_file_path] == service._hand_reload_to_hub


def test_the_watcher_thread_only_hands_the_reload_to_the_hub(service, listed):
    service.auth_entries = [entry("peer.b", KEY_B)]
    queued = []
    service.core.send = lambda func, *a, **k: queued.append((func, a, k))
    make_refresh(service, peers=["agent.one"])
    pushed_on = []
    service.core.socket.send_vip.side_effect = (
        lambda *a, **k: pushed_on.append(threading.get_ident()))
    service.read_auth_file = lambda: service._send_update([])

    worker = threading.Thread(target=service._hand_reload_to_hub)
    worker.start()
    worker.join()
    assert pushed_on == []
    assert len(queued) == 1
    func, args, kwargs = queued[0]
    func(*args, **kwargs)
    assert pushed_on == [threading.get_ident()]


def test_two_reloads_handed_to_the_hub_do_not_overlap(service):
    log = []

    def slow_reload():
        log.append("start")
        gevent.sleep(0.05)
        log.append("end")

    service.read_auth_file = slow_reload
    gevent.joinall([gevent.spawn(service._reload_on_hub),
                    gevent.spawn(service._reload_on_hub)])
    assert log == ["start", "end", "start", "end"]
