import tempfile

import pytest
import gevent

from volttron.platform.auth import AuthEntry, AuthFile
from volttron.platform.keystore import KeyStore

simple_primary_config = {
    "agent_id": "simple_primary",
    "remote_id": "simple_secondary",
    # "remote_vip": "",
    "agent_vip_identity": "listener",
    "heartbeat_period": 1,
    "timeout": 5
}

simple_secondary_config = {
    "agent_id": "simple_secondary",
    "remote_id": "simple_primary",
    # "remote_vip": "",
    "agent_vip_identity": "listener",
    "heartbeat_period": 1,
    "timeout": 5
}

uuid_primary = None

def tcp_to(instance):
    if not instance.encrypt:
        return instance.vip_address

    tmp = tempfile.NamedTemporaryFile()
    key = KeyStore(tmp.name)
    key.generate()

    return "{}?serverkey={}&publickey={}&secretkey={}".format(
        instance.vip_address,
        instance.serverkey,
        key.public(),
        key.secret())


def all_agents_running(instance):
    agents = instance.list_agents()
    uuids = [a['uuid'] for a in agents]
    return all([instance.is_agent_running(uuid) for uuid in uuids])


@pytest.fixture
def simple_failover(get_volttron_instances):
    global simple_primary_config
    global simple_secondary_config
    global uuid_primary

    primary, secondary = get_volttron_instances(2)
    primary.allow_all_connections()
    secondary.allow_all_connections()

    # configure primary
    uuid = primary.install_agent(agent_dir="examples/ListenerAgent",
                                 vip_identity="listener",
                                 start=False)

    simple_primary_config["remote_vip"] = tcp_to(secondary)
    uuid_primary = primary.install_agent(agent_dir="services/core/FailoverAgent",
                                         config_file=simple_primary_config)

    # configure secondary
    uuid = secondary.install_agent(agent_dir="examples/ListenerAgent",
                                   vip_identity="listener",
                                   start=False)

    simple_secondary_config["remote_vip"] = tcp_to(primary)
    secondary.install_agent(agent_dir="services/core/FailoverAgent",
                            config_file=simple_secondary_config)

    return primary, secondary


def test_simple_failover(simple_failover):
    global uuid_primary

    primary, secondary = simple_failover

    # baseline behavior, primary active
    gevent.sleep(5)
    assert all_agents_running(primary)
    assert not all_agents_running(secondary)
    
    # make sure the secondary will take over
    primary.stop_agent(uuid_primary)
    gevent.sleep(5)
    assert not all_agents_running(primary)
    assert all_agents_running(secondary)

    # secondary should stop its listener
    primary.start_agent(uuid_primary)
    gevent.sleep(5)
    assert all_agents_running(primary)
    assert not all_agents_running(secondary)
