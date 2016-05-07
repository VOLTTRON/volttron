import json
import pytest
import requests
import sys

from volttron.platform.messaging.health import STATUS_GOOD
from volttrontesting.utils.utils import poll_gevent_sleep
from zmq.utils import jsonapi


class FailedToGetAuthorization(Exception):
    pass


class APITester(object):
    def __init__(self, url, username='admin', password='admin'):
        self._url = url
        self._username = username
        self._password = password
        self._auth_token = self.get_auth_token()

    def do_rpc(self, method, use_auth_token=True, **params):
        data = {
            'jsonrpc': '2.0',
            'method': method,
            'params': params,
            'id': '1'
        }
        if use_auth_token:
            data['authorization'] = self._auth_token
        return requests.post(self._url, json=data)

    def get_auth_token(self):
        response = self.do_rpc(
            'get_authorization', use_auth_token=False,
            username=self._username, password=self._password)
        if not response:
            raise FailedToGetAuthorization
        validate_response(response)
        return json.loads(response.content)['result']

    def inspect(self, platform_uuid, agent_uuid):
        return self.do_rpc('platforms.uuid.{}.agents.uuid.{}.'
                           'inspect'.format(platform_uuid, agent_uuid))

    def register_instance(self, addr, name=None):
        return self.do_rpc('register_instance', discovery_address=addr,
                           display_name=name)

    def list_platforms(self):
        return self.do_rpc('list_platforms')

    def list_agents(self, platform_uuid):
        return self.do_rpc('platforms.uuid.' + platform_uuid + '.list_agents')

    def unregister_platform(self, platform_uuid):
        return self.do_rpc('unregister_platform', platform_uuid=platform_uuid)


@pytest.fixture(scope="function")
def web_api_tester(request, vc_instance, pa_instance):
    pa_wrapper, pa_uuid = pa_instance
    vc_wrapper, vc_uuid, vc_jsonrpc = vc_instance
    check_multiple_platforms(vc_wrapper, pa_wrapper)

    tester = APITester(vc_jsonrpc)
    response = tester.register_instance(pa_wrapper.bind_web_address)

    validate_response(response)
    result = response.json()['result']
    assert result['status'] == 'SUCCESS'

    def cleanup():
        for platform in tester.list_platforms().json()['result']:
            tester.unregister_platform(platform['uuid'])

    request.addfinalizer(cleanup)
    return tester


def do_rpc(method, params=None, auth_token=None, rpc_root=None):
    """ A utility method for calling json rpc based funnctions.

    :param method: The method to call
    :param params: the parameters to the method
    :param auth_token: A token if the user has one.
    :param rpc_root: Root of jsonrpc api.
    :return: The result of the rpc method.
    """

    assert rpc_root, "Must pass a jsonrpc url in to the function."

    json_package = {
        'jsonrpc': '2.0',
        'id': '2503402',
        'method': method,
    }

    if auth_token:
        json_package['authorization'] = auth_token

    if params:
        json_package['params'] = params

    data = jsonapi.dumps(json_package)

    return requests.post(rpc_root, data=data)


def authenticate(jsonrpcaddr, username, password):
    """ Authenticate a user with a username and password.

    :param jsonrpcaddr:
    :param username:
    :param password:
    :return a tuple with username and auth token
    """

    print('RPCADDR: ', jsonrpcaddr)
    response = do_rpc("get_authorization", {'username': username,
                                            'password': password},
                      rpc_root=jsonrpcaddr)

    validate_response(response)
    jsonres = response.json()

    return username, jsonres['result']


def check_multiple_platforms(platformwrapper1, platformwrapper2):
    assert platformwrapper1.bind_web_address
    assert platformwrapper2.bind_web_address
    assert platformwrapper1.bind_web_address != \
        platformwrapper2.bind_web_address


def each_result_contains(result_list, fields):
    for result in result_list:
        assert all(field in result.keys() for field in fields)


def validate_at_least_one(response):
    validate_response(response)
    result = response.json()['result']
    assert len(result) > 0
    return result


