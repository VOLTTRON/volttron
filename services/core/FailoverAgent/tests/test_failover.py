import tempfile

import pytest
import gevent

from volttron.platform.auth import AuthEntry, AuthFile
from volttron.platform.keystore import KeyStore

primary_config = {
    "agent_id": "primary",
    "remote_id": "secondary",
    # "remote_vip": "",
    "volttron_ctl_tag": "listener",
    "heartbeat_period": 1,
    "timeout": 3
}

secondary_config = {
    "agent_id": "secondary",
    "remote_id": "primary",
    # "remote_vip": "",
    "volttron_ctl_tag": "listener",
    "heartbeat_period": 1,
    "timeout": 3
}

SLEEP_TIME = 5

use_encryption = False
primary_failover = None
secondary_failover = None
vc_uuid = None

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
def failover(request, get_volttron_instances):
    global primary_config
    global secondary_config
    global use_encryption
    global primary_failover
    global secondary_failover
    global vc_uuid

    [primary, secondary, vc], param = get_volttron_instances(3)
    primary.allow_all_connections()
    secondary.allow_all_connections()
    vc.allow_all_connections()
    use_encryption = bool(param == 'encrypted')

    # configure vc
    vc_uuid = vc.install_agent(agent_dir="services/core/VolttronCentralPlatform")

    # configure primary
    primary_platform = primary.install_agent(agent_dir="services/core/VolttronCentralPlatform")
    # register with vc
    primary_listener = primary.install_agent(agent_dir="examples/ListenerAgent", start=False)
    aip = primary._aip()
    aip.tag_agent(primary_listener, "listener")

    primary_config["remote_vip"] = tcp_to(secondary)
    primary_failover = primary.install_agent(agent_dir="services/core/FailoverAgent",
                                             config_file=primary_config)

    # configure secondary
    secondary_platform = secondary.install_agent(agent_dir="services/core/VolttronCentralPlatform")
    # register with vc
    secondary_listener = secondary.install_agent(agent_dir="examples/ListenerAgent", start=False)
    aip = secondary._aip()
    aip.tag_agent(secondary_listener, "listener")

    secondary_config["remote_vip"] = tcp_to(primary)
    secondary_failover = secondary.install_agent(agent_dir="services/core/FailoverAgent",
                                                 config_file=secondary_config)

    def stop():
        vc.stop_agent(vc_uuid)
        vc.shutdown_platform()
        
        primary.stop_agent(primary_failover)
        primary.stop_agent(primary_platform)
        primary.stop_agent(primary_listener)
        primary.shutdown_platform()

        secondary.stop_agent(secondary_failover)
        secondary.stop_agent(secondary_platform)
        secondary.stop_agent(secondary_listener)
        secondary.shutdown_platform()

    request.addfinalizer(stop)

    return primary, secondary, vc


def test_baseline(failover):
    primary, secondary, vc = failover

    gevent.sleep(SLEEP_TIME)

    assert all_agents_running(vc)
    assert all_agents_running(primary)
    assert not all_agents_running(secondary)


def test_vc_death_behavior(failover):
    global vc_uuid
    primary, secondary, vc = failover

    assert all_agents_running(vc)
    assert all_agents_running(primary)
    assert not all_agents_running(secondary)

    vc.stop_agent(vc_uuid)
    gevent.sleep(SLEEP_TIME)

    assert all_agents_running(primary)
    assert not all_agents_running(secondary)

@pytest.mark.xfail(reason='VC coordination posponed for feature/web')
def test_primary_death_behavior(failover):
    global primary_failover
    primary, secondary, vc = failover

    assert all_agents_running(vc)
    assert all_agents_running(primary)
    assert not all_agents_running(secondary)

    primary.stop_agent(primary_failover)
    gevent.sleep(SLEEP_TIME)

    assert all_agents_running(vc)
    assert  all_agents_running(secondary)

@pytest.mark.xfail(reason='VC coordination posponed for feature/web')
def test_secondary_death_behavior(failover):
    global secondary_failover
    primary, secondary, vc = failover

    assert all_agents_running(vc)
    assert all_agents_running(primary)
    assert not all_agents_running(secondary)

    secondary.stop_agent(secondary_failover)
    gevent.sleep(SLEEP_TIME)

    assert all_agents_running(vc)
    assert all_agents_running(primary)


def test_primary_when_others_dead(failover):
    global vc_uuid
    global secondary_failover
    primary, secondary, vc = failover

    vc.stop_agent(vc_uuid)
    secondary.stop_agent(secondary_failover)
    gevent.sleep(SLEEP_TIME)
    
    assert not all_agents_running(vc)
    assert not all_agents_running(primary)
    assert not all_agents_running(secondary)
    

def test_secondary_when_others_dead(failover):
    global vc_uuid
    global primary_failover
    primary, secondary, vc = failover

    vc.stop_agent(vc_uuid)
    primary.stop_agent(primary_failover)
    gevent.sleep(SLEEP_TIME)
    
    assert not all_agents_running(vc)
    assert not all_agents_running(primary)
    assert not all_agents_running(secondary)
    

