# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

import os

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
