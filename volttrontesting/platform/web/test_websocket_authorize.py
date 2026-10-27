"""A websocket is authorized by its owning agent before the upgrade, the
owner's answer when a socket opens is honored, and the web subsystem and the
platform's user check behave as the owner needs."""

import logging
from unittest.mock import MagicMock

import gevent
import pytest

from volttron.platform.agent.known_identities import PLATFORM_WEB, VOLTTRON_CENTRAL
from volttron.platform.vip.agent.subsystems.web import WebSubSystem
from volttron.platform.web.authenticate_endpoint import AuthenticateEndpoints
from volttron.platform.web.webapp import WebApplicationWrapper
from volttrontesting.platform.web.conftest import set_caller

ENDPOINT = '/vc/ws/channel-id/configure'
OWNER = 'volttron.central'


def make_environ(**extra):
    environ = {
        'PATH_INFO': ENDPOINT,
        'REMOTE_ADDR': '10.1.2.3',
        'HTTP_HOST': 'vc.example:8443',
        'HTTP_ORIGIN': 'https://vc.example:8443',
        'HTTP_COOKIE': 'bearer=platform-token; vcsession=abc123; theme=dark',
        'HTTP_AUTHORIZATION': 'Bearer secret',
        'wsgi.input': object(),
    }
    environ.update(extra)
    return environ


@pytest.fixture()
def app():
    platformweb = MagicMock()
    wrapper = WebApplicationWrapper(platformweb, 'localhost', 8080)
    wrapper.ws = MagicMock(return_value=['upgraded'])
    wrapper.create_ws_endpoint(ENDPOINT, OWNER)
    return wrapper


def answer(app, value=None, error=None):
    """Make the owner's next rpc answer value, or raise error from get()."""
    result = app.platformweb.vip.rpc.call.return_value
    if error is not None:
        result.get.side_effect = error
    else:
        result.get.return_value = value
    return result


def request_to(app, environ=None):
    start_response = MagicMock()
    environ = make_environ() if environ is None else environ
    body = app(environ, start_response)
    return body, start_response


# Pre-upgrade authorization in WebApplicationWrapper.__call__


def test_upgrade_proceeds_only_when_the_owner_answers_true(app):
    answer(app, True)
    body, start_response = request_to(app)
    assert body == ['upgraded']
    assert app.ws.call_count == 1
    assert start_response.call_count == 0


@pytest.mark.parametrize('value', [False, None, 1, 'yes', {'ok': True}, []])
def test_any_answer_but_true_is_forbidden(app, value):
    answer(app, value)
    body, start_response = request_to(app)
    assert start_response.call_args[0][0].startswith('403')
    assert app.ws.call_count == 0
    assert b'upgraded' not in b''.join(body)


@pytest.mark.parametrize('error', [
    RuntimeError('remote failed'),
    gevent.Timeout(0.01),
    PermissionError('not allowed'),
])
def test_an_error_or_timeout_from_the_owner_is_forbidden(app, error):
    answer(app, error=error)
    _, start_response = request_to(app)
    assert start_response.call_args[0][0].startswith('403')
    assert app.ws.call_count == 0


def test_the_owner_is_asked_with_a_fixed_subset_and_a_ten_second_wait(app):
    result = answer(app, True)
    request_to(app)
    args = app.platformweb.vip.rpc.call.call_args[0]
    assert args[0] == OWNER
    assert args[1] == 'client.authorize'
    assert args[2] == {
        'REMOTE_ADDR': '10.1.2.3',
        'PATH_INFO': ENDPOINT,
        'HTTP_HOST': 'vc.example:8443',
        'HTTP_ORIGIN': 'https://vc.example:8443',
        'HTTP_COOKIE': 'vcsession=abc123; theme=dark',
    }
    result.get.assert_called_once_with(timeout=10)


def test_absent_request_fields_are_left_out_of_the_subset(app):
    answer(app, True)
    environ = make_environ()
    for key in ('HTTP_ORIGIN', 'HTTP_COOKIE'):
        del environ[key]
    request_to(app, environ)
    subset = app.platformweb.vip.rpc.call.call_args[0][2]
    assert 'HTTP_ORIGIN' not in subset
    assert 'HTTP_COOKIE' not in subset
    assert subset['PATH_INFO'] == ENDPOINT


def test_an_unregistered_path_is_not_asked_and_goes_to_routing(app):
    app.platformweb.app_routing.return_value = ['routed']
    body, _ = request_to(app, make_environ(PATH_INFO='/other/ws'))
    assert body == ['routed']
    assert app.platformweb.vip.rpc.call.call_count == 0
    assert app.ws.call_count == 0


