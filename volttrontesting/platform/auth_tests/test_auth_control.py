import os
import re
import subprocess

import gevent
import pytest
from mock import MagicMock
from volttron.platform.auth.auth_protocols.auth_zmq import ZMQAuthorization, ZMQServerAuthentication

from volttrontesting.platform.auth_tests.conftest import assert_auth_entries_same
from volttrontesting.utils.platformwrapper import with_os_environ
from volttrontesting.utils.utils import AgentMock, poll_gevent_sleep
from volttron.platform.vip.agent import Agent, RPC
from volttron.platform.auth import AuthService
from volttron.platform.auth import AuthEntry, AuthFile
from volttron.platform import jsonapi, jsonrpc
from volttron.platform.agent.known_identities import AUTH
from volttron.platform.keystore import KeyStore

_auth_entry1 = AuthEntry(
    domain='test1_domain', address='test1_address', mechanism='NULL',
    user_id='test1_userid', identity='test_userid', groups=['test1_group1', 'test1_group2'],
    roles=['test1_role1', 'test1_role2'],
    capabilities=['test1_cap1', 'test1_cap2'],
    comments='test1 comment', enabled=True)

_auth_entry2 = AuthEntry(
    domain='test2_domain', address='test2_address', mechanism='NULL',
    user_id='test2_userid', identity='test2_userid', groups=['test2_group1', 'test2_group2'],
    roles=['test2_role1', 'test2_role2'],
    capabilities=['test2_cap1', 'test2_cap2'],
    comments='test2 comment', enabled=True)

_auth_entry3 = AuthEntry(
    domain='test3_domain', address='test3_address', mechanism='NULL',
    user_id='test3_userid', identity='test3_userid', groups=['test3_group1', 'test3_group2'],
    roles=['test3_role1', 'test3_role2'],
    capabilities=['test3_cap1', 'test3_cap2'],
    comments='test3 comment', enabled=True)

_auth_entry4 = AuthEntry(
    domain='test4_domain', address='test4_address', mechanism='NULL',
    user_id='test4_userid', identity='test4_userid', groups=['test4_group1', 'test4_group2'],
    roles=['test4_role1', 'test4_role2'],
    capabilities=['test4_cap1', 'test4_cap2'],
    comments='test4 comment', enabled=True)

_auth_entry5 = AuthEntry(
    domain='test5_domain', address='test5_address', mechanism='NULL',
    user_id='test5_userid', identity='test5_userid', groups=['test5_group1', 'test5_group2'],
    roles=['test5_role1', 'test5_role2'],
    capabilities=['test5_cap1', 'test5_cap2'],
    comments='test5 comment', enabled=True)

_auth_entry6 = AuthEntry(
    domain='test6_domain', address='test6_address', mechanism='NULL',
    user_id='test6_userid', identity='test6_userid', groups=['test6_group1', 'test6_group2'],
    roles=['test6_role1', 'test6_role2'],
    capabilities=['test6_cap1', 'test6_cap2'],
    comments='test6 comment', enabled=True)

_auth_entry7 = AuthEntry(
    domain='test7_domain', address='test7_address', mechanism='NULL',
    user_id='test7_userid', identity='test7_userid', groups=['test7_group1', 'test7_group2'],
    roles=['test7_role1', 'test7_role2'],
    capabilities=['test7_cap1', 'test7_cap2'],
    comments='test7 comment', enabled=True)

_auth_entry8 = AuthEntry(
    domain='test8_domain', address='test8_address', mechanism='NULL',
    user_id='test8_userid', identity='test8_userid', groups=['test8_group1', 'test8_group2'],
    roles=['test8_role1', 'test8_role2'],
    capabilities=['test8_cap1', 'test8_cap2'],
    comments='test8 comment', enabled=True)


def auth_list(platform):
    with with_os_environ(platform.env):
        return subprocess.check_output(['volttron-ctl', 'auth', 'list'], env=platform.env, universal_newlines=True)


def auth_list_json(platform):
    output = auth_list(platform)
    entries = re.findall(r'\nINDEX: \d+(\n{.*?\n}\n)', output, re.DOTALL)
    return [jsonapi.loads(entry) for entry in entries]


