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
"""auth.json is shared by several AuthFile objects and processes. These tests
cover the lock that makes each change a read-modify-write of the file as it is
on disk (#3320, #3338)."""

import contextlib
import copy
import fcntl
import inspect
import os
import stat
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import gevent
import gevent.event
import gevent.fileobject
import pytest

from volttron.platform import jsonapi
from volttron.platform.agent import utils
from volttron.platform.agent.known_identities import (CONTROL_CONNECTION,
                                                      PROCESS_IDENTITIES)
from volttron.platform.auth import AuthEntry, AuthFile, AuthService
from volttron.platform.auth import auth_file as auth_file_module
from volttron.platform.auth.auth_file import (AuthFileLockError,
                                              AuthFileLockTimeout,
                                              AuthFileReadError)
from volttron.platform.jsonrpc import INTERNAL_ERROR, RemoteError
from volttron.platform.vip.agent.decorators import annotations


def _key(char):
    return char * 43


def _entry(user_id, char, **kwargs):
    return AuthEntry(user_id=user_id, credentials=_key(char), **kwargs)


def _seed(auth_path, allow=(), deny=(), version=None):
    """Writes auth.json directly, as another process would leave it."""
    data = {"allow": [vars(e) for e in allow],
            "deny": [vars(e) for e in deny],
            "groups": {}, "roles": {},
            "version": version or {"major": 1, "minor": 4}}
    with open(auth_path, "w") as fil:
        fil.write(jsonapi.dumps(data, indent=2))


def _disk_allow(auth_path):
    with open(auth_path) as fil:
        return jsonapi.load(fil)["allow"]


def _users(auth_path):
    return [e["user_id"] for e in _disk_allow(auth_path)]


def _bytes(path):
    with open(path, "rb") as fil:
        return fil.read()


@contextlib.contextmanager
def _hold_lock(auth_path, operation=fcntl.LOCK_EX):
    """Holds the auth file lock from a separate open file, as another
    process would."""
    fd = os.open(auth_path + ".lock", os.O_RDONLY | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, operation)
        yield
    finally:
        os.close(fd)


