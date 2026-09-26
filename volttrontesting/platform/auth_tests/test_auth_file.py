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

import logging
import os
import time

import gevent
import pytest
from pytest import raises

from volttron.platform.auth import (AuthEntry, AuthFile, AuthFileIndexError,
                                    AuthFileEntryAlreadyExists,
                                    AuthFileUserIdAlreadyExists,
                                    AuthEntryInvalid)
from volttron.platform.agent.known_identities import VOLTTRON_CENTRAL_PLATFORM, CONTROL
from volttron.platform import jsonapi
from volttrontesting.fixtures.volttron_platform_fixtures import get_test_volttron_home
from volttrontesting.platform.auth_tests.conftest import assert_auth_entries_same


@pytest.fixture(scope='function')
def auth_file_platform_tuple():
    with get_test_volttron_home('zmq') as vhome:
        auth_file = AuthFile(os.path.join(vhome, 'auth.json'))
        gevent.sleep(0.5)
        yield auth_file

        allow_entries = auth_file.read_allow_entries()

        auth_file.remove_by_indices(list(range(3, len(allow_entries))))
        gevent.sleep(0.5)


@pytest.fixture(scope='module')
def auth_entry_only_creds():
    return AuthEntry(credentials='B'*43)


@pytest.fixture(scope='function')
def auth_entry1():
    return AuthEntry(domain='domain1', address='tcp://127.0.0.1',
                     mechanism='NULL', user_id='user1', groups=['group1'],
                     roles=['role1'], capabilities=['cap1'], comments='com1',
                     enabled=True)


@pytest.fixture(scope='function')
def auth_entry2():
    return AuthEntry(domain='domain2', address='tcp://127.0.0.2',
                     credentials='A'*43,
                     user_id='user2', groups=['group2'], roles=['role2'],
                     capabilities=['cap2'], comments='com2', enabled=False)


@pytest.fixture(scope='function')
def auth_entry3():
    return AuthEntry(domain='domain3', address='tcp://127.0.0.3',
                     credentials='B'*43,
                     user_id='user3', groups=['group3'], roles=['role3'],
                     capabilities=['cap3'], comments='com3', enabled=False)

counter = 50

@pytest.mark.auth
def test_auth_file_overwrite(auth_file_platform_tuple, auth_entry_only_creds):
    auth_file = auth_file_platform_tuple
    auth_file.add(auth_entry_only_creds)
    auth_file.load()
    auth_file.add(auth_entry_only_creds, overwrite=True)
    auth_file.load()
    entries = auth_file.read_allow_entries()
    with raises(AuthFileEntryAlreadyExists):
        auth_file.add(auth_entry_only_creds)


@pytest.mark.auth
def test_auth_file_same_user_id(auth_file_platform_tuple, auth_entry1, auth_entry2):
    auth_file = auth_file_platform_tuple
    auth_file.add(auth_entry1)
    auth_file.load()
    auth_entry2.user_id = auth_entry1.user_id
    with raises(AuthFileUserIdAlreadyExists):
        auth_file.add(auth_entry2, False)

@pytest.mark.auth
def test_auth_file_api(auth_file_platform_tuple, auth_entry1,
                       auth_entry2, auth_entry3):
    auth_file = auth_file_platform_tuple

    # add entries
    auth_file.add(auth_entry1)
    auth_file.load()
    auth_file.add(auth_entry2)
    auth_file.load()
    entries = auth_file.read_allow_entries()
    entries_len = len(entries)
    assert entries_len == 2

    # update entries
    auth_file.update_by_index(auth_entry3, entries_len-2)
    auth_file.load()
    entries = auth_file.read_allow_entries()
    assert entries_len == len(entries)

    # remove entries
    auth_file.remove_by_index(entries_len-1)
    auth_file.load()
    entries = auth_file.read_allow_entries()
    assert entries_len - 1 == len(entries)


@pytest.mark.auth
def test_remove_auth_by_credentials(auth_file_platform_tuple, auth_entry1,
                                    auth_entry2, auth_entry3):
    auth_file = auth_file_platform_tuple

    # add entries
    auth_file.add(auth_entry1)
    auth_file.load()
    auth_file.add(auth_entry2)
    auth_file.load()
    auth_entry3.credentials = auth_entry2.credentials
    auth_file.add(auth_entry3)
    auth_file.load()
    entries = auth_file.read_allow_entries()
    entries_len = len(entries)

    # remove entries
    auth_file.remove_by_credentials(auth_entry2.credentials)
    auth_file.load()
    entries = auth_file.read_allow_entries()
    assert entries_len - 2 == len(entries)


