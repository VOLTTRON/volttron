
import pytest

from .volttron_platform_fixtures import print_log

PLATFORM_AGENT_CONFIG = {
    # Agent id is used in the display on volttron central.
    "agentid": "Platform Agent",

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
    "agentid": "Volttron Central",

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
def vc_instance(request, volttron_instance1_web):
    """
    Creates an instance of volttron with a `VolttronCentral` agent
    already installed and started.

    :returns tuple:
        - the PlatformWrapper
        - the uuid of the `VolttronCentral` agent.
        - the jsonrpc address to be used for communicating with the
          `VolttronCentral` agent.
    """
    agent_uuid = volttron_instance1_web.install_agent(
        agent_dir="services/core/VolttronCentral",
        config_file=VC_CONFIG,
        start=True
    )

    rpc_addr = "{}/jsonrpc"\
        .format(volttron_instance1_web.bind_web_address)

    # Allow all incoming connections that are encrypted.
    volttron_instance1_web.allow_all_connections()

    def cleanup():
        print('Cleanup vc_instance')
        volttron_instance1_web.remove_agent(agent_uuid)
        print_log(volttron_instance1_web.volttron_home)

    request.addfinalizer(cleanup)
    return volttron_instance1_web, agent_uuid, rpc_addr


@pytest.fixture
def pa_instance(request, volttron_instance2_web):
    """
    Creates an instance of volttron with a `VolttronCentralPlatform` agent
    already installed and started.

    :returns tuple: the platformwrapper and the uuid of the agaent installed.
    """
    agent_uuid = volttron_instance2_web.install_agent(
        agent_dir="services/core/VolttronCentralPlatform",
        config_file=PLATFORM_AGENT_CONFIG,
        start=True
    )

    # Allow all incoming encrypted connections
    volttron_instance2_web.allow_all_connections()

    def cleanup():
        print('Cleanup pa_instance')
        volttron_instance2_web.remove_agent(agent_uuid)
        print_log(volttron_instance2_web.volttron_home)

    request.addfinalizer(cleanup)

    return volttron_instance2_web, agent_uuid
