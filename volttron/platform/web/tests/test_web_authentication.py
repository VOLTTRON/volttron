import os
from urllib.parse import urlencode

import gevent
from deepdiff import DeepDiff

import pytest

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

HAS_RMQ = is_rabbitmq_available()
ci_skipif = pytest.mark.skipif(os.getenv('CI', None) == 'true', reason='SSL does not work in CI')
rmq_skipif = pytest.mark.skipif(not HAS_RMQ,
                                reason='RabbitMQ is not setup and/or SSL does not work in CI')


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


def test_authenticate_must_use_post_request():
    with get_test_volttron_home(messagebus='zmq'):

        env = get_test_web_env('/authenticate', method='GET')

        authorize_ep = AuthenticateEndpoints(web_secret_key=get_random_key())
        response = authorize_ep.get_auth_token(env, {})
        assert ('Content-Type', 'text/html') in response.headers.items()
        assert '401 Unauthorized' in response.status


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

        response = authorizeep.get_auth_token(env, invalid_login_username_params)

        assert '401' == response.status
        # TODO: Get the actual response content here
        # assert '401 Unauthorized' in response.content

        invalid_login_password_params = dict(username=user, password='hazzah')
        response = authorizeep.get_auth_token(env, invalid_login_password_params)

        assert '401' == response.status
        valid_login_params = urlencode(dict(username=user, password=passwd))
        response = authorizeep.get_auth_token(env, valid_login_params)
        assert '200 OK' == response.status
        assert "text/plain" in response.content_type
        assert 3 == len(response.response[0].decode('utf-8').split('.'))


@pytest.mark.web
def test_get_credentials(volttron_instance_web):
    instance = volttron_instance_web
    auth_pending = instance.dynamic_agent.vip.rpc.call(AUTH, "get_authorization_pending").get()
    print(f"Auth pending is: {auth_pending}")
    assert len(auth_pending) == 0
    with with_os_environ(instance.env):
        pending_agent = Agent(identity="PendingAgent")
        task = gevent.spawn(pending_agent.core.run)
        task.join()
        gevent.sleep(5)
        pending_agent.core.stop()

    auth_pending = instance.dynamic_agent.vip.rpc.call(AUTH, "get_authorization_pending").get()
    print(f"Auth pending is: {auth_pending}")

    assert len(auth_pending) == 1


@pytest.mark.web
def test_accept_credential(volttron_instance_web):
    instance = volttron_instance_web
    with with_os_environ(instance.env):
        pending_agent = Agent(identity="PendingAgent")
        task = gevent.spawn(pending_agent.core.run)
        task.join()
        gevent.sleep(5)
        pending_agent.core.stop()

        auth_pending = instance.dynamic_agent.vip.rpc.call(AUTH, "get_authorization_pending").get()
        print(f"Auth pending is: {auth_pending}")
        assert len(auth_pending) == 1

        auth_approved = instance.dynamic_agent.vip.rpc.call(AUTH, "get_authorization_approved").get()
        assert len(auth_approved) == 0

        print(f"agent uuid: {pending_agent.core.agent_uuid}")
        instance.dynamic_agent.vip.rpc.call(AUTH, "approve_authorization_failure", auth_pending[0]["user_id"]).get()
        auth_approved = instance.dynamic_agent.vip.rpc.call(AUTH, "get_authorization_approved").get()

        assert len(auth_approved) == 1


@pytest.mark.web
def test_deny_credential(volttron_instance_web):
    instance = volttron_instance_web
    with with_os_environ(instance.env):
        pending_agent = Agent(identity="PendingAgent")
        task = gevent.spawn(pending_agent.core.run)
        task.join()
        gevent.sleep(5)
        pending_agent.core.stop()

        auth_pending = instance.dynamic_agent.vip.rpc.call(AUTH, "get_authorization_pending").get()
        print(f"Auth pending is: {auth_pending}")
        assert len(auth_pending) == 1

        auth_denied = instance.dynamic_agent.vip.rpc.call(AUTH, "get_authorization_denied").get()
        assert len(auth_denied) == 0

        print(f"agent uuid: {pending_agent.core.agent_uuid}")
        instance.dynamic_agent.vip.rpc.call(AUTH, "deny_authorization_failure", auth_pending[0]["user_id"]).get()
        auth_denied = instance.dynamic_agent.vip.rpc.call(AUTH, "get_authorization_denied").get()

        assert len(auth_denied) == 1


@pytest.mark.web
def test_delete_credential(volttron_instance_web):
    instance = volttron_instance_web
    auth_pending = instance.dynamic_agent.vip.rpc.call(AUTH, "get_authorization_pending").get()
    print(f"Auth pending is: {auth_pending}")
    assert len(auth_pending) == 0
    with with_os_environ(instance.env):
        pending_agent = Agent(identity="PendingAgent")
        task = gevent.spawn(pending_agent.core.run)
        task.join()
        gevent.sleep(5)
        pending_agent.core.stop()

        auth_pending = instance.dynamic_agent.vip.rpc.call(AUTH, "get_authorization_pending").get()
        print(f"Auth pending is: {auth_pending}")
        assert len(auth_pending) == 1

        instance.dynamic_agent.vip.rpc.call(AUTH, "delete_authorization_failure", auth_pending[0]["user_id"]).get()
        auth_pending = instance.dynamic_agent.vip.rpc.call(AUTH, "get_authorization_pending").get()

        assert len(auth_pending) == 0