@pytest.mark.auth
def test_remove_invalid_index(auth_file_platform_tuple):
    auth_file = auth_file_platform_tuple
    with pytest.raises(AuthFileIndexError):
        # by default will have 3 entries - platform, control and dynamic_agent created by platform wrapper
        auth_file.remove_by_index(3)


@pytest.mark.auth
def test_update_invalid_index(auth_file_platform_tuple, auth_entry1):
    auth_file = auth_file_platform_tuple
    with pytest.raises(AuthFileIndexError):
        # by default will have 3 entries - platform, control and dynamic_agent created by platform wrapper
        auth_file.update_by_index(auth_entry1, 3)


@pytest.mark.auth
def test_invalid_auth_entries(auth_file_platform_tuple):
    auth_file = auth_file_platform_tuple
    with pytest.raises(AuthEntryInvalid):
        AuthEntry()
    with pytest.raises(AuthEntryInvalid):
        AuthEntry(credentials='invalid key')
    with pytest.raises(AuthEntryInvalid):
        AuthEntry(mechanism='Not NULL or PLAIN or CURVE')


@pytest.mark.auth
def test_find_by_credentials(auth_file_platform_tuple):
    auth_file = auth_file_platform_tuple
    cred1 = 'A'*43
    cred2 = 'B'*43
    auth_file.add(AuthEntry(domain='test1', credentials=cred1))
    auth_file.load()
    auth_file.add(AuthEntry(domain='test2', credentials=cred1))
    auth_file.load()
    auth_file.add(AuthEntry(domain='test3', credentials=cred2))
    auth_file.load()

    # find non-regex creds
    results = auth_file.find_by_credentials(cred1)
    assert len(results) == 2
    domains = [entry.domain for entry in results]
    assert 'test1' in domains and 'test2' in domains

    # try to find non-existing creds
    results = auth_file.find_by_credentials('C'*43)
    assert len(results) == 0


@pytest.mark.auth
def test_groups_and_roles(auth_file_platform_tuple):
    auth_file = auth_file_platform_tuple
    cred = 'C'*43
    auth_file.add(AuthEntry(credentials=cred, groups=['group_1'],
                            roles=['role_b']))
    auth_file.load()
    # This entry hasn not been granted any capabilities
    results = auth_file.find_by_credentials(cred)
    assert len(results) == 1
    entry = results[0]
    assert not set(entry.capabilities)

    # Add roles and groups to the auth file
    roles = {
        'role_a': ['cap_a_1', 'cap_a_2'],
        'role_b': ['cap_b_1'],
        'role_c': ['cap_c_1'],
        'role_d': ['cap_d_1']
    }
    groups = {
        'group_1': ['role_a', 'role_c'],
        'group_2': ['role_b']
    }
    auth_file.set_roles(roles)
    auth_file.load()
    auth_file.set_groups(groups)
    auth_file.load()
    # Now the entry has inherited capabilities from its roles and groups
    results = auth_file.find_by_credentials(cred)
    assert len(results) == 1
    entry = results[0]
    assert set(entry.capabilities) == set(['cap_a_1', 'cap_a_2', 'cap_b_1',
                                           'cap_c_1'])


@pytest.mark.auth
def test_upgrade_file_verison_0_to_latest(tmpdir_factory):
    mechanism = "CURVE"
    publickey = "A" * 43
    version0 = {
        "allow": [
            {
                "domain": "vip",
                "address": "127.0.0.1",
                "user_id": "user123",
                "enabled": True,
                "comments": "This is a test entry",
                "capabilities": ["can_publish_temperature"],
                "roles": [],
                "groups": [],
                "credentials": mechanism + ":" + publickey
            }
        ],
        "roles": {
            "manager": ["can_managed_platform"]
        },
        "groups": {
            "admin": ["reader", "writer"]
        },
        "version": {
            "major": 0,
            "minor": 0
        },
    }

    filename = str(tmpdir_factory.mktemp('auth_test').join('auth.json'))
    with open(filename, 'w') as fp:
        fp.write(jsonapi.dumps(version0, indent=2))

    upgraded = AuthFile(filename)
    entries, denied_entries, groups, roles = upgraded.read()
    assert groups == version0['groups']
    assert roles == version0['roles']
    assert len(entries) == 1

    expected = version0['allow'][0]
    expected["credentials"] = publickey
    expected["mechanism"] = mechanism
    expected["capabilities"] = {'can_publish_temperature': None,
                                'edit_config_store': {'identity': entries[0].user_id}}
    expected["rpc_method_authorizations"] = {}
    assert_auth_entries_same(expected, vars(entries[0]))
    # RPC Method Authorizations added with 1.3
    for entry in upgraded.auth_data["allow_list"]:
        assert entry["rpc_method_authorizations"] == {}

