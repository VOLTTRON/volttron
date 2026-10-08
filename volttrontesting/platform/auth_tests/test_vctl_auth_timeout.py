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
import sys
from types import SimpleNamespace

import gevent
import gevent.event
import pytest

from volttron.platform.control import control_auth, control_parser

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
    """An immediate reply to a read; this accepts any get(), so the wait
    passed to it is not recorded."""

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

# Commands whose only RPC is the auth file read.
READ_ONLY = {
    "list": (control_auth.list_auth, {}),
    "list-roles": (control_auth.list_roles, {}),
    "list-groups": (control_auth.list_groups, {}),
}


@pytest.fixture
def vctl(monkeypatch):
    monkeypatch.setattr(control_auth, "_stdout", io.StringIO())
    monkeypatch.setattr(control_auth, "_stderr", io.StringIO())
    monkeypatch.setattr(control_auth, "_ask_yes_no", lambda *args: True)
    monkeypatch.setattr(control_auth, "_ask_for_auth_fields",
                        lambda **entry: dict(entry, comments="edited"))

    def run(command, delay, timeout=OPTS_TIMEOUT, read_delay=None):
        func, fields = {**COMMANDS, **READ_ONLY}[command]
        rpc = _Rpc(delay)
        real_call = rpc.call

        def call(peer, method, *args):
            if method == "auth_file.read":
                value = copy.deepcopy(_AUTH_FILE)
                if read_delay is None:
                    return _Read(value)
                return _Reply(value, read_delay, rpc.waits)
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


LIST_REMOTES_RPCS = ["get_approved_authorizations",
                     "get_denied_authorizations",
                     "get_pending_authorizations"]


@pytest.mark.auth
@pytest.mark.parametrize("slow", LIST_REMOTES_RPCS)
def test_list_remotes_each_wait_times_out(slow):
    waits = []

    def call(peer, method, *args):
        delay = OPTS_TIMEOUT + 1 if method == slow else 0
        return _Reply([], delay, waits)

    opts = SimpleNamespace(
        connection=SimpleNamespace(
            server=SimpleNamespace(vip=SimpleNamespace(
                rpc=SimpleNamespace(call=call)))),
        timeout=OPTS_TIMEOUT, status=None)

    with pytest.raises(gevent.Timeout):
        control_auth.list_remotes(opts)

    assert waits == [OPTS_TIMEOUT] * (LIST_REMOTES_RPCS.index(slow) + 1)


READ_COMMANDS = ["list", "list-roles", "list-groups", "remove", "update",
                 "add-role", "update-role", "remove-role", "add-group",
                 "update-group", "remove-group"]


@pytest.mark.auth
@pytest.mark.parametrize("command", READ_COMMANDS)
def test_slow_auth_file_read_succeeds_within_timeout(vctl, command):
    rpc, func, opts = vctl(command, 0, read_delay=SLOW_REPLY)

    func(opts)

    assert rpc.waits[0] == OPTS_TIMEOUT
    assert all(wait == OPTS_TIMEOUT for wait in rpc.waits)


@pytest.mark.auth
@pytest.mark.parametrize("command", READ_COMMANDS)
def test_auth_file_read_slower_than_timeout_times_out(vctl, command):
    rpc, func, opts = vctl(command, 0, read_delay=OPTS_TIMEOUT + 1)

    with pytest.raises(gevent.Timeout):
        func(opts)

    assert rpc.waits == [OPTS_TIMEOUT]


@pytest.mark.auth
def test_real_slow_reply_succeeds_within_timeout(monkeypatch):
    """The same property with a real delayed reply instead of a simulated one."""
    stdout = io.StringIO()
    monkeypatch.setattr(control_auth, "_stdout", stdout)
    result = gevent.event.AsyncResult()
    # spawn_later times from the loop's cached clock, which is stale unless
    # refreshed, and a stale clock makes the reply arrive early.
    gevent.get_hub().loop.update_now()
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


@pytest.mark.auth
def test_main_reports_timed_out_auth_command_and_exits_75(monkeypatch,
                                                           tmp_path):
    """Stubbed: the home directory, the agent install platform, the
    running check, the connection and the log setup. The reply is a real
    AsyncResult that is never set, and the parser, the --timeout option and
    the timeout handling in main() run unstubbed."""
    stderr = io.StringIO()
    never = gevent.event.AsyncResult()
    rpc = SimpleNamespace(call=lambda *args: never)
    connection = SimpleNamespace(
        server=SimpleNamespace(vip=SimpleNamespace(rpc=rpc)),
        kill=lambda: None)
    monkeypatch.setattr(control_parser, "get_home", lambda: str(tmp_path))
    monkeypatch.setattr(control_parser, "_stderr", stderr)
    monkeypatch.setattr(control_parser, "log_to_file", lambda *a, **k: None)
    monkeypatch.setattr(control_parser.utils, "is_volttron_running",
                        lambda home: True)
    monkeypatch.setattr(control_parser, "ControlConnection",
                        lambda address: connection)
    monkeypatch.setattr(
        control_parser.aipmod, "AIPplatform",
        lambda opts: SimpleNamespace(setup=lambda: None))
    monkeypatch.setenv("SKIP_VOLTTRON_CONFIG", "1")
    monkeypatch.setattr(
        sys, "argv",
        ["vctl", "--timeout", "0.2", "auth", "remote", "approve", "u"])

    assert control_parser.main() == 75
    assert stderr.getvalue() == "auth: operation timed out\n"
