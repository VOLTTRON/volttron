
import os
import re
import subprocess

import gevent
import pytest
from mock import MagicMock
from volttron.platform.auth.auth_protocols.auth_zmq import ZMQAuthorization, ZMQServerAuthentication

from volttrontesting.platform.auth_tests.conftest import assert_auth_entries_same
from volttrontesting.utils.platformwrapper import with_os_environ
from volttrontesting.utils.utils import AgentMock
from volttron.platform.vip.agent import Agent
from volttron.platform.auth import AuthService
from volttron.platform.auth import AuthEntry
from volttron.platform import jsonapi

@pytest.fixture(autouse=True)
def auth_instance(volttron_instance):
    if not volttron_instance.auth_enabled:
        pytest.skip("AUTH tests are not applicable if auth is disabled")
    with open(os.path.join(volttron_instance.volttron_home, "auth.json"), 'r') as f:
        auth_file = jsonapi.load(f)
    print(auth_file)
    try:
        yield volttron_instance
    finally:
        with with_os_environ(volttron_instance.env):
            with open(os.path.join(volttron_instance.volttron_home, "auth.json"), 'w') as f:
                jsonapi.dump(auth_file, f)


def _run_group_or_role_cmds(platform, add_fn, list_fn, update_fn, remove_fn):
    expected = []
    key = '0'
    values = ['0', '1']
    expected.extend(values)

    add_fn(platform, key, values)
    gevent.sleep(4)
    keys = list_fn(platform)
    assert set(keys[key]) == set(expected)

    # Update add single value
    values = ['2']
    expected.extend(values)
    update_fn(platform, key, values)
    gevent.sleep(2)
    keys = list_fn(platform)
    assert set(keys[key]) == set(expected)

    # Update add multiple values
    values = ['3', '4']
    expected.extend(values)
    update_fn(platform, key, values)
    gevent.sleep(2)
    keys = list_fn(platform)
    assert set(keys[key]) == set(expected)

    # Update remove single value
    value = '0'
    expected.remove(value)
    update_fn(platform, key, [value], remove=True)
    gevent.sleep(2)
    keys = list_fn(platform)
    assert set(keys[key]) == set(expected)

    # Update remove single value
    values = ['1', '2']
    for value in values:
        expected.remove(value)
    update_fn(platform, key, values, remove=True)
    gevent.sleep(2)
    keys = list_fn(platform)
    assert set(keys[key]) == set(expected)

    # Remove key
    remove_fn(platform, key)
    gevent.sleep(2)
    keys = list_fn(platform)
    assert key not in keys



def _add_group_or_role(platform, cmd, name, list_):
    with with_os_environ(platform.env):
        args = ['volttron-ctl', 'auth', cmd, name]
        args.extend(list_)
        p = subprocess.Popen(args, env=platform.env, stdin=subprocess.PIPE, universal_newlines=True)
        p.communicate()
        assert p.returncode == 0


def _add_group(platform, group, roles):
    _add_group_or_role(platform, 'add-group', group, roles)


def _add_role(platform, role, capabilities):
    _add_group_or_role(platform, 'add-role', role, capabilities)


def _list_groups_or_roles(platform, cmd):
    with with_os_environ(platform.env):
        output = subprocess.check_output(['volttron-ctl', 'auth', cmd],
                                        env=platform.env, universal_newlines=True)
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
    with with_os_environ(platform.env):
        args = ['volttron-ctl', 'auth', cmd, key]
        args.extend(values)
        if remove:
            args.append('--remove')
        p = subprocess.Popen(args, env=platform.env, stdin=subprocess.PIPE, universal_newlines=True)
        p.communicate()
        assert p.returncode == 0


def _update_group(platform, group, roles, remove=False):
    _update_group_or_role(platform, 'update-group', group, roles, remove)


def _update_role(platform, role, caps, remove=False):
    _update_group_or_role(platform, 'update-role', role, caps, remove)


def _remove_group_or_role(platform, cmd, key):
    with with_os_environ(platform.env):
        args = ['volttron-ctl', 'auth', cmd, key]
        p = subprocess.Popen(args, env=platform.env, stdin=subprocess.PIPE, universal_newlines=True)
        p.communicate()
        assert p.returncode == 0


def _remove_group(platform, group):
    _remove_group_or_role(platform, 'remove-group', group)


def _remove_role(platform, role):
    _remove_group_or_role(platform, 'remove-role', role)


@pytest.mark.control
def test_group_cmds(auth_instance):
    """Test add-group, list-groups, update-group, and remove-group"""
    _run_group_or_role_cmds(auth_instance, _add_group, _list_groups,
            _update_group, _remove_group)


@pytest.mark.control
def test_role_cmds(auth_instance):
    """Test add-role, list-roles, update-role, and remove-role"""
    _run_group_or_role_cmds(auth_instance, _add_role, _list_roles,
            _update_role, _remove_role)

