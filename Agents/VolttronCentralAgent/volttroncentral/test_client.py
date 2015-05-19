import requests
import uuid
from volttron.platform.agent.vipagent import jsonapi as json

auth_token = None


def send(method, params=None):
    global auth_token
    url = "http://localhost:8080/jsonrpc"
    headers = {'content-type': 'application/json'}
    payload = {
        "method": method,
        "jsonrpc": "2.0",
        #"params": params,
        "id": str(uuid.uuid4()),
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
    import sys
    platforms = []
    print "Getting Auth"
    response = send("get_authorization",
                        {'username': 'admin', 'password': 'admin'})
    auth_token = response['result']
    print "Token is: " +auth_token

    print "Listing Platforms"
    response = send('list_platforms')
    if 'error' in response:
        print "ERROR: ", response['error']
        sys.exit(0)
    else:
        print "RESPONSE: ", response['result']
        platforms = response['result']

    if len(platforms) < 1:
        print "No platforms registered!"
        sys.exit(0)

    print "Listing Agents on platforms"
    for x in platforms:
        platform_uuid = x['uuid']
        print ('platform: '+platform_uuid)
        cmd = 'platforms.uuid.{}.list_agents'.format(platform_uuid)
        print('executing: {}'.format(cmd))
        response = send(cmd)
        if 'error' in response:
            print "ERROR: ", response['error']
            sys.exit(0)
        else:
            print "RESPONSE: ", response['result']
        agents = response['result']

        print "Status agents"
        cmd = 'platforms.uuid.{}.status_agents'.format(platform_uuid)
        response = send(cmd)
        if 'error' in response:
            print "ERROR: ", response['error']
        else:
            print "RESPONSE: ", response['result']

if __name__ == "__main__":
    main()