def _lock_is_held(auth_path):
    fd = os.open(auth_path + ".lock", os.O_RDONLY | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    finally:
        os.close(fd)
    return False


def _wait_until(condition, timeout=5):
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            return False
        time.sleep(0.05)
    return True


def _service(auth_path):
    """An AuthService with the state its rpc authorization methods and
    read_auth_file use, without a platform."""
    service = object.__new__(AuthService)
    service.auth_file_path = auth_path
    service.auth_file = AuthFile(auth_path)
    service._last_loaded_allow_entries = []
    service._auth_pending = []
    service._auth_approved = []
    service._auth_denied = []
    service._is_connected = False
    service.auth_entries = []
    return service


@pytest.fixture
def auth_path(tmp_path):
    return str(tmp_path / "auth.json")


@pytest.fixture
def short_lock(monkeypatch):
    monkeypatch.setattr(AuthFile, "lock_timeout", 0.2)


@pytest.fixture
def no_pause(monkeypatch):
    """add() and approve_deny_credential() pause a second after writing."""
    monkeypatch.setattr(gevent, "sleep", lambda *args, **kwargs: None)


@pytest.mark.auth
def test_add_through_another_object_survives(auth_path):
    _seed(auth_path)
    stale = AuthFile(auth_path)
    AuthFile(auth_path).add(_entry("x", "X"))

    stale.add(_entry("y", "Y"))

    assert _users(auth_path) == ["x", "y"]
    assert stale.auth_data["allow_list"] == _disk_allow(auth_path)


@pytest.mark.auth
def test_remove_through_another_object_stays_removed(auth_path):
    _seed(auth_path, [_entry("keep", "K"), _entry("revoked", "R")])
    stale = AuthFile(auth_path)
    AuthFile(auth_path).remove_by_credentials(_key("R"))

    stale.add(_entry("new", "N"))

    assert _users(auth_path) == ["keep", "new"]


@pytest.mark.auth
def test_agent_start_keeps_an_entry_another_writer_added(auth_path):
    _seed(auth_path, [_entry("target", "T", identity="target")])
    service = _service(auth_path)
    AuthFile(auth_path).add(_entry("rpc_caller", "C", identity="rpc_caller"))

    returned = service.update_id_rpc_authorizations("target", {"m": ["cap"]})

    disk = {e["user_id"]: e for e in _disk_allow(auth_path)}
    assert set(disk) == {"target", "rpc_caller"}
    assert disk["target"]["rpc_method_authorizations"] == {"m": ["cap"]}
    assert returned == {"m": ["cap"]}


@pytest.mark.auth
def test_rpc_authorization_edit_keeps_other_fields_of_the_entry(auth_path):
    _seed(auth_path, [_entry("target", "T", identity="target",
                             capabilities=["old"])])
    service = _service(auth_path)
    AuthFile(auth_path).update_by_index(
        _entry("target", "T", identity="target", capabilities=["new"]), 0)

    service.add_rpc_authorizations("target", "m", ["c"])

    entry = _disk_allow(auth_path)[0]
    assert set(entry["capabilities"]) == {"new"}
    assert entry["rpc_method_authorizations"] == {"m": ["c"]}


@pytest.mark.auth
def test_lock_timeout_refuses_the_write(auth_path, short_lock):
    _seed(auth_path, [_entry("x", "X")])
    writer = AuthFile(auth_path)
    before = _bytes(auth_path)

    with _hold_lock(auth_path):
        with pytest.raises(AuthFileLockTimeout):
            writer.add(_entry("y", "Y"))

    assert _bytes(auth_path) == before


@pytest.mark.auth
def test_writer_waits_for_the_lock_then_writes(auth_path):
    _seed(auth_path)
    writer = AuthFile(auth_path)
    before = _bytes(auth_path)

    with _hold_lock(auth_path):
        task = gevent.spawn(writer.add, _entry("y", "Y"))
        gevent.sleep(0.3)
        assert _bytes(auth_path) == before
        assert not task.dead
    task.join(timeout=5)

    assert task.successful()
    assert _users(auth_path) == ["y"]


@pytest.mark.auth
def test_waiting_for_the_lock_polls_through_the_hub(auth_path, short_lock,
                                                    monkeypatch):
    # The platform does not patch time, so a wait that slept outside gevent
    # would stall every greenlet. Under pytest it is patched, so the call
    # itself is what is checked.
    _seed(auth_path)
    writer = AuthFile(auth_path)
    sleeps = []
    sleep = gevent.sleep

    def counting_sleep(*args, **kwargs):
        sleeps.append(args)
        return sleep(*args, **kwargs)

    monkeypatch.setattr(gevent, "sleep", counting_sleep)

    with _hold_lock(auth_path):
        with pytest.raises(AuthFileLockTimeout):
            writer.add(_entry("y", "Y"))

    assert sleeps


@pytest.mark.auth
def test_reader_never_takes_a_file_mid_write(auth_path):
    _seed(auth_path, [_entry("x", "X")])
    full = _bytes(auth_path)
    loaded = []
    reader = threading.Thread(
        target=lambda: loaded.append(AuthFile(auth_path)), daemon=True)

    with _hold_lock(auth_path):
        # Truncated, as a writer holding the lock leaves it mid-write.
        open(auth_path, "wb").close()
        reader.start()
        time.sleep(0.3)
        assert not loaded
        with open(auth_path, "wb") as fil:
            fil.write(full)
    reader.join(timeout=5)

    assert [e["user_id"] for e in loaded[0].auth_data["allow_list"]] == ["x"]
    assert _bytes(auth_path) == full


@pytest.mark.auth
def test_watcher_fires_after_a_locked_write_and_mode_is_kept(auth_path,
                                                             monkeypatch):
    _seed(auth_path)
    os.chmod(auth_path, 0o660)
    writer = AuthFile(auth_path)
    events = []
    observers = []

    class RecordedObserver(utils.Observer):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            observers.append(self)

    monkeypatch.setattr(utils, "Observer", RecordedObserver)
    utils.watch_file(auth_path, lambda: events.append(time.monotonic()))
    try:
        writer.add(_entry("y", "Y"))
        assert _wait_until(lambda: events)
    finally:
        for observer in observers:
            observer.stop()
            observer.join(timeout=5)

    assert stat.S_IMODE(os.stat(auth_path).st_mode) == 0o660
    assert _users(auth_path) == ["y"]


def _seed_for_mutations(auth_path):
    _seed(auth_path,
          allow=[_entry("x", "X", identity="x")],
          deny=[_entry("denied", "D")])


MUTATIONS = {
    "add": lambda f: f.add(_entry("new", "N")),
    "add_overwrite": lambda f: f.add(_entry("x", "X", capabilities=["c"]),
                                     overwrite=True),
    "approve": lambda f: f.approve_deny_credential("denied", is_approved=True),
    "deny": lambda f: f.approve_deny_credential("x", is_approved=False),
    "remove_by_credentials": lambda f: f.remove_by_credentials(_key("X")),
    "remove_by_index": lambda f: f.remove_by_index(0),
    "remove_by_indices": lambda f: f.remove_by_indices([0]),
    "set_groups": lambda f: f.set_groups({"g": ["r"]}),
    "set_roles": lambda f: f.set_roles({"r": ["c"]}),
    "update_by_index": lambda f: f.update_by_index(_entry("z", "Z"), 0),
    "modify_rpc_method_authorizations":
        lambda f: f.modify_rpc_method_authorizations("x",
                                                     lambda a: {"m": ["c"]}),
}


@pytest.mark.auth
@pytest.mark.parametrize("mutation", sorted(MUTATIONS))
def test_every_write_holds_the_lock(auth_path, monkeypatch, no_pause,
                                    mutation):
    _seed_for_mutations(auth_path)
    auth_file = AuthFile(auth_path)
    held = []
    write = AuthFile._write

    def checked_write(self, *args):
        held.append(_lock_is_held(auth_path))
        return write(self, *args)

    monkeypatch.setattr(AuthFile, "_write", checked_write)

    MUTATIONS[mutation](auth_file)

    assert held and all(held)


@pytest.mark.auth
def test_upgrade_write_holds_the_lock(auth_path, monkeypatch):
    _seed(auth_path, [_entry("x", "X")], version={"major": 1, "minor": 3})
    held = []
    write = AuthFile._write

    def checked_write(self, *args):
        held.append(_lock_is_held(auth_path))
        return write(self, *args)

    monkeypatch.setattr(AuthFile, "_write", checked_write)

    AuthFile(auth_path)

    assert held == [True]


@pytest.mark.auth
@pytest.mark.parametrize("text", ["{not json", "[]"])
def test_unreadable_file_refuses_the_write(auth_path, text):
    _seed(auth_path, [_entry("x", "X")])
    auth_file = AuthFile(auth_path)
    with open(auth_path, "w") as fil:
        fil.write(text)

    with pytest.raises(AuthFileReadError):
        auth_file.add(_entry("y", "Y"))

    assert _bytes(auth_path) == text.encode()


@pytest.mark.auth
def test_constructing_on_a_corrupt_file_does_not_rewrite_it(auth_path):
    with open(auth_path, "w") as fil:
        fil.write('{"allow": [')

    with pytest.raises(AuthFileReadError):
        AuthFile(auth_path)

    assert _bytes(auth_path) == b'{"allow": ['
    assert not [name for name in os.listdir(os.path.dirname(auth_path))
                if name.endswith(".bak")]


@pytest.mark.auth
def test_zmq_delete_reports_a_removal_it_could_not_write(auth_path,
                                                          short_lock):
    from volttron.platform.auth.auth_protocols.auth_zmq import \
        ZMQAuthorization

    _seed(auth_path, [_entry("revoked", "R")])
    service = _service(auth_path)
    service._auth_approved = [{"user_id": "revoked",
                               "credentials": _key("R")}]
    authorization = ZMQAuthorization(auth_service=service)

    with _hold_lock(auth_path):
        with pytest.raises(AuthFileLockTimeout):
            authorization.delete_authorization("revoked")

    assert _users(auth_path) == ["revoked"]


class _AuthServiceRpc:
    """Answers auth_file.* calls from an AuthFile the way the platform's RPC
    layer would: a remote exception arrives as a RemoteError on get()."""

    def __init__(self, auth_file):
        self.auth_file = auth_file

    def call(self, peer, method, *args):
        result = gevent.event.AsyncResult()
        try:
            result.set(getattr(self.auth_file, method.split(".", 1)[1])(*args))
        except Exception as err:
            result.set_exception(RemoteError(str(err),
                                             exc_type=type(err).__name__))
        return result


@pytest.mark.auth
def test_disable_setup_mode_reports_a_removal_it_could_not_write(
        auth_path, short_lock, monkeypatch):
    repo_root = Path(__file__).resolve().parents[3]
    monkeypatch.syspath_prepend(
        str(repo_root / "services" / "core" / "VolttronCentral"))
    from volttroncentral.agent import VolttronCentralAgent

    _seed(auth_path, [AuthEntry(credentials="/.*/", user_id="unknown")])
    agent = object.__new__(VolttronCentralAgent)
    agent.vip = SimpleNamespace(rpc=_AuthServiceRpc(AuthFile(auth_path)))

    with _hold_lock(auth_path):
        response = agent._disable_setup_mode({"groups": ["admin"]},
                                             {"message_id": 7})

    assert response != "SUCCESS"
    assert response["error"]["code"] == INTERNAL_ERROR
    assert [e["credentials"] for e in _disk_allow(auth_path)] == ["/.*/"]


@pytest.mark.auth
def test_agent_start_under_a_held_lock_keeps_the_file_value(auth_path):
    _seed(auth_path, [_entry("target", "T", identity="target",
                             rpc_method_authorizations={"m": ["tight"]})])
    service = _service(auth_path)
    cached = copy.deepcopy(service.auth_file.auth_data)
    before = _bytes(auth_path)

    with _hold_lock(auth_path):
        start = time.monotonic()
        returned = service.update_id_rpc_authorizations(
            "target", {"m": ["loose"], "n": ["x"]})
        elapsed = time.monotonic() - start

    # Agents give this call 4 seconds before keeping their own defaults.
    assert elapsed < 4
    assert returned == {"m": ["tight"], "n": ["x"]}
    assert _bytes(auth_path) == before
    assert service.auth_file.auth_data == cached


@pytest.mark.auth
def test_lock_file_symlink_is_refused(auth_path, tmp_path):
    _seed(auth_path, [_entry("x", "X")])
    auth_file = AuthFile(auth_path)
    lock_path = auth_path + ".lock"
    if os.path.lexists(lock_path):
        os.remove(lock_path)
    target = tmp_path / "elsewhere"
    os.symlink(target, lock_path)
    before = _bytes(auth_path)

    with pytest.raises(AuthFileLockError):
        auth_file.add(_entry("y", "Y"))

    assert not target.exists()
    assert _bytes(auth_path) == before


@pytest.mark.auth
def test_lock_file_is_created_owner_only_and_not_inherited(auth_path,
                                                           monkeypatch):
    _seed(auth_path)
    locked_fds = []
    flock = fcntl.flock

    def recording_flock(fd, operation):
        locked_fds.append(os.get_inheritable(fd))
        return flock(fd, operation)

    monkeypatch.setattr(fcntl, "flock", recording_flock)

    AuthFile(auth_path)

    lock_stat = os.lstat(auth_path + ".lock")
    assert stat.S_ISREG(lock_stat.st_mode)
    assert stat.S_IMODE(lock_stat.st_mode) == 0o600
    assert locked_fds and not any(locked_fds)


@pytest.mark.auth
def test_lock_file_open_to_others_is_refused(auth_path):
    _seed(auth_path, [_entry("x", "X")])
    lock_path = auth_path + ".lock"
    os.close(os.open(lock_path, os.O_CREAT | os.O_WRONLY, 0o644))
    os.chmod(lock_path, 0o644)
    before = _bytes(auth_path)

    with pytest.raises(AuthFileLockError):
        AuthFile(auth_path).add(_entry("y", "Y"))

    assert stat.S_IMODE(os.stat(lock_path).st_mode) == 0o644
    assert _bytes(auth_path) == before


@pytest.mark.auth
def test_lock_file_that_is_not_a_regular_file_is_refused(auth_path):
    _seed(auth_path, [_entry("x", "X")])
    os.mkfifo(auth_path + ".lock", 0o600)
    outcome = []

    def construct():
        try:
            AuthFile(auth_path)
        except AuthFileLockError as err:
            outcome.append(err)

    opener = threading.Thread(target=construct, daemon=True)
    opener.start()
    opener.join(timeout=5)

    assert not opener.is_alive()
    assert len(outcome) == 1


@pytest.mark.auth
def test_watcher_reload_under_a_held_lock_gives_up_and_keeps_entries(
        auth_path, monkeypatch):
    monkeypatch.setattr(AuthFile, "lock_timeout", 0.5)
    _seed(auth_path, [_entry("x", "X")])
    full = _bytes(auth_path)
    service = _service(auth_path)
    service.read_auth_file()
    loaded = service.auth_entries
    assert [e.user_id for e in loaded] == ["x"]
    reader = threading.Thread(target=service.read_auth_file, daemon=True)

    with _hold_lock(auth_path):
        open(auth_path, "wb").close()
        start = time.monotonic()
        reader.start()
        reader.join(timeout=5)
        elapsed = time.monotonic() - start
        with open(auth_path, "wb") as fil:
            fil.write(full)

    assert not reader.is_alive()
    assert elapsed < 2
    assert service.auth_entries is loaded

    AuthFile(auth_path).add(_entry("y", "Y"))
    service.read_auth_file()
    assert {e.user_id for e in service.auth_entries} == {"x", "y"}


def _rpc_exports(service):
    names = set()
    for _, member in inspect.getmembers(type(service)):
        names |= annotations(member, set, "rpc.exports")
    service.vip = SimpleNamespace(rpc=SimpleNamespace(
        export=lambda method, name=None: names.add(name or method.__name__)))
    service.export_auth_file()
    return names


@pytest.mark.auth
def test_auth_service_rpc_exports_are_unchanged(auth_path):
    _seed(auth_path)

    assert _rpc_exports(_service(auth_path)) == {
        "approve_authorization", "deny_authorization", "delete_authorization",
        "get_authorization", "get_authorization_status",
        "get_pending_authorizations", "get_approved_authorizations",
        "get_denied_authorizations", "get_authorizations", "get_capabilities",
        "get_groups", "get_roles", "get_user_to_capabilities",
        "update_id_rpc_authorizations", "add_rpc_authorizations",
        "delete_rpc_authorizations",
        "auth_file.read", "auth_file.find_by_credentials", "auth_file.add",
        "auth_file.update_by_index", "auth_file.remove_by_credentials",
        "auth_file.remove_by_index", "auth_file.remove_by_indices",
        "auth_file.set_groups", "auth_file.set_roles"}


@pytest.mark.auth
def test_agent_start_never_replaces_a_non_empty_authorization(auth_path):
    _seed(auth_path, [_entry("target", "T", identity="target",
                             rpc_method_authorizations={"m": ["tight"],
                                                        "n": []})])
    service = _service(auth_path)

    returned = service.update_id_rpc_authorizations(
        "target", {"m": ["loose"], "n": ["filled"], "o": ["added"]})

    expected = {"m": ["tight"], "n": ["filled"], "o": ["added"]}
    assert _disk_allow(auth_path)[0]["rpc_method_authorizations"] == expected
    assert returned == expected


@pytest.mark.auth
def test_rpc_authorization_edit_changes_the_first_entry_with_the_identity(
        auth_path):
    _seed(auth_path, [_entry("first", "F", identity="dup"),
                      _entry("second", "S", identity="dup")])
    service = _service(auth_path)

    service.add_rpc_authorizations("dup", "m", ["c"])

    disk = _disk_allow(auth_path)
    assert disk[0]["rpc_method_authorizations"] == {"m": ["c"]}
    assert disk[1]["rpc_method_authorizations"] == {}


@pytest.mark.auth
@pytest.mark.parametrize("identity",
                         [CONTROL_CONNECTION, PROCESS_IDENTITIES[0]])
def test_protected_identities_are_refused_before_taking_the_lock(
        auth_path, short_lock, identity):
    _seed(auth_path, [_entry("protected", "P", identity=identity,
                             rpc_method_authorizations={"m": ["c"]})])
    service = _service(auth_path)
    before = _bytes(auth_path)

    with _hold_lock(auth_path):
        assert service.add_rpc_authorizations(identity, "m", ["d"]) is None
        assert service.delete_rpc_authorizations(identity, "m", ["c"]) is None

    assert _bytes(auth_path) == before


READS = {
    "construct": lambda f: AuthFile(f.auth_file),
    "load": lambda f: f.load(),
    "load_allow_snapshot": lambda f: f.load_allow_snapshot(),
}


@pytest.mark.auth
@pytest.mark.parametrize("operation", sorted(MUTATIONS) + sorted(READS))
def test_nothing_yields_while_the_lock_is_held(auth_path, monkeypatch,
                                               operation):
    _seed_for_mutations(auth_path)
    auth_file = AuthFile(auth_path)
    yields_under_lock = []

    def refuse_under_lock(name):
        if _lock_is_held(auth_path):
            yields_under_lock.append(name)
            raise AssertionError(f"{name} called while holding the lock")

    def checked_sleep(*args, **kwargs):
        refuse_under_lock("gevent.sleep")

    def checked_file_object(*args, **kwargs):
        refuse_under_lock("FileObject")
        return gevent.fileobject.FileObject(*args, **kwargs)

    monkeypatch.setattr(gevent, "sleep", checked_sleep)
    monkeypatch.setattr(auth_file_module, "FileObject", checked_file_object,
                        raising=False)

    {**MUTATIONS, **READS}[operation](auth_file)

    assert yields_under_lock == []
