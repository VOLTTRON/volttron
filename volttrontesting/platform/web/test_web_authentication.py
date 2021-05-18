import json
from urllib.parse import urlencode

import gevent
from datetime import datetime, timedelta
from mock import MagicMock
from deepdiff import DeepDiff
import jwt
import pytest

from volttron.platform.agent.known_identities import AUTH
from volttron.platform.certs import CertWrapper
from volttron.platform.vip.agent import Agent
from volttron.utils import get_random_key
from volttrontesting.utils.platformwrapper import create_volttron_home
from volttrontesting.utils.utils import AgentMock
from volttrontesting.utils.web_utils import get_test_web_env
from volttron.platform.web.platform_web_service import PlatformWebService
from volttron.platform.web.admin_endpoints import AdminEndpoints
from volttron.platform.web.authenticate_endpoint import AuthenticateEndpoints
from volttrontesting.fixtures.cert_fixtures import certs_profile_1
from volttrontesting.fixtures.volttron_platform_fixtures import get_test_volttron_home


@pytest.mark.parametrize("encryption_type", ("private_key", "tls"))
def test_jwt_encode(encryption_type):
    with get_test_volttron_home(messagebus='zmq') as vhome:
        if encryption_type == "private_key":
            algorithm = "HS256"
            encoded_key = get_random_key().encode("utf-8")
        else:
            with certs_profile_1(vhome) as certs:
                algorithm = "RS256"
                encoded_key = CertWrapper.get_private_key(certs.server_certs[0].key_file)
        claims = {"woot": ["bah"], "all I want": 3210, "do it next": {"foo": "billy"}}
        token = jwt.encode(claims, encoded_key, algorithm)
        if encryption_type == 'tls':
            decode_key = CertWrapper.get_cert_public_key(certs.server_certs[0].cert_file)
            new_claimes = jwt.decode(token, decode_key, algorithm)
        else:
            new_claimes = jwt.decode(token, encoded_key, algorithm)

        assert not DeepDiff(claims, new_claimes)

# Child of AuthenticateEndpoints.
# Exactly the same but includes helper methods to set access and refresh token timeouts
class MockAuthenticateEndpoints(AuthenticateEndpoints):
    def set_refresh_token_timeout(self, timeout):
        self.refresh_token_timeout = timeout
    def set_access_token_timeout(self, timeout):
        self.access_token_timeout = timeout

# Setup test values for authenticate tests
def set_test_admin():
    authorize_ep = MockAuthenticateEndpoints(web_secret_key=get_random_key())
    authorize_ep.set_access_token_timeout(0.1)
    authorize_ep.set_refresh_token_timeout(0.2)
    AdminEndpoints().add_user("test_admin", "Pass123", groups=['admin'])
    test_user = {"username": "test_admin", "password": "Pass123"}
    gevent.sleep(1)
    return authorize_ep, test_user

def test_authenticate_get_request_fails():
    with get_test_volttron_home(messagebus='zmq'):
        authorize_ep, test_user = set_test_admin()
        env = get_test_web_env('/authenticate', method='GET')
        response = authorize_ep.handle_authenticate(env, test_user)
        assert ('Content-Type', 'text/plain') in response.headers.items()
        assert '405 Method Not Allowed' in response.status

def test_authenticate_post_request():
    with get_test_volttron_home(messagebus='zmq'):
        authorize_ep, test_user = set_test_admin()
        env = get_test_web_env('/authenticate', method='POST')
        response = authorize_ep.handle_authenticate(env, test_user)
        assert ('Content-Type', 'application/json') in response.headers.items()
        assert '200 OK' in response.status
        response_token = json.loads(response.response[0].decode('utf-8'))
        refresh_token = response_token['refresh_token']
        access_token = response_token["access_token"]
        assert 3 == len(refresh_token.split('.'))
        assert 3 == len(access_token.split("."))


def test_authenticate_put_request():
    with get_test_volttron_home(messagebus='zmq'):

        authorize_ep, test_user = set_test_admin()
        # Get tokens for test
        env = get_test_web_env('/authenticate', method='POST')
        response = authorize_ep.handle_authenticate(env, test_user)
        response_token = json.loads(response.response[0].decode('utf-8'))
        refresh_token = response_token['refresh_token']
        access_token = response_token["access_token"]

        # Test PUT Request
        env = get_test_web_env('/authenticate', method='PUT')
        env["HTTP_AUTHORIZATION"] = "BEARER " + refresh_token
        response = authorize_ep.handle_authenticate(env, data={})
        assert ('Content-Type', 'application/json') in response.headers.items()
        assert '200 OK' in response.status


