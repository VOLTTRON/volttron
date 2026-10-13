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
"""A user id the platform reserves is honored only for a key file the platform
itself could have written, and a key that cannot be read never costs the
auth file an entry."""

import json
import logging
import os
from types import SimpleNamespace

import pytest

from volttron.platform.agent.known_identities import (
    CONTROL,
    PLATFORM,
    VOLTTRON_CENTRAL,
)
from volttron.platform.auth import AuthEntry, AuthEntryInvalid, AuthFile
from volttron.platform.auth import reserved_user_ids
from volttron.platform.keystore import KeyStore
from volttrontesting.platform.auth_tests.conftest import (
    held_key, install_agent)


@pytest.fixture
def vhome(tmp_path, monkeypatch):
    monkeypatch.setenv("VOLTTRON_HOME", str(tmp_path))
    for sub in ("agents", "keystores"):
        os.makedirs(tmp_path / sub)
    monkeypatch.setattr("gevent.sleep", lambda *args, **kwargs: None)
    return tmp_path


@pytest.fixture
def auth_file(vhome):
    return AuthFile(str(vhome / "auth.json"))


def foreign_key(vhome, name="foreign"):
    return KeyStore(str(vhome / name / "keystore.json")).public


def keystore_file(identity):
    return KeyStore.get_agent_keystore_path(identity)


def raw_entry(user_id, credentials):
    return {"credentials": credentials, "user_id": user_id,
            "mechanism": "CURVE", "identity": user_id}


def write_entries(auth_file, allow=(), deny=()):
    with open(auth_file.auth_file) as fil:
        data = json.load(fil)
    data["allow"] = list(allow)
    data["deny"] = list(deny)
    with open(auth_file.auth_file, "w") as fil:
        json.dump(data, fil)
    auth_file.load()


def file_user_ids(auth_file, section):
    with open(auth_file.auth_file) as fil:
        return [entry["user_id"] for entry in json.load(fil)[section]]


# ---- the key file must be one the platform could have written ----

def test_a_key_file_of_the_platform_is_accepted(vhome):
    key = held_key(CONTROL)
    assert reserved_user_ids.platform_held_keys(CONTROL) == {key}


def test_the_platforms_own_key_file_is_accepted(vhome):
    key = KeyStore().public
    assert reserved_user_ids.platform_held_keys(PLATFORM) == {key}


def test_a_symlinked_key_file_is_refused(vhome):
    key = held_key(CONTROL)
    real = vhome / "real-keystore.json"
    os.replace(keystore_file(CONTROL), real)
    os.symlink(real, keystore_file(CONTROL))
    assert json.load(open(keystore_file(CONTROL)))["public"] == key
    assert reserved_user_ids.platform_held_keys(CONTROL) == frozenset()


def test_a_key_file_that_is_not_a_regular_file_is_refused(vhome):
    held_key(CONTROL)
    os.remove(keystore_file(CONTROL))
    os.mkdir(keystore_file(CONTROL))
    assert reserved_user_ids.platform_held_keys(CONTROL) == frozenset()


def test_a_pipe_in_place_of_a_key_file_is_refused(vhome):
    key = held_key(CONTROL)
    path = keystore_file(CONTROL)
    os.remove(path)
    os.mkfifo(path)
    reader = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    writer = os.open(path, os.O_WRONLY)
    try:
        os.write(writer, json.dumps({"public": key}).encode())
        assert reserved_user_ids.platform_held_keys(CONTROL) == frozenset()
    finally:
        os.close(writer)
        os.close(reader)


def test_a_key_file_owned_by_another_user_is_refused(vhome, monkeypatch):
    held_key(CONTROL)
    monkeypatch.setattr(os, "getuid", lambda: os.stat(vhome).st_uid + 1)
    assert reserved_user_ids.platform_held_keys(CONTROL) == frozenset()


def _as_owned_by_another_user(real):
    def wrapper(*args, **kwargs):
        info = real(*args, **kwargs)
        return SimpleNamespace(st_mode=info.st_mode, st_uid=info.st_uid + 1)
    return wrapper


def test_a_key_file_owned_by_another_user_in_our_directory_is_refused(
        vhome, monkeypatch):
    held_key(CONTROL)
    monkeypatch.setattr(os, "fstat", _as_owned_by_another_user(os.fstat))
    assert reserved_user_ids.platform_held_keys(CONTROL) == frozenset()


def test_a_key_directory_owned_by_another_user_is_refused(vhome, monkeypatch):
    held_key(CONTROL)
    monkeypatch.setattr(os, "lstat", _as_owned_by_another_user(os.lstat))
    assert reserved_user_ids.platform_held_keys(CONTROL) == frozenset()


def test_a_symlinked_key_directory_is_refused(vhome):
    held_key(CONTROL)
    real = vhome / "real-keystores-control"
    os.replace(os.path.dirname(keystore_file(CONTROL)), real)
    os.symlink(real, os.path.dirname(keystore_file(CONTROL)))
    assert reserved_user_ids.platform_held_keys(CONTROL) == frozenset()