def entry_to_input_string(domain='', address='', user_id='', identity='',
                          capabilities='', rpc_method_authorizations='',
                          roles='', groups='', mechanism="NULL", credentials='',
                          comments='', enabled=''):
    inputs = []
    inputs.append(domain)
    inputs.append(address)
    inputs.append(user_id)
    inputs.append(identity)
    inputs.append(','.join(capabilities))
    inputs.append(','.join(roles))
    inputs.append(','.join(groups))
    inputs.append(mechanism)
    inputs.append(credentials or '')
    inputs.append(comments)

    if isinstance(enabled, bool):
        enabled = 'True' if enabled else 'False'
    inputs.append(enabled)
    print(inputs)
    return '\n'.join(inputs) + '\n'


def auth_add(platform, entry):
    with with_os_environ(platform.env):
        p = subprocess.Popen(['volttron-ctl', 'auth', 'add'], env=platform.env,
                             stdin=subprocess.PIPE, universal_newlines=True)
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
                args.extend(['--' + k, f"{jsonapi.dumps(v)}"])
            else:
                args.extend(['--' + k, v])

    if not enabled:
        args.append('--disabled')

    with with_os_environ(platform.env):
        print(args)
        p = subprocess.Popen(args, env=platform.env, stdin=subprocess.PIPE, universal_newlines=True)
        p.communicate()
        assert p.returncode == 0


def auth_remove(platform, index):
    with with_os_environ(platform.env):
        p = subprocess.Popen(['volttron-ctl', 'auth', 'remove', str(index)], env=platform.env,
                             stdin=subprocess.PIPE, universal_newlines=True)
        p.communicate(input='Y\n')
        assert p.returncode == 0


def auth_update(platform, index, **kwargs):
    with with_os_environ(platform.env):
        p = subprocess.Popen(['volttron-ctl', 'auth', 'update', str(index)], env=platform.env,
                             stdin=subprocess.PIPE, universal_newlines=True)
        p.communicate(input=entry_to_input_string(**kwargs))
        assert p.returncode == 0


def auth_rpc_method_add(platform, agent, method, auth_cap):
    with with_os_environ(platform.env):
        with subprocess.Popen(['volttron-ctl', 'auth', 'rpc', 'add', f'{agent}.{method}', auth_cap], env=platform.env,
                             stdin=subprocess.PIPE, universal_newlines=True) as p:
            out, err = p.communicate()
            assert p.returncode == 0
    print(f"Out is: {out}")
    print(f"ERROR is: {err}")

def auth_rpc_method_remove(platform, agent, method, auth_cap):
    with with_os_environ(platform.env):
        with subprocess.Popen(['volttron-ctl', 'auth', 'rpc', 'remove', f'{agent}.{method}', auth_cap], env=platform.env,
                             stdin=subprocess.PIPE, universal_newlines=True) as p:
            out, err = p.communicate()
            assert p.returncode == 0
    print(f"Out is: {out}")
    print(f"ERROR is: {err}")


class _RpcTarget(Agent):
    """An agent with one ungated export for the rpc add and remove tests."""

    @RPC.export
    def echo(self, value):
        return value


def _echo_refusal(caller, target_identity):
    """Returns None when caller's call to echo succeeds, else the error text."""
    try:
        result = caller.vip.rpc.call(target_identity, "echo", 7).get(timeout=2)
    except (jsonrpc.Error, jsonrpc.RemoteError) as err:
        return str(err)
    assert result == 7
    return None


def _wait_for_echo(caller, target_identity, refused, timeout=10):
    outcome = []

    def settled():
        outcome[:] = [_echo_refusal(caller, target_identity)]
        return (outcome[0] is not None) == refused

    poll_gevent_sleep(timeout, settled, 0.5)
    return outcome[0]


def _build_agent_once_authorized(platform, identity, **kwargs):
    """build_agent connects a fixed 4 s after writing the auth entry, which
    is too soon while the auth service is still pushing an earlier change.
    Write the same entry first and wait until the service has loaded it."""
    with with_os_environ(platform.env):
        publickey = KeyStore(KeyStore.get_agent_keystore_path(identity)).public
        AuthFile().add(AuthEntry(
            user_id=identity, identity=identity, credentials=publickey,
            capabilities={"edit_config_store": {"identity": identity}}),
            no_error=True)
    assert poll_gevent_sleep(
        30,
        lambda: platform.dynamic_agent.vip.rpc.call(
            AUTH, "get_authorizations", identity).get(timeout=5) is not None,
        0.5), f"auth service never loaded {identity}"
    return platform.build_agent(identity=identity, **kwargs)


