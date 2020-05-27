import requests
import sys
from volttron.platform import jsonapi
authentication=None

def do_rpc(method, params=None ):
    global authentication
    url_root = 'http://localhost:8080/jsonrpc'


    json_package = {
        'jsonrpc': '2.0',
        'id': '2503402',
        'method':method,
    }

    if authentication:
        json_package['authorization'] = authentication

    if params:
        json_package['params'] = params

    data = jsonapi.dumps(json_package)

    return requests.post(url_root, data=data)

def main(platform_uri, agent_id):
    response = do_rpc("get_authorization", {'username': 'admin',
                                       'password': 'admin'})

    if response.ok:
        authentication = jsonapi.loads(response.text)['result']
        print('Authentication successful')
    else:
        print('login unsuccessful')
        sys.exit(0)

    print('registering {} {}'.format(platform_uri, agent_id))
    response = do_rpc('register_platform', {'identity': 'platform.agent',
                                            'agentid': agent_id,
                                            'address': platform_uri})

    print(response.text)
    if response.ok:
        data = jsonapi.loads(response.text)['result']
        print("Response: " + data)
    else:
        print('Not registered successfully.')
        sys.exit(0)





if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('invalid args must have uri and readable agent id to register.')
        sys.exit()

    main(sys.argv[1], sys.argv[2])
