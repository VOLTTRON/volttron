import requests

from volttron.platform import jsonapi


class APITester(object):
    def __init__(self, wrapper, username='admin', password='admin'):
        """
        :param url:string:
            The jsonrpc endpoint for posting data to.
        :param username:
        :param password:
        """
        self._wrapper = wrapper
        self._url = wrapper.jsonrpc_endpoint
        self._username = username
        self._password = password

        self._auth_token = None
        self._auth_token = self.get_auth_token()

    def do_rpc(self, method, **params):
        data = {
            'jsonrpc': '2.0',
            'method': method,
            'params': params,
            'authorization': self._auth_token,
            'id': '1'
        }

        print('Posting: {}'.format(data))

        r = requests.post(self._url, json=data)
        validate_response(r)

        rpcjson = r.json()
        if 'result' in rpcjson:
            return rpcjson['result']
        else:
            return rpcjson['error']

    def get_auth_token(self):
        return self.do_rpc('get_authorization',
                           username=self._username,
                           password=self._password)

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

    def remove_agent(self, plataform_uuid, agent_uuid):
        rpc = 'platforms.uuid.{}.remove_agent'.format(plataform_uuid)
        return self.do_rpc(rpc, **dict(uuid=agent_uuid))

    def list_agents(self, platform_uuid):
        print('Listing agents for platform: {}'.format(platform_uuid))
        return self.do_rpc('platforms.uuid.' + platform_uuid + '.list_agents')

    def unregister_platform(self, platform_uuid):
        return self.do_rpc('unregister_platform', platform_uuid=platform_uuid)

    def store_agent_config(self, platform_uuid, agent_identity, config_name,
                           raw_contents, config_type="json"):
        params = dict(platform_uuid=platform_uuid,
                      agent_identity=agent_identity,
                      config_name=config_name,
                      raw_contents=raw_contents,
                      config_type=config_type)
        return self.do_rpc("store_agent_config", **params)

    def list_agent_configs(self, platform_uuid, agent_identity):
        params = dict(platform_uuid=platform_uuid,
                      agent_identity=agent_identity)
        return self.do_rpc("list_agent_configs", **params)

    def get_agent_config(self, platform_uuid, agent_identity, config_name,
                         raw=True):
        params = dict(platform_uuid=platform_uuid,
                      agent_identity=agent_identity,
                      config_name=config_name,
                      raw=raw)
        return self.do_rpc("get_agent_config", **params)

    def delete_agent_config(self, platform_uuid, agent_identity, config_name):
        params = dict(platform_uuid=platform_uuid,
                      agent_identity=agent_identity,
                      config_name=config_name)
        return self.do_rpc("delete_agent_config", **params)

    def set_setting(self, **params):
        return self.do_rpc("set_setting", **params)

    def get_setting(self, **params):
        return self.do_rpc("get_setting", **params)

    def get_setting_keys(self):
        return self.do_rpc("get_setting_keys")


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
    assert 'error' in rpcdict or 'result' in rpcdict
