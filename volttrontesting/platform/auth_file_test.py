# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2015, Battelle Memorial Institute
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

from volttron.platform import jsonrpc
from volttron.platform.auth import AuthEntry, AuthFile

@pytest.fixture(scope='function')
def auth_file_platform_tuple(volttron_instance1_encrypt):
    platform = volttron_instance1_encrypt
    auth_file = AuthFile(os.path.join(platform.volttron_home, 'auth.json'))

    allow_entries, groups, roles = auth_file.read()
    assert len(allow_entries) == 0
    assert len(groups) == 0
    assert len(roles) == 0
    return auth_file, platform

@pytest.fixture(scope='module')
def auth_entry1():
    return AuthEntry(domain='domain1', address='tcp://127.0.0.1', 
            credentials='NULL', user_id='user1', groups=['group1'],
            roles=['role1'], capabilities=['cap1'], comments='comment1',
            enabled=True)

@pytest.fixture(scope='module')
def auth_entry2():
    return AuthEntry(domain='domain2', address='tcp://127.0.0.2',
            credentials='CURVE:' + 'A'*43,
            user_id='user2', groups=['group2'], roles=['role2'], 
            capabilities=['cap2'], comments='comment2', enabled=False)

@pytest.fixture(scope='module')
def auth_entry3():
    return AuthEntry(domain='domain3', address='tcp://127.0.0.3',
            credentials='CURVE:' + 'A'*43,
            user_id='user3', groups=['group3'], roles=['role3'], 
            capabilities=['cap3'], comments='comment3', enabled=False)

def assert_attributes_match(list1, list2):
    assert len(list1) == len(list2)
    for i in range(len(list1)):
        for key in vars(list1[i]):
            assert vars(list1[i])[key] == vars(list2[i])[key]

@pytest.mark.auth
def test_auth_file_api(auth_file_platform_tuple, auth_entry1,
        auth_entry2, auth_entry3):
    auth_file, platform = auth_file_platform_tuple
    
    # add entries
    auth_file.add(auth_entry1)
    auth_file.add(auth_entry2)
    entries = auth_file.read_allow_entries()
    assert len(entries) == 2

    my_entries = [auth_entry1, auth_entry2]
    assert_attributes_match(entries, my_entries)

    # update entries
    auth_file.update_by_index(auth_entry3, 0)
    entries = auth_file.read_allow_entries()
    my_entries = [auth_entry3, auth_entry2]
    assert_attributes_match(entries, my_entries)

    # remove entries
    auth_file.remove_by_index(1)
    entries = auth_file.read_allow_entries()
    my_entries = [auth_entry3]
    assert_attributes_match(entries, my_entries)
