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
"""A reload, a failed write or a busy lock must never leave auth.json, or
what a later change is built from, older or emptier than the file was
(#3320)."""

import contextlib
import errno
import fcntl
import logging
import os
import stat
import time
import uuid
from types import SimpleNamespace

import gevent
import gevent.event
import pytest
from zmq import green as zmq

from volttron.platform import jsonapi
from volttron.platform.auth import AuthFile
from volttron.platform.auth import auth_file as auth_file_module
from volttron.platform.auth.auth_file import (AuthFileLockError,
                                              AuthFileLockTimeout,
                                              AuthFileReadError)
from volttron.platform.vip.socket import encode_key
from volttrontesting.platform.auth_tests.test_auth_file_lock import (
    _bytes, _disk_allow, _entry, _hold_lock, _key, _seed, _service, _users)


@pytest.fixture
def auth_path(tmp_path):
    return str(tmp_path / "auth.json")


class _PausedReload(AuthFile):
    """Stops a reload greenlet just before it replaces auth_data, standing
    in for the watcher thread being preempted there."""

    reloader = None

    def __init__(self, *args, **kwargs):
        self.reached = gevent.event.Event()
        self.resume = gevent.event.Event()
        super().__init__(*args, **kwargs)

    @property
    def auth_data(self):
        return self.__dict__["auth_data"]

    @auth_data.setter
    def auth_data(self, value):
        if gevent.getcurrent() is self.reloader:
            self.reached.set()
            self.resume.wait(timeout=5)
        self.__dict__["auth_data"] = value


@pytest.mark.auth
@pytest.mark.parametrize("reload", ["load", "load_allow_snapshot"])
def test_reload_cannot_replace_the_data_a_change_is_built_from(auth_path,
                                                               monkeypatch,
                                                               reload):
    _seed(auth_path)
    auth_file = _PausedReload(auth_path)
    other_file = AuthFile(auth_path)
    test_greenlet = gevent.getcurrent()
    read = auth_file.read

    def yield_then_read():
        if gevent.getcurrent() is test_greenlet:
            # The watcher runs on its own thread, so it can run here, after
            # the change has loaded the file and before it uses auth_data.
            auth_file.resume.set()
            gevent.sleep(0)
        return read()

    monkeypatch.setattr(auth_file, "read", yield_then_read)

    auth_file.reloader = gevent.spawn(getattr(auth_file, reload))
    assert auth_file.reached.wait(timeout=5)
    other = gevent.spawn(other_file.add, _entry("x", "X"))
    other.join(timeout=0.5)
    if "x" not in _users(auth_path):
        # The reload still holds the lock, so release it on a timer rather
        # than from inside the change below.
        gevent.spawn_later(0.3, auth_file.resume.set)

    auth_file.add(_entry("y", "Y"))
    other.join(timeout=5)
    auth_file.reloader.join(timeout=5)

    assert other.successful()
    assert set(_users(auth_path)) == {"x", "y"}


class _FailingWrite:
    """A file that takes `budget` bytes across all writes and then fails
    partway through the next one, as a full disk does. With
    fail_truncate, every write succeeds and the truncate fails."""

    def __init__(self, fil, budget, fail_truncate):
        self.fil = fil
        self.budget = budget
        self.fail_truncate = fail_truncate

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.fil.close()

    def __getattr__(self, name):
        return getattr(self.fil, name)

    def write(self, data):
        if self.budget is not None and len(data) > self.budget:
            self.fil.write(data[:self.budget])
            self.fil.flush()
            self.budget = 0
            raise OSError(errno.ENOSPC, os.strerror(errno.ENOSPC))
        if self.budget is not None:
            self.budget -= len(data)
        return self.fil.write(data)

    def truncate(self, *args):
        if self.fail_truncate:
            raise OSError(errno.EIO, os.strerror(errno.EIO))
        return self.fil.truncate(*args)


def _edit_comment(auth_file):
    auth_file.update_by_index(_entry("x", "X", comments="bbbbbbbb"), 0)


def _stop_inside_comment(old_text):
    # The edit keeps every length, so the new text matches the old one up
    # to the comment; stop two bytes into it.
    return old_text.index(b"aaaaaaaa") + 2


TORN_WRITES = {
    "add-nothing-written": (lambda f: f.add(_entry("y", "Y")),
                            lambda old: 0, False),
    "add-some-written": (lambda f: f.add(_entry("y", "Y")),
                         lambda old: 10, False),
    "edit-stops-inside-a-string": (_edit_comment, _stop_inside_comment,
                                   False),
    "remove-truncate-fails": (lambda f: f.remove_by_index(1),
                              lambda old: None, True),
}


