import tempfile

import pytest
import gevent

from volttron.platform.auth import AuthEntry, AuthFile
from volttron.platform.keystore import KeyStore

simple_primary_config = {
    "agent_id": "simple_primary",
    "remote_id": "simple_secondary",
    # "remote_vip": "",
    # "remote_serverkey":"",
    "agent_vip_identity": "listener",
    "heartbeat_period": 1,
    "timeout": 2
}

simple_secondary_config = {
    "agent_id": "simple_secondary",
    "remote_id": "simple_primary",
    # "remote_vip": "",
    # "remote_serverkey": "",
    "agent_vip_identity": "listener",
    "heartbeat_period": 1,
    "timeout": 2
}

SLEEP_TIME = 3

uuid_primary = None


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

    if primary.encrypt == False:
        pytest.skip("Only encrypted communication allowed for failovers")

    primary.allow_all_connections()
    secondary.allow_all_connections()

    # configure primary
    uuid = primary.install_agent(agent_dir="examples/ListenerAgent",
                                 vip_identity="listener",
                                 start=False)

    simple_primary_config["remote_vip"] = secondary.vip_address
    simple_primary_config["remote_serverkey"] = secondary.serverkey
    uuid_primary = primary.install_agent(agent_dir="services/core/FailoverAgent",
                                         config_file=simple_primary_config)

    # configure secondary
    uuid = secondary.install_agent(agent_dir="examples/ListenerAgent",
                                   vip_identity="listener",
                                   start=False)

    simple_secondary_config["remote_vip"] = primary.vip_address
    simple_secondary_config["remote_serverkey"] = primary.serverkey
    secondary.install_agent(agent_dir="services/core/FailoverAgent",
                            config_file=simple_secondary_config)

    gevent.sleep(SLEEP_TIME)
    assert all_agents_running(primary)
    assert not all_agents_running(secondary)

    return primary, secondary


def test_simple_failover(simple_failover):
    global uuid_primary

    primary, secondary = simple_failover

    # make sure the secondary will take over
    primary.stop_agent(uuid_primary)
    gevent.sleep(SLEEP_TIME)
    assert not all_agents_running(primary)
    assert all_agents_running(secondary)

    # secondary should stop its listener
    primary.start_agent(uuid_primary)
    gevent.sleep(SLEEP_TIME)
    assert all_agents_running(primary)
    assert not all_agents_running(secondary)

def test_secondary_on_primary_crash(simple_failover):
    primary, secondary = simple_failover

    primary.shutdown_platform()
    gevent.sleep(SLEEP_TIME)
    assert all_agents_running(secondary)
