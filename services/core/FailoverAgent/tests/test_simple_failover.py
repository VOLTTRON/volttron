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

primary_failover = None

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
def simple_failover(request, get_volttron_instances):
    global simple_primary_config
    global simple_secondary_config
    global primary_failover

    primary, secondary = get_volttron_instances(2)
    primary.allow_all_connections()
    secondary.allow_all_connections()

    # configure primary
    primary_listener = primary.install_agent(agent_dir="examples/ListenerAgent",
                                 vip_identity="listener",
                                 start=False)

    simple_primary_config["remote_vip"] = tcp_to(secondary)
    primary_failover = primary.install_agent(agent_dir="services/core/FailoverAgent",
                                         config_file=simple_primary_config)

    # configure secondary
    secondary_listener = secondary.install_agent(agent_dir="examples/ListenerAgent",
                                   vip_identity="listener",
                                   start=False)

    simple_secondary_config["remote_vip"] = tcp_to(primary)
    secondary_failover = secondary.install_agent(agent_dir="services/core/FailoverAgent",
                                                 config_file=simple_secondary_config)

    def stop():
        primary.stop_agent(primary_listener)
        primary.stop_agent(primary_failover)
        primary.remove_agent(primary_listener)
        primary.remove_agent(primary_failover)
        primary.shutdown_platform()

        secondary.stop_agent(secondary_listener)
        secondary.stop_agent(secondary_failover)
        secondary.remove_agent(secondary_listener)
        secondary.remove_agent(secondary_failover)
        secondary.shutdown_platform()

    request.addfinalizer(stop)
    return primary, secondary


def test_simple_failover(simple_failover):
    global primary_failover

    primary, secondary = simple_failover

    # baseline behavior, primary active
    gevent.sleep(5)
    assert all_agents_running(primary)
    assert not all_agents_running(secondary)
    
    # make sure the secondary will take over
    primary.stop_agent(primary_failover)
    gevent.sleep(5)
    assert not all_agents_running(primary)
    assert all_agents_running(secondary)

    # secondary should stop its listener
    primary.start_agent(primary_failover)
    gevent.sleep(5)
    assert all_agents_running(primary)
    assert not all_agents_running(secondary)
