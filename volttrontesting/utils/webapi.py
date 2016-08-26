import urlparse
import uuid

import requests

from volttron.platform.jsonrpc import json_method

from zmq.utils import jsonapi


class FailedToGetAuthorization(Exception):
    pass


class WebAPI(object):
    """
    The WebAPI class allows the test to invoke all of the volttron central
    WebAPI through methods that will invoke the json call to volttron central.

    The construction of the url allows the passing of the correct url to
    post messages to.
    """
    def __init__(self, url, username='admin', password='admin'):
        """
        :param url:string:
            The jsonrpc endpoint for posting data to.
        :param username:
        :param password:
        """
        response = requests.get(url)
        print('RESPONSE CODE IS: {}'.format(response.status_code))
        if not response.ok:
            raise ValueError(
                'url not resolvable. Are you sure vc is installed?')
        if not url.endswith('jsonrpc'):
            if not url.endswith('/'):
                url += '/'
            url += 'jsonrpc'
        self._url = url
        self._username = username
        self._password = password
        self._auth_token = self.get_auth_token()

    def call(self, rpcmethod, *params, **kwparams):
        """ Call the web rpc method.

        According to the json-rpc specification one can have either argument
        based parameters or keyword arguments.

        :param method:string:
            The method to call on volttron central.
        :param params:list:
        :param kwparams:
        :return:
        """
        print(params)
        print(kwparams)
        if params and kwparams:
            raise ValueError('jsonrpc requires either args or kwargs not both!')
        if params:
            data = json_method(str(uuid.uuid4()), rpcmethod, params, None)
        else:
            data = json_method(str(uuid.uuid4()), rpcmethod, None, kwparams)

        if rpcmethod != 'get_authorization':
            data['authorization'] = self._auth_token
        resp = requests.post(self._url, json=data)
        if resp.ok:
            d = resp.json()
            if 'result' in d:
                return d['result']
            return d['error']
        return resp

    def do_rpc(self, rpcmethod, use_auth_token=True, **params):
        data = {
            'jsonrpc': '2.0',
            'method': rpcmethod,
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
        resp = self.call('register_instance', discovery_address=addr,
                         display_name=name)
        assert resp.ok, "Must have a 200 response code."
        validate_response(resp)
        return resp.json()

    def list_platforms(self):
        return self.call('list_platforms')

    def list_agents(self, platform_uuid):
        return self.call('platforms.uuid.' + platform_uuid + '.list_agents')

    def unregister_platform(self, platform_uuid):
        return self.call('unregister_platform', platform_uuid=platform_uuid)


def do_rpc(rpcmethod, params=None, auth_token=None, rpc_root=None):
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
        'method': rpcmethod,
    }

    print("PARAMS ARE: {}".format(params))
    if auth_token:
        json_package['authorization'] = auth_token

    if params:
        json_package['params'] = params

    data = jsonapi.dumps(json_package)
    print('Posted data is {}'.format(data))

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