def _build_rpc_target_and_caller(platform, suffix):
    target = _build_agent_once_authorized(
        platform, f"rpc_target_{suffix}", agent_class=_RpcTarget)
    caller = _build_agent_once_authorized(platform, f"rpc_caller_{suffix}")
    return target, caller


def assert_auth_entries_same(e1, e2):
    for field in ['domain', 'address', 'user_id', 'credentials', 'comments',
                  'enabled']:
        assert e1[field] == e2[field]
    for field in ['roles', 'groups']:
        assert set(e1[field]) == set(e2[field])
    assert e1['capabilities'] == e2['capabilities']


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


# Number of tries to check if auth file is updated properly
auth_retry = 5


@pytest.mark.control
def test_auth_list(auth_instance):
    output = auth_list(auth_instance)
    assert output.startswith('No entries in') or output.startswith('\nINDEX')


@pytest.mark.control
def test_auth_add(auth_instance):
    """Add a single entry"""
    platform = auth_instance
    entries = auth_list_json(platform)
    len_entries = len(entries)
    auth_add(platform, _auth_entry1)
    # Verify entry shows up in list
    entries = auth_list_json(platform)
    print(entries)
    assert len(entries) > 0
    i = 0
    while len(entries) <= len_entries and i < auth_retry:
        gevent.sleep(i)
        entries = auth_list_json(platform)
        i += 1

    assert_auth_entries_same(entries[-1], _auth_entry1.__dict__)


@pytest.mark.control
def test_auth_add_cmd_line(auth_instance):
    """Add a single entry, specifying parameters on the command line"""
    platform = auth_instance
    entries = auth_list_json(platform)
    len_entries = len(entries)
    auth_add_cmd_line(platform, _auth_entry2)
    # Verify entry shows up in list
    entries = auth_list_json(platform)
    print(entries)
    assert len(entries) > 0
    i = 0
    while len(entries) <= len_entries and i < auth_retry:
        gevent.sleep(i)
        entries = auth_list_json(platform)
        i += 1
    assert_auth_entries_same(entries[-1], _auth_entry2.__dict__)


@pytest.mark.control
def test_auth_update(auth_instance):
    """Add an entry then update it with a different entry"""
    platform = auth_instance
    entries = auth_list_json(platform)
    len_entries = len(entries)
    auth_add(platform, _auth_entry3)
    entries = auth_list_json(platform)
    print(entries)
    assert len(entries) > 0
    i = 0
    while len(entries) <= len_entries and i < auth_retry:
        gevent.sleep(i)
        entries = auth_list_json(platform)
        i += 1
    auth_update(platform, len(entries) - 1, **_auth_entry4.__dict__)
    gevent.sleep(4)
    entries = auth_list_json(platform)
    print(entries)
    assert_auth_entries_same(entries[-1], _auth_entry4.__dict__)
    gevent.sleep(1)


@pytest.mark.control
def test_auth_remove(auth_instance):
    """Add two entries then remove the last entry"""
    platform = auth_instance
    entries = auth_list_json(platform)
    len_entries = len(entries)
    auth_add(platform, _auth_entry5)
    entries = auth_list_json(platform)
    assert len(entries) > 0
    i = 0
    while len(entries) <= len_entries and i < auth_retry:
        gevent.sleep(i)
        entries = auth_list_json(platform)
        i += 1
    auth_add(platform, _auth_entry6)
    entries = auth_list_json(platform)
    assert len(entries) > 0
    i = 0
    while len(entries) <= (len_entries + 1) and i < auth_retry:
        gevent.sleep(i)
        entries = auth_list_json(platform)
        i += 1
    print(entries)
    auth_remove(platform, len(entries) - 1)
    gevent.sleep(1)

    # Verify _auth_entry6 was removed and _auth_entry5 remains
    entries = auth_list_json(platform)
    print(entries)
    assert len(entries) > 0
    i = 0
    while len(entries) > (len_entries + 1) and i < auth_retry:
        gevent.sleep(i)
        entries = auth_list_json(platform)
        i += 1
    assert_auth_entries_same(entries[-1], _auth_entry5.__dict__)


