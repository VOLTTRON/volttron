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


def auth_add_cmd_line(platform, entry):
    args = ['volttron-ctl', 'auth', 'add']
    fields = entry.__dict__.copy()
    enabled = fields.pop('enabled')
    for k, v in fields.items():
        if isinstance(v, list):
            v = ','.join(v)
        if v:
            if k == "capabilities":
                args.extend(['--' + k, json.dumps(v)])
            else:
                args.extend(['--' + k, v])

    if not enabled:
        args.append('--disabled')

    env = get_env(platform)
    p = subprocess.Popen(args, env=env, stdin=subprocess.PIPE)
    p.communicate()
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
    for field in ['roles', 'groups']:
        assert set(e1[field]) == set(e2[field])
    assert e1['capabilities'] == e2['capabilities']


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
def test_auth_add_cmd_line(volttron_instance_encrypt):
    """Add a single entry, specifying parameters on the command line"""
    platform = volttron_instance_encrypt
    auth_add_cmd_line(platform, _auth_entry1)
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


@pytest.mark.control
def test_group_cmds(volttron_instance_encrypt):
    """Test add-group, list-groups, update-group, and remove-group"""
    _run_group_or_role_cmds(volttron_instance_encrypt, _add_group, _list_groups,
            _update_group, _remove_group)


@pytest.mark.control
def test_role_cmds(volttron_instance_encrypt):
    """Test add-role, list-roles, update-role, and remove-role"""
    _run_group_or_role_cmds(volttron_instance_encrypt, _add_role, _list_roles,
            _update_role, _remove_role)


def _run_group_or_role_cmds(platform, add_fn, list_fn, update_fn, remove_fn):
    expected = []
    key = '0'
    values = ['0', '1']
    expected.extend(values)

    add_fn(platform, key, values)
    keys = list_fn(platform)
    assert set(keys[key]) == set(expected)

    # Update add single value
    values = ['2']
    expected.extend(values)
    update_fn(platform, key, values)
    keys = list_fn(platform)
    assert set(keys[key]) == set(expected)

    # Update add multiple values
    values = ['3', '4']
    expected.extend(values)
    update_fn(platform, key, values)
    keys = list_fn(platform)
    assert set(keys[key]) == set(expected)

    # Update remove single value
    value = '0'
    expected.remove(value)
    update_fn(platform, key, [value], remove=True)
    keys = list_fn(platform)
    assert set(keys[key]) == set(expected)

    # Update remove single value
    values = ['1', '2']
    for value in values:
        expected.remove(value)
    update_fn(platform, key, values, remove=True)
    keys = list_fn(platform)
    assert set(keys[key]) == set(expected)

    # Remove key
    remove_fn(platform, key)
    keys = list_fn(platform)
    assert key not in keys


def _add_group_or_role(platform, cmd, name, list_):
    args = ['volttron-ctl', 'auth', cmd, name]
    args.extend(list_)
    env = get_env(platform)
    p = subprocess.Popen(args, env=env, stdin=subprocess.PIPE)
    p.communicate()
    assert p.returncode == 0


def _add_group(platform, group, roles):
    _add_group_or_role(platform, 'add-group', group, roles)


def _add_role(platform, role, capabilities):
    _add_group_or_role(platform, 'add-role', role, capabilities)


def _list_groups_or_roles(platform, cmd):
    env = get_env(platform)
    output = subprocess.check_output(['volttron-ctl', 'auth', cmd],
                                    env=env)
    output = output.decode("utf-8")
    # For these tests don't use names that contain space, [, comma, or '
    output = output.replace('[', '').replace("'", '').replace(']', '')
    output = output.replace(',', '')
    lines = output.split('\n')

    dict_ = {}
    for line in lines[2:-1]: # skip two header lines and last (empty) line
        list_ = ' '.join(line.split()).split() # combine multiple spaces
        dict_[list_[0]] = list_[1:]
    return dict_


def _list_groups(platform):
    return _list_groups_or_roles(platform, 'list-groups')


def _list_roles(platform):
    return _list_groups_or_roles(platform, 'list-roles')


def _update_group_or_role(platform, cmd, key, values, remove):
    args = ['volttron-ctl', 'auth', cmd, key]
    args.extend(values)
    if remove:
        args.append('--remove')
    env = get_env(platform)
    p = subprocess.Popen(args, env=env, stdin=subprocess.PIPE)
    p.communicate()
    assert p.returncode == 0


def _update_group(platform, group, roles, remove=False):
    _update_group_or_role(platform, 'update-group', group, roles, remove)


def _update_role(platform, role, caps, remove=False):
    _update_group_or_role(platform, 'update-role', role, caps, remove)


def _remove_group_or_role(platform, cmd, key):
    args = ['volttron-ctl', 'auth', cmd, key]
    env = get_env(platform)
    p = subprocess.Popen(args, env=env, stdin=subprocess.PIPE)
    p.communicate()
    assert p.returncode == 0


def _remove_group(platform, group):
    _remove_group_or_role(platform, 'remove-group', group)


def _remove_role(platform, role):
    _remove_group_or_role(platform, 'remove-role', role)


@pytest.mark.control
def test_known_host_cmds(volttron_instance_encrypt):
    platform = volttron_instance_encrypt
    host = '1.2.3.4:5678'
    key = 'w-mKufe5hiRSPKK2LnkK_Z9VwRPMohdafhS6IekxYE7'
    _add_known_host(platform, host, key)

    hosts = _list_known_hosts(platform)
    assert hosts[host] == key

    _remove_known_host(platform, host)
    hosts = _list_known_hosts(platform)
    assert host not in hosts


def _add_known_host(platform, host, serverkey):
    args = ['volttron-ctl', 'auth', 'add-known-host']
    args.extend(['--host', host])
    args.extend(['--serverkey', serverkey])
    env = get_env(platform)
    p = subprocess.Popen(args, env=env, stdin=subprocess.PIPE)
    p.communicate()
    assert p.returncode == 0


def _list_known_hosts(platform):
    env = get_env(platform)
    output = subprocess.check_output(['volttron-ctl', 'auth',
                                      'list-known-hosts'], env=env)

    output = output.decode("utf-8")
    lines = output.split('\n')
    dict_ = {}
    for line in lines[2:-1]: # skip two header lines and last (empty) line
        host, pubkey = ' '.join(line.split()).split() # combine multiple spaces
        dict_[host] = pubkey
    return dict_


def _remove_known_host(platform, host):
    args = ['volttron-ctl', 'auth', 'remove-known-host', host]
    env = get_env(platform)
    p = subprocess.Popen(args, env=env, stdin=subprocess.PIPE)
    p.communicate()
    assert p.returncode == 0
