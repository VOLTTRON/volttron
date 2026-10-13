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
"""Agent isolation mode runs with umask 007. The key directories the platform
creates must still be closed to group writes, or every reserved key is
refused and startup aborts."""

import logging
import os
import stat
from types import SimpleNamespace

import pytest

from volttron.platform import aip as aip_module
from volttron.platform.agent.known_identities import (
    CONTROL_CONNECTION,
    VOLTTRON_CENTRAL,
)
from volttron.platform.auth import AuthEntry, AuthFile
from volttron.platform.auth import reserved_user_ids
from volttron.platform.keystore import (KeyStore, create_keystore_dir,
                                        tighten_keystore_dirs)
from volttrontesting.platform.auth_tests.conftest import install_agent


def mode_of(path):
    return stat.S_IMODE(os.lstat(path).st_mode)


@pytest.fixture
def isolation_umask():
    previous = os.umask(0o007)
    yield
    os.umask(previous)


@pytest.fixture
def vhome(tmp_path, monkeypatch):
    monkeypatch.setenv("VOLTTRON_HOME", str(tmp_path))
    monkeypatch.setattr("gevent.sleep", lambda *args, **kwargs: None)
    return tmp_path


def control_dirs(vhome):
    keystores = str(vhome / "keystores")
    return keystores, os.path.join(keystores, CONTROL_CONNECTION)


def make_dirs(vhome, root_mode, child_mode):
    """A keystores/ tree with a held control key, as an older release or a
    loose umask left it."""
    root, child = control_dirs(vhome)
    os.makedirs(child)
    key = KeyStore(KeyStore.get_agent_keystore_path(CONTROL_CONNECTION)).public
    os.chmod(child, child_mode)
    os.chmod(root, root_mode)
    return key


# ---- creation ----

def test_key_directories_are_created_closed_to_group_under_umask_007(
        vhome, isolation_umask):
    keystore = KeyStore(KeyStore.get_agent_keystore_path(CONTROL_CONNECTION))
    root, child = control_dirs(vhome)
    assert mode_of(root) & 0o022 == 0
    assert mode_of(child) & 0o022 == 0
    assert reserved_user_ids.platform_held_keys(CONTROL_CONNECTION) == {
        keystore.public}
    AuthFile(str(vhome / "auth.json")).add(AuthEntry(
        credentials=keystore.public, user_id=CONTROL_CONNECTION,
        identity=CONTROL_CONNECTION))


def test_key_directories_are_owner_only(vhome, isolation_umask):
    KeyStore(KeyStore.get_agent_keystore_path(CONTROL_CONNECTION))
    root, child = control_dirs(vhome)
    assert mode_of(root) == 0o700
    assert mode_of(child) == 0o700


@pytest.mark.parametrize("umask", [0o000, 0o077, 0o277])
def test_key_directories_are_owner_only_whatever_the_umask(vhome, umask):
    previous = os.umask(umask)
    try:
        create_keystore_dir(str(vhome / "keystores" / "some.service"))
    finally:
        os.umask(previous)
    assert mode_of(vhome / "keystores") == 0o700
    assert mode_of(vhome / "keystores" / "some.service") == 0o700


# ---- tightening at startup ----

def test_a_group_writable_key_directory_is_tightened_and_accepted(vhome):
    key = make_dirs(vhome, 0o770, 0o770)
    assert reserved_user_ids.platform_held_keys(
        CONTROL_CONNECTION) == frozenset()
    tighten_keystore_dirs()
    root, child = control_dirs(vhome)
    assert mode_of(root) == 0o700
    assert mode_of(child) == 0o700
    assert reserved_user_ids.platform_held_keys(CONTROL_CONNECTION) == {key}


def test_a_key_directory_owned_by_another_user_is_not_chmodded(
        vhome, monkeypatch):
    make_dirs(vhome, 0o770, 0o770)
    monkeypatch.setattr(os, "getuid", lambda: os.stat(vhome).st_uid + 1)
    tighten_keystore_dirs()
    root, child = control_dirs(vhome)
    assert mode_of(root) == 0o770
    assert mode_of(child) == 0o770
    assert reserved_user_ids.platform_held_keys(
        CONTROL_CONNECTION) == frozenset()


def test_a_symlinked_key_directory_is_not_followed_when_tightening(vhome):
    make_dirs(vhome, 0o700, 0o700)
    root, child = control_dirs(vhome)
    target = vhome / "elsewhere"
    os.mkdir(target)
    os.chmod(target, 0o770)
    os.symlink(target, os.path.join(root, "linked"))
    tighten_keystore_dirs()
    assert mode_of(target) == 0o770