@pytest.mark.auth
@pytest.mark.parametrize("case", sorted(TORN_WRITES))
def test_failed_write_never_leaves_other_valid_data(auth_path, monkeypatch,
                                                    case):
    _seed(auth_path, [_entry("x", "X", comments="aaaaaaaa"),
                      _entry("w", "W")])
    writer = AuthFile(auth_path)
    change, budget, fail_truncate = TORN_WRITES[case]
    old_text = _bytes(auth_path)
    old_allow = AuthFile(auth_path).auth_data["allow_list"]

    def failing_open(path, mode="r", *args, **kwargs):
        fil = open(path, mode, *args, **kwargs)
        if "w" in mode or "+" in mode:
            return _FailingWrite(fil, budget(old_text), fail_truncate)
        return fil

    monkeypatch.setattr(auth_file_module, "open", failing_open,
                        raising=False)
    with pytest.raises(OSError):
        change(writer)
    monkeypatch.delattr(auth_file_module, "open")

    # Refused, or still the data from before the change: never a mix of
    # old and new, and never an empty file read as no entries.
    try:
        after = AuthFile(auth_path).auth_data["allow_list"]
    except AuthFileReadError:
        after = None
    assert after in (None, old_allow)


@pytest.mark.auth
def test_empty_file_reads_as_no_entries_and_takes_a_change(auth_path):
    open(auth_path, "w").close()
    auth_file = AuthFile(auth_path)

    assert auth_file.read_allow_entries() == []

    auth_file.add(_entry("x", "X"))

    assert _users(auth_path) == ["x"]


@pytest.mark.auth
@pytest.mark.parametrize("text", ["\n", "  \n\t",
                                  "# none yet\n// none\n/* none */\n"])
def test_blank_or_comment_only_file_reads_as_no_entries(auth_path, text):
    with open(auth_path, "w") as fil:
        fil.write(text)
    auth_file = AuthFile(auth_path)

    assert auth_file.read_allow_entries() == []

    auth_file.add(_entry("x", "X"))

    assert _users(auth_path) == ["x"]


@pytest.mark.auth
def test_file_led_by_the_torn_write_marker_is_refused(auth_path):
    with open(auth_path, "wb") as fil:
        fil.write(b"\0 \n")

    with pytest.raises(AuthFileReadError):
        AuthFile(auth_path)

    assert _bytes(auth_path) == b"\0 \n"


@pytest.mark.auth
def test_write_keeps_the_inode_and_mode(auth_path):
    _seed(auth_path, [_entry("x", "X"), _entry("w", "W")])
    os.chmod(auth_path, 0o640)
    before = os.stat(auth_path)

    AuthFile(auth_path).remove_by_index(1)

    after = os.stat(auth_path)
    assert (after.st_ino, stat.S_IMODE(after.st_mode)) == (
        before.st_ino, 0o640)
    assert _users(auth_path) == ["x"]


@pytest.mark.auth
def test_missing_file_is_created_and_takes_a_change(auth_path):
    AuthFile(auth_path).add(_entry("x", "X"))

    assert _users(auth_path) == ["x"]


def _pending_authorization(auth_path):
    from volttron.platform.auth.auth_protocols.auth_zmq import \
        ZMQAuthorization

    service = _service(auth_path)
    service._auth_pending = [{"domain": "vip", "address": "127.0.0.1",
                              "mechanism": "CURVE", "credentials": _key("P"),
                              "user_id": "pending", "retries": 1}]
    return service, ZMQAuthorization(auth_service=service)


@contextlib.contextmanager
def _unreadable(auth_path):
    full = _bytes(auth_path)
    with open(auth_path, "w") as fil:
        fil.write('{"allow": [')
    try:
        yield
    finally:
        with open(auth_path, "wb") as fil:
            fil.write(full)


FAILURES = {
    "lock": (_hold_lock, AuthFileLockTimeout),
    "read": (_unreadable, AuthFileReadError),
}


@pytest.mark.auth
@pytest.mark.parametrize("failure", sorted(FAILURES))
@pytest.mark.parametrize("approve", [True, False])
def test_zmq_decision_that_cannot_be_written_keeps_it_pending(
        auth_path, monkeypatch, failure, approve):
    monkeypatch.setattr(AuthFile, "lock_timeout", 0.2)
    monkeypatch.setattr(gevent, "sleep", lambda *args, **kwargs: None)
    _seed(auth_path)
    service, authorization = _pending_authorization(auth_path)
    decide = (authorization.approve_authorization if approve
              else authorization.deny_authorization)
    condition, error = FAILURES[failure]

    with condition(auth_path):
        with pytest.raises(error):
            decide("pending")

    assert [p["user_id"] for p in service._auth_pending] == ["pending"]
    assert _users(auth_path) == []

    decide("pending")

    assert service._auth_pending == []
    with open(auth_path) as fil:
        disk = jsonapi.load(fil)
    decided = disk["allow"] if approve else disk["deny"]
    assert [e["credentials"] for e in decided] == [_key("P")]


