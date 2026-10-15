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
"""Empty user ids and the reserved user ids of platform principals in the
auth file: refused when added or updated, skipped when loaded, unless the
entry holds the key the platform itself holds for that identity."""

import json
import os

import pytest

from volttron.platform.agent import known_identities
from volttron.platform.agent.known_identities import (
    CONTROL,
    PLATFORM,
    VOLTTRON_CENTRAL,
)
from volttron.platform.auth import AuthEntry, AuthEntryInvalid, AuthFile
from volttron.platform.keystore import KeyStore
from volttrontesting.platform.auth_tests.conftest import (
    held_key, install_agent)

IN_PROCESS = {"platform.auth", "platform.health", "config.store", "control",
              "platform_web", "keydiscovery", "zmq.proxy.router", "aip"}
RESERVED = IN_PROCESS | {"control.connection", "platform", "volttron.central",
                         "vip.service"}

# Reserved ids the platform holds a key for: its own keypair, vctl's, and
# each service's keystore.
STARTUP_IDS = sorted({"platform", "control.connection"} | (IN_PROCESS - {"aip"}))
# Reserved ids no key is held for.
NO_KEY_IDS = sorted(RESERVED - set(STARTUP_IDS) - {VOLTTRON_CENTRAL})


@pytest.fixture
def vhome(tmp_path, monkeypatch):
    monkeypatch.setenv("VOLTTRON_HOME", str(tmp_path))
    for sub in ("agents", "keystores"):
        os.makedirs(tmp_path / sub)
    # AuthFile.add pauses a second after each write.
    monkeypatch.setattr("gevent.sleep", lambda *args, **kwargs: None)
    return tmp_path


@pytest.fixture
def auth_file(vhome):
    return AuthFile(str(vhome / "auth.json"))


def foreign_key(vhome):
    return KeyStore(str(vhome / "foreign" / "keystore.json")).public


def write_entries(auth_file, allow=(), deny=()):
    """Writes entries to the file as an operator editing it by hand would."""
    with open(auth_file.auth_file) as fil:
        data = json.load(fil)
    data["allow"] = list(allow)
    data["deny"] = list(deny)
    with open(auth_file.auth_file, "w") as fil:
        json.dump(data, fil)
    auth_file.load()


def raw_entry(user_id, credentials):
    return {"credentials": credentials, "user_id": user_id,
            "mechanism": "CURVE", "identity": user_id}


def allow_user_ids(auth_file):
    auth_file.load()
    return [entry.user_id for entry in auth_file.read_allow_entries()]


def test_reserved_sets_are_defined_once_in_known_identities():
    assert set(getattr(known_identities, "IN_PROCESS_IDENTITIES", ())) \
        == IN_PROCESS
    assert set(getattr(known_identities, "RESERVED_USER_IDS", ())) == RESERVED
    assert len(RESERVED) == 12


def test_empty_user_id_is_invalid(vhome):
    with pytest.raises(AuthEntryInvalid):
        AuthEntry(credentials=foreign_key(vhome), user_id="")


def test_missing_user_id_still_gets_a_generated_one(vhome):
    entry = AuthEntry(credentials=foreign_key(vhome))
    assert entry.user_id


def test_empty_user_id_is_skipped_at_load_with_a_warning(
        auth_file, vhome, caplog):
    keep = raw_entry("keep", foreign_key(vhome))
    empty = raw_entry("", held_key(CONTROL))
    write_entries(auth_file, allow=[keep, empty], deny=[empty])
    with caplog.at_level("WARNING"):
        assert allow_user_ids(auth_file) == ["keep"]
    assert auth_file.read_deny_entries() == []
    assert any(rec.levelname == "WARNING" and "invalid entry" in rec.message
               for rec in caplog.records)


@pytest.mark.parametrize("user_id", sorted(RESERVED))
def test_reserved_user_id_with_foreign_key_is_refused_on_add(
        auth_file, vhome, user_id):
    entry = AuthEntry(credentials=foreign_key(vhome), user_id=user_id,
                      identity=user_id, capabilities=["allow_auth_modifications"])
    with pytest.raises(AuthEntryInvalid, match=user_id.replace(".", r"\.")):
        auth_file.add(entry)
    assert allow_user_ids(auth_file) == []


