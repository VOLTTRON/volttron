import sys

import pytest
import requests
from zmq.utils import jsonapi

VC_CONFIG = {
    # The agentid is used during display on the VOLTTRON central platform
    # it does not need to be unique.
    "agentid": "volttron central",

    # Must be unique on a given instance of VOLTTRON
    "vip_identity": "volttron.central",
    "identity": "volttron.central",

    # By default the webroot will be relative to the installation directory
    # of the agent when it is installed.  One can override this by specifying
    # the root directory here.
    # "webroot": "path/to/webroot",

    # Authentication for users is handled through a naive password algorithm
    # import hashlib
    # hashlib.sha512(password).hexdigest() where password is the plain text password.
    "users": {
        "reader": {
            "password": "2d7349c51a3914cd6f5dc28e23c417ace074400d7c3e176bcf5da72fdbeb6ce7ed767ca00c6c1fb754b8df5114fc0b903960e7f3befe3a338d4a640c05dfaf2d",
            "groups": [
                "reader"
            ]
        },
        "writer": {
            "password": "f7c31a682a838bbe0957cfa0bb060daff83c488fa5646eb541d334f241418af3611ff621b5a1b0d327f1ee80da25e04099376d3bc533a72d2280964b4fab2a32",
            "groups": [
                "writer"
            ]
        },
        "admin": {
            "password": "c7ad44cbad762a5da0a452f9e854fdc1e0e7a52a38015f23f3eab1d80b931dd472634dfac71cd34ebc35d16ab7fb8a90c81f975113d6c7538dc69dd8de9077ec",
            "groups": [
                "admin"
            ]
        },
        "dorothy": {
            "password": "cf1b67402d648f51ef6ff8805736d588ca07cbf018a5fba404d28532d839a1c046bfcd31558dff658678b3112502f4da9494f7a655c3bdc0e4b0db3a5577b298",
            "groups": [
                "reader, writer"
            ]
        }
    }
}


@pytest.fixture
def vc_agent(request, volttron_instance1_encrypt):
    agent_uuid = volttron_instance1_encrypt.install_agent(
        agent_dir="services/core/VolttronCentral",
        config_file=VC_CONFIG,
        start=True
    )

    retvalue = {
        "jsonrpc": "http://127.0.0.1:8080/api/jsonrpc"
    }

    def cleanup():
        print('VC_AGENT TEARDOWN!')
        volttron_instance1_encrypt.remove_agent(agent_uuid)

    request.addfinalizer(cleanup)
    print("VC_AGENT FIXTURE!")

    return retvalue


@pytest.fixture(params=["admin:admin",
                        "writer:writer",
                        "reader:reader"])
def vc_agent_with_auth(request, volttron_instance1_encrypt):
    agent_uuid = volttron_instance1_encrypt.install_agent(
        agent_dir="services/core/VolttronCentral",
        config_file=VC_CONFIG,
        start=True
    )

    retvalue = {
        "jsonrpc": "http://127.0.0.1:8080/api/jsonrpc"
    }

    user, passwd = request.param.split(':')

    response = do_rpc("get_authorization", {'username': user,
                                            'password': passwd})

    assert response.ok
    retvalue['username'] = user
    retvalue['auth_token'] = jsonapi.loads(response.text)['result']

    def cleanup():
        volttron_instance1_encrypt.remove_agent(agent_uuid)

    request.addfinalizer(cleanup)

    return retvalue


def do_rpc(method, params=None, auth_token=None, rpc_root=None):
    """ A utility method for calling json rpc based funnctions.

    :param method: The method to call
    :param params: the parameters to the method
    :param auth_token: A token if the user has one.
    :param rpc_root: Override the http root location url.
    :return: The result of the rpc method.
    """
    url_root = 'http://localhost:8080/jsonrpc'

    if rpc_root:
        url_root = rpc_root

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

    return requests.post(url_root, data=jsonapi.dumps(json_package))


@pytest.mark.web
def test_can_login_as_admin(vc_agent):
    p = {"username": "admin", "password": "admin"}
    response = do_rpc(method="get_authorization", params=p)

    assert response.ok
    assert response.text
    retval = response.json()
    assert retval['jsonrpc'] == '2.0'
    assert retval['result']
    assert retval['id']

@pytest.mark.web
def test_login_rejected_for_foo(vc_agent):
    p = {"username": "foo", "password": ""}
    response = do_rpc(method="get_authorization", params=p)

    assert 'Unauthorized' in response.text
    assert response.status_code == 401 # Unauthorized.