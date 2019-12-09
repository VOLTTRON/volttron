"""
This file tests the MasterWebService as it is used in the base platform.  Most
of the tests in here are not integration tests, but unit tests to test the
functionality of the MasterWebService agent.
"""
import binascii
import contextlib
from io import BytesIO
import mock
import os
import shutil
import tempfile
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest
from deepdiff import DeepDiff
from werkzeug.wrappers import Response

from volttron.platform import jsonapi
from volttron.platform.agent.known_identities import MASTER_WEB
from volttron.platform.keystore import KeyStore
from volttron.platform.vip.agent import Agent
from volttron.platform.vip.agent.subsystems.web import ResourceType
from volttron.platform.vip.socket import decode_key
from volttron.platform.web import MasterWebService
from volttron.platform.web.admin_endpoints import AdminEndpoints
from volttron.utils import get_random_key
from volttrontesting.fixtures.environment_fixtures import build_test_environment
from volttrontesting.utils.platformwrapper import create_volttron_home

from volttrontesting.utils.web_utils import get_test_web_env, get_test_volttron_home
from volttrontesting.utils.utils import AgentMock, get_hostname_and_random_port
#from volttrontesting.utils.platformwrapper import create_volttron_home
from volttrontesting.fixtures.cert_fixtures import certs_profile_1

# Patch the MasterWebService so the underlying Agent interfaces are mocked
# so we can just test the things that the MasterWebService is responsible for.
MasterWebService.__bases__ = (AgentMock.imitate(Agent, Agent()),)


@pytest.fixture()
def master_web_service():
    serverkey = "serverkey"
    mock_aip = mock.Mock()
    yield MasterWebService(serverkey=serverkey, identity=MASTER_WEB, address="tcp://stuff",
                           bind_web_address="http://v2:8888")


@contextlib.contextmanager
def get_master_web(bind_web_address="http://v2:8080", **kwargs) -> MasterWebService:
    """
    Create a new MasterWebService instance with a mocked aip.

    :return: MasterWebService
    """
    serverkey = "serverkey"

    mws = MasterWebService(serverkey=serverkey, identity=MASTER_WEB, address="tcp://stuff",
                           bind_web_address=bind_web_address, **kwargs)
    mws.startupagent(sender='testweb')
    # original_volttron_home = os.environ.get('VOLTTRON_HOME')
    # new_volttron_home = create_volttron_home()
    # os.environ['VOLTTRON_HOME'] = new_volttron_home

    yield mws

    # if original_volttron_home is None:
    #     os.environ.unsetenv('VOLTTRON_HOME')
    # else:
    #     os.environ['VOLTTRON_HOME'] = original_volttron_home

    mws.unregister_all_agent_routes()
    mws.onstop(sender='testweb')
    #shutil.rmtree(new_volttron_home, ignore_errors=True)


def get_server_response(env_fixture, ws):
    """
    Use the `MasterWebService` instance passed to call the app_routing function with
    the environment <env_fixture> and a mocked start_response function.

    :param env_fixture: environment to run in
    :param ws: MasterWebServer instance.
    :return: tuple
    """
    mocked_start_response = mock.MagicMock()
    iobytes = ws.app_routing(env_fixture, mocked_start_response)
    response = BytesIO()
    if isinstance(iobytes, Response):
        for chunk in iobytes.response:
            if isinstance(chunk, str):
                response.write(chunk.encode('utf-8'))
            else:
                response.write(chunk)
    else:
        for chunk in iobytes:
            response.write(chunk)
    # use getvalue instead of moving to the begining of stream and reading.
    response = response.getvalue().decode('utf-8')
    return mocked_start_response, response


def add_points_of_interest(ws: MasterWebService, endpoints: dict):
    """
    Adds endpoints based upon type.

    The three t ypes of

    :param ws: The masterwebservice object
    :param endpoints: A dictionary of endpoints
    """
    for k, v in endpoints.items():
        if v['type'] == 'agent_route':
            ws.register_agent_route(k, v['fn'])
        elif v['type'] == 'endpoint':
            ws.register_endpoint(k, ResourceType.RAW.value)
        elif v['type'] == 'path':
            ws.register_path_route(k, v['root_dir'])
        else:
            raise ValueError(f"Invalid type specified in endpoints dictionary {k}")


