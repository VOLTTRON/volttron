# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

import json
import os

import gevent
import pytest
from py.test import raises

from volttron.platform import jsonrpc
from volttron.platform.auth import (AuthEntry, AuthFile, AuthFileIndexError,
                                    AuthFileEntryAlreadyExists,
                                    AuthEntryInvalid)
from volttrontesting.platform.auth_control_test import assert_auth_entries_same


@pytest.fixture(scope='function')
def auth_file_platform_tuple(volttron_instance_encrypt):
    platform = volttron_instance_encrypt
    auth_file = AuthFile(os.path.join(platform.volttron_home, 'auth.json'))

    allow_entries, groups, roles = auth_file.read()
    gevent.sleep(0.5)
    return auth_file, platform


@pytest.fixture(scope='module')
def auth_entry_only_creds():
    return AuthEntry(credentials='B'*43)


@pytest.fixture(scope='module')
def auth_entry1():
    return AuthEntry(domain='domain1', address='tcp://127.0.0.1',
                     mechanism='NULL', user_id='user1', groups=['group1'],
                     roles=['role1'], capabilities=['cap1'], comments='com1',
                     enabled=True)


@pytest.fixture(scope='module')
def auth_entry2():
    return AuthEntry(domain='domain2', address='tcp://127.0.0.2',
                     credentials='A'*43,
                     user_id='user2', groups=['group2'], roles=['role2'],
                     capabilities=['cap2'], comments='com2', enabled=False)


@pytest.fixture(scope='module')
def auth_entry3():
    return AuthEntry(domain='domain3', address='tcp://127.0.0.3',
                     credentials='B'*43,
                     user_id='user3', groups=['group3'], roles=['role3'],
                     capabilities=['cap3'], comments='com3', enabled=False)


@pytest.mark.auth
def test_auth_file_overwrite(auth_file_platform_tuple, auth_entry_only_creds):
    authfile, platform = auth_file_platform_tuple
    authfile.add(auth_entry_only_creds)
    authfile.add(auth_entry_only_creds)
    with raises(AuthFileEntryAlreadyExists):
        authfile.add(auth_entry_only_creds, False)


@pytest.mark.auth
def test_auth_file_api(auth_file_platform_tuple, auth_entry1,
                       auth_entry2, auth_entry3):
    auth_file, platform = auth_file_platform_tuple

    # add entries
    auth_file.add(auth_entry1)
    auth_file.add(auth_entry2)
    entries = auth_file.read_allow_entries()
    entries_len = len(entries)
    assert entries_len >= 2

    # update entries
    auth_file.update_by_index(auth_entry3, 0)
    entries = auth_file.read_allow_entries()
    assert entries_len == len(entries)

    # remove entries
    auth_file.remove_by_index(1)
    entries = auth_file.read_allow_entries()
    assert entries_len - 1 == len(entries)


@pytest.mark.auth
def test_remove_auth_by_credentials(auth_file_platform_tuple, auth_entry1,
                                    auth_entry2, auth_entry3):
    auth_file, platform = auth_file_platform_tuple

    # add entries
    auth_file.add(auth_entry1)
    auth_file.add(auth_entry2)
    auth_entry3.credentials = auth_entry2.credentials
    auth_file.add(auth_entry3)
    entries = auth_file.read_allow_entries()
    entries_len = len(entries)

    # remove entries
    auth_file.remove_by_credentials(auth_entry2.credentials)
    entries = auth_file.read_allow_entries()
    assert entries_len - 2 == len(entries)


@pytest.mark.auth
def test_remove_invalid_index(auth_file_platform_tuple):
    auth_file, _ = auth_file_platform_tuple
    with pytest.raises(AuthFileIndexError):
        auth_file.remove_by_index(2)


@pytest.mark.auth
def test_update_invalid_index(auth_file_platform_tuple, auth_entry1):
    auth_file, _ = auth_file_platform_tuple
    with pytest.raises(AuthFileIndexError):
        auth_file.update_by_index(auth_entry1, 2)


@pytest.mark.auth
def test_invalid_auth_entries(auth_file_platform_tuple):
    auth_file, _ = auth_file_platform_tuple
    with pytest.raises(AuthEntryInvalid):
        AuthEntry()
    with pytest.raises(AuthEntryInvalid):
        AuthEntry(credentials='invalid key')
    with pytest.raises(AuthEntryInvalid):
        AuthEntry(mechanism='Not NULL or PLAIN or CURVE')


@pytest.mark.auth
def test_find_by_credentials(auth_file_platform_tuple):
    auth_file = auth_file_platform_tuple[0]
    cred1 = 'A'*43
    cred2 = 'B'*43
    auth_file.add(AuthEntry(domain='test1', credentials=cred1))
    auth_file.add(AuthEntry(domain='test2', credentials=cred1))
    auth_file.add(AuthEntry(domain='test3', credentials=cred2))

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
    auth_file = auth_file_platform_tuple[0]
    cred = 'C'*43
    auth_file.add(AuthEntry(credentials=cred, groups=['group_1'],
                            roles=['role_b']))

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
    auth_file.set_groups(groups)

    # Now the entry has inherited capabilities from its roles and groups
    results = auth_file.find_by_credentials(cred)
    assert len(results) == 1
    entry = results[0]
    assert set(entry.capabilities) == set(['cap_a_1', 'cap_a_2', 'cap_b_1',
                                           'cap_c_1'])


@pytest.mark.auth
def test_upgrade_file_verison_0_to_1(tmpdir_factory):
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
        }
    }

    filename = str(tmpdir_factory.mktemp('auth_test').join('auth.json'))
    with open(filename, 'w') as fp:
        fp.write(json.dumps(version0, indent=2))

    upgraded = AuthFile(filename)
    entries, groups, roles = upgraded.read()
    assert groups == version0['groups']
    assert roles == version0['roles']
    assert len(entries) == 1

    expected = version0['allow'][0]
    expected["credentials"] = publickey
    expected["mechanism"] = mechanism
    assert_auth_entries_same(expected, vars(entries[0]))
