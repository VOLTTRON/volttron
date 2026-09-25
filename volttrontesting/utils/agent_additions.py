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