@pytest.mark.parametrize('scheme', ('http', 'https'))
def test_authenticate_endpoint(scheme):
    kwargs = {}

    # Note this is not a context wrapper, it just does the creation for us
    vhome = create_volttron_home()

    if scheme == 'https':
        with certs_profile_1(vhome) as certs:
            kwargs['web_ssl_key'] = certs.server_certs[0].key_file
            kwargs['web_ssl_cert'] = certs.server_certs[0].cert_file
    else:
        kwargs['web_secret_key'] = binascii.hexlify(os.urandom(65)).decode('utf-8')
    host, port = get_hostname_and_random_port()
    kwargs['bind_web_address'] = f"{scheme}://{host}:{port}"

    # We are specifying the volttron_home here so we don't create an additional one.
    with get_test_volttron_home(volttron_config_params=kwargs, volttron_home=vhome):

        # add a user so that we can actually log in.
        user = 'bogart'
        passwd = 'cat'
        adminep = AdminEndpoints()
        adminep.add_user(user, passwd, groups=['foo', 'read-only'])
        expected_claims = dict(groups=['foo', 'read-only'])

        with get_master_web(**kwargs) as mw:

            data = urlencode(dict(username=user, password=passwd)).encode('utf-8')
            assert len(data) > 0
            # test not sending any parameters.
            env = get_test_web_env("/authenticate", input_data=data, method='POST')
            mocked_start_response, response = get_server_response(env, mw)
            assert 3 == len(response.split("."))

            claims = mw.get_user_claims(response)
            assert claims
            assert not DeepDiff(expected_claims, claims)


class MockQuery(object):
    """
    The MockQuery object is used to be able to mock the .get() from AsyncResult()
    objects.

    The constructor takes key:value arguments.  The keys should be the arguments passed
    to the query method, with the values the return value of the call.
    """
    def __init__(self, **kwargs):
        """
        Constructs a MockQuery instance and creates key value entries for each
        of the kwargs.

        :param kwargs:
        """
        self._kvargs = {}

        for k, v in kwargs.items():
            self._kvargs[k] = v

    def query(self, key):
        """
        Mock for the query function of the volttron.platform.vip.agent.subsystems.query.Query object.

        :param key: the key on the server to be returned.
        :return: A class with a .get(timeout) function available.
        """
        return MockQuery.InnerClass(self._kvargs[key])

    class InnerClass(object):
        def __init__(self, value):
            self.value = value

        def get(self, timeout=5):
            return self.value


@pytest.mark.parametrize('scheme', ('http', 'https'))
def test_discovery(scheme):
    vhome = create_volttron_home()
    # creates a vhome level key store
    keystore = KeyStore()
    serverkey = decode_key(keystore.public)

    # Depending upon scheme we enable/disable password jwt and certificate based jwt.
    if scheme == 'https':
        with certs_profile_1('/'.join([vhome, 'certs'])) as certs:
            config_params = dict(web_ssl_key=certs.server_certs[0].key_file,
                                 web_ssl_cert=certs.server_certs[0].cert_file)
    else:
        config_params = dict(web_secret_key=get_random_key())

    with get_test_volttron_home(volttron_config_params=config_params):
        instance_name = "booballoon"
        host, port = get_hostname_and_random_port()

        # this is the vip address
        address = f"tcp://{host}:{port}"

        def _construct_query_mock(core):
            """
            Internal function that creates a concrete response for the data.
            when query('instance-name').get() is called the passed instance name
            is returned
            """
            nonlocal instance_name, address

            kv = {
                "instance-name": instance_name,
                "addresses": [address]
            }
            return MockQuery(**kv)

        with mock.patch('volttron.platform.vip.agent.subsystems.query.Query', _construct_query_mock):
            host, port = get_hostname_and_random_port()
            bind_web_address = f"{scheme}://{host}:{port}"
            serverkey = decode_key(keystore.public)

            mws = MasterWebService(serverkey=serverkey, identity=MASTER_WEB, address=address,
                                   bind_web_address=bind_web_address, **config_params)
            mws.startupagent(sender='testweb')

            env = get_test_web_env("/discovery/")
            mock_start_response = mock.Mock()
            # A closingiterator is returned from the response object so we use the next
            # on the returned response.  Then we can do json responses.
            response = mws.app_routing(env, mock_start_response).__next__()
            # load json into a dict for testing responses.
            response = jsonapi.loads(response.decode('utf-8'))

            assert response.get('instance-name') is not None
            assert instance_name == response.get('instance-name')
            assert keystore.public == response.get('serverkey')
            assert address == response.get('vip-address')


