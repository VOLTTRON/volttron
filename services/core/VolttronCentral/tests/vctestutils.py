import requests

from zmq.utils import jsonapi


class FailedToGetAuthorization(Exception):
    pass


class APITester(object):
    def __init__(self, url, username='admin', password='admin'):
        """
        :param url:string:
            The jsonrpc endpoint for posting data to.
        :param username:
        :param password:
        """
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
        print('posting data')
        print(data)
        return requests.post(self._url, json=data)

    def get_auth_token(self):
        response = self.do_rpc(
            'get_authorization', use_auth_token=False,
            username=self._username, password=self._password)
        if not response:
            raise FailedToGetAuthorization
        validate_response(response)
        return jsonapi.loads(response.content)['result']

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
