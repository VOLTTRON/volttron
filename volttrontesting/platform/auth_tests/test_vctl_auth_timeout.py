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
"""vctl auth commands bound each RPC wait by the command's --timeout, not a
fixed few seconds (#3367)."""

import copy
import io
from types import SimpleNamespace

import gevent
import gevent.event
import pytest

from volttron.platform.control import control_auth

# Longer than the old fixed 4 second wait, shorter than the --timeout used.
SLOW_REPLY = 5
OPTS_TIMEOUT = 6


class _Reply:
    """A reply that arrives after `delay` seconds, judged against the wait
    passed to get() without sleeping, so the tests run instantly."""

    def __init__(self, value, delay, waits):
        self.value = value
        self.delay = delay
        self.waits = waits

    def get(self, block=True, timeout=None):
        self.waits.append(timeout)
        if timeout is None:
            pytest.fail("vctl waits forever for a reply")
        if self.delay > timeout:
            raise gevent.Timeout(timeout)
        return self.value


class _Read:
    """An immediate reply to a read; the reads are not among the waits under
    test, so this accepts any get()."""

    def __init__(self, value):
        self.value = value

    def get(self, block=True, timeout=None):
        return self.value


class _Rpc:
    def __init__(self, delay):
        self.delay = delay
        self.waits = []
        self.methods = []

    def call(self, peer, method, *args):
        self.methods.append(method)
        value = [] if method.startswith("get_") else None
        return _Reply(value, self.delay, self.waits)


_ENTRY = {"user_id": "x", "identity": "x", "credentials": "c" * 43,
          "enabled": True, "groups": [], "roles": [], "capabilities": {},
          "comments": "", "domain": None, "address": None,
          "mechanism": "CURVE", "rpc_method_authorizations": {}}
_AUTH_FILE = {"allow_list": [_ENTRY], "deny_list": [],
              "groups": {"g": ["r"]}, "roles": {"r": ["c"]}}

COMMANDS = {
    "add": (control_auth.add_auth,
            {"domain": None, "address": None, "mechanism": "CURVE",
             "credentials": "c" * 43, "user_id": "u", "groups": "",
             "roles": "", "capabilities": "", "comments": "",
             "disabled": False, "add_known_host": False}),
    "approve": (control_auth.approve_remote, {"user_id": "u"}),
    "deny": (control_auth.deny_remote, {"user_id": "u"}),
    "delete": (control_auth.delete_remote, {"user_id": "u"}),
    "list-remotes": (control_auth.list_remotes, {"status": None}),
    "remove": (control_auth.remove_auth, {"indices": [0]}),
    "update": (control_auth.update_auth, {"index": 0}),
    "add-role": (control_auth.add_role,
                 {"role": "new", "capabilities": ["c"]}),
    "update-role": (control_auth.update_role,
                    {"role": "r", "capabilities": ["d"], "remove": False}),
    "remove-role": (control_auth.remove_role, {"role": "r"}),
    "add-group": (control_auth.add_group,
                  {"group": "new", "roles": ["r"]}),
    "update-group": (control_auth.update_group,
                     {"group": "g", "roles": ["s"], "remove": False}),
    "remove-group": (control_auth.remove_group, {"group": "g"}),
    "rpc-add": (control_auth.add_agent_rpc_authorizations,
                {"pattern": ["x.n", "d"]}),
    "rpc-remove": (control_auth.remove_agent_rpc_authorizations,
                   {"pattern": ["x.m", "c"]}),
}


@pytest.fixture
def vctl(monkeypatch):
    monkeypatch.setattr(control_auth, "_stdout", io.StringIO())
    monkeypatch.setattr(control_auth, "_stderr", io.StringIO())
    monkeypatch.setattr(control_auth, "_ask_yes_no", lambda *args: True)
    monkeypatch.setattr(control_auth, "_ask_for_auth_fields",
                        lambda **entry: dict(entry, comments="edited"))

    def run(command, delay, timeout=OPTS_TIMEOUT):
        func, fields = COMMANDS[command]
        rpc = _Rpc(delay)
        real_call = rpc.call

        def call(peer, method, *args):
            if method == "auth_file.read":
                return _Read(copy.deepcopy(_AUTH_FILE))
            return real_call(peer, method, *args)

        rpc.call = call
        opts = SimpleNamespace(
            connection=SimpleNamespace(
                server=SimpleNamespace(vip=SimpleNamespace(rpc=rpc))),
            timeout=timeout, **fields)
        return rpc, func, opts

    return run


@pytest.mark.auth
@pytest.mark.parametrize("command", sorted(COMMANDS))
def test_reply_slower_than_four_seconds_succeeds_within_timeout(vctl, command):
    rpc, func, opts = vctl(command, SLOW_REPLY)

    func(opts)

    assert rpc.waits, "no RPC wait was made"
    assert all(wait == OPTS_TIMEOUT for wait in rpc.waits)


@pytest.mark.auth
@pytest.mark.parametrize("command", sorted(COMMANDS))
def test_reply_slower_than_timeout_still_times_out(vctl, command):
    rpc, func, opts = vctl(command, OPTS_TIMEOUT + 1)

    with pytest.raises(gevent.Timeout):
        func(opts)

    assert rpc.waits == [OPTS_TIMEOUT]


@pytest.mark.auth
def test_real_slow_reply_succeeds_within_timeout(monkeypatch):
    """The same property with a real delayed reply instead of a simulated one."""
    stdout = io.StringIO()
    monkeypatch.setattr(control_auth, "_stdout", stdout)
    result = gevent.event.AsyncResult()
    gevent.spawn_later(4.5, result.set, None)
    rpc = SimpleNamespace(call=lambda *args: result)
    func, fields = COMMANDS["approve"]
    opts = SimpleNamespace(
        connection=SimpleNamespace(
            server=SimpleNamespace(vip=SimpleNamespace(rpc=rpc))),
        timeout=OPTS_TIMEOUT, **fields)

    try:
        func(opts)
    except gevent.Timeout:
        pytest.fail("vctl gave up before the reply arrived")

    assert result.ready()