def validate_response(response):
    """ Validate that the message is a json-rpc response.

    :param response:
    :return:
    """
    assert response.ok
    rpcdict = response.json()
    print('RPCDICT', rpcdict)
    assert rpcdict['jsonrpc'] == '2.0'
    assert rpcdict['id']
    assert 'error' in rpcdict.keys() or 'result' in rpcdict.keys()


@pytest.mark.vc
@pytest.mark.xfail(reason='Not sure why this is failing.')
def test_auto_register_platform(vc_instance):
    vc, vcuuid, jsonrpc = vc_instance

    adir = "services/core/VolttronCentralPlatform/"
    pauuid = vc.install_agent(agent_dir=adir, config_file=adir+"config")
    assert pauuid
    print(pauuid)

    tester = APITester(jsonrpc)

    def redo_request():
        response = tester.do_rpc("list_platforms")
        print('Response is: {}'.format(response.json()))
        jsonresp = response.json()
        if len(jsonresp['result']) > 0:
            p = jsonresp['result'][0]
            assert p['uuid']
            assert p['name'] == 'local'
            assert isinstance(p['health'], dict)
            assert STATUS_GOOD == p['health']['status']

            return True
        return len(response.json()['result']) > 0

    assert poll_gevent_sleep(6, redo_request)


@pytest.mark.vc
def test_register_instance(vc_instance, pa_instance):

    pa_wrapper, pa_uuid = pa_instance
    vc_wrapper, vc_uuid, vc_jsonrpc = vc_instance

    check_multiple_platforms(vc_wrapper, pa_wrapper)

    username, auth = authenticate(vc_jsonrpc, "admin", "admin")
    assert auth

    print("vip address of pa_agent: {}".format(pa_wrapper.vip_address))
    print("vip address of vc_agent: {}".format(vc_wrapper.vip_address))

    # Call register_instance rpc method on vc
    response = do_rpc("register_instance", [pa_wrapper.bind_web_address],
                      auth, vc_jsonrpc)

    validate_response(response)
    result = response.json()['result']
    assert result['status'] == 'SUCCESS'

    # list platforms
    response = do_rpc("list_platforms", [pa_wrapper.bind_web_address],
                      auth, vc_jsonrpc)
    validate_response(response)
    platforms = response.json()['result']
    assert len(platforms) == 1
    uuid = platforms[0]['uuid']


@pytest.mark.vc
@pytest.mark.xfail(reason='Hmmmm')
def test_list_exported_methods(web_api_tester):
    platforms = web_api_tester.list_platforms().json()['result']
    agents = web_api_tester.list_agents(platforms[0]['uuid']).json()['result']
    for agent in agents:
        response = web_api_tester.inspect(platforms[0]['uuid'], agent['uuid'])
        validate_response(response)


@pytest.mark.vc
def test_list_agents(web_api_tester):
    platforms = web_api_tester.list_platforms().json()['result']
    assert len(platforms) > 0
    response = web_api_tester.list_agents(platforms[0]['uuid'])
    result = validate_at_least_one(response)
    each_result_contains(result, ['name', 'uuid'])


@pytest.mark.vc
def test_list_platforms(web_api_tester):
    response = web_api_tester.list_platforms()
    result = validate_at_least_one(response)
    each_result_contains(result, ['name', 'uuid'])


@pytest.mark.vc
def test_unregister_platform(web_api_tester):
    platforms = web_api_tester.list_platforms().json()['result']
    orig_platform_count = len(platforms)
    assert orig_platform_count > 0

    uuid_to_remove = platforms[0]['uuid']
    response = web_api_tester.unregister_platform(uuid_to_remove)
    validate_response(response)
    platforms = web_api_tester.list_platforms().json()['result']
    assert len(platforms) == orig_platform_count - 1


@pytest.mark.web
def test_login_rejected_for_foo(vc_instance):
    vc_jsonrpc = vc_instance[2]
    with pytest.raises(FailedToGetAuthorization):
        tester = APITester(vc_jsonrpc, "foo", "")