@pytest.mark.parametrize("mode", [0o620, 0o602, 0o660, 0o666])
def test_a_group_or_world_writable_key_file_is_refused(vhome, mode):
    held_key(CONTROL)
    os.chmod(keystore_file(CONTROL), mode)
    assert reserved_user_ids.platform_held_keys(CONTROL) == frozenset()


@pytest.mark.parametrize("mode", [0o770, 0o707, 0o777])
def test_a_group_or_world_writable_key_directory_is_refused(vhome, mode):
    held_key(CONTROL)
    os.chmod(os.path.dirname(keystore_file(CONTROL)), mode)
    assert reserved_user_ids.platform_held_keys(CONTROL) == frozenset()


def test_a_key_file_readable_by_others_but_not_writable_is_accepted(vhome):
    key = held_key(CONTROL)
    os.chmod(keystore_file(CONTROL), 0o644)
    assert reserved_user_ids.platform_held_keys(CONTROL) == {key}


def test_an_entry_for_a_refused_key_file_is_refused(auth_file, vhome):
    key = held_key(CONTROL)
    os.chmod(keystore_file(CONTROL), 0o666)
    with pytest.raises(AuthEntryInvalid):
        auth_file.add(AuthEntry(credentials=key, user_id=CONTROL,
                                identity=CONTROL))


# ---- a deny entry never grants, so it is never dropped ----

def test_a_deny_entry_with_a_reserved_id_is_kept(auth_file, vhome):
    bad = raw_entry(CONTROL, foreign_key(vhome))
    write_entries(auth_file, deny=[bad])
    assert [e.user_id for e in auth_file.read_deny_entries()] == [CONTROL]


def test_a_reserved_allow_entry_is_still_refused_beside_a_kept_deny_entry(
        auth_file, vhome):
    bad = raw_entry(CONTROL, foreign_key(vhome))
    write_entries(auth_file, allow=[bad], deny=[bad])
    assert auth_file.read_allow_entries() == []
    assert len(auth_file.read_deny_entries()) == 1


# ---- an entry hidden by a failed key read is not lost on write ----

MUTATORS = {
    "add": lambda af, vhome: af.add(AuthEntry(
        credentials=foreign_key(vhome, "extra"), user_id="other", identity="other")),
    "remove_by_index": lambda af, vhome: af.remove_by_index(0),
    "remove_by_credentials": lambda af, vhome: af.remove_by_credentials(
        "no-such-credentials"),
    "update_by_index": lambda af, vhome: af.update_by_index(AuthEntry(
        credentials=foreign_key(vhome, "extra"), user_id="replacement"), 0),
    "set_groups": lambda af, vhome: af.set_groups({"g": ["c"]}),
    "set_roles": lambda af, vhome: af.set_roles({"r": ["g"]}),
    "approve_deny_credential": lambda af, vhome:
        af.approve_deny_credential("missing"),
    "modify_rpc_method_authorizations": lambda af, vhome:
        af.modify_rpc_method_authorizations(
            "visible", lambda current: {"m": ["cap"]}),
}


@pytest.mark.parametrize("name", sorted(MUTATORS))
def test_a_change_during_a_failing_key_read_keeps_the_reserved_entries(
        auth_file, vhome, monkeypatch, name):
    key = held_key(CONTROL)
    visible = AuthEntry(credentials=foreign_key(vhome), user_id="visible",
                        identity="visible")
    auth_file.add(visible)
    auth_file.add(AuthEntry(credentials=key, user_id=CONTROL,
                            identity=CONTROL))
    with open(auth_file.auth_file) as fil:
        denied = json.load(fil)
    denied["deny"] = [raw_entry(CONTROL, foreign_key(vhome))]
    with open(auth_file.auth_file, "w") as fil:
        json.dump(denied, fil)
    auth_file.load()

    with monkeypatch.context() as patch:
        patch.setattr(reserved_user_ids, "platform_held_keys",
                      lambda user_id: frozenset())
        MUTATORS[name](auth_file, vhome)

    assert CONTROL in file_user_ids(auth_file, "allow")
    assert file_user_ids(auth_file, "deny") == [CONTROL]
    auth_file.load()
    assert CONTROL in [e.user_id for e in auth_file.read_allow_entries()]


def test_visible_indexes_ignore_entries_hidden_by_a_failed_key_read(
        auth_file, vhome, monkeypatch):
    key = held_key(CONTROL)
    first = AuthEntry(credentials=key, user_id=CONTROL, identity=CONTROL)
    second = AuthEntry(credentials=foreign_key(vhome, "extra"), user_id="second",
                       identity="second")
    auth_file.add(first)
    auth_file.add(second)
    with monkeypatch.context() as patch:
        patch.setattr(reserved_user_ids, "platform_held_keys",
                      lambda user_id: frozenset())
        auth_file.load()
        assert [e.user_id for e in auth_file.read_allow_entries()] \
            == ["second"]
        auth_file.remove_by_index(0)

    assert file_user_ids(auth_file, "allow") == [CONTROL]