def test_a_refusal_logs_one_warning_with_owner_and_first_segment_only(app, caplog):
    answer(app, False)
    with caplog.at_level(logging.DEBUG, logger='volttron.platform.web.webapp'):
        request_to(app)
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    text = warnings[0].getMessage()
    assert OWNER in text
    assert 'vc' in text
    for secret in ('channel-id', 'configure', 'vcsession', 'abc123', 'platform-token'):
        assert secret not in ' '.join(r.getMessage() for r in caplog.records)


def test_an_error_refusal_logs_one_warning_without_the_request(app, caplog):
    answer(app, error=RuntimeError('boom'))
    with caplog.at_level(logging.DEBUG, logger='volttron.platform.web.webapp'):
        request_to(app)
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert 'abc123' not in warnings[0].getMessage()
    assert 'channel-id' not in warnings[0].getMessage()


# client_opened: the owner's answer counts


def opened_client(app):
    client = MagicMock()
    client.environ = {'REMOTE_ADDR': '10.1.2.3'}
    app.client_opened(client, ENDPOINT, OWNER)
    return client


def test_opened_waits_ten_seconds_for_the_answer(app):
    result = answer(app, True)
    opened_client(app)
    result.get.assert_called_once_with(timeout=10)


@pytest.mark.parametrize('value', [True, None])
def test_true_and_none_keep_the_socket_open(app, value):
    answer(app, value)
    client = opened_client(app)
    assert client.close.call_count == 0
    assert (OWNER, client) in app.endpoint_clients[ENDPOINT]


def test_false_closes_the_socket_and_lists_no_client(app):
    answer(app, False)
    client = opened_client(app)
    assert client.close.call_count == 1
    assert app.endpoint_clients[ENDPOINT] == set()


@pytest.mark.parametrize('error', [RuntimeError('boom'), gevent.Timeout(0.01)])
def test_error_or_timeout_closes_the_socket(app, error):
    answer(app, error=error)
    client = opened_client(app)
    assert client.close.call_count == 1
    assert app.endpoint_clients[ENDPOINT] == set()


# Agent web subsystem


@pytest.fixture()
def subsystem():
    rpc = MagicMock()
    rpc.context.vip_message.user = PLATFORM_WEB
    web = WebSubSystem(MagicMock(), MagicMock(), rpc)
    return web, rpc


def register(web, endpoint=ENDPOINT, **callbacks):
    web.register_websocket(endpoint, **callbacks)


def test_authorize_callback_gets_the_request_and_its_answer_is_returned(subsystem):
    web, _ = subsystem
    seen = []

    def authorize(request):
        seen.append(request)
        return True

    register(web, authorize=authorize)
    request = {'PATH_INFO': ENDPOINT, 'REMOTE_ADDR': '10.1.2.3'}
    assert web._authorize(request) is True
    assert seen == [request]


def test_authorize_callback_answer_is_not_coerced(subsystem):
    web, _ = subsystem
    register(web, authorize=lambda request: 'yes')
    assert web._authorize({'PATH_INFO': ENDPOINT}) == 'yes'


def test_authorize_callback_false_is_returned(subsystem):
    web, _ = subsystem
    register(web, authorize=lambda request: False)
    assert web._authorize({'PATH_INFO': ENDPOINT}) is False


def test_no_authorize_callback_means_true(subsystem):
    web, _ = subsystem
    register(web, opened=lambda ip, endpoint: True)
    assert web._authorize({'PATH_INFO': ENDPOINT}) is True


def test_unknown_endpoint_is_not_authorized(subsystem):
    web, _ = subsystem
    register(web, authorize=lambda request: True)
    assert web._authorize({'PATH_INFO': '/vc/ws/other'}) is False


@pytest.mark.parametrize('request_', [None, 'text', {}, {'PATH_INFO': None}, {'PATH_INFO': ['x']}])
def test_a_malformed_request_is_not_authorized(subsystem, request_):
    web, _ = subsystem
    register(web, authorize=lambda request: True)
    assert web._authorize(request_) is False


def test_only_platform_web_may_ask(subsystem, caplog):
    web, rpc = subsystem
    calls = []
    register(web, authorize=lambda request: calls.append(request) or True)
    rpc.context.vip_message.user = 'rogue.agent'
    with caplog.at_level(logging.DEBUG, logger='volttron.platform.vip.agent.subsystems.web'):
        assert web._authorize({'PATH_INFO': ENDPOINT}) is False
    assert calls == []
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert 'rogue.agent' in warnings[0]