@pytest.mark.auth
def test_upgrade_file_verison_0_to_latest_minimum_entries(tmpdir_factory):
    """The only required field in 'version 0' was credentials"""
    mechanism = "CURVE"
    publickey = "A" * 43
    version0 = {
        "allow": [{"credentials": mechanism + ":" + publickey}],
        "version": {
            "major": 0,
            "minor": 0
        },
    }

    filename = str(tmpdir_factory.mktemp('auth_test').join('auth.json'))
    with open(filename, 'w') as fp:
        fp.write(jsonapi.dumps(version0, indent=2))

    upgraded = AuthFile(filename)
    entries = upgraded.read()[0]
    assert len(entries) == 1
    assert entries[0].user_id is not None

    expected = version0['allow'][0]
    expected["credentials"] = publickey
    expected["mechanism"] = mechanism
    expected["domain"] = None
    expected["address"] = None
    expected["user_id"] = entries[0].user_id #this will be a UUID
    expected["enabled"] = True
    expected["comments"] = None
    expected["capabilities"] = {'edit_config_store': {'identity': entries[0].user_id}}
    expected["rpc_method_authorizations"] = {}
    expected["roles"] = []
    expected["groups"] = []
    assert_auth_entries_same(expected, vars(entries[0]))

    # RPC Method Authorizations added with 1.3
    for entry in upgraded.auth_data["allow_list"]:
        assert entry["rpc_method_authorizations"] == {}

@pytest.mark.auth
def test_upgrade_file_version_1_1_to_1_2(tmpdir_factory):
    """The only required field in 'version 0' was credentials"""

    version1_1 = {
      "roles":{
        "manager":[
          "can_managed_platform"
        ]
      },
      "version":{
        "major":1,
        "minor":1
      },
      "groups":{
        "admin":[
          "reader",
          "writer"
        ]
      },
      "allow":[
        {
          "domain":"vip",
          "user_id":"user1",
          "roles":[],
          "enabled":True,
          "mechanism":"CURVE",
          "capabilities":["can_publish_temperature"],
          "groups":[],
          "address":"127.0.0.1",
          "credentials":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
          "comments":"This is a test entry"
        },
        {
          "domain": "vip",
          "user_id": "user2",
          "roles": [],
          "enabled": True,
          "mechanism": "CURVE",
          "capabilities": ["blah", "foo"],
          "groups": [],
          "address": "127.0.0.1",
          "credentials": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
          "comments": "This is a test entry"
        },
        {
          "domain": "vip",
          "user_id": CONTROL,
          "roles": [],
          "enabled": True,
          "mechanism": "CURVE",
          "capabilities": [],
          "groups": [],
          "address": "127.0.0.1",
          "credentials": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
          "comments": "This is a test entry"
        },
        {
          "domain": "vip",
          "user_id": VOLTTRON_CENTRAL_PLATFORM,
          "roles": [],
          "enabled": True,
          "mechanism": "CURVE",
          "capabilities": [],
          "groups": [],
          "address": "127.0.0.1",
          "credentials": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
          "comments": "This is a test entry"
        }

      ]
    }

    filename = str(tmpdir_factory.mktemp('auth_test').join('auth.json'))
    with open(filename, 'w') as fp:
        fp.write(jsonapi.dumps(version1_1, indent=2))

    upgraded = AuthFile(filename)
    entries = upgraded.read()[0]
    assert len(entries) == 4
    for entry in entries:
        if entry.user_id in [CONTROL, VOLTTRON_CENTRAL_PLATFORM]:
            assert entry.capabilities == {'edit_config_store': {'identity': '/.*/'}}
        elif entry.user_id == "user1":
            assert entry.capabilities == {'can_publish_temperature': None,
                                           'edit_config_store': {'identity': 'user1'}}
        elif entry.user_id == "user2":
            assert entry.capabilities == {'blah': None, 'foo': None,
                                          'edit_config_store': {'identity': 'user2'}}