def test_a_write_with_no_read_of_its_own_adds_nothing_back(
        auth_file, vhome, monkeypatch):
    key = held_key(CONTROL)
    auth_file.add(AuthEntry(credentials=key, user_id=CONTROL,
                            identity=CONTROL))
    with monkeypatch.context() as patch:
        patch.setattr(reserved_user_ids, "platform_held_keys",
                      lambda user_id: frozenset())
        auth_file.read_allow_entries()
    with auth_file._transaction():
        auth_file._write([], [], {}, {})
    assert file_user_ids(auth_file, "allow") == []


def test_an_entry_removed_on_purpose_is_gone(auth_file, vhome):
    key = held_key(CONTROL)
    auth_file.add(AuthEntry(credentials=key, user_id=CONTROL,
                            identity=CONTROL))
    auth_file.remove_by_index(0)
    assert file_user_ids(auth_file, "allow") == []


# ---- volttron.central's key is read from its resolved install path ----

def test_volttron_central_with_two_install_dirs_is_not_trusted(vhome):
    agent_dir = vhome / "agents" / "0123"
    install_agent(vhome, VOLTTRON_CENTRAL)
    stray = agent_dir / "stray" / "stray.dist-info"
    os.makedirs(stray)
    KeyStore(str(stray / "keystore.json"))
    assert reserved_user_ids.platform_held_keys(VOLTTRON_CENTRAL) \
        == frozenset()


def test_volttron_central_key_comes_from_the_one_install_dir(vhome):
    key = install_agent(vhome, VOLTTRON_CENTRAL)
    other = install_agent(vhome, "other.agent", uuid="4567")
    assert reserved_user_ids.platform_held_keys(VOLTTRON_CENTRAL) == {key}
    assert other not in reserved_user_ids.platform_held_keys(VOLTTRON_CENTRAL)


def test_volttron_central_key_file_is_checked_like_any_platform_key(vhome):
    key = install_agent(vhome, VOLTTRON_CENTRAL)
    path = vhome / "agents" / "0123" / "pkg" / "pkg.dist-info" / "keystore.json"
    os.chmod(path, 0o666)
    assert key not in reserved_user_ids.platform_held_keys(VOLTTRON_CENTRAL)


# ---- every refusal says why ----

def reasons(caplog):
    return [r.getMessage() for r in caplog.records
            if r.levelno >= logging.WARNING]


def test_a_missing_service_key_file_says_so(vhome, caplog):
    with caplog.at_level(logging.WARNING, logger=reserved_user_ids.__name__):
        assert reserved_user_ids.platform_held_keys(CONTROL) == frozenset()
    assert any(keystore_file(CONTROL) in r and "does not exist" in r
               for r in reasons(caplog))


def test_an_unreadable_agents_folder_says_why(vhome, caplog, monkeypatch):
    real = os.listdir

    def listdir(path):
        if str(path).startswith(str(vhome / "agents" / "0123")):
            raise PermissionError(13, "denied", str(path))
        return real(path)

    install_agent(vhome, VOLTTRON_CENTRAL)
    monkeypatch.setattr(os, "listdir", listdir)
    with caplog.at_level(logging.WARNING, logger=reserved_user_ids.__name__):
        assert reserved_user_ids.platform_held_keys(
            VOLTTRON_CENTRAL) == frozenset()
    assert any("0123" in r and "denied" in r for r in reasons(caplog))


def test_an_agent_folder_with_two_packages_says_why(vhome, caplog):
    install_agent(vhome, VOLTTRON_CENTRAL)
    os.makedirs(vhome / "agents" / "0123" / "pkg2" / "pkg2.dist-info")
    with caplog.at_level(logging.WARNING, logger=reserved_user_ids.__name__):
        assert reserved_user_ids.platform_held_keys(
            VOLTTRON_CENTRAL) == frozenset()
    assert any("0123" in r and "2" in r and "one" in r
               for r in reasons(caplog))


def test_an_agent_folder_with_no_identity_file_says_why(vhome, caplog):
    install_agent(vhome, VOLTTRON_CENTRAL)
    os.remove(vhome / "agents" / "0123" / "IDENTITY")
    with caplog.at_level(logging.WARNING, logger=reserved_user_ids.__name__):
        assert reserved_user_ids.platform_held_keys(
            VOLTTRON_CENTRAL) == frozenset()
    assert any("IDENTITY" in r and "0123" in r for r in reasons(caplog))


def test_the_refusal_names_whether_the_platform_holds_no_key(vhome):
    entry = AuthEntry(credentials=foreign_key(vhome), user_id=CONTROL,
                      identity=CONTROL)
    with pytest.raises(reserved_user_ids.ReservedUserIdRefused,
                       match="holds no key"):
        reserved_user_ids.check_reserved_user_id(entry)


def test_the_refusal_names_a_key_that_does_not_match(vhome):
    held_key(CONTROL)
    entry = AuthEntry(credentials=foreign_key(vhome), user_id=CONTROL,
                      identity=CONTROL)
    with pytest.raises(reserved_user_ids.ReservedUserIdRefused) as raised:
        reserved_user_ids.check_reserved_user_id(entry)
    assert "different key" in str(raised.value)
    assert "holds no key" not in str(raised.value)
