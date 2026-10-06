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
"""Capabilities required to change auth.json and RPC method authorizations
through AuthService's RPC exports, checked through the export table the RPC
subsystem builds, and from a live platform."""

import fcntl
import inspect
import logging
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import gevent
import gevent.event
import pytest
from mock import MagicMock

from volttron.platform import jsonapi, jsonrpc
from volttron.platform.agent.known_identities import AUTH
from volttron.platform.auth import AuthEntry, AuthFile, AuthService
from volttron.platform.auth import auth as auth_module
from volttron.platform.jsonrpc import INTERNAL_ERROR, RemoteError
from volttron.platform.vip.agent.subsystems.rpc import RPC
from volttrontesting.utils.platformwrapper import with_os_environ

AUTH_MODS = "allow_auth_modifications"
RPC_MODS = "modify_rpc_method_allowance"

# Every name in AuthService's export table and the capabilities it requires.
# A new export fails test_export_table_requires_the_listed_capabilities
# until it is added here, gated or not.
EXPORT_CAPABILITIES = {
    "auth_file.read": set(),
    "auth_file.find_by_credentials": set(),
    "auth_file.add": {AUTH_MODS},
    "auth_file.update_by_index": {AUTH_MODS},
    "auth_file.remove_by_credentials": {AUTH_MODS},
    "auth_file.remove_by_index": {AUTH_MODS},
    "auth_file.remove_by_indices": {AUTH_MODS},
    "auth_file.set_groups": {AUTH_MODS},
    "auth_file.set_roles": {AUTH_MODS},
    "add_rpc_authorizations": {RPC_MODS},
    "delete_rpc_authorizations": {RPC_MODS},
    "update_id_rpc_authorizations": set(),
    "approve_authorization": {AUTH_MODS},
    "deny_authorization": {AUTH_MODS},
    "delete_authorization": {AUTH_MODS},
    "get_authorization": {AUTH_MODS},
    "get_authorization_status": {AUTH_MODS},
    "get_pending_authorizations": set(),
    "get_approved_authorizations": set(),
    "get_denied_authorizations": set(),
    "get_authorizations": set(),
    "get_capabilities": set(),
    "get_groups": set(),
    "get_roles": set(),
    "get_user_to_capabilities": set(),
}


def _key(char):
    return char * 43


def _entry(user_id, char, **kwargs):
    return AuthEntry(user_id=user_id, credentials=_key(char), **kwargs)


def _seed(auth_path, allow):
    data = {"allow": [vars(e) for e in allow], "deny": [],
            "groups": {}, "roles": {}, "version": {"major": 1, "minor": 4}}
    with open(auth_path, "w") as fil:
        fil.write(jsonapi.dumps(data, indent=2))


def _bytes(path):
    with open(path, "rb") as fil:
        return fil.read()


def _disk_allow(auth_path):
    with open(auth_path) as fil:
        return jsonapi.load(fil)["allow"]


def _required_capabilities(exported):
    """The capability set an export table entry enforces: the RPC
    subsystem's auth wrapper closes over it, a plain export has none."""
    return set(inspect.getclosurevars(exported).nonlocals.get(
        "required_caps", set()))


class _Wired:
    """An AuthService on auth_path with a real RPC subsystem, so calls go
    through the export table and its capability checks. capabilities maps
    a user to the capabilities the auth subsystem reports for it."""

    def __init__(self, auth_path, capabilities, enable_auth=True):
        service = object.__new__(AuthService)
        service.auth_file_path = auth_path
        service.auth_file = AuthFile(auth_path)
        service._last_loaded_allow_entries = []
        service.auth_entries = []
        core = MagicMock(enable_auth=enable_auth, messagebus="zmq")
        self.rpc = RPC(core, service, MagicMock())
        service.vip = SimpleNamespace(
            rpc=self.rpc,
            auth=SimpleNamespace(
                get_capabilities=lambda user: capabilities.get(user, {})))
        service.export_auth_file()
        self.service = service

    def call(self, user, name, *args, **kwargs):
        self.rpc.context = SimpleNamespace(
            vip_message=SimpleNamespace(user=user))
        return self.rpc._exports[name](*args, **kwargs)


@pytest.fixture
def auth_path(tmp_path):
    return str(tmp_path / "auth.json")