@pytest.mark.auth
def test_upgrade_file_version_1_2_to_1_3(tmpdir_factory):
    """The only required field in 'version 0' was credentials"""

    version1_2 = {
      "roles":{
        "manager":[
          "can_managed_platform"
        ]
      },
      "version":{
        "major":1,
        "minor":2
      },
      "groups":{
        "admin":[
          "reader",
          "writer"
        ]
      },
      "allow":[
        {
          "domain":"vip",
          "user_id":"user1",
          "roles":[],
          "enabled":True,
          "mechanism":"CURVE",
          "capabilities":{'can_publish_temperature': None,
                                           'edit_config_store': {'identity': 'user1'}},
          "groups":[],
          "address":"127.0.0.1",
          "credentials":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
          "comments":"This is a test entry"
        },
        {
          "domain": "vip",
          "user_id": "user2",
          "roles": [],
          "enabled": True,
          "mechanism": "CURVE",
          "capabilities": {'blah': None, 'foo': None,
                                          'edit_config_store': {'identity': 'user2'}},
          "groups": [],
          "address": "127.0.0.1",
          "credentials": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
          "comments": "This is a test entry"
        },
        {
          "domain": "vip",
          "user_id": CONTROL,
          "roles": [],
          "enabled": True,
          "mechanism": "CURVE",
          "capabilities": {'edit_config_store': {'identity': '/.*/'}},
          "groups": [],
          "address": "127.0.0.1",
          "credentials": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
          "comments": "This is a test entry"
        },
        {
          "domain": "vip",
          "user_id": VOLTTRON_CENTRAL_PLATFORM,
          "roles": [],
          "enabled": True,
          "mechanism": "CURVE",
          "capabilities": {'edit_config_store': {'identity': '/.*/'}},
          "groups": [],
          "address": "127.0.0.1",
          "credentials": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
          "comments": "This is a test entry"
        }

      ]
    }

    filename = str(tmpdir_factory.mktemp('auth_test').join('auth.json'))
    with open(filename, 'w') as fp:
        fp.write(jsonapi.dumps(version1_2, indent=2))

    upgraded = AuthFile(filename)
    entries = upgraded.read()[0]
    assert len(entries) == 4
    for entry in entries:
        assert entry.rpc_method_authorizations == {}


@pytest.mark.auth
def test_add_multiple_entries_one_object_all_persist(tmp_path):
    """#3248: the harness pre-seed builds one AuthFile and calls add()
    on it repeatedly (platformwrapper.py startup_platform). Each write
    must keep what the previous write already persisted."""
    auth_path = str(tmp_path / "auth.json")
    auth_file = AuthFile(auth_path)
    added = [
        AuthEntry(credentials=chr(65 + i) * 43, user_id=f"user{i}")
        for i in range(4)
    ]
    for entry in added:
        auth_file.add(entry)

    # A fresh object reads what is actually on disk, not whichever
    # in-memory view the writer instance happens to hold.
    persisted = AuthFile(auth_path).read_allow_entries()
    persisted_creds = {str(e.credentials) for e in persisted}
    assert persisted_creds == {str(e.credentials) for e in added}


@pytest.mark.auth
def test_add_capabilities_writes_matched_entry_only(tmp_path):
    """#3247: add_capabilities matches an entry by credentials but must
    not let AuthFile.add(overwrite=True) resolve the write target by
    user_id alone, which can land on a different entry."""
    from volttrontesting.utils.platformwrapper import PlatformWrapper

    auth_path = str(tmp_path / "auth.json")
    cred_a = "A" * 43
    cred_b = "B" * 43
    entry_a = AuthEntry(user_id="shared", credentials=cred_a)
    entry_b = AuthEntry(user_id="shared", credentials=cred_b)

    # add() itself refuses a second entry with a duplicate user_id, so
    # this shape (two entries sharing a user_id, differing by key) is
    # seeded with a direct write, bypassing that check.
    seed = AuthFile(auth_path)
    seed._write([entry_a, entry_b], [], {}, {})

    wrapper = PlatformWrapper.__new__(PlatformWrapper)
    wrapper.auth_enabled = True
    wrapper.env = {}
    wrapper.volttron_home = str(tmp_path)

    wrapper.add_capabilities(cred_b, "new_cap")

    reread = {
        str(e.credentials): e for e in AuthFile(auth_path).read_allow_entries()
    }
    assert "new_cap" in reread[cred_b].capabilities
    assert "new_cap" not in reread[cred_a].capabilities


