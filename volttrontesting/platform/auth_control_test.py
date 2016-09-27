import json
import os
import re
import subprocess

import pytest

from volttron.platform.auth import AuthEntry

_auth_entry1 = AuthEntry(
    domain='test1_domain', address='test1_address', mechanism='NULL',
    user_id='test1_userid', groups=['test1_group1', 'test1_group2'],
    roles=['test1_role1', 'test1_role2'],
    capabilities=['test1_cap1', 'test1_cap2'],
    comments='test1 comment', enabled=True)

_auth_entry2 = AuthEntry(
    domain='test2_domain', address='test2_address', mechanism='NULL',
    user_id='test2_userid', groups=['test2_group1', 'test2_group2'],
    roles=['test2_role1', 'test2_role2'],
    capabilities=['test2_cap1', 'test2_cap2'],
    comments='test2 comment', enabled=False)


def get_env(platform):
    env = os.environ.copy()
    env['VOLTTRON_HOME'] = platform.volttron_home
    return env


def auth_list(platform):
    env = get_env(platform)
    return subprocess.check_output(['volttron-ctl', 'auth', 'list'], env=env)


def auth_list_json(platform):
    output = auth_list(platform)
    entries = re.findall('\nINDEX: \d+(\n{.*?\n}\n)', output, re.DOTALL)
    return [json.loads(entry) for entry in entries]


def entry_to_input_string(domain='', address='', user_id='', capabilities='',
                          roles='', groups='', mechanism='', credentials='',
                          comments='', enabled=''):
    inputs = []
    inputs.append(domain)
    inputs.append(address)
    inputs.append(user_id)
    inputs.append(','.join(capabilities))
    inputs.append(','.join(roles))
    inputs.append(','.join(groups))
    inputs.append(mechanism)
    inputs.append(credentials or '')
    inputs.append(comments)

    if isinstance(enabled, bool):
        enabled = 'True' if enabled else 'False'
    inputs.append(enabled)
    return '\n'.join(inputs) + '\n'


def auth_add(platform, entry):
    env = get_env(platform)
    p = subprocess.Popen(['volttron-ctl', 'auth', 'add'], env=env,
                         stdin=subprocess.PIPE)
    p.communicate(input=entry_to_input_string(**entry.__dict__))
    assert p.returncode == 0


def auth_remove(platform, index):
    env = get_env(platform)
    p = subprocess.Popen(['volttron-ctl', 'auth', 'remove', str(index)], env=env,
                         stdin=subprocess.PIPE)
    p.communicate(input='Y\n')
    assert p.returncode == 0


def auth_update(platform, index, **kwargs):
    env = get_env(platform)
    p = subprocess.Popen(['volttron-ctl', 'auth', 'update', str(index)], env=env,
                         stdin=subprocess.PIPE)
    p.communicate(input=entry_to_input_string(**kwargs))
    assert p.returncode == 0


def assert_auth_entries_same(e1, e2):
    for field in ['domain', 'address', 'user_id', 'credentials', 'comments',
                  'enabled']:
        assert e1[field] == e2[field]
    for field in ['capabilities', 'roles', 'groups']:
        assert set(e1[field]) == set(e2[field])


@pytest.mark.control
def test_auth_list(volttron_instance_encrypt):
    output = auth_list(volttron_instance_encrypt)
    assert output.startswith('No entries in') or output.startswith('\nINDEX')


@pytest.mark.control
def test_auth_add(volttron_instance_encrypt):
    """Add a single entry"""
    platform = volttron_instance_encrypt
    auth_add(platform, _auth_entry1)
    # Verify entry shows up in list
    entries = auth_list_json(platform)
    assert len(entries) > 0
    assert_auth_entries_same(entries[-1], _auth_entry1.__dict__)


@pytest.mark.control
def test_auth_update(volttron_instance_encrypt):
    """Add an entry then update it with a different entry"""
    platform = volttron_instance_encrypt
    auth_add(platform, _auth_entry1)
    entries = auth_list_json(platform)
    assert len(entries) > 0

    auth_update(platform, len(entries) - 1, **_auth_entry2.__dict__)

    entries = auth_list_json(platform)
    assert_auth_entries_same(entries[-1], _auth_entry2.__dict__)


@pytest.mark.control
def test_auth_remove(volttron_instance_encrypt):
    """Add two entries then remove the last entry"""
    platform = volttron_instance_encrypt
    auth_add(platform, _auth_entry1)
    auth_add(platform, _auth_entry2)
    entries = auth_list_json(platform)
    assert len(entries) > 0

    auth_remove(platform, len(entries) - 1)

    # Verify _auth_entry2 was removed and _auth_entry1 remains
    entries = auth_list_json(platform)
    assert len(entries) > 0
    assert_auth_entries_same(entries[-1], _auth_entry1.__dict__)
