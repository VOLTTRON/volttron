"""Unit tests for the VolttronCentralPlatform request surface.

They build the agents without a platform and call the methods directly, so
the checks run on the code path an incoming call takes.
"""
import base64
import os
import types
from unittest import mock

import pytest

from volttron.platform import jsonrpc
from vcplatform import agent as vcp_agent
from vcplatform.agent import MAX_UPLOAD_BYTES, VolttronCentralPlatform
from vcplatform.vcconnection import VCConnection

VC_USER = 'volttron.central'


def _connection(user):
    conn = object.__new__(VCConnection)
    conn._main_agent = mock.MagicMock()
    conn._log = mock.MagicMock()
    context = types.SimpleNamespace(vip_message=types.SimpleNamespace(user=user))
    conn.vip = types.SimpleNamespace(
        rpc=types.SimpleNamespace(context=context))
    return conn


def _exported_names():
    return sorted(name for name in dir(VCConnection)
                  if 'rpc.exports' in getattr(
                      getattr(VCConnection, name), '_annotations', {}))


# Arguments that satisfy each export's signature.
EXPORT_ARGS = {
    'start_bacnet_scan': ('topic', 'proxy'),
    'get_instance_uuid': (),
    'get_health': (),
    'start_agent': ('u',),
    'stop_agent': ('u',),
    'restart': ('u',),
    'agent_status': ('u',),
    'status_agents': (),
    'get_devices': (),
    'publish_bacnet_props': ('proxy', 'topic', 'addr', 1),
    'store_agent_config': ('id', 'name', 'raw'),
    'list_agent_configs': ('id',),
    'get_agent_config': ('id', 'name'),
    'delete_agent_config': ('id', 'name'),
    'subscribe_to_vcp': ('status', 'platforms/x'),
    'route_to_agent_method': (1, 'list_agents', {}),
    'get_vip_addresses': (),
    'get_instance_name': (),
    'restart_agent': ('u',),
    'list_agents': (),
}


def test_connection_exports_are_the_expected_set():
    assert _exported_names() == sorted(EXPORT_ARGS)


@pytest.mark.parametrize('name', sorted(EXPORT_ARGS))
@pytest.mark.parametrize('user', ['evil.agent', '', None, 'volttron.central2'])
def test_connection_refuses_every_export_for_other_callers(name, user, caplog):
    conn = _connection(user)
    with pytest.raises(Exception) as err:
        getattr(conn, name)(*EXPORT_ARGS[name])
    assert 'may only be called by volttron.central' in str(err.value)
    assert conn._main_agent.mock_calls == []
    assert any(r.levelname == 'WARNING' and name in r.getMessage()
               for r in caplog.records)


@pytest.mark.parametrize('name', sorted(EXPORT_ARGS))
def test_connection_allows_volttron_central(name):
    conn = _connection(VC_USER)
    getattr(conn, name)(*EXPORT_ARGS[name])
    assert conn._main_agent.mock_calls != []


def test_connection_refuses_when_caller_cannot_be_identified():
    conn = _connection(VC_USER)
    conn.vip = types.SimpleNamespace(rpc=types.SimpleNamespace(context=None))
    with pytest.raises(Exception):
        conn.list_agents()
    assert conn._main_agent.mock_calls == []


def test_call_and_install_agent_stay_as_methods_but_are_not_exported():
    exported = _exported_names()
    assert 'call' not in exported
    assert 'install_agent' not in exported
    conn = _connection(VC_USER)
    conn._main_agent.call.return_value = 'ok'
    # The in-process install path still reaches the main agent.
    assert conn.call('list_agents') == 'ok'
    conn._main_agent.call.assert_called_once_with('list_agents')
    assert callable(conn.install_agent)
    assert callable(conn.kill)


def _vcp():
    vcp = object.__new__(VolttronCentralPlatform)
    vcp.vip = mock.MagicMock()
    vcp._vc_connection = mock.MagicMock()
    return vcp


UNKNOWN_METHODS = [
    'historian.delete_all',
    'historian.query',
    'platforms.uuid.U.config_store.set_config',
    'x.y.U.store_agent_config',
    'U.some_method',
    'set_setting',
    'get_setting',
    'edit_config_store',
    '',
]


