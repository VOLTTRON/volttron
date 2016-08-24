import tempfile

import pytest
import gevent

from volttron.platform.auth import AuthEntry, AuthFile
from volttron.platform.keystore import KeyStore

simple_primary_config = {
    "agent_id": "simple_primary",
    "remote_id": "simple_secondary",
    # "remote_vip": "",
    "volttron_ctl_tag": "listener",
    "heartbeat_period": 1,
    "timeout": 5
}

simple_secondary_config = {
    "agent_id": "simple_secondary",
    "remote_id": "simple_primary",
    # "remote_vip": "",
    "volttron_ctl_tag": "listener",
    "heartbeat_period": 1,
    "timeout": 5
}

use_encryption = False
uuid_primary = None

def tcp_to(instance):
    global use_encryption

    if not use_encryption:
        return instance.vip_address

    tmp = tempfile.NamedTemporaryFile()
    key = KeyStore(tmp.name)
    key.generate()

    return "{}?serverkey={}&publickey={}&secretkey={}".format(
        instance.vip_address,
        instance.publickey,
        key.public(),
        key.secret())


def all_agents_running(instance):
    agents = instance.list_agents()
    return all([instance.is_agent_running(a) for a in agents])


@pytest.fixture
def simple_failover(get_volttron_instances):
    global simple_primary_config
    global simple_secondary_config
    global use_encryption
    global uuid_primary

    [primary, secondary], param = get_volttron_instances(2)
    primary.allow_all_connections()
    secondary.allow_all_connections()
    use_encryption = bool(param == 'encrypted')

    # configure primary
    uuid = primary.install_agent(agent_dir="examples/ListenerAgent", start=False)
    aip = primary._aip()
    aip.tag_agent(uuid, "listener")

    simple_primary_config["remote_vip"] = tcp_to(secondary)
    uuid_primary = primary.install_agent(agent_dir="services/core/FailoverAgent",
                                         config_file=simple_primary_config)

    # configure secondary
    uuid = secondary.install_agent(agent_dir="examples/ListenerAgent", start=False)
    aip = secondary._aip()
    aip.tag_agent(uuid, "listener")

    simple_secondary_config["remote_vip"] = tcp_to(primary)
    secondary.install_agent(agent_dir="services/core/FailoverAgent",
                            config_file=simple_secondary_config)

    return primary, secondary


def test_simple_baseline(simple_failover):
    primary, secondary = simple_failover

    gevent.sleep(5)

    assert all_agents_running(primary)
    assert not all_agents_running(secondary)


def test_simple_pickup(simple_failover):
    global uuid_primary

    primary, secondary = simple_failover

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
