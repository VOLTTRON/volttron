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