@pytest.mark.parametrize('method', UNKNOWN_METHODS)
def test_route_request_refuses_methods_outside_the_fixed_set(method):
    vcp = _vcp()
    result = vcp.route_request(7, method, {'a': 1})
    assert result['error']['code'] == jsonrpc.METHOD_NOT_FOUND
    assert result['id'] == 7
    assert vcp.vip.mock_calls == []


def test_route_request_known_methods_still_route():
    vcp = _vcp()
    vcp.list_agents = mock.Mock(return_value=['a'])
    vcp.get_devices = mock.Mock(return_value={'d': 1})
    assert vcp.route_request(1, 'list_agents', None) == ['a']
    assert vcp.route_request(1, 'get_devices', None) == {'d': 1}

    vcp.vip.rpc.call.return_value.get.return_value = (1234, None)
    assert vcp.route_request(1, 'start_agent', ['uuid-1']) == {
        'process_id': 1234, 'return_code': None}
    vcp.vip.rpc.call.assert_called_once_with('control', 'start_agent',
                                             'uuid-1')


def test_bacnet_scan_gets_only_named_arguments():
    vcp = _vcp()
    vcp.start_bacnet_scan = mock.Mock(return_value=None)
    vcp.route_request(3, 'start_bacnet_scan', {
        'iam_vc_response_topic': 'iam/x', 'proxy_identity': 'proxy',
        'low_device_id': 1, 'high_device_id': 9, 'target_address': '1.2.3.4',
        'scan_length': 2, 'instance_address': 'tcp://evil:1',
        'instance_serverkey': 'k'})
    vcp.start_bacnet_scan.assert_called_once_with(
        iam_vc_response_topic='iam/x', proxy_identity='proxy',
        low_device_id=1, high_device_id=9, target_address='1.2.3.4',
        scan_length=2)


@pytest.mark.parametrize('params', [None, [], {'proxy_identity': 'p'},
                                    {'iam_vc_response_topic': 't'}])
def test_bacnet_scan_missing_values_are_invalid_params(params):
    vcp = _vcp()
    vcp.start_bacnet_scan = mock.Mock()
    result = vcp.route_request(3, 'start_bacnet_scan', params)
    assert result['error']['code'] == jsonrpc.INVALID_PARAMS
    vcp.start_bacnet_scan.assert_not_called()


def test_publish_bacnet_props_gets_only_named_arguments():
    vcp = _vcp()
    vcp.publish_bacnet_props = mock.Mock(return_value='PUBLISHING')
    result = vcp.route_request(3, 'publish_bacnet_props', {
        'proxy_identity': 'p', 'publish_topic': 't', 'address': 'a',
        'device_id': 5, 'filter': ['x'], 'extra': 'ignored'})
    assert result == 'PUBLISHING'
    vcp.publish_bacnet_props.assert_called_once_with('p', 't', 'a', 5,
                                                     filter=['x'])


def test_publish_bacnet_props_missing_values_are_invalid_params():
    vcp = _vcp()
    vcp.publish_bacnet_props = mock.Mock()
    result = vcp.route_request(3, 'publish_bacnet_props', {'address': 'a'})
    assert result['error']['code'] == jsonrpc.INVALID_PARAMS
    vcp.publish_bacnet_props.assert_not_called()


def _upload(name='agent.whl', data=b'wheel-bytes', prefix='data:x;base64,'):
    return {'file_name': name,
            'file': prefix + base64.b64encode(data).decode('ascii')}


@pytest.fixture
def installer():
    vcp = _vcp()
    seen = {}

    def fake_install(opts):
        with open(opts.install_path, 'rb') as fin:
            seen['bytes'] = fin.read()
        seen['path'] = opts.install_path
        seen['mode'] = os.stat(opts.install_path).st_mode & 0o777
        return 'new-uuid'

    with mock.patch.object(vcp_agent, 'install_agent_local',
                           side_effect=fake_install) as fake:
        yield vcp, fake, seen


def test_valid_upload_installs_the_decoded_bytes(installer):
    vcp, fake, seen = installer
    result = vcp._install_agent(_upload(data=b'abc123'))
    assert result == {'uuid': 'new-uuid'}
    assert seen['bytes'] == b'abc123'
    assert os.path.basename(seen['path']) == 'agent.whl'
    assert seen['mode'] == 0o600
    assert fake.call_args[0][0].install_path == seen['path']
    assert not os.path.exists(os.path.dirname(seen['path']))