def test_each_tightened_directory_is_logged_once(vhome, caplog):
    make_dirs(vhome, 0o770, 0o750)

    def tightened():
        return [r.getMessage() for r in caplog.records
                if r.getMessage().startswith("tightened ")]

    with caplog.at_level(logging.INFO, logger="volttron.platform.keystore"):
        tighten_keystore_dirs()
        first = tightened()
        tighten_keystore_dirs()
        second = tightened()
    assert len(first) == 2
    assert "from mode 770 to 700" in first[0]
    assert "from mode 750 to 700" in first[1]
    assert second == first


def test_tightening_with_no_key_directory_does_nothing(vhome):
    tighten_keystore_dirs()
    assert not os.path.exists(vhome / "keystores")


# ---- keystores/ itself is checked ----

def test_a_group_writable_keystores_directory_above_a_closed_child_is_refused(
        vhome):
    make_dirs(vhome, 0o770, 0o700)
    assert reserved_user_ids.platform_held_keys(
        CONTROL_CONNECTION) == frozenset()


def test_a_closed_keystores_directory_above_a_closed_child_is_accepted(vhome):
    key = make_dirs(vhome, 0o700, 0o700)
    assert reserved_user_ids.platform_held_keys(CONTROL_CONNECTION) == {key}


# ---- an unpacked agent's tree ----

def make_agent_tree(root, dir_mode=0o770, file_mode=0o660):
    dist_info = root / "pkg" / "pkg.dist-info"
    os.makedirs(dist_info)
    key_file = dist_info / "keystore.json"
    key_file.write_text("{}")
    script = root / "pkg" / "agent.py"
    script.write_text("")
    for path in (root, root / "pkg", dist_info):
        os.chmod(path, dir_mode)
    for path in (key_file, script):
        os.chmod(path, file_mode)
    return dist_info, key_file, script


def test_group_write_is_removed_from_every_entry_of_an_agent_tree(tmp_path):
    dist_info, key_file, script = make_agent_tree(tmp_path / "agent")
    aip_module.remove_group_write(str(tmp_path / "agent"))
    for path in (tmp_path / "agent", tmp_path / "agent" / "pkg", dist_info):
        assert mode_of(path) == 0o750
    for path in (key_file, script):
        assert mode_of(path) == 0o640


def test_group_write_removal_leaves_other_bits_as_they_were(tmp_path):
    dist_info, key_file, _ = make_agent_tree(
        tmp_path / "agent", dir_mode=0o757, file_mode=0o646)
    aip_module.remove_group_write(str(tmp_path / "agent"))
    assert mode_of(dist_info) == 0o757
    assert mode_of(key_file) == 0o646


def test_install_closes_the_tree_before_the_agent_key_is_authorized(
        vhome, monkeypatch):
    """The reserved-key check runs when the key is authorized, so the tree
    must already be closed to group writes at that point."""
    uuid = "0123"
    seen = {}
    os.makedirs(vhome / "agents")

    def fake_unpack(wheel, dest):
        install_agent(vhome, VOLTTRON_CENTRAL, uuid=uuid)
        for root, dirs, files in os.walk(dest):
            for name in dirs + files:
                os.chmod(os.path.join(root, name), 0o770)

    platform = object.__new__(aip_module.AIPplatform)
    platform.env = SimpleNamespace(volttron_home=str(vhome),
                                   verify_agents=False)
    platform.agents = {}
    platform.agent_uuid_name_map = {}
    platform.secure_agent_user = False
    platform.message_bus = "zmq"
    monkeypatch.setattr(aip_module, "auth", None)
    monkeypatch.setattr(aip_module, "unpack", fake_unpack)
    monkeypatch.setattr(aip_module.uuid, "uuid4", lambda: uuid)
    monkeypatch.setattr(
        platform, "_setup_agent_vip_id",
        lambda agent_uuid, vip_identity=None: VOLTTRON_CENTRAL,
        raising=False)

    def record(agent_uuid, identity, publickey):
        dist_info = os.path.join(platform.install_dir, agent_uuid, "pkg",
                                 "pkg.dist-info")
        seen["dist_info"] = mode_of(dist_info)
        seen["key"] = reserved_user_ids.platform_held_keys(VOLTTRON_CENTRAL)

    monkeypatch.setattr(platform, "_authorize_agent_keys", record,
                        raising=False)
    wheel = vhome / "agent.whl"
    wheel.write_text("")
    platform.install_agent(str(wheel))
    assert seen["dist_info"] & 0o022 == 0
    assert len(seen["key"]) == 1
