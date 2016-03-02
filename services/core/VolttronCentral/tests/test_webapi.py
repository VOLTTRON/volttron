import sys

import pytest
import requests
from zmq.utils import jsonapi


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

def validate_response(response):
    assert response.ok
    rpcdict = response.json()
    assert rpcdict['jsonrpc'] == '2.0'
    assert rpcdict['id']
    assert 'error' in rpcdict.keys() or 'result' in rpcdict.keys()

# @pytest.mark.web
# def test_register_local_instance(request, vc_agent_with_auth,
#                                  platform_agent_on_instance1):
#
#     if vc_agent_with_auth['username'] == 'reader':
#         pytest.fail("Modify so that we know that it should fail from response")
#     else:
#         pytest.fail("Add success criteria here for admin")
#     #print(vc_agent_with_auth, platform_agent_on_instance1)
#     #assert platform_agent_on_instance1

@pytest.mark.web
def test_register_instance(volttron_instance1_web, volttron_instance2_web,
                           vc_agent_with_auth):
    # , platform_agent_on_instance1,
    #                       platform_agent_on_instance2):
    if vc_agent_with_auth['username'] == 'reader':
        pytest.skip("user: reader can't register new instances.")

    # the root jsonrpc
    rpc_addr = vc_agent_with_auth['jsonrpc']

    # Make smaller names for the instances so that it's easier to deal with
    vi1 = volttron_instance1_web
    vi2 = volttron_instance2_web

    assert rpc_addr
    assert vc_agent_with_auth['username'] == 'admin'
    assert vi1.bind_web_address
    assert vi2.bind_web_address != vi1.bind_web_address

    # This is where we make the request to the vc server to register the
    # secondary platform.
    p = {'uri': vi2.bind_web_address}
    res = do_rpc(auth_token=vc_agent_with_auth['auth_token'],
                 method="register_instance", params=p, rpc_root=rpc_addr )
    assert res.ok
    validate_response(res)
    result = res.json()['result']
    assert result['status'] == 'SUCCESS'


@pytest.mark.web
def test_can_login_as_admin(vc_agent, platform_agent_on_instance1):
    p = {"username": "admin", "password": "admin"}
    rpc_root = vc_agent["jsonrpc"]
    response = do_rpc(method="get_authorization", params=p, rpc_root=rpc_root)

    assert response.ok
    assert response.text
    retval = response.json()
    assert retval['jsonrpc'] == '2.0'
    assert retval['result']
    assert retval['id']

@pytest.mark.web
def test_login_rejected_for_foo(vc_agent):
    p = {"username": "foo", "password": ""}
    rpc_root = vc_agent["jsonrpc"]
    response = do_rpc(method="get_authorization", params=p, rpc_root=rpc_root)

    assert 'Unauthorized' in response.text
    assert response.status_code == 401 # Unauthorized.