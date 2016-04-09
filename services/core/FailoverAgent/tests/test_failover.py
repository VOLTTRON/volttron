import tempfile

import pytest

from volttron.platform.auth import AuthEntry, AuthFile
from volttron.platform.keystore import KeyStore

primary_config = {
    "agent_id": "primary",
    "remote_id": "secondary",
    # "remote_vip": "",
    "volttron_ctl_tag": "listener",
    "heartbeat_period": 1,
    "check_pulse_interval": 1,
    "timeout": 5
}

secondary_config = {
    "agent_id": "secondary",
    "remote_id": "primary",
    # "remote_vip": "",
    "volttron_ctl_tag": "listener",
    "heartbeat_period": 1,
    "check_pulse_interval": 1,
    "timeout": 5
}

use_encryption = False


def tcp_to(instance):
    global use_encryption

    if not use_encryption:
        return instance.vip_address[0]

    tmp = tempfile.NamedTemporaryFile()
    key = KeyStore(tmp.name)
    key.generate()

    authfile = AuthFile(instance.volttron_home + "/auth.json")
    entry = AuthEntry(credentials="CURVE:{}".format(key.public()))
    authfile.add(entry)

    return "{}?serverkey={}&publickey={}&secretkey={}".format(
        instance.vip_address[0],
        instance.publickey,
        key.public(),
        key.secret())


def prep(instance, tgt, config):
    uuid = instance.install_agent(agent_dir="examples/ListenerAgent", start=False)
    aip = instance._aip()
    aip.tag_agent(uuid, "listener")

    config["remote_vip"] = tcp_to(tgt)
    instance.install_agent(agent_dir="services/core/Platform")
    instance.install_agent(agent_dir="services/core/FailoverAgent",
                           config_file=config)


def all_agents_running(instance):
    agents = instance.list_agents()
    return all([instance.is_agent_running(a) for a in agents])


@pytest.fixture
def failover(get_volttron_instances):
    global primary_config
    global secondary_config
    global use_encryption

    [vc, primary, secondary], param = get_volttron_instances(3)
    use_encryption = bool(param == 'encrypted')

    prep(primary, secondary, primary_config)
    prep(secondary, primary, secondary_config)

    vc.install_agent(agent_dir="services/core/VolttronCentral")
    agent = vc.build_agent(address=tcp_to(vc))
    agent.vip.rpc.call('volttron.central',
                       'register_platform',
                       'platform.agent',
                       'platform.agent',
                       tcp_to(primary)).get()
    agent.vip.rpc.call('volttron.central',
                       'register_platform',
                       'platform.agent',
                       'platform.agent',
                       tcp_to(secondary)).get()
    agent.core.stop()

    return vc, primary, secondary


def test_baseline(failover):
    vc, primary, secondary = failover

    assert all_agents_running(vc)
    assert all_agents_running(primary)
    assert not all_agents_running(secondary)
