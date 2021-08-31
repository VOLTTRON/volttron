import os
import json
from urllib.parse import urlencode

import gevent
from datetime import datetime, timedelta
from mock import MagicMock
from deepdiff import DeepDiff

import pytest

from volttron.platform.web import PlatformWebService
from volttrontesting.utils.utils import AgentMock

try:
    import jwt
except ImportError:
    pytest.mark.skip(reason="JWT is missing! Web is not enabled for this installation of VOLTTRON")

from volttron.platform import is_rabbitmq_available
from volttron.platform.agent.known_identities import AUTH
from volttron.platform.certs import CertWrapper, Certs
from volttron.platform.vip.agent import Agent
from volttron.utils import get_random_key
from volttrontesting.utils.platformwrapper import create_volttron_home, with_os_environ
from volttrontesting.utils.web_utils import get_test_web_env
from volttron.platform.web.admin_endpoints import AdminEndpoints
from volttron.platform.web.authenticate_endpoint import AuthenticateEndpoints
from volttrontesting.fixtures.cert_fixtures import certs_profile_1
from volttrontesting.fixtures.volttron_platform_fixtures import get_test_volttron_home, volttron_instance_web

# HAS_RMQ = is_rabbitmq_available()
# ci_skipif = pytest.mark.skipif(os.getenv('CI', None) == 'true', reason='SSL does not work in CI')
# rmq_skipif = pytest.mark.skipif(not HAS_RMQ,
#                                 reason='RabbitMQ is not setup and/or SSL does not work in CI')


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


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_authenticate_endpoint(scheme):
    kwargs = {}

    # Note this is not a context wrapper, it just does the creation for us
    vhome = create_volttron_home()

    if scheme == 'https':
        with certs_profile_1(vhome) as certs:
            kwargs['web_ssl_key'] = certs.server_certs[0].key_file
            kwargs['web_ssl_cert'] = certs.server_certs[0].cert_file
    else:
        kwargs['web_secret_key'] = get_random_key()

    # We are specifying the volttron_home here so we don't create an additional one.
    with get_test_volttron_home(messagebus='zmq', config_params=kwargs, volttron_home=vhome):

        user = 'bogart'
        passwd = 'cat'
        adminep = AdminEndpoints()
        adminep.add_user(user, passwd)

        env = get_test_web_env('/authenticate', method='POST')

        if scheme == 'http':
            authorizeep = AuthenticateEndpoints(web_secret_key=kwargs.get('web_secret_key'))
        else:
            authorizeep = AuthenticateEndpoints(tls_private_key=CertWrapper.load_key(kwargs.get('web_ssl_key')))

        invalid_login_username_params = dict(username='fooey', password=passwd)

        response = authorizeep.get_auth_tokens(env, invalid_login_username_params)

        # assert '401 Unauthorized' in response.content
        assert '401 UNAUTHORIZED' == response.status

        invalid_login_password_params = dict(username=user, password='hazzah')
        response = authorizeep.get_auth_tokens(env, invalid_login_password_params)

        assert '401 UNAUTHORIZED' == response.status
        valid_login_params = urlencode(dict(username=user, password=passwd))
        response = authorizeep.get_auth_tokens(env, valid_login_params)
        assert '200 OK' == response.status
        assert "application/json" in response.content_type
        response_data = json.loads(response.data.decode('utf-8'))
        assert 3 == len(response_data["refresh_token"].split('.'))
        assert 3 == len(response_data["access_token"].split('.'))


@pytest.mark.web
def test_get_credentials(volttron_instance_web):
    instance = volttron_instance_web
    auth_pending = instance.dynamic_agent.vip.rpc.call(AUTH, "get_authorization_pending").get()
    len_auth_pending = len(auth_pending)
    with with_os_environ(instance.env):
        pending_agent = Agent(identity="PendingAgent")
        task = gevent.spawn(pending_agent.core.run)
        task.join(timeout=5)
        pending_agent.core.stop()

    auth_pending = instance.dynamic_agent.vip.rpc.call(AUTH, "get_authorization_pending").get()
    print(f"Auth pending is: {auth_pending}")

    assert len(auth_pending) == len_auth_pending + 1


