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
"""The router's auth setting is required and follows the same option as the
platform agents' auth setting."""

import ast
import importlib.util

import pytest
import zmq

from volttron.platform import main as platform_main

ROUTER_CLASSES = ("Router", "GreenRouter")


@pytest.fixture
def context():
    ctx = zmq.Context()
    yield ctx
    ctx.term()


@pytest.mark.parametrize("router_class", ROUTER_CLASSES)
def test_router_without_enable_auth_fails_at_construction(
        router_class, context):
    with pytest.raises(TypeError, match="enable_auth"):
        getattr(platform_main, router_class)(
            "ipc://@router-test", context=context)


@pytest.mark.parametrize("router_class", ROUTER_CLASSES)
@pytest.mark.parametrize("enable_auth", [True, False])
def test_router_keeps_the_enable_auth_it_is_given(
        router_class, enable_auth, context):
    router = getattr(platform_main, router_class)(
        "ipc://@router-test", context=context, enable_auth=enable_auth)
    assert router.enable_auth is enable_auth


def enable_auth_keywords():
    """Lists (call name, source of the enable_auth argument, line) for every
    call in main.py that passes one, except a constructor handing its own
    parameter to its parent class."""
    path = importlib.util.find_spec("volttron.platform.main").origin
    with open(path) as source:
        tree = ast.parse(source.read())
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg == "enable_auth":
                name = ast.unparse(node.func)
                if name.endswith(".__init__"):
                    continue
                found.append((name, ast.unparse(keyword.value), node.lineno))
    return found


def test_every_enable_auth_in_main_comes_from_the_allow_auth_option():
    found = enable_auth_keywords()
    names = {name for name, _, _ in found}
    # Denominator: the routers and the agents main.py starts.
    assert set(ROUTER_CLASSES) <= names
    assert len(found) >= 9, found
    wrong = [item for item in found if item[1] != "opts.allow_auth"]
    assert wrong == []