# def test_masterweb_has_discovery():
#     web_secret = "my secret key"
#
#     def _construct_query_mock(core):
#         instance_name = "booballoon"
#         kv = {
#             "instance-name": instance_name,
#             "addresses": []
#         }3
#         return MockQuery(**kv)
#
#     with mock.patch('volttron.platform.vip.agent.subsystems.query.Query', _construct_query_mock):
#         with get_master_web(web_secret_key=web_secret) as mw:
#             env = get_test_web_env("/discovery/")
#             mocked_start_response, response = get_server_response(env, mw)
#
#             assert response


@pytest.mark.web
def test_path_route():
    with get_master_web(web_secret_key="oh my goodnes") as ws:
        # Stage 1 create a temp dir and add index.html to that directory
        tempdir = tempfile.mkdtemp(prefix="web")
        html = """<html><head><title>sweet</title><body>Yay I am here</body></html>"""
        index_filepath = f"{tempdir}/myhtml/index.html"
        os.makedirs(os.path.dirname(index_filepath))
        with open(index_filepath, 'w') as fp:
            fp.write(html)

        # Stage 2 register the path route and specify the root directory as the
        # tempdirectory created above.
        interest = {"/myhtml": {"type": "path", "root_dir": tempdir}}
        registerd_routes_before = len(ws.registeredroutes)
        add_points_of_interest(ws, interest)

        assert 1 == len(ws.pathroutes)
        assert registerd_routes_before + 1 == len(ws.registeredroutes)

        # Stage 3 - emulate a request which will call the app_routing function
        #
        # We need to update the enf_fixture to what the webserver will normally send
        # in to the server.  So for this we are going to update the PATH_INFO
        #
        # since we registered the path /myhtml then this should route to
        # <tempdir>/myhtml/index.html for this example.
        env_fixture = get_test_web_env('/myhtml/index.html')
        mocked_start_response, response = get_server_response(env_fixture, ws)
        assert response == html
        assert mocked_start_response.call_count == 1
        mocked_start_response.reset_mock()

        # file not found
        env_fixture = get_test_web_env('/myhtml/alpha.jpg')
        mocked_start_response, response = get_server_response(env_fixture, ws)
        assert response == '<h1>Not Found</h1>'
        assert mocked_start_response.call_count == 1
        mocked_start_response.reset_mock()

        # TODO: redirect to new content, need to set up some more stuff for this one to work
        # env_fixture = get_test_web_env('/')
        # mocked_start_response, response = get_server_response(env_fixture, ws)
        # assert response == '<h1>Not Found</h1>'
        # assert mocked_start_response.call_count == 1
        # mocked_start_response.reset_mock()


@pytest.mark.web
def test_register_route(master_web_service: MasterWebService):
    ws = master_web_service
    fn_mock = mock.Mock()
    fn_mock.__name__ = "test_register_route"
    interest = {'/web': {'type': 'agent_route', 'fn': fn_mock}}
    routes_before = len(ws.peerroutes)
    registered_routes_before = len(ws.registeredroutes)
    # setup the context for the rpc call
    ws.vip.rpc.context.vip_message.peer.return_value = "my_agent"
    add_points_of_interest(ws, interest)
    assert routes_before + 1 == len(ws.peerroutes)
    assert registered_routes_before + 1 == len(ws.registeredroutes)

    ws.unregister_all_agent_routes()
    assert routes_before == len(ws.peerroutes)
    assert registered_routes_before == len(ws.registeredroutes)


@pytest.mark.web
def test_register_endpoint(master_web_service: MasterWebService):
    ws = master_web_service
    fn_mock = mock.Mock()
    fn_mock.__name__ = "test_register_endpoint"
    interest = {"/battle/one": {'type': 'endpoint'}}
    # setup the context for the rpc call
    ws.vip.rpc.context.vip_message.peer.return_value = "my_agent"
    add_points_of_interest(ws, interest)

    assert len(ws.endpoints) == 1

    ws.unregister_all_agent_routes()
    assert len(ws.endpoints) == 0



