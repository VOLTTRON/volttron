import requests
import json

auth_token = None

def send(method, params=None):
    global auth_token
    url = "http://localhost:8080/jsonrpc"
    headers = {'content-type': 'application/json'}
    payload = {
        "method": method,
        "jsonrpc": "2.0",
        #"params": params,
        "id": 0,
    }
    if params:
        payload["params"] = params
    if auth_token:
        payload['authorization'] = auth_token
    print "payload: ", payload
    data = json.dumps(payload)
    print data
    return requests.post(
        url, data=data, headers=headers).json()

def main():
    global auth_token
    print "Getting Auth"
    response = send("getAuthorization",
                        {'username': 'admin', 'password': 'admin'})
    auth_token = response['result']

    print "Listing Platforms"
    response = send('listPlatforms')
    if 'error' in response:
        print "ERROR: ", response['error']
    else:
        print "RESPONSE: ", response['result']

    print "Listing Agents on first_platform"
    response = send('platforms.uuid.first_platform.listAgents')
    if 'error' in response:
        print "ERROR: ", response['error']
    else:
        print "RESPONSE: ", response['result']

    print "Status agents"
    response = send('platforms.uuid.first_platform.statusAgents')
    if 'error' in response:
        print "ERROR: ", response['error']
    else:
        print "RESPONSE: ", response['result']

    print "Start agent"
    response = send('platforms.uuid.first_platform.startAgent', ['e335586e-a301-41ba-94a6-3f6887cae6e0'])
    if 'error' in response:
        print "ERROR: ", response['error']
    else:
        print "RESPONSE: ", response['result']
    print "Status agents"
    response = send('platforms.uuid.first_platform.statusAgents')
    if 'error' in response:
        print "ERROR: ", response['error']
    else:
        print "RESPONSE: ", response['result']

    print "Stop agent"
    response = send('platforms.uuid.first_platform.stopAgent', ['e335586e-a301-41ba-94a6-3f6887cae6e0'])
    if 'error' in response:
        print "ERROR: ", response['error']
    else:
        print "RESPONSE: ", response['result']

    print "Status agents"
    response = send('platforms.uuid.first_platform.statusAgents')
    if 'error' in response:
        print "ERROR: ", response['error']
    else:
        print "RESPONSE: ", response['result']






#     print "list Methods on agent"
#     response = send('platforms.uuid.first_platform.agents.uuid.5bcd7eb4-4475-4237-bcfb-81a650b6e069.listMethods')
#     if 'error' in response:
#         print "ERROR: ", response['error']
#     else:
#         print "RESPONSE: ", response['result']
#
#     print "list Methods on agent"
#     response = send('platforms.uuid.first_platform.agents.uuid.e335586e-a301-41ba-94a6-3f6887cae6e0.listMethods')
#     if 'error' in response:
#         print "ERROR: ", response['error']
#     else:
#         print "RESPONSE: ", response['result']

if __name__ == "__main__":
    main()