def _curve_key(char):
    return char * 43


def _disk_allow(auth_path):
    with open(auth_path) as f:
        return jsonapi.load(f)["allow"]


def _auth_service_on(auth_path, monkeypatch):
    """An AuthService with only the state read_auth_file and the rpc
    authorization methods use, after its onsetup load. _send_update
    records the entries it would push instead of calling peers."""
    from volttron.platform.auth import AuthService

    monkeypatch.setattr(gevent, "sleep", lambda *args, **kwargs: None)
    service = object.__new__(AuthService)
    service.auth_file_path = auth_path
    service.auth_file = AuthFile(auth_path)
    service._last_loaded_allow_entries = []
    service._auth_approved = []
    service._auth_denied = []
    service._is_connected = False
    service.read_auth_file()
    service._is_connected = True
    service.pushed = []
    service._send_update = (
        lambda modified_entries=None: service.pushed.append(
            {e.identity: e.rpc_method_authorizations
             for e in modified_entries or []}))
    return service


@pytest.mark.auth
def test_read_auth_file_diffs_write_through_own_authfile(tmp_path, monkeypatch):
    """#3248: a write through the service's own AuthFile (vctl auth rpc
    add|remove) must still reach running agents when the watcher reloads."""
    auth_path = str(tmp_path / "auth.json")
    AuthFile(auth_path).add(AuthEntry(
        user_id="agentx", identity="agentx", credentials=_curve_key("X")))
    service = _auth_service_on(auth_path, monkeypatch)

    service.add_rpc_authorizations("agentx", "method1", ["cap1"])
    service.read_auth_file()
    service.delete_rpc_authorizations("agentx", "method1", ["cap1"])
    service.read_auth_file()

    assert service.pushed == [
        {"agentx": {"method1": ["cap1"]}},
        {"agentx": {"method1": [""]}},
    ]
    assert _disk_allow(auth_path)[0]["rpc_method_authorizations"] == {
        "method1": [""]}


@pytest.mark.auth
def test_mixed_mutators_one_object(tmp_path):
    """#3248: each mutator on one AuthFile builds on the previous write,
    so a removal is not undone by a later write through the same object."""
    auth_path = str(tmp_path / "auth.json")
    for char in "ABCD":
        AuthFile(auth_path).add(AuthEntry(user_id=f"u{char}",
                                          credentials=_curve_key(char)))
    auth_file = AuthFile(auth_path)

    auth_file.remove_by_indices([0])
    auth_file.update_by_index(
        AuthEntry(user_id="uZ", credentials=_curve_key("Z")), 0)

    disk = _disk_allow(auth_path)
    assert [e["user_id"] for e in disk] == ["uZ", "uC", "uD"]
    assert auth_file.auth_data["allow_list"] == disk

    auth_path = str(tmp_path / "revoke.json")
    AuthFile(auth_path).add(
        AuthEntry(user_id="keep", credentials=_curve_key("K")))
    AuthFile(auth_path).add(
        AuthEntry(user_id="revoked", credentials=_curve_key("R")))
    auth_file = AuthFile(auth_path)

    auth_file.remove_by_indices([1])
    auth_file.add(AuthEntry(user_id="new", credentials=_curve_key("N")))

    assert [e["user_id"] for e in _disk_allow(auth_path)] == ["keep", "new"]


@pytest.mark.auth
def test_write_does_not_read_back(tmp_path, monkeypatch):
    """#3248: _write keeps what it wrote without reading the file back, so
    a read that sees an empty or truncated file cannot drop entries."""
    auth_path = str(tmp_path / "auth.json")
    auth_file = AuthFile(auth_path)
    empty = {"allow_list": [], "deny_list": [], "groups": {}, "roles": {},
             "version": {"major": 0, "minor": 0}}
    monkeypatch.setattr(auth_file, "_read", lambda: empty)

    auth_file.add(AuthEntry(user_id="first", credentials=_curve_key("F")))
    auth_file.add(AuthEntry(user_id="second", credentials=_curve_key("S")))

    assert [e["user_id"] for e in _disk_allow(auth_path)] == [
        "first", "second"]


