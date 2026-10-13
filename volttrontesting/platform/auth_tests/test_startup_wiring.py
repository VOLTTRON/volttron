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
"""Startup must close the key directories before it authorizes any reserved
key. start_volttron_process is too large to run here, so these tests read
its source for the calls that matter."""

import ast
import importlib.util

import pytest


def startup_function():
    path = importlib.util.find_spec("volttron.platform.main").origin
    with open(path) as source:
        tree = ast.parse(source.read())
    for node in ast.walk(tree):
        if (isinstance(node, ast.FunctionDef)
                and node.name == "start_volttron_process"):
            return node
    raise AssertionError("start_volttron_process not found")


def calls(function, name):
    """Calls in the function to `name`, whether written bare (name(...)) or
    as an attribute (os.name(...))."""
    found = []
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        if isinstance(target, ast.Name) and target.id == name:
            found.append(node)
        elif isinstance(target, ast.Attribute) and target.attr == name:
            found.append(node)
    return found


def test_startup_tightens_the_home_and_the_key_directories():
    function = startup_function()
    assert len(calls(function, "tighten_volttron_home")) == 1
    assert len(calls(function, "tighten_keystore_dirs")) == 1


def test_the_tightening_runs_after_setup_and_before_any_key_is_authorized():
    function = startup_function()
    setup = [c.lineno for c in calls(function, "setup")
             if isinstance(c.func, ast.Attribute)
             and ast.dump(c.func.value).endswith("attr='aip', ctx=Load())")]
    assert len(setup) == 1
    first_auth_file = min(c.lineno for c in calls(function, "AuthFile"))
    for name in ("tighten_volttron_home", "tighten_keystore_dirs"):
        line = calls(function, name)[0].lineno
        assert setup[0] < line < first_auth_file, name


def test_the_control_connection_key_directory_is_made_by_the_owner_only_helper():
    function = startup_function()
    made = calls(function, "create_keystore_dir")
    assert len(made) == 1
    assert "control_conn_path" in ast.dump(made[0])
    assert calls(function, "makedirs") == []


def main_function():
    path = importlib.util.find_spec("volttron.platform.main").origin
    with open(path) as source:
        tree = ast.parse(source.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return node
    raise AssertionError("main not found")


def test_main_resolves_the_home_before_it_reads_the_config_or_parses():
    function = main_function()
    resolved = calls(function, "resolve_volttron_home")
    assert len(resolved) == 1
    for name in ("exists", "parse_args", "ArgumentParser"):
        assert resolved[0].lineno < min(
            c.lineno for c in calls(function, name)), name
    assert calls(function, "normpath") == []


def test_startup_reports_a_resolved_home_before_it_tightens_anything():
    function = startup_function()
    reported = calls(function, "report_resolved_home")
    assert len(reported) == 1
    tightened = calls(function, "tighten_volttron_home")[0]
    assert reported[0].lineno < tightened.lineno


def test_a_home_owned_by_another_user_logs_and_exits_with_status_1():
    function = startup_function()
    tightened = calls(function, "tighten_volttron_home")[0]
    guards = [node for node in ast.walk(function)
              if isinstance(node, ast.Try) and any(
                  tightened is inner for stmt in node.body
                  for inner in ast.walk(stmt))]
    assert len(guards) == 1
    handlers = [h for h in guards[0].handlers
                if isinstance(h.type, ast.Name)
                and h.type.id == "HomeOwnedByAnotherUser"]
    assert len(handlers) == 1
    handler = handlers[0]
    assert len(calls(handler, "error")) == 1
    exits = calls(handler, "exit")
    assert len(exits) == 1
    assert [arg.value for arg in exits[0].args] == [1]


def test_main_hands_the_requested_home_to_startup_for_the_log_line():
    function = main_function()
    defaults = [c for c in calls(function, "set_defaults")]
    assert len(defaults) == 1
    given = {k.arg: ast.dump(k.value) for k in defaults[0].keywords}
    assert given["requested_home"] == ast.dump(
        ast.Name(id="requested_home", ctx=ast.Load()))
    assert given["volttron_home"] == ast.dump(
        ast.Name(id="volttron_home", ctx=ast.Load()))


def test_the_report_gets_the_requested_home_first_and_the_resolved_home_second():
    function = startup_function()
    call = calls(function, "report_resolved_home")[0]
    args = [ast.unparse(a) for a in call.args]
    assert len(args) == 2
    assert "requested_home" in args[0]
    assert args[1] == "opts.volttron_home"
