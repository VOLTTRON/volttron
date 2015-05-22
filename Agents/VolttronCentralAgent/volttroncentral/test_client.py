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
    ret = requests.post(
        url, data=data, headers=headers)
    print ret
    return ret.json()

def test_upload(platform_uuid):
    print('INSTALLING AGENT')
    method = "platforms.uuid.{}.install".format(platform_uuid)
    params = {
        "files":[
            {
                "tag":"myagenttag",
                "file_name":"helloagent-0.1-py2-none-any.whl",
                "file":"data:application/octet-stream;base64,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"
            }
        ]
    }
    #print("method: {}, params: {}".format(method, params))
    return send(method, params)

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
        response = test_upload(platform_uuid)
        if 'error' in response:
            print "ERROR: ", response['error']
            sys.exit(0)
        else:
            print "RESPONSE: ", response['result']

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