@pytest.mark.auth
def test_failed_write_keeps_auth_data(tmp_path):
    """auth_data changes only after the file is written, so a failed write
    leaves it matching the file."""
    auth_path = str(tmp_path / "auth.json")
    auth_file = AuthFile(auth_path)
    auth_file.add(AuthEntry(user_id="first", credentials=_curve_key("F")))
    before = jsonapi.loads(jsonapi.dumps(auth_file.auth_data))
    os.chmod(auth_path, 0o444)
    try:
        with raises(PermissionError):
            auth_file.add(AuthEntry(user_id="second",
                                    credentials=_curve_key("S")))
    finally:
        os.chmod(auth_path, 0o644)

    assert auth_file.auth_data == before
    assert [e["user_id"] for e in _disk_allow(auth_path)] == ["first"]


@pytest.mark.auth
def test_snapshot_not_aliased(tmp_path, monkeypatch):
    """update_id_rpc_authorizations edits an entry's rpc dict in place; the
    reload after its write must still see the new method as a change."""
    auth_path = str(tmp_path / "auth.json")
    AuthFile(auth_path).add(AuthEntry(
        user_id="agentx", identity="agentx", credentials=_curve_key("X"),
        rpc_method_authorizations={"method1": ["cap1"]}))
    service = _auth_service_on(auth_path, monkeypatch)

    service.update_id_rpc_authorizations(
        "agentx", {"method1": ["cap1"], "method2": ["cap2"]})
    service.read_auth_file()

    assert service.pushed == [
        {"agentx": {"method1": ["cap1"], "method2": ["cap2"]}}]


@pytest.mark.auth
def test_failed_push_is_sent_again(tmp_path, monkeypatch):
    """A push that raises is logged, not raised, and does not advance the
    snapshot, so the next reload sends the same change again."""
    auth_path = str(tmp_path / "auth.json")
    AuthFile(auth_path).add(AuthEntry(
        user_id="agentx", identity="agentx", credentials=_curve_key("X")))
    service = _auth_service_on(auth_path, monkeypatch)
    record = service._send_update

    def fail_once(modified_entries=None):
        service._send_update = record
        raise RuntimeError("no peers")

    service._send_update = fail_once
    service.add_rpc_authorizations("agentx", "method1", ["cap1"])
    service.read_auth_file()
    service.read_auth_file()

    assert service.pushed == [{"agentx": {"method1": ["cap1"]}}]


def _wait_until(condition, timeout=10):
    # gevent.sleep is stubbed here and the file watcher is a native
    # thread, so wait on the clock rather than on the hub.
    deadline = time.time() + timeout
    while not condition():
        if time.time() > deadline:
            return False
        time.sleep(0.1)
    return True


@pytest.mark.auth
def test_watcher_survives_a_failed_push(tmp_path, monkeypatch, caplog):
    """Through the real file watcher: a push that raises is logged, later
    changes to auth.json still load, and the failed change is sent again."""
    from volttron.platform.agent import utils

    auth_path = str(tmp_path / "auth.json")
    AuthFile(auth_path).add(AuthEntry(
        user_id="agentx", identity="agentx", credentials=_curve_key("X")))
    service = _auth_service_on(auth_path, monkeypatch)
    record = service._send_update
    attempts = []

    def fail_first(modified_entries=None):
        attempts.append(modified_entries)
        if len(attempts) == 1:
            raise BaseException("No peers connected to the platform")
        record(modified_entries)

    service._send_update = fail_first
    observers = []

    class RecordedObserver(utils.Observer):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            observers.append(self)

    monkeypatch.setattr(utils, "Observer", RecordedObserver)
    utils.watch_file(auth_path, service.read_auth_file)
    try:
        service.add_rpc_authorizations("agentx", "method1", ["cap1"])
        assert _wait_until(lambda: attempts)
        AuthFile(auth_path).add(
            AuthEntry(user_id="later", credentials=_curve_key("L")))
        assert _wait_until(
            lambda: "later" in [e.user_id for e in service.auth_entries])
        assert _wait_until(
            lambda: {"agentx": {"method1": ["cap1"]}} in service.pushed)
        service.add_rpc_authorizations("agentx", "method2", ["cap2"])
        assert _wait_until(
            lambda: {"agentx": {"method1": ["cap1"], "method2": ["cap2"]}}
            in service.pushed)
    finally:
        for observer in observers:
            observer.stop()
            observer.join(timeout=5)

    assert [type(o).__mro__[1].__name__ for o in observers] == [
        "InotifyObserver"]
    assert any(r.levelno == logging.ERROR and r.exc_info
               for r in caplog.records)
