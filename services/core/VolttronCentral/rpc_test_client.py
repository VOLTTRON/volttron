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
        'method': method,
    }

    if authentication:
        json_package['authorization'] = authentication

    if params:
        json_package['params'] = params

    data = jsonapi.dumps(json_package)

    return requests.post(url_root, data=jsonapi.dumps(json_package))

def get_dict(text):
    return jsonapi.loads(text)

def inspect_agent(platform_uuid, agent_uuid):
    method = "platforms.uuid.{}.agents.uuid.{}.inspect".format(platform_uuid,
                                                       agent_uuid)
    return do_rpc(method)

def list_agents(platform_uuid):
    method = "platforms.uuid.{}.list_agents".format(platform_uuid)
    return do_rpc(method)

def inspect_method(platform_uuid, agent_uuid, method):
    method = "platforms.uuid.{}.agents.uuid.{}.{}.inspect".format(platform_uuid,
                                                                  agent_uuid,
                                                                  method)
    return do_rpc(method)

def exec_method(platform_uuid, agent_uuid, method, params):
    method = "platforms.uuid.{}.agents.uuid.{}.{}".format(platform_uuid,
                                                                  agent_uuid,
                                                                  method)
    return do_rpc(method, params)

def register_platform(address, identity):
    print("Registering platform platform")
    return do_rpc('register_platform', {'address': address,
                                        'identity': identity});

def register_instance(discovery_address):
    print("Registering platform instance")
    return do_rpc(
        'register_instance', {'discovery_address': discovery_address})


if __name__ == '__main__':
    response = do_rpc("get_authorization", {'username': 'admin',
                                           'password': 'admin'})

    response = register_instance("127.0.0.2:8080")
    if response.ok:
        success = response.json()['result']
        if success:
            print('default platform registered')
        else:
            print("default platform not registered correctly")
            sys.exit(0)
    else:
        print('Getting platforms unsuccessful')
        sys.exit(0)

    response = do_rpc("list_platforms")
    platforms = None
    if response.ok:
        platforms = jsonapi.loads(response.text)['result']
        print('Platforms retrieved')
    else:
        print('Getting platforms unsuccessful')
        sys.exit(0)


    if len(platforms) > 0:
        for p in platforms:
            print(p)

            response = list_agents(p['uuid'])
            if response.ok:
                print("RESPONSE WAS: "+response.text)

                agents = jsonapi.loads(response.text)['result']

                for a in agents:
                    print('agents name {name}'.format(**a))
                    if 'hello' in a['name']: # hello agent only
                        print("routing to: ", p['uuid'])
                        print('agent uuid: ', a['uuid'])
                        response = inspect_agent(p['uuid'], a['uuid'])

                        print("INSPECT RESPONSE {}".format(response))
                        print("INSPECT RESPONSE {}".format(response.text))

                        methods = jsonapi.loads(response.text)

                        response = inspect_method(p['uuid'], a['uuid'], 'sayHello')
                        print("RESPONSE WAS: "+response.text)

                        response = exec_method(p['uuid'], a['uuid'], 'sayHello', {'name': 'Ralphie'})
                        print("RESPONSE WAS: "+response.text)

                        if response.ok:
                            print("RESPONSE WAS: "+response.text)
                            methods = jsonapi.loads(response.text)['result']
                            print('Methods received for {}'.format(p['uuid']))

                            print(methods)
                        else:
                            print('Getting methods unsuccessful')
                            sys.exit(0)


            else:
                print('Listing agents unsuccessful')
                sys.exit(0)





