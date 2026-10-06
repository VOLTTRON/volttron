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
"""vctl auth commands that change auth.json must wait for the platform's
answer, so a change the platform refused is reported as an error (#3320)."""

import contextlib
import fcntl
import io
import os
from types import SimpleNamespace

import gevent
import gevent.event
import pytest

from volttron.platform import jsonapi
from volttron.platform.auth import AuthEntry, AuthFile, AuthService
from volttron.platform.control import control_auth
from volttron.platform.jsonrpc import RemoteError
from volttron.platform.vip.agent.decorators import annotations


def _key(char):
    return char * 43


def _seed(auth_path):
    entry = AuthEntry(user_id="x", identity="x", credentials=_key("X"),
                      rpc_method_authorizations={"m": ["c"]})
    data = {"allow": [vars(entry)], "deny": [],
            "groups": {"g": ["r"]}, "roles": {"r": ["c"]},
            "version": {"major": 1, "minor": 5}}
    with open(auth_path, "w") as fil:
        fil.write(jsonapi.dumps(data, indent=2))


def _bytes(path):
    with open(path, "rb") as fil:
        return fil.read()


@contextlib.contextmanager
def _hold_lock(auth_path):
    fd = os.open(auth_path + ".lock", os.O_RDONLY | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


class _Platform:
    """Answers vctl's RPC calls from an AuthService's real exports; an
    exception reaches vctl as a RemoteError on get(), as over VIP."""

    def __init__(self, auth_path):
        service = object.__new__(AuthService)
        service.auth_file_path = auth_path
        service.auth_file = AuthFile(auth_path)
        self.exports = {}
        for member in vars(AuthService).values():
            for name in annotations(member, set, "rpc.exports"):
                self.exports[name] = member.__get__(service)
        self.service = service

    def call(self, peer, method, *args):
        target = self.exports.get(method) or getattr(self.service, method)
        result = gevent.event.AsyncResult()
        try:
            result.set(target(*args))
        except Exception as err:
            result.set_exception(RemoteError(str(err),
                                             exc_type=type(err).__name__))
        return result


COMMANDS = {
    "remove": (control_auth.remove_auth, {"indices": [0]}, "removed entry"),
    "update": (control_auth.update_auth, {"index": 0}, "updated entry"),
    "add-role": (control_auth.add_role,
                 {"role": "new", "capabilities": ["c"]}, "added role"),
    "update-role": (control_auth.update_role,
                    {"role": "r", "capabilities": ["d"], "remove": False},
                    "updated role"),
    "remove-role": (control_auth.remove_role, {"role": "r"}, "removed role"),
    "add-group": (control_auth.add_group,
                  {"group": "new", "roles": ["r"]}, "added group"),
    "update-group": (control_auth.update_group,
                     {"group": "g", "roles": ["s"], "remove": False},
                     "updated group"),
    "remove-group": (control_auth.remove_group, {"group": "g"},
                     "removed group"),
    "rpc-add": (control_auth.add_agent_rpc_authorizations,
                {"pattern": ["x.n", "d"]}, None),
    "rpc-remove": (control_auth.remove_agent_rpc_authorizations,
                   {"pattern": ["x.m", "c"]}, None),
}


@pytest.fixture
def vctl(tmp_path, monkeypatch):
    auth_path = str(tmp_path / "auth.json")
    _seed(auth_path)
    platform = _Platform(auth_path)
    stdout, stderr = io.StringIO(), io.StringIO()
    monkeypatch.setattr(control_auth, "_stdout", stdout)
    monkeypatch.setattr(control_auth, "_stderr", stderr)
    monkeypatch.setattr(control_auth, "_ask_yes_no", lambda *args: True)
    monkeypatch.setattr(control_auth, "_ask_for_auth_fields",
                        lambda **entry: dict(entry, comments="edited"))
    # add() pauses a second after writing; nothing here waits on it.
    monkeypatch.setattr(gevent, "sleep", lambda *args, **kwargs: None)

    def run(command):
        func, fields, _ = COMMANDS[command]
        opts = SimpleNamespace(connection=SimpleNamespace(
            server=SimpleNamespace(vip=SimpleNamespace(rpc=platform))),
            **fields)
        return func(opts)

    return SimpleNamespace(run=run, auth_path=auth_path, stdout=stdout,
                           platform=platform)


@pytest.mark.auth
@pytest.mark.parametrize("command", sorted(COMMANDS))
def test_refused_change_is_reported_as_an_error(vctl, monkeypatch, command):
    monkeypatch.setattr(AuthFile, "lock_timeout", 0.2)
    before = _bytes(vctl.auth_path)

    with _hold_lock(vctl.auth_path):
        with pytest.raises(RemoteError) as raised:
            vctl.run(command)

    assert raised.value.exc_info["exc_type"] == "AuthFileLockTimeout"
    success = COMMANDS[command][2]
    if success:
        assert success not in vctl.stdout.getvalue()
    assert _bytes(vctl.auth_path) == before


@pytest.mark.auth
@pytest.mark.parametrize("command", sorted(COMMANDS))
def test_accepted_change_is_written_and_reported(vctl, command):
    before = _bytes(vctl.auth_path)

    vctl.run(command)

    assert _bytes(vctl.auth_path) != before
    success = COMMANDS[command][2]
    if success:
        assert success in vctl.stdout.getvalue()


class _Unanswered:
    """A call the platform never answers. get() with a timeout times out;
    get() without one would wait forever, so it fails the test instead."""

    def __init__(self, waits):
        self.waits = waits

    def get(self, block=True, timeout=None):
        self.waits.append(timeout)
        if timeout is None:
            pytest.fail("vctl waits forever for a change never answered")
        raise gevent.Timeout(timeout)


@pytest.mark.auth
@pytest.mark.parametrize("command", sorted(COMMANDS))
def test_change_never_answered_is_not_waited_on_forever(vctl, monkeypatch,
                                                        command):
    waits = []
    call = vctl.platform.call

    def answer_reads_only(peer, method, *args):
        if method == "auth_file.read":
            return call(peer, method, *args)
        return _Unanswered(waits)

    monkeypatch.setattr(vctl.platform, "call", answer_reads_only)
    before = _bytes(vctl.auth_path)

    with pytest.raises(gevent.Timeout):
        vctl.run(command)

    assert len(waits) == 1 and waits[0] is not None
    success = COMMANDS[command][2]
    if success:
        assert success not in vctl.stdout.getvalue()
    assert _bytes(vctl.auth_path) == before