@pytest.fixture
def no_pause(monkeypatch):
    """AuthFile.add pauses a second after writing."""
    monkeypatch.setattr(gevent, "sleep", lambda *args, **kwargs: None)


def _seed_target(auth_path):
    _seed(auth_path, [
        _entry("target", "T", identity="target",
               rpc_method_authorizations={"m": ["tight"]}),
        _entry("other", "O", identity="other")])


# Each mutating export, the capability it needs and arguments that change
# the file when the capability is held.
MUTATING_CALLS = [
    ("auth_file.add", AUTH_MODS,
     ({"credentials": _key("N"), "user_id": "new",
       "capabilities": [AUTH_MODS]},)),
    ("auth_file.update_by_index", AUTH_MODS,
     ({"credentials": _key("T"), "user_id": "target", "identity": "target",
       "capabilities": [AUTH_MODS]}, 0)),
    ("auth_file.remove_by_credentials", AUTH_MODS, (_key("O"),)),
    ("auth_file.remove_by_index", AUTH_MODS, (1,)),
    ("auth_file.remove_by_indices", AUTH_MODS, ([1],)),
    ("auth_file.set_groups", AUTH_MODS, ({"g": [AUTH_MODS]},)),
    ("auth_file.set_roles", AUTH_MODS, ({"r": [AUTH_MODS]},)),
    ("add_rpc_authorizations", RPC_MODS, ("target", "m", ["loose"])),
    ("delete_rpc_authorizations", RPC_MODS, ("target", "m", ["tight"])),
]


@pytest.mark.auth
def test_export_table_requires_the_listed_capabilities(auth_path):
    _seed_target(auth_path)
    wired = _Wired(auth_path, {})

    table = {name: _required_capabilities(wired.rpc._exports[name])
             for name in wired.rpc.get_exports()}

    assert table == EXPORT_CAPABILITIES


@pytest.mark.auth
@pytest.mark.parametrize("name,capability,args", MUTATING_CALLS,
                         ids=[c[0] for c in MUTATING_CALLS])
def test_caller_without_the_capability_cannot_change_the_file(
        auth_path, no_pause, name, capability, args):
    _seed_target(auth_path)
    before = _bytes(auth_path)
    wired = _Wired(auth_path, {"other": {"edit_config_store": {}}})

    with pytest.raises(jsonrpc.Error) as refused:
        wired.call("other", name, *args)

    assert refused.value.code == jsonrpc.UNAUTHORIZED
    assert capability in refused.value.message
    assert _bytes(auth_path) == before


@pytest.mark.auth
@pytest.mark.parametrize("name,capability,args", MUTATING_CALLS,
                         ids=[c[0] for c in MUTATING_CALLS])
def test_caller_with_the_capability_changes_the_file(
        auth_path, no_pause, name, capability, args):
    _seed_target(auth_path)
    before = _bytes(auth_path)
    wired = _Wired(auth_path, {"admin": {capability: None}})

    wired.call("admin", name, *args)

    assert _bytes(auth_path) != before


@pytest.mark.auth
def test_auth_disabled_skips_the_gates_and_warns(auth_path, no_pause, caplog):
    _seed_target(auth_path)
    caplog.set_level(logging.WARNING)
    wired = _Wired(auth_path, {}, enable_auth=False)

    wired.call("other", "auth_file.set_groups", {"g": ["c"]})
    wired.call("other", "add_rpc_authorizations", "target", "n", ["c"])

    warnings = [r.getMessage() for r in caplog.records
                if "authentication is disabled" in r.getMessage()]
    assert len(warnings) == 1
    for name in ("auth_file.add", "auth_file.set_roles",
                 "add_rpc_authorizations", "delete_rpc_authorizations"):
        assert name in warnings[0]
    disk = jsonapi.loads(_bytes(auth_path))
    assert disk["groups"] == {"g": ["c"]}
    assert disk["allow"][0]["rpc_method_authorizations"] == {
        "m": ["tight"], "n": ["c"]}


def _refusals(caplog):
    return [r for r in caplog.records if r.levelno == logging.WARNING
            and r.name == auth_module.__name__]