@pytest.mark.control
def test_auth_rpc_method_add(auth_instance):
    """Add an entry then update it with a different entry"""
    platform = auth_instance
    # The change must reach the running agent, not only the file: a caller
    # without the new capability is refused once it is pushed. Run first,
    # while no push to an agent that is not connected is still pending.
    target, caller = _build_rpc_target_and_caller(platform, "add")
    try:
        target_id = target.core.identity
        assert _echo_refusal(caller, target_id) is None
        auth_rpc_method_add(platform, target_id, 'echo', 'test_auth')
        refusal = _wait_for_echo(caller, target_id, refused=True)
        assert refusal is not None
        assert "method 'echo' requires capabilities {'test_auth'}" in refusal
    finally:
        caller.core.stop()
        target.core.stop()

    entries = auth_list_json(platform)
    len_entries = len(entries)
    auth_add(platform, _auth_entry7)
    entries = auth_list_json(platform)
    assert len(entries) > 0
    i = 0
    while len(entries) <= len_entries and i < auth_retry:
        gevent.sleep(i)
        entries = auth_list_json(platform)
        i += 1
    print(entries)

    auth_rpc_method_add(platform, 'test7_userid', 'test_method', 'test_auth')
    entries = auth_list_json(platform)
    print(entries[-1])

    i = 0
    while entries[-1]['rpc_method_authorizations'] != {'test_method': ["test_auth"]} and i < auth_retry:
        gevent.sleep(i)
        entries = auth_list_json(platform)
        i += 1

    assert entries[-1]['rpc_method_authorizations'] == {'test_method': ["test_auth"]}


@pytest.mark.control
def test_auth_rpc_method_remove(auth_instance):
    """Add an entry then update it with a different entry"""
    platform = auth_instance
    # Removing the last capability opens the method again on the running
    # agent, so the removal must be pushed as well as the addition.
    target, caller = _build_rpc_target_and_caller(platform, "remove")
    try:
        target_id = target.core.identity
        auth_rpc_method_add(platform, target_id, 'echo', 'test_auth')
        assert _wait_for_echo(caller, target_id, refused=True) is not None
        auth_rpc_method_remove(platform, target_id, 'echo', 'test_auth')
        assert _wait_for_echo(caller, target_id, refused=False) is None
    finally:
        caller.core.stop()
        target.core.stop()

    entries = auth_list_json(platform)
    len_entries = len(entries)
    auth_add(platform, _auth_entry8)
    entries = auth_list_json(platform)
    assert len(entries) > 0
    i = 0
    while len(entries) <= len_entries and i < auth_retry:
        gevent.sleep(i)
        entries = auth_list_json(platform)
        i += 1
    print(entries)

    auth_rpc_method_add(platform, 'test8_userid', 'test_method', 'test_auth')
    entries = auth_list_json(platform)
    print(entries[-1])

    i = 0
    while entries[-1]['rpc_method_authorizations'] != {'test_method': ["test_auth"]} and i < auth_retry:
        gevent.sleep(i)
        entries = auth_list_json(platform)
        i += 1

    assert entries[-1]['rpc_method_authorizations'] == {'test_method': ["test_auth"]}

    auth_rpc_method_remove(platform, 'test8_userid', 'test_method', 'test_auth')
    entries = auth_list_json(platform)
    print(entries[-1])

    i = 0
    while entries[-1]['rpc_method_authorizations'] == {'test_method': ["test_auth"]} and i < auth_retry:
        gevent.sleep(i)
        entries = auth_list_json(platform)
        i += 1

    assert entries[-1]['rpc_method_authorizations'] != {'test_method': ["test_auth"]}


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
def test_known_host_cmds(auth_instance):
    platform = auth_instance
    host = '1.2.3.4:5678'
    key = 'w-mKufe5hiRSPKK2LnkK_Z9VwRPMohdafhS6IekxYE7'
    _add_known_host(platform, host, key)

    hosts = _list_known_hosts(platform)
    assert hosts[host] == key

    _remove_known_host(platform, host)
    hosts = _list_known_hosts(platform)
    assert host not in hosts


