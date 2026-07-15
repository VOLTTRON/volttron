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

"""Regression tests guarding the import path that reaches the auth package.

Importing volttron.platform.auth pulls in volttron.platform.messaging.topics,
which builds AGENT_PING at module import time from the machine hostname. That
construction previously used platform.uname()[1], and uname() shells out to a
subprocess to populate its processor field. Under gevent's monkey-patched os
that subprocess call deadlocks at import time on newer CPython, hanging every
importer of the auth package. These tests lock in the behavior-preserving fix
(platform.node(), no subprocess) so the regression cannot return silently.
"""

import os
import platform

import pytest


@pytest.mark.auth
def test_auth_package_imports_without_hanging():
    """The auth package must import cleanly.

    A bare import is the smallest reproduction of the deadlock: the hang
    occurred while executing volttron.platform.messaging.topics during the
    auth import chain, so a successful import is the assertion.
    """
    import volttron.platform.auth as auth

    for name in ("AuthService", "AuthEntry", "AuthFile"):
        assert hasattr(auth, name), f"auth package is missing {name}"


@pytest.mark.auth
def test_agent_ping_topic_carries_node_and_pid():
    """AGENT_PING renders agent/ping/<node>/<pid>/<cookie> with real values.

    Asserts the field values, not just that rendering does not crash: the
    hostname segment must equal platform.node() and the pid segment must equal
    the current process id, so the fix cannot regress into emitting an empty or
    wrong hostname.
    """
    from volttron.platform.messaging import topics

    rendered = topics.AGENT_PING(cookie="test-cookie")

    expected = f"agent/ping/{platform.node()}/{os.getpid()}/test-cookie"
    assert rendered == expected

    segments = rendered.split("/")
    assert segments[0] == "agent"
    assert segments[1] == "ping"
    assert segments[2] == platform.node()
    assert segments[2] != "", "hostname segment must not be empty"
    assert segments[3] == str(os.getpid())
    assert segments[4] == "test-cookie"