def _assert_refused(vcp, fake, fileargs, message=None):
    with mock.patch.object(vcp_agent.tempfile, 'mkdtemp') as mkdtemp:
        result = vcp._install_agent(fileargs)
    assert result['error']['code'] == jsonrpc.INVALID_PARAMS
    if message is not None:
        assert result['error']['message'] == message
    fake.assert_not_called()
    mkdtemp.assert_not_called()


def test_local_key_is_refused(installer):
    vcp, fake, _ = installer
    args = _upload()
    args['local'] = True
    _assert_refused(vcp, fake, args,
                    "The 'local' install option is not accepted.")


@pytest.mark.parametrize('name', [
    '', '.', '..', '../evil.whl', 'a/b.whl', '/abs.whl', 'nul\0.whl',
    'dir/..'])
def test_bad_file_names_are_refused(installer, name):
    vcp, fake, _ = installer
    args = _upload()
    args['file_name'] = name
    _assert_refused(vcp, fake, args, 'Invalid file_name.')


@pytest.mark.parametrize('name', [7, None, ['a'], {'a': 1}])
def test_non_string_file_names_are_refused(installer, name):
    vcp, fake, _ = installer
    args = _upload()
    args['file_name'] = name
    _assert_refused(vcp, fake, args, 'file_name and file must be strings.')


@pytest.mark.parametrize('blob', [7, None, ['x'], b'base64,AAAA'])
def test_non_string_file_is_refused(installer, blob):
    vcp, fake, _ = installer
    args = _upload()
    args['file'] = blob
    _assert_refused(vcp, fake, args, 'file_name and file must be strings.')


def test_file_without_base64_marker_is_refused(installer):
    vcp, fake, _ = installer
    args = _upload()
    args['file'] = 'AAAA'
    _assert_refused(vcp, fake, args, 'File must be base64 encoded.')


@pytest.mark.parametrize('fileargs', [None, [], 'text', 3])
def test_non_dict_file_arguments_are_refused(installer, fileargs):
    vcp, fake, _ = installer
    _assert_refused(vcp, fake, fileargs, 'Invalid file arguments.')


def test_upload_at_the_bound_is_accepted_and_one_byte_over_is_refused(
        installer):
    vcp, fake, seen = installer
    at_bound = _upload(data=b'\0' * MAX_UPLOAD_BYTES)
    assert vcp._install_agent(at_bound) == {'uuid': 'new-uuid'}
    assert len(seen['bytes']) == MAX_UPLOAD_BYTES
    fake.reset_mock()
    over = _upload(data=b'\0' * (MAX_UPLOAD_BYTES + 1))
    _assert_refused(vcp, fake, over, 'File is larger than the upload limit.')


def test_oversized_encoded_text_is_refused_before_decoding(installer):
    vcp, fake, _ = installer
    args = {'file_name': 'a.whl',
            'file': 'base64,' + 'A' * (4 * -(-MAX_UPLOAD_BYTES // 3) + 4)}
    with mock.patch.object(vcp_agent.base64, 'decodebytes') as decode:
        _assert_refused(vcp, fake, args,
                        'File is larger than the upload limit.')
    decode.assert_not_called()


def test_file_name_resolving_outside_the_temp_dir_is_refused(installer, tmp_path):
    vcp, fake, _ = installer
    outside = str(tmp_path / 'elsewhere')
    real = os.path.realpath

    def fake_realpath(path):
        return outside if path.endswith('agent.whl') else real(path)

    with mock.patch.object(vcp_agent.os.path, 'realpath',
                           side_effect=fake_realpath):
        result = vcp._install_agent(_upload())
    assert 'error' in result
    fake.assert_not_called()


def test_existing_file_is_never_overwritten(installer):
    vcp, fake, _ = installer
    real_open = os.open
    flags_seen = []

    def spy(path, flags, *args, **kwargs):
        flags_seen.append(flags)
        return real_open(path, flags, *args, **kwargs)

    with mock.patch.object(vcp_agent.os, 'open', side_effect=spy):
        vcp._install_agent(_upload())
    assert flags_seen
    assert flags_seen[0] & os.O_EXCL
    assert flags_seen[0] & os.O_NOFOLLOW
    assert flags_seen[0] & os.O_CREAT