def _add_known_host(platform, host, serverkey):
    with with_os_environ(platform.env):
        args = ['volttron-ctl', 'auth', 'add-known-host']
        args.extend(['--host', host])
        args.extend(['--serverkey', serverkey])
        p = subprocess.Popen(args, env=platform.env, stdin=subprocess.PIPE, universal_newlines=True)
        p.communicate()
        assert p.returncode == 0


def _list_known_hosts(platform):
    with with_os_environ(platform.env):
        output = subprocess.check_output(['volttron-ctl', 'auth',
                                          'list-known-hosts'], env=platform.env, universal_newlines=True)

        lines = output.split('\n')
        dict_ = {}
        for line in lines[2:-1]: # skip two header lines and last (empty) line
            host, pubkey = ' '.join(line.split()).split() # combine multiple spaces
            dict_[host] = pubkey
        return dict_


def _remove_known_host(platform, host):
    with with_os_environ(platform.env):
        args = ['volttron-ctl', 'auth', 'remove-known-host', host]
        p = subprocess.Popen(args, env=platform.env, stdin=subprocess.PIPE, universal_newlines=True)
        p.communicate()
        assert p.returncode == 0


@pytest.fixture()
def mock_auth_service():
    AuthService.__bases__ = (AgentMock.imitate(Agent, Agent()), )
    auth_service = AuthService(
        auth_file=MagicMock(), protected_topics_file=MagicMock(), setup_mode=MagicMock(), aip=MagicMock())
    auth_service.authentication_server = ZMQServerAuthentication(auth_service=auth_service)
    auth_service.authorization_server = ZMQAuthorization(auth_service=auth_service)
    yield auth_service


@pytest.fixture()
def mock_zmq_credential():
    auth = {
        "domain": "test_domain",
        "address": "test_address",
        "mechanism": "NULL",
        "credentials": None,
        "user_id": "test_auth",
        "capabilities": ["test_caps"],
        "groups": ["test_group"],
        "roles": ["test_roles"],
        "comments": "test_comment"
    }
    yield auth


def test_get_authorization_pending(mock_auth_service, mock_zmq_credential):
    mock_auth = mock_auth_service
    auth = mock_zmq_credential
    mock_auth.authentication_server._update_auth_pending(
        auth['domain'], auth['address'], auth['mechanism'], auth['credentials'], auth['user_id'])
    auth_pending = mock_auth.get_pending_authorizations()[0]
    assert auth['domain'] == auth_pending['domain']
    assert auth['address'] == auth_pending['address']
    assert auth['mechanism'] == auth_pending['mechanism']
    assert auth['credentials'] == auth_pending['credentials']
    assert auth['user_id'] == auth_pending['user_id']
    assert auth_pending['retries'] == 1


@pytest.mark.control
def test_approve_authorization_failure(mock_auth_service, mock_zmq_credential):
    mock_auth = mock_auth_service
    auth = mock_zmq_credential
    mock_auth.authentication_server._update_auth_pending(
        auth['domain'], auth['address'], auth['mechanism'], auth['credentials'], auth['user_id'])
    assert len(mock_auth._auth_pending) == 1

    mock_auth.approve_authorization(auth['user_id'])
    assert len(mock_auth.auth_entries) == 0

    mock_auth.read_auth_file()
    assert len(mock_auth.auth_entries) == 1
    assert len(mock_auth._auth_approved) == 1
    assert len(mock_auth._auth_pending) == 0


@pytest.mark.control
def test_deny_approved_authorization(mock_auth_service, mock_zmq_credential):
    mock_auth = mock_auth_service
    auth = mock_zmq_credential
    mock_auth.authentication_server._update_auth_pending(
        auth['domain'], auth['address'], auth['mechanism'], auth['credentials'], auth['user_id'])
    assert len(mock_auth._auth_pending) == 1
    assert len(mock_auth._auth_approved) == 0

    mock_auth.approve_authorization(auth['user_id'])
    mock_auth.read_auth_file()
    assert len(mock_auth.auth_entries) == 1
    assert len(mock_auth._auth_approved) == 1

    mock_auth.deny_authorization(auth['user_id'])
    mock_auth.read_auth_file()
    assert len(mock_auth._auth_denied) == 1
    assert len(mock_auth._auth_approved) == 0
    assert len(mock_auth.auth_entries) == 0


