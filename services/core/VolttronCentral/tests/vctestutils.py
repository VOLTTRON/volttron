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

        print('Posting: {}'.format(data))
        return requests.post(self._url, json=data)

    @staticmethod
    def get_result(cb, *args, **kwargs):
        return cb(*args, **kwargs).json()['result']

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

    def register_instance_with_serverkey(self, addr, serverkey, name=None):
        return self.do_rpc('register_instance', adress=addr,
                           serverkey=serverkey, display_name=name)

    def list_platforms(self):
        return self.do_rpc('list_platforms')

    def install_agent(self, platform_uuid, fileargs):
        rpc = 'platforms.uuid.{}.install'.format(platform_uuid)
        return self.do_rpc(rpc, files=[fileargs])

    def list_agents(self, platform_uuid):
        print('Listing agents for platform: {}'.format(platform_uuid))
        return self.do_rpc('platforms.uuid.' + platform_uuid + '.list_agents')

    def unregister_platform(self, platform_uuid):
        return self.do_rpc('unregister_platform', platform_uuid=platform_uuid)

    def store_agent_config(self, platform_uuid, agent_identity, config_name,
                           raw_contents, config_type="json"):
        params = dict(platform_uuid=platform_uuid,
                      agent_identity=agent_identity,
                      config_name=config_name, raw_contents=raw_contents,
                      config_type=config_type)
        return self.do_rpc("store_agent_config", **params)

    def list_agent_configs(self, platform_uuid, agent_identity):
        params = dict(platform_uuid=platform_uuid,
                      agent_identity=agent_identity)
        return self.do_rpc("list_agent_configs", **params)

    def get_agent_config(self, platform_uuid, agent_identity, config_name,
                         raw=True):
        params = dict(platform_uuid=platform_uuid,
                      agent_identity=agent_identity, config_name=config_name,
                      raw=raw)
        return self.do_rpc("get_agent_config", **params)


def check_multiple_platforms(platformwrapper1, platformwrapper2):
    assert platformwrapper1.bind_web_address
    assert platformwrapper2.bind_web_address
    assert platformwrapper1.bind_web_address != \
        platformwrapper2.bind_web_address


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