def test_client_authorize_is_exported_next_to_client_opened():
    rpc = MagicMock()
    core = MagicMock()
    WebSubSystem(MagicMock(), core, rpc)
    onsetup = core.onsetup.connect.call_args[0][0]
    onsetup(None)
    exported = {call[0][1]: call[0][0] for call in rpc.export.call_args_list}
    assert 'client.opened' in exported
    assert 'client.authorize' in exported


def test_opened_returns_the_registered_callbacks_answer_unchanged(subsystem):
    web, _ = subsystem
    sentinel = object()
    register(web, opened=lambda ip, endpoint: sentinel)
    assert web._opened('10.1.2.3', ENDPOINT) is sentinel
    register(web, opened=lambda ip, endpoint: False)
    assert web._opened('10.1.2.3', ENDPOINT) is False


def test_opened_without_a_callback_returns_none_for_a_known_endpoint(subsystem):
    web, _ = subsystem
    register(web)
    assert web._opened('10.1.2.3', ENDPOINT) is None


def test_opened_for_an_unknown_endpoint_returns_false(subsystem):
    web, _ = subsystem
    assert web._opened('10.1.2.3', '/nowhere') is False


def test_other_callbacks_still_work_with_the_wider_registration(subsystem):
    web, _ = subsystem
    events = []
    register(web, closed=lambda endpoint: events.append(('closed', endpoint)),
             received=lambda endpoint, message: events.append(('received', message)),
             authorize=lambda request: True)
    web._closed(ENDPOINT)
    web._message(ENDPOINT, 'hello')
    assert events == [('closed', ENDPOINT), ('received', 'hello')]


# authenticate_web_user


class FakeEndpoints(AuthenticateEndpoints):
    """AuthenticateEndpoints over a given user store, no file watcher."""

    def __init__(self, users):
        self._userdict = users


def hashed(password):
    from passlib.hash import argon2
    return argon2.hash(password)


@pytest.fixture()
def endpoints():
    return FakeEndpoints({
        'admin': {'hashed_password': hashed('s3cret'), 'groups': ['admin'],
                  'note': 'must not leave platform.web'},
        'viewer': {'hashed_password': hashed('look'), 'groups': ['reader', 'ops']},
        'blank': {'hashed_password': hashed(''), 'groups': ['admin']},
        'u' * 257: {'hashed_password': hashed('pw'), 'groups': ['admin']},
        'u' * 256: {'hashed_password': hashed('pw'), 'groups': ['reader']},
    })


def test_valid_credentials_return_exactly_user_and_groups(endpoints):
    assert endpoints.authenticate_web_user('admin', 's3cret') == {
        'user': 'admin', 'groups': ['admin']}
    assert endpoints.authenticate_web_user('viewer', 'look') == {
        'user': 'viewer', 'groups': ['reader', 'ops']}


def test_the_answer_is_a_copy_of_the_groups(endpoints):
    result = endpoints.authenticate_web_user('viewer', 'look')
    result['groups'].append('admin')
    assert endpoints._userdict['viewer']['groups'] == ['reader', 'ops']


@pytest.mark.parametrize('username,password', [
    ('admin', 'wrong'),
    ('nobody', 's3cret'),
    ('admin', ''),
    ('', 's3cret'),
    (None, 's3cret'),
    ('admin', None),
    (b'admin', 's3cret'),
    ('admin', b's3cret'),
    (['admin'], 's3cret'),
    ('admin', 5),
])
def test_bad_or_non_string_credentials_return_an_empty_dict(endpoints, username, password):
    assert endpoints.authenticate_web_user(username, password) == {}


def test_over_length_input_is_refused_before_any_hash_runs(endpoints, monkeypatch):
    calls = []
    monkeypatch.setattr('volttron.platform.web.authenticate_endpoint.argon2.verify',
                        lambda *args: calls.append(args) or True)
    assert endpoints.authenticate_web_user('a' * 257, 's3cret') == {}
    assert endpoints.authenticate_web_user('admin', 'p' * 1025) == {}
    assert calls == []
    assert endpoints.authenticate_web_user('admin', 'p' * 1024) == {
        'user': 'admin', 'groups': ['admin']}
    assert len(calls) == 1


def test_a_username_is_bounded_at_256_characters(endpoints):
    assert endpoints.authenticate_web_user('u' * 257, 'pw') == {}
    assert endpoints.authenticate_web_user('u' * 256, 'pw') == {
        'user': 'u' * 256, 'groups': ['reader']}


def test_an_empty_password_never_authenticates(endpoints):
    assert endpoints.authenticate_web_user('blank', '') == {}


def test_an_empty_store_returns_an_empty_dict():
    assert FakeEndpoints({}).authenticate_web_user('admin', 's3cret') == {}
    assert FakeEndpoints(None).authenticate_web_user('admin', 's3cret') == {}


def test_malformed_groups_return_an_empty_dict():
    users = {'odd': {'hashed_password': hashed('pw'), 'groups': 'admin'}}
    assert FakeEndpoints(users).authenticate_web_user('odd', 'pw') == {}


def test_the_service_keeps_its_authenticate_endpoints(web_service):
    assert isinstance(web_service._authenticate_endpoints, AuthenticateEndpoints)


def test_the_service_keeps_its_authenticate_endpoints_on_an_https_bind(tmp_path, monkeypatch):
    from unittest import mock
    from volttrontesting.platform.web.conftest import build_web_service, start_web_service
    service = build_web_service(tmp_path, monkeypatch, start=False)
    service.bind_web_address = 'https://127.0.0.1:8443'
    service.web_ssl_key = 'key.pem'
    service.web_ssl_cert = 'cert.pem'
    module = 'volttron.platform.web.platform_web_service.'
    with mock.patch(module + 'CertWrapper') as certs, \
            mock.patch(module + 'AdminEndpoints'), \
            mock.patch(module + 'AuthenticateEndpoints') as endpoints:
        certs.get_private_key.return_value = 'private'
        certs.get_cert_public_key.return_value = 'public'
        endpoints.return_value.get_routes.return_value = []
        start_web_service(service)
    endpoints.assert_called_once_with(tls_private_key='private', tls_public_key='public',
                                      revoked_sessions=service._revoked_sessions,
                                      on_revoke=service._session_revoked)
    assert service._authenticate_endpoints is endpoints.return_value


def test_the_service_answers_for_volttron_central(web_service):
    web_service._authenticate_endpoints = MagicMock()
    web_service._authenticate_endpoints.authenticate_web_user.return_value = {
        'user': 'admin', 'groups': ['admin']}
    set_caller(web_service, VOLTTRON_CENTRAL)
    assert web_service.authenticate_web_user('admin', 's3cret') == {
        'user': 'admin', 'groups': ['admin']}
    web_service._authenticate_endpoints.authenticate_web_user.assert_called_once_with(
        'admin', 's3cret')


def test_any_other_caller_is_refused_with_one_warning_naming_it(web_service, caplog):
    web_service._authenticate_endpoints = MagicMock()
    set_caller(web_service, 'rogue.agent')
    with caplog.at_level(logging.DEBUG, logger='volttron.platform.web.platform_web_service'):
        with pytest.raises(PermissionError):
            web_service.authenticate_web_user('admin-user-name', 'pw-secret-value')
    assert web_service._authenticate_endpoints.authenticate_web_user.call_count == 0
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert 'rogue.agent' in warnings[0]
    assert 'admin-user-name' not in ' '.join(r.getMessage() for r in caplog.records)
    assert 'pw-secret-value' not in ' '.join(r.getMessage() for r in caplog.records)


def test_the_check_runs_with_authentication_disabled(tmp_path, monkeypatch):
    from volttrontesting.platform.web.conftest import build_web_service
    service = build_web_service(tmp_path, monkeypatch, enable_auth=False)
    service._authenticate_endpoints = MagicMock()
    set_caller(service, 'rogue.agent')
    with pytest.raises(PermissionError):
        service.authenticate_web_user('admin', 'pw')
    assert service._authenticate_endpoints.authenticate_web_user.call_count == 0


def test_a_service_not_yet_started_answers_an_empty_dict(web_service):
    web_service._authenticate_endpoints = None
    set_caller(web_service, VOLTTRON_CENTRAL)
    assert web_service.authenticate_web_user('admin', 's3cret') == {}


# create_response: headers that crossed the bus as lists


def test_three_element_response_headers_reach_start_response_as_tuples(web_service):
    start_response = MagicMock()
    res = ['200 OK', 'body', [['Set-Cookie', 'vcsession=x; HttpOnly'], ['Content-Type', 'text/plain']]]
    body = web_service.create_response(res, start_response)
    status, headers = start_response.call_args[0]
    assert status == '200 OK'
    assert headers == [('Set-Cookie', 'vcsession=x; HttpOnly'), ('Content-Type', 'text/plain')]
    assert all(isinstance(header, tuple) for header in headers)
    assert body == [b'body']


def test_three_element_response_tuple_headers_still_work(web_service):
    start_response = MagicMock()
    web_service.create_response(['200 OK', b'raw', [('A', 'b')]], start_response)
    assert start_response.call_args[0][1] == [('A', 'b')]
