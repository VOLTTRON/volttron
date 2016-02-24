import sys

import pytest
import requests
from zmq.utils import jsonapi

PLATFORM_AGENT_CONFIG = {
    # Agent id is used in the display on volttron central.
    "agentid": "Platform Agent",

    # Set the Platform agents identity
    #
    # Default "identity": "platform.agent"
    "identity": "platform.agent",

    # Configuration parameters.
    #
    # The period of time to go between attempting to report status to the
    # platform.historian.
    #
    # Default "report_status_period": 30
    "report_status_period": 15
}

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
def vc_agent(request, volttron_instance1_web):
    agent_uuid = volttron_instance1_web.install_agent(
        agent_dir="services/core/VolttronCentral",
        config_file=VC_CONFIG,
        start=True
    )

    rpc_addr = "http://{}/api/jsonrpc"\
        .format(volttron_instance1_web.bind_web_address)
    retvalue = {
        "jsonrpc":rpc_addr
    }

    def cleanup():
        volttron_instance1_web.remove_agent(agent_uuid)

    request.addfinalizer(cleanup)
    return retvalue

@pytest.fixture(params=["admin:admin",
                        "reader:reader"])
def vc_agent_with_auth(request, volttron_instance1_web):
    agent_uuid = volttron_instance1_web.install_agent(
        agent_dir="services/core/VolttronCentral",
        config_file=VC_CONFIG,
        start=True
    )

    rpc_addr = "http://{}/api/jsonrpc"\
        .format(volttron_instance1_web.bind_web_address)

    retvalue = {
        "jsonrpc": rpc_addr
    }

    user, passwd = request.param.split(':')

    response = do_rpc("get_authorization", {'username': user,
                                            'password': passwd},
                      rpc_root=rpc_addr)

    assert response.ok
    retvalue['username'] = user
    retvalue['auth_token'] = jsonapi.loads(response.text)['result']

    def cleanup():
        volttron_instance1_web.remove_agent(agent_uuid)

    request.addfinalizer(cleanup)

    return retvalue

@pytest.fixture
def platform_agent_on_instance1(request, volttron_instance1_web):
    agent_uuid = volttron_instance1_web.install_agent(
        agent_dir="services/core/Platform",
        config_file=PLATFORM_AGENT_CONFIG,
        start=True
    )

    def cleanup():
        volttron_instance1_web.remove_agent(agent_uuid)

    request.addfinalizer(cleanup)

    return agent_uuid

@pytest.fixture
def platform_agent_on_instance2(request, volttron_instance2_web):
    agent_uuid = volttron_instance2_web.install_agent(
        agent_dir="services/core/Platform",
        config_file=PLATFORM_AGENT_CONFIG,
        start=True
    )

    def cleanup():
        volttron_instance2_web.remove_agent(agent_uuid)

    request.addfinalizer(cleanup)

    return agent_uuid


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
@pytest.mark.xfail(reason="We haven't finished implementing yet!")
def test_register_instance(volttron_instance1_web, volttron_instance2_web,
                           vc_agent_with_auth, platform_agent_on_instance1,
                           platform_agent_on_instance2):
    if vc_agent_with_auth['username'] == 'reader':
        pytest.skip("user: reader can't register new instances.")

    # the root jsonrpc
    rpc_addr = vc_agent_with_auth['jsonrpc']

    assert rpc_addr
    assert vc_agent_with_auth['username'] == 'admin'
    assert volttron_instance2_web.bind_web_address !=\
           volttron_instance1_web.bind_web_address
    pytest.faile('Now we need to actually do the registration rpc call')

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