@contextlib.contextmanager
def _zap_loop(auth_path):
    """Runs the ZAP loop in setup mode on its own inproc socket and yields
    the loop greenlet and a function sending one CURVE request."""
    from volttron.platform.auth.auth_protocols.auth_zmq import \
        ZMQServerAuthentication

    service = _service(auth_path)
    service._setup_mode = True
    service.allow_any = False
    service.core = SimpleNamespace(socket=SimpleNamespace(
        send_vip=lambda *args, **kwargs: None))
    server = ZMQServerAuthentication(service)
    context = zmq.Context()
    address = "inproc://zap-{}".format(uuid.uuid4())
    server.zap_socket = context.socket(zmq.ROUTER)
    server.zap_socket.bind(address)
    client = context.socket(zmq.DEALER)
    client.connect(address)

    def request(request_id, raw_key):
        client.send_multipart([b"", b"1.0", request_id, b"vip",
                               b"127.0.0.1", b"", b"CURVE", raw_key])
        if not client.poll(5000):
            return None
        return client.recv_multipart()

    loop = gevent.spawn(server.handle_authentication, {})
    try:
        yield loop, request
    finally:
        loop.kill()
        client.close(linger=0)
        server.zap_socket.close(linger=0)
        context.term()


def _zap_success(request_id):
    return [b"", b"1.0", request_id, b"200", b"SUCCESS", b"", b""]


@pytest.mark.auth
@pytest.mark.parametrize("failure", sorted(FAILURES))
def test_setup_mode_answers_a_request_it_cannot_record(auth_path, monkeypatch,
                                                       caplog, failure):
    monkeypatch.setattr(AuthFile, "lock_timeout", 0.2)
    _seed(auth_path)
    condition, _ = FAILURES[failure]

    with _zap_loop(auth_path) as (loop, request):
        with caplog.at_level(logging.ERROR):
            with condition(auth_path):
                replies = [request(b"1", b"A" * 32), request(b"2", b"B" * 32)]
        assert replies == [_zap_success(b"1"), _zap_success(b"2")]
        assert not loop.dead
        assert _users(auth_path) == []
        assert [r for r in caplog.records if r.levelno == logging.ERROR
                and "not recorded" in r.getMessage()]

        assert request(b"3", b"C" * 32) == _zap_success(b"3")

    assert [e["credentials"] for e in _disk_allow(auth_path)] == [
        encode_key(b"C" * 32)]


@pytest.mark.auth
def test_lock_file_owned_by_another_user_is_refused(auth_path, monkeypatch):
    _seed(auth_path, [_entry("x", "X")])
    auth_file = AuthFile(auth_path)
    before = _bytes(auth_path)
    uid = os.geteuid()
    monkeypatch.setattr(os, "geteuid", lambda: uid + 1)

    with pytest.raises(AuthFileLockError, match="owned by this user"):
        auth_file.add(_entry("y", "Y"))

    assert _bytes(auth_path) == before


@pytest.mark.auth
@pytest.mark.parametrize("reload", ["load", "load_allow_snapshot"])
def test_reads_share_the_lock_and_writes_do_not(auth_path, monkeypatch,
                                                reload):
    monkeypatch.setattr(AuthFile, "lock_timeout", 0.2)
    _seed(auth_path, [_entry("x", "X")])
    auth_file = AuthFile(auth_path)
    before = _bytes(auth_path)

    with _hold_lock(auth_path, fcntl.LOCK_SH):
        getattr(auth_file, reload)()
        with pytest.raises(AuthFileLockTimeout):
            auth_file.add(_entry("y", "Y"))

    assert [e["user_id"] for e in auth_file.auth_data["allow_list"]] == ["x"]
    assert _bytes(auth_path) == before


@pytest.mark.auth
def test_lock_wait_is_bounded_at_two_seconds(auth_path):
    _seed(auth_path)
    auth_file = AuthFile(auth_path)

    with _hold_lock(auth_path):
        start = time.monotonic()
        with pytest.raises(AuthFileLockTimeout):
            auth_file.add(_entry("y", "Y"))
        elapsed = time.monotonic() - start

    assert AuthFile.lock_timeout == 2.0
    assert 2.0 <= elapsed < 2.5


@pytest.mark.auth
@pytest.mark.parametrize("field, value", [
    ("allow", {"x": {}}), ("deny", "x"), ("groups", ["g"]), ("roles", "r"),
    ("version", "1.4")])
def test_field_of_the_wrong_type_refuses_the_write(auth_path, field, value):
    _seed(auth_path, [_entry("x", "X")])
    auth_file = AuthFile(auth_path)
    with open(auth_path) as fil:
        data = jsonapi.load(fil)
    data[field] = value
    with open(auth_path, "w") as fil:
        fil.write(jsonapi.dumps(data))
    before = _bytes(auth_path)

    with pytest.raises(AuthFileReadError, match=field):
        auth_file.add(_entry("y", "Y"))

    assert _bytes(auth_path) == before


@pytest.mark.auth
def test_agent_start_for_an_unknown_identity_returns_none(auth_path):
    _seed(auth_path, [_entry("x", "X", identity="x")])
    service = _service(auth_path)
    before = _bytes(auth_path)

    assert service.update_id_rpc_authorizations("unknown",
                                                {"m": ["c"]}) is None
    assert _bytes(auth_path) == before