@pytest.mark.web
def test_accept_credential(volttron_instance_web):
    instance = volttron_instance_web
    auth_pending = instance.dynamic_agent.vip.rpc.call(AUTH, "get_authorization_pending").get()
    len_auth_pending = len(auth_pending)
    with with_os_environ(instance.env):
        pending_agent = Agent(identity="PendingAgent1")
        task = gevent.spawn(pending_agent.core.run)
        task.join(timeout=5)
        pending_agent.core.stop()

        auth_pending = instance.dynamic_agent.vip.rpc.call(AUTH, "get_authorization_pending").get()
        print(f"Auth pending is: {auth_pending}")
        assert len(auth_pending) == len_auth_pending + 1

        auth_approved = instance.dynamic_agent.vip.rpc.call(AUTH, "get_authorization_approved").get()
        len_auth_approved = len(auth_approved)
        assert len_auth_approved == 0

        print(f"agent uuid: {pending_agent.core.agent_uuid}")
        instance.dynamic_agent.vip.rpc.call(AUTH, "approve_authorization_failure", auth_pending[0]["user_id"]).wait(timeout=4)
        gevent.sleep(2)
        auth_approved = instance.dynamic_agent.vip.rpc.call(AUTH, "get_authorization_approved").get()

        assert len(auth_approved) == len_auth_approved + 1


@pytest.mark.web
def test_deny_credential(volttron_instance_web):
    instance = volttron_instance_web
    auth_pending = instance.dynamic_agent.vip.rpc.call(AUTH, "get_authorization_pending").get()
    len_auth_pending = len(auth_pending)
    with with_os_environ(instance.env):
        pending_agent = Agent(identity="PendingAgent2")
        task = gevent.spawn(pending_agent.core.run)
        task.join(timeout=5)
        pending_agent.core.stop()

        auth_pending = instance.dynamic_agent.vip.rpc.call(AUTH, "get_authorization_pending").get()
        print(f"Auth pending is: {auth_pending}")
        assert len(auth_pending) == len_auth_pending + 1

        auth_denied = instance.dynamic_agent.vip.rpc.call(AUTH, "get_authorization_denied").get()
        len_auth_denied = len(auth_denied)
        assert len_auth_denied == 0

        print(f"agent uuid: {pending_agent.core.agent_uuid}")
        instance.dynamic_agent.vip.rpc.call(AUTH, "deny_authorization_failure", auth_pending[0]["user_id"]).wait(timeout=4)
        gevent.sleep(2)
        auth_denied = instance.dynamic_agent.vip.rpc.call(AUTH, "get_authorization_denied").get()

        assert len(auth_denied) == len_auth_denied + 1


@pytest.mark.web
def test_delete_credential(volttron_instance_web):
    instance = volttron_instance_web
    auth_pending = instance.dynamic_agent.vip.rpc.call(AUTH, "get_authorization_pending").get()
    print(f"Auth pending is: {auth_pending}")
    len_auth_pending = len(auth_pending)
    with with_os_environ(instance.env):
        pending_agent = Agent(identity="PendingAgent3")
        task = gevent.spawn(pending_agent.core.run)
        task.join(timeout=5)
        pending_agent.core.stop()

        auth_pending = instance.dynamic_agent.vip.rpc.call(AUTH, "get_authorization_pending").get()
        print(f"Auth pending is: {auth_pending}")
        assert len(auth_pending) == len_auth_pending + 1

        instance.dynamic_agent.vip.rpc.call(AUTH, "delete_authorization_failure", auth_pending[0]["user_id"]).wait(timeout=4)
        gevent.sleep(2)
        auth_pending = instance.dynamic_agent.vip.rpc.call(AUTH, "get_authorization_pending").get()

        assert len(auth_pending) == len_auth_pending
