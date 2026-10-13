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
"""An agent accepts a capabilities update only from the auth service itself,
as authenticated by the router."""

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from volttron.platform.agent.known_identities import AUTH
from volttron.platform.vip.agent.subsystems import auth as auth_subsystem

CURRENT = {"agent.one": ["cap"]}
UPDATE = {"agent.two": ["other"]}


def make_subsystem(peer, user):
    rpc = MagicMock()
    rpc.context.vip_message = SimpleNamespace(peer=peer, user=user)
    subsystem = auth_subsystem.Auth(SimpleNamespace(), MagicMock(), rpc)
    subsystem._user_to_capabilities = dict(CURRENT)
    subsystem._dirty = False
    return subsystem


def test_an_update_from_the_auth_service_is_accepted():
    subsystem = make_subsystem(peer=AUTH, user=AUTH)
    subsystem._update_capabilities(UPDATE)
    assert subsystem._user_to_capabilities == UPDATE
    assert subsystem._dirty is True


@pytest.mark.parametrize("user", ["", "some.agent", "Auth"])
def test_an_update_whose_user_is_not_auth_is_refused(user):
    subsystem = make_subsystem(peer=AUTH, user=user)
    subsystem._update_capabilities(UPDATE)
    assert subsystem._user_to_capabilities == CURRENT
    assert subsystem._dirty is False


def test_an_update_from_another_peer_is_refused():
    subsystem = make_subsystem(peer="some.agent", user="some.agent")
    subsystem._update_capabilities(UPDATE)
    assert subsystem._user_to_capabilities == CURRENT
    assert subsystem._dirty is False


def test_a_refused_update_is_logged_with_its_sender(caplog):
    subsystem = make_subsystem(peer="some.agent", user="some.user")
    with caplog.at_level(logging.WARNING, logger=auth_subsystem.__name__):
        subsystem._update_capabilities(UPDATE)
    warnings = [r.getMessage() for r in caplog.records
                if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "some.agent" in warnings[0]
    assert "some.user" in warnings[0]


def test_an_accepted_update_logs_no_warning(caplog):
    subsystem = make_subsystem(peer=AUTH, user=AUTH)
    with caplog.at_level(logging.WARNING, logger=auth_subsystem.__name__):
        subsystem._update_capabilities(UPDATE)
    assert caplog.records == []


def refusals(caplog):
    return [r.getMessage() for r in caplog.records
            if r.levelno == logging.WARNING]


def test_repeated_refusals_from_one_peer_log_one_warning(caplog):
    subsystem = make_subsystem(peer="some.agent", user="some.user")
    with caplog.at_level(logging.WARNING, logger=auth_subsystem.__name__):
        for _ in range(5):
            subsystem._update_capabilities(UPDATE)
    assert len(refusals(caplog)) == 1


def test_a_second_peer_gets_its_own_refusal_warning(caplog):
    subsystem = make_subsystem(peer="some.agent", user="some.user")
    with caplog.at_level(logging.WARNING, logger=auth_subsystem.__name__):
        subsystem._update_capabilities(UPDATE)
        subsystem._rpc().context.vip_message = SimpleNamespace(
            peer="other.agent", user="other.user")
        subsystem._update_capabilities(UPDATE)
    warnings = refusals(caplog)
    assert len(warnings) == 2 and "other.agent" in warnings[1]


def test_the_refusal_log_is_capped_with_one_suppressed_line(
        caplog, monkeypatch):
    monkeypatch.setattr(auth_subsystem, "_REFUSED_PEERS_LIMIT", 2)
    subsystem = make_subsystem(peer="p0", user="u")
    with caplog.at_level(logging.WARNING, logger=auth_subsystem.__name__):
        for number in range(6):
            subsystem._rpc().context.vip_message = SimpleNamespace(
                peer="p{}".format(number), user="u")
            subsystem._update_capabilities(UPDATE)
    warnings = refusals(caplog)
    assert len(warnings) == 3
    assert "suppressed" in warnings[2]
    assert subsystem._user_to_capabilities == CURRENT
