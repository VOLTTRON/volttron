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

def authenticate(jsonrpcaddr, username, password):
    """ Authenticate a user with a username and password.

    :param jsonrpcaddr:
    :param username:
    :param password:
    :return a dictionary with usernam, auth_token and jsonrpcroot
    """

    print('RPCADDR: ', jsonrpcaddr)
    response = do_rpc("get_authorization", {'username': username,
                                            'password': password},
                      rpc_root=jsonrpcaddr)

    validate_response(response)
    jsonres = response.json()

    retvalue={
        "jsonrpcroot": jsonrpcaddr,
        "username": username,
        "auth_token": jsonres['result']
    }

    return retvalue


def get_wrappers(instance1, instance2):
    return instance1['wrapper'], instance2['wrapper']


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

@pytest.mark.vc
def test_register_instance(vc_instance, pa_instance):

    auth = authenticate(vc_instance['jsonrpc'], "admin", "admin")

    # unwrap the platfromwrappers from the instances.
    vc_wrapper, pa_wrapper = get_wrappers(vc_instance, pa_instance)

    check_multiple_platforms(vc_wrapper, pa_wrapper)

    # This is where we make the request to the vc server to register the
    # secondary platform.
    p = {'uri': pa_wrapper.bind_web_address}
    res = do_rpc(auth_token=auth['auth_token'],
                 method="register_instance", params=p,
                 rpc_root=vc_instance['jsonrpc'] )
    assert res.ok
    validate_response(res)
    result = res.json()['result']
    assert result['status'] == 'SUCCESS'
#
#
# @pytest.mark.web
# def test_can_login_as_admin(vc_agent, platform_agent_on_instance1):
#     p = {"username": "admin", "password": "admin"}
#     rpc_root = vc_agent["jsonrpc"]
#     response = do_rpc(method="get_authorization", params=p, rpc_root=rpc_root)
#
#     assert response.ok
#     assert response.text
#     retval = response.json()
#     assert retval['jsonrpc'] == '2.0'
#     assert retval['result']
#     assert retval['id']
#
# @pytest.mark.web
# def test_login_rejected_for_foo(vc_agent):
#     p = {"username": "foo", "password": ""}
#     rpc_root = vc_agent["jsonrpc"]
#     response = do_rpc(method="get_authorization", params=p, rpc_root=rpc_root)
#
#     assert 'Unauthorized' in response.text
#     assert response.status_code == 401 # Unauthorized.