@pytest.mark.auth
def test_agent_cannot_record_methods_for_another_identity(auth_path, caplog):
    _seed_target(auth_path)
    before = _bytes(auth_path)
    wired = _Wired(auth_path, {})
    caplog.set_level(logging.WARNING)

    returned = wired.call("other", "update_id_rpc_authorizations",
                          "target", {"new_method": ["c"]})

    assert returned is None
    assert _bytes(auth_path) == before
    assert len(_refusals(caplog)) == 1


@pytest.mark.auth
def test_agent_records_its_own_missing_methods(auth_path, caplog):
    _seed_target(auth_path)
    wired = _Wired(auth_path, {})
    caplog.set_level(logging.WARNING)

    returned = wired.call("target", "update_id_rpc_authorizations",
                          "target", {"m": ["loose"], "new_method": ["c"]})

    assert returned == {"m": ["tight"], "new_method": ["c"]}
    assert _disk_allow(auth_path)[0]["rpc_method_authorizations"] == {
        "m": ["tight"], "new_method": ["c"]}
    assert _refusals(caplog) == []


@pytest.mark.auth
def test_entry_is_matched_by_user_id_not_by_identity(auth_path):
    """The caller must be the entry's user, even when it shares the
    identity's name with another entry's user_id."""
    _seed(auth_path, [_entry("agent-user", "A", identity="agent")])
    before = _bytes(auth_path)
    wired = _Wired(auth_path, {})

    assert wired.call("agent", "update_id_rpc_authorizations",
                      "agent", {"m": ["c"]}) is None
    assert _bytes(auth_path) == before

    assert wired.call("agent-user", "update_id_rpc_authorizations",
                      "agent", {"m": ["c"]}) == {"m": ["c"]}


@pytest.mark.auth
def test_caller_cannot_name_the_user_to_check(auth_path):
    _seed_target(auth_path)
    before = _bytes(auth_path)
    wired = _Wired(auth_path, {})

    with pytest.raises(TypeError):
        wired.call("other", "update_id_rpc_authorizations",
                   "target", {"new_method": ["c"]}, user_id="target")

    assert _bytes(auth_path) == before


@pytest.mark.auth
def test_rmq_user_drops_the_instance_name(auth_path, monkeypatch):
    monkeypatch.setattr(auth_module, "get_messagebus", lambda: "rmq")
    _seed_target(auth_path)
    wired = _Wired(auth_path, {})

    assert wired.call("instance.other", "update_id_rpc_authorizations",
                      "target", {"new_method": ["c"]}) is None
    assert wired.call("instance.target", "update_id_rpc_authorizations",
                      "target", {"new_method": ["c"]}) == {
        "new_method": ["c"]}


@pytest.mark.auth
def test_cached_answer_under_a_held_lock_is_refused_to_another_user(
        auth_path, monkeypatch, caplog):
    """When the file cannot be locked the service answers from its last
    load; that answer is also only given to the entry's own user."""
    monkeypatch.setattr(AuthFile, "lock_timeout", 0.2)
    _seed_target(auth_path)
    wired = _Wired(auth_path, {})
    caplog.set_level(logging.WARNING)
    fd = os.open(auth_path + ".lock", os.O_RDONLY | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        refused = wired.call("other", "update_id_rpc_authorizations",
                             "target", {"new_method": ["c"]})
        allowed = wired.call("target", "update_id_rpc_authorizations",
                             "target", {"new_method": ["c"]})
    finally:
        os.close(fd)

    assert refused is None
    assert len(_refusals(caplog)) == 1
    assert allowed == {"new_method": ["c"]}


class _AuthServiceCalls:
    """Sends VolttronCentral's AUTH calls through a wired AuthService as
    the user volttron.central; a remote exception arrives as a RemoteError
    on get(), and hang makes every call time out."""

    def __init__(self, wired, hang=False):
        self.wired = wired
        self.hang = hang
        self.timeouts = []

    def call(self, peer, method, *args):
        assert peer == AUTH
        if self.hang:
            return _NeverReady(self.timeouts)
        result = gevent.event.AsyncResult()
        try:
            result.set(self.wired.call("volttron.central", method, *args))
        except Exception as err:
            # Named as the platform's dispatcher names a remote exception.
            exc_type = f"{type(err).__module__}.{type(err).__name__}"
            result.set_exception(RemoteError(
                str(err), exc_type=exc_type, exc_args=list(err.args)))
        return result


class _NeverReady:
    def __init__(self, timeouts):
        self.timeouts = timeouts

    def get(self, timeout=None):
        self.timeouts.append(timeout)
        raise gevent.Timeout(timeout)


def _volttron_central(auth_path, capabilities, monkeypatch, hang=False):
    repo_root = Path(__file__).resolve().parents[3]
    monkeypatch.syspath_prepend(
        str(repo_root / "services" / "core" / "VolttronCentral"))
    from volttroncentral.agent import VolttronCentralAgent

    agent = object.__new__(VolttronCentralAgent)
    calls = _AuthServiceCalls(
        _Wired(auth_path, {"volttron.central": capabilities}), hang=hang)
    agent.vip = SimpleNamespace(rpc=calls)
    return agent, calls


def _enable(agent):
    return agent._enable_setup_mode({"groups": ["admin"]}, {"message_id": 7})


@pytest.mark.auth
def test_setup_mode_without_the_capability_is_an_error(
        auth_path, no_pause, monkeypatch):
    _seed_target(auth_path)
    before = _bytes(auth_path)
    agent, _ = _volttron_central(auth_path, {}, monkeypatch)

    response = _enable(agent)

    assert response != "SUCCESS"
    assert response["error"]["code"] == INTERNAL_ERROR
    assert response["id"] == 7
    assert _bytes(auth_path) == before


@pytest.mark.auth
def test_setup_mode_with_the_capability_adds_the_entry(
        auth_path, no_pause, monkeypatch):
    _seed_target(auth_path)
    agent, _ = _volttron_central(auth_path, {AUTH_MODS: None}, monkeypatch)

    assert _enable(agent) == "SUCCESS"

    added = [e for e in _disk_allow(auth_path) if e["credentials"] == "/.*/"]
    assert [e["user_id"] for e in added] == ["unknown"]


@pytest.mark.auth
def test_setup_mode_enabled_twice_succeeds_and_keeps_one_entry(
        auth_path, no_pause, monkeypatch):
    _seed_target(auth_path)
    agent, _ = _volttron_central(auth_path, {AUTH_MODS: None}, monkeypatch)
    assert _enable(agent) == "SUCCESS"
    before = _bytes(auth_path)

    assert _enable(agent) == "SUCCESS"

    assert _bytes(auth_path) == before


@pytest.mark.auth
def test_setup_mode_unanswered_is_an_error_after_a_bounded_wait(
        auth_path, monkeypatch):
    _seed_target(auth_path)
    agent, calls = _volttron_central(auth_path, {AUTH_MODS: None},
                                     monkeypatch, hang=True)

    response = _enable(agent)

    assert response["error"]["code"] == INTERNAL_ERROR
    assert calls.timeouts and all(t is not None for t in calls.timeouts)


def _auth_list(platform):
    with with_os_environ(platform.env):
        return subprocess.check_output(["volttron-ctl", "auth", "list"],
                                       env=platform.env,
                                       universal_newlines=True)


@pytest.mark.auth
def test_live_agent_without_capabilities_cannot_add_an_auth_entry(
        volttron_instance):
    if not volttron_instance.auth_enabled:
        pytest.skip("capabilities are not enforced with auth disabled")
    agent = volttron_instance.build_agent(identity="no.capabilities",
                                          capabilities={})
    refused_key = _key("Q")
    allowed_key = _key("P")
    try:
        with pytest.raises(RemoteError) as refused:
            agent.vip.rpc.call(AUTH, "auth_file.add", {
                "credentials": refused_key, "user_id": "refused.entry",
                "capabilities": [AUTH_MODS]}).get(timeout=10)
        assert AUTH_MODS in str(refused.value)

        volttron_instance.dynamic_agent.vip.rpc.call(AUTH, "auth_file.add", {
            "credentials": allowed_key, "user_id": "allowed.entry"}).get(
                timeout=10)

        listing = _auth_list(volttron_instance)
        assert refused_key not in listing
        assert "refused.entry" not in listing
        assert allowed_key in listing
    finally:
        agent.core.stop()
        AuthFile(os.path.join(volttron_instance.volttron_home,
                              "auth.json")).remove_by_credentials(allowed_key)