@pytest.mark.parametrize("user_id", sorted(RESERVED))
def test_reserved_user_id_with_foreign_key_is_skipped_at_load(
        auth_file, vhome, user_id, caplog):
    keep = raw_entry("keep", held_key(CONTROL))
    bad = raw_entry(user_id, foreign_key(vhome))
    write_entries(auth_file, allow=[keep, bad], deny=[bad])
    with caplog.at_level("WARNING"):
        assert allow_user_ids(auth_file) == ["keep"]
    assert [e.user_id for e in auth_file.read_deny_entries()] == [user_id]
    assert any(rec.levelname == "WARNING" and user_id in rec.message
               for rec in caplog.records)


@pytest.mark.parametrize("user_id", NO_KEY_IDS)
def test_reserved_user_id_with_no_held_key_is_always_refused(
        auth_file, vhome, user_id):
    # A keystore existing under the id's name does not make it held.
    key = KeyStore(KeyStore.get_agent_keystore_path(user_id)).public
    with pytest.raises(AuthEntryInvalid):
        auth_file.add(AuthEntry(credentials=key, user_id=user_id))
    write_entries(auth_file, allow=[raw_entry(user_id, key)])
    assert allow_user_ids(auth_file) == []


@pytest.mark.parametrize("user_id", STARTUP_IDS)
def test_startup_entry_with_the_held_key_is_honored(auth_file, user_id):
    key = held_key(user_id)
    auth_file.add(AuthEntry(credentials=key, user_id=user_id,
                            identity=user_id), overwrite=True)
    assert allow_user_ids(auth_file) == [user_id]
    entry = auth_file.read_allow_entries()[0]
    assert str(entry.credentials) == key


def test_startup_entry_is_honored_again_at_load(auth_file):
    key = held_key(CONTROL)
    write_entries(auth_file, allow=[raw_entry(CONTROL, key)])
    assert allow_user_ids(auth_file) == [CONTROL]


def test_installed_volttron_central_with_its_own_key_is_honored(
        auth_file, vhome):
    key = install_agent(vhome, VOLTTRON_CENTRAL)
    auth_file.add(AuthEntry(credentials=key, user_id=VOLTTRON_CENTRAL,
                            identity=VOLTTRON_CENTRAL))
    assert allow_user_ids(auth_file) == [VOLTTRON_CENTRAL]


def test_volttron_central_entry_with_another_agents_key_is_refused(
        auth_file, vhome):
    install_agent(vhome, "other.agent")
    other_key = install_agent(vhome, "second.agent", uuid="4567")
    with pytest.raises(AuthEntryInvalid):
        auth_file.add(AuthEntry(credentials=other_key,
                                user_id=VOLTTRON_CENTRAL))
    assert allow_user_ids(auth_file) == []


def test_non_reserved_user_id_is_unaffected(auth_file, vhome):
    auth_file.add(AuthEntry(credentials=foreign_key(vhome), user_id="my.agent",
                            identity="my.agent"))
    assert allow_user_ids(auth_file) == ["my.agent"]


def test_overwrite_cannot_replace_an_entry_with_a_reserved_foreign_one(
        auth_file, vhome):
    key = foreign_key(vhome)
    auth_file.add(AuthEntry(credentials=key, user_id="my.agent"))
    with pytest.raises(AuthEntryInvalid):
        auth_file.add(AuthEntry(credentials=key, user_id=CONTROL,
                                capabilities=["allow_auth_modifications"]),
                      overwrite=True)
    assert allow_user_ids(auth_file) == ["my.agent"]


def test_update_by_index_refuses_a_reserved_foreign_entry(auth_file, vhome):
    key = foreign_key(vhome)
    auth_file.add(AuthEntry(credentials=key, user_id="my.agent"))
    with pytest.raises(AuthEntryInvalid):
        auth_file.update_by_index(
            AuthEntry(credentials=key, user_id=PLATFORM), 0)
    assert allow_user_ids(auth_file) == ["my.agent"]


def test_reserved_entry_with_regex_credentials_is_refused(auth_file):
    with pytest.raises(AuthEntryInvalid):
        auth_file.add(AuthEntry(credentials="/.*/", user_id=CONTROL))
    assert allow_user_ids(auth_file) == []


def test_reserved_entry_with_null_mechanism_is_refused(auth_file):
    with pytest.raises(AuthEntryInvalid):
        auth_file.add(AuthEntry(mechanism="NULL", user_id=CONTROL))
    assert allow_user_ids(auth_file) == []


def test_reserved_entry_with_null_mechanism_is_refused_even_with_the_held_key(
        auth_file):
    # A NULL entry matches every peer whatever its credentials say.
    entry = AuthEntry(mechanism="NULL", credentials=held_key(CONTROL),
                      user_id=CONTROL)
    with pytest.raises(AuthEntryInvalid):
        auth_file.add(entry)
    assert allow_user_ids(auth_file) == []