@pytest.mark.control
def test_delete_approved_authorization(mock_auth_service, mock_zmq_credential):
    mock_auth = mock_auth_service
    auth = mock_zmq_credential
    mock_auth.authentication_server._update_auth_pending(
        auth['domain'], auth['address'], auth['mechanism'], auth['credentials'], auth['user_id'])
    assert len(mock_auth._auth_pending) == 1
    assert len(mock_auth._auth_approved) == 0

    mock_auth.approve_authorization(auth['user_id'])
    assert len(mock_auth.auth_entries) == 0
    mock_auth.read_auth_file()
    assert len(mock_auth._auth_approved) == 1
    assert len(mock_auth._auth_pending) == 0
    assert len(mock_auth.auth_entries) == 1

    mock_auth.delete_authorization(auth['user_id'])
    mock_auth.read_auth_file()
    assert len(mock_auth._auth_approved) == 0
    assert len(mock_auth.auth_entries) == 0


@pytest.mark.control
def test_approve_denied_authorization(mock_auth_service, mock_zmq_credential):
    mock_auth = mock_auth_service
    auth = mock_zmq_credential
    mock_auth.authentication_server._update_auth_pending(
        auth['domain'], auth['address'], auth['mechanism'], auth['credentials'], auth['user_id'])
    assert len(mock_auth._auth_pending) == 1
    assert len(mock_auth._auth_denied) == 0

    mock_auth.deny_authorization(auth['user_id'])
    mock_auth.read_auth_file()
    assert len(mock_auth._auth_denied) == 1
    assert len(mock_auth._auth_pending) == 0

    mock_auth.approve_authorization(auth['user_id'])
    assert len(mock_auth.auth_entries) == 0
    mock_auth.read_auth_file()
    assert len(mock_auth._auth_approved) == 1
    assert len(mock_auth.auth_entries) == 1
    assert len(mock_auth._auth_denied) == 0


@pytest.mark.control
def test_deny_authorization_failure(mock_auth_service, mock_zmq_credential):
    mock_auth = mock_auth_service
    auth = mock_zmq_credential
    mock_auth.authentication_server._update_auth_pending(
        auth['domain'], auth['address'], auth['mechanism'], auth['credentials'], auth['user_id'])
    assert len(mock_auth._auth_pending) == 1
    assert len(mock_auth._auth_denied) == 0

    mock_auth.deny_authorization(auth['user_id'])
    mock_auth.read_auth_file()
    assert len(mock_auth._auth_denied) == 1
    assert len(mock_auth._auth_pending) == 0


@pytest.mark.control
def test_delete_authorization_failure(mock_auth_service, mock_zmq_credential):
    mock_auth = mock_auth_service
    auth = mock_zmq_credential
    mock_auth.authentication_server._update_auth_pending(
        auth['domain'], auth['address'], auth['mechanism'], auth['credentials'], auth['user_id'])
    assert len(mock_auth._auth_pending) == 1
    assert len(mock_auth._auth_denied) == 0
    mock_auth.delete_authorization(auth['user_id'])

    assert len(mock_auth._auth_pending) == 0
    assert len(mock_auth._auth_denied) == 0


@pytest.mark.control
def test_delete_denied_authorization(mock_auth_service, mock_zmq_credential):
    mock_auth = mock_auth_service
    auth = mock_zmq_credential
    mock_auth.authentication_server._update_auth_pending(
        auth['domain'], auth['address'], auth['mechanism'], auth['credentials'], auth['user_id'])
    assert len(mock_auth._auth_pending) == 1
    assert len(mock_auth._auth_denied) == 0

    mock_auth.deny_authorization(auth['user_id'])
    mock_auth.read_auth_file()
    assert len(mock_auth._auth_denied) == 1
    assert len(mock_auth._auth_pending) == 0

    mock_auth.delete_authorization(auth['user_id'])
    mock_auth.read_auth_file()
    assert len(mock_auth._auth_denied) == 0
