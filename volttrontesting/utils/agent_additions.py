from volttron.platform import get_services_core, get_ops, get_examples
from volttron.platform.agent.known_identities import VOLTTRON_CENTRAL, \
    VOLTTRON_CENTRAL_PLATFORM


def add_volttron_central(wrapper, config=None, **kwargs):
    config_dict = {
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

    if config is not None:
        config_dict = config

    print('Adding vc to {}'.format(wrapper.vip_address))
    agent_uuid = wrapper.install_agent(
        config_file=config_dict,
        agent_dir=get_services_core("VolttronCentral"),
        vip_identity=VOLTTRON_CENTRAL,
        **kwargs
    )

    return agent_uuid


def add_listener(wrapper, config={}, vip_identity=None, **kwargs):
    print("Adding to {wrapper} a listener agent".format(wrapper=wrapper))
    agent_uuid = wrapper.install_agent(
        config_file=config,
        vip_identity=vip_identity,
        agent_dir=get_services_core("ListenerAgent"),
        **kwargs
    )
    return agent_uuid


def add_volttron_central_platform(wrapper, config={}, **kwargs):
    print('Adding vcp to {}'.format(wrapper.vip_address))
    agent_uuid = wrapper.install_agent(
        config_file=config,
        agent_dir=get_services_core("VolttronCentralPlatform"),
        vip_identity=VOLTTRON_CENTRAL_PLATFORM
    )
    return agent_uuid


def add_sqlhistorian(wrapper, config, vip_identity='platform.historian',
                     **kwargs):
    agent_uuid = wrapper.install_agent(
        config_file=config,
        agent_dir=get_services_core("SQLHistorian"),
        vip_identity=vip_identity,
        **kwargs
    )
    return agent_uuid


def add_mongohistorian(wrapper, config, vip_identity='platform.historian',
                       **kwargs):
    agent_uuid = wrapper.install_agent(
        config_file=config,
        agent_dir=get_services_core("MongodbHistorian"),
        vip_identity=vip_identity,
        **kwargs
    )
    return agent_uuid


def add_sysmon(wrapper, config, **kwargs):
    agent_uuid = wrapper.install_agent(
        config_file=config,
        agent_dir=get_ops("SysMonAgent"),
        **kwargs
    )
    return agent_uuid


def add_thresholddetection(wrapper, config, **kwargs):
    agent_uuid = wrapper.install_agent(
        config_file=config,
        agent_dir=get_ops("ThresholdDetectionAgent"),
        **kwargs
    )
    return agent_uuid


def add_emailer(wrapper, config, **kwargs):
    agent_uuid = wrapper.install_agent(
        config_file=config,
        agent_dir=get_ops("EmailerAgent"),
        **kwargs
    )
    return agent_uuid


def add_listener(wrapper, config={}, **kwargs):
    agent_uuid = wrapper.install_agent(
        config_file=config,
        agent_dir=get_examples("ListenerAgent"),
        **kwargs
    )
    return agent_uuid


def add_forward_historian(wrapper, config={}, **kwargs):
    agent_uuid = wrapper.install_agent(
        config_file=config,
        agent_dir=get_services_core("ForwardHistorian"),
        **kwargs
    )
    return agent_uuid