def test_authenticate_put_request_access_expires():
    with get_test_volttron_home(messagebus='zmq'):

        authorize_ep, test_user = set_test_admin()
        # Get tokens for test
        env = get_test_web_env('/authenticate', method='POST')
        response = authorize_ep.handle_authenticate(env, test_user)
        response_token = json.loads(response.response[0].decode('utf-8'))
        refresh_token = response_token['refresh_token']
        access_token = response_token["access_token"]

        # Get access token after previous token expires. Verify they are different
        gevent.sleep(7)
        env = get_test_web_env('/authenticate', method='PUT')
        env["HTTP_AUTHORIZATION"] = "BEARER " + refresh_token
        response = authorize_ep.handle_authenticate(env, data={})
        assert ('Content-Type', 'application/json') in response.headers.items()
        assert '200 OK' in response.status
        assert access_token != json.loads(response.response[0].decode('utf-8'))["access_token"]

def test_authenticate_put_request_refresh_expires():
    with get_test_volttron_home(messagebus='zmq'):

        authorize_ep, test_user = set_test_admin()
        # Get tokens for test
        env = get_test_web_env('/authenticate', method='POST')
        response = authorize_ep.handle_authenticate(env, test_user)
        response_token = json.loads(response.response[0].decode('utf-8'))
        refresh_token = response_token['refresh_token']
        access_token = response_token["access_token"]

        # Wait for refresh token to expire
        gevent.sleep(20)
        env = get_test_web_env('/authenticate', method='PUT')
        env["HTTP_AUTHORIZATION"] = "BEARER " + refresh_token
        response = authorize_ep.handle_authenticate(env, data={})
        assert ('Content-Type', 'text/html') in response.headers.items()
        assert "401 Unauthorized" in response.status

def test_authenticate_delete_request():
    with get_test_volttron_home(messagebus='zmq'):
        authorize_ep, test_user = set_test_admin()
        # Get tokens for test
        env = get_test_web_env('/authenticate', method='POST')
        response = authorize_ep.handle_authenticate(env, test_user)

        # Touch Delete endpoint
        env = get_test_web_env('/authenticate', method='DELETE')
        response = authorize_ep.handle_authenticate(env, test_user)
        assert ('Content-Type', 'text/plain') in response.headers.items()
        assert '501 Not Implemented' in response.status


def test_no_private_key_or_passphrase():
    with pytest.raises(ValueError,
                       match="Must have either ssl_private_key or web_secret_key specified!"):
        authorizeep = AuthenticateEndpoints()


def test_both_private_key_and_passphrase():
    with pytest.raises(ValueError,
                       match="Must use either ssl_private_key or web_secret_key not both!"):
        with get_test_volttron_home(messagebus='zmq') as vhome:
            with certs_profile_1(vhome) as certs:
                authorizeep = AuthenticateEndpoints(web_secret_key=get_random_key(),
                                                    tls_private_key=certs.server_certs[0].key)


@pytest.fixture()
def mock_platformweb_service():
    PlatformWebService.__bases__ = (AgentMock.imitate(Agent, Agent()),)
    platformweb = PlatformWebService(serverkey=MagicMock(), identity=MagicMock(), address=MagicMock(), bind_web_address=MagicMock())
    rpc_caller = platformweb.vip.rpc
    platformweb._admin_endpoints = AdminEndpoints(rpc_caller=rpc_caller)
    yield platformweb

# TODO: These tests are updated in PR#2650

# @pytest.mark.web
# def test_get_credentials(mock_platformweb_service):
#     mock_platformweb_service._admin_endpoints._pending_auths = mock_platformweb_service._admin_endpoints._rpc_caller.call(AUTH, 'get_authorization_pending')
#     mock_platformweb_service._admin_endpoints._denied_auths = mock_platformweb_service._admin_endpoints._rpc_caller.call(AUTH, 'get_authorization_denied')
#     pass
#
#
# @pytest.mark.web
# def test_accept_credential(mock_platformweb_service):
#     mock_platformweb_service._admin_endpoints._pending_auths = mock_platformweb_service._admin_endpoints._rpc_caller.call(AUTH, 'get_authorization_pending').get()
#     mock_platformweb_service._admin_endpoints._denied_auths = mock_platformweb_service._admin_endpoints._rpc_caller.call(AUTH, 'get_authorization_denied').get()
#     pass
#
#
# @pytest.mark.web
# def test_deny_credential():
#     pass
#
#
# @pytest.mark.web
# def test_delete_credential():
#     pass
