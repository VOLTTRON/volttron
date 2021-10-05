import tempfile

from contextlib import contextmanager

import pytest
import gevent

from volttron.platform import get_services_core, get_examples, get_ops
from volttron.platform.keystore import KeyStore

primary_config = {
    "agent_id": "primary",
    "remote_id": "secondary",
    # "remote_vip": "",
    "agent_vip_identity": "listener",
    "heartbeat_period": 1,
    "timeout": 3
}

secondary_config = {
    "agent_id": "secondary",
    "remote_id": "primary",
    # "remote_vip": "",
    "agent_vip_identity": "listener",
    "heartbeat_period": 1,
    "timeout": 3
}

SLEEP_TIME = 5

primary_failover = None
secondary_failover = None
vc_uuid = None


def tcp_to(instance):

    tmp = tempfile.NamedTemporaryFile()
    key = KeyStore(tmp.name)
    key.generate()

    return "{}?serverkey={}&publickey={}&secretkey={}".format(
        instance.vip_address,
        instance.serverkey,
        key.public,
        key.secret)


def all_agents_running(instance):
    agents = instance.list_agents()
    uuids = [a['uuid'] for a in agents]
    return all([instance.is_agent_running(uuid) for uuid in uuids])


@pytest.fixture(scope="module")
def failover(request, get_volttron_instances):
    global primary_config
    global secondary_config
    global primary_failover
    global secondary_failover
    global vc_uuid

    pytest.skip("Coordination with VC not implemted")

    primary, secondary, vc = get_volttron_instances(3)
    primary.allow_all_connections()
    secondary.allow_all_connections()
    vc.allow_all_connections()

    # configure vc
    vc_uuid = vc.install_agent(
        agent_dir=get_services_core("VolttronCentralPlatform"))

    # configure primary
    primary_platform = primary.install_agent(
        agent_dir=get_services_core("VolttronCentralPlatform"))
    # register with vc
    primary_listener = primary.install_agent(agent_dir=get_examples("ListenerAgent"),
                                             vip_identity="listener",
                                             start=False)

    primary_config["remote_vip"] = tcp_to(secondary)
    primary_failover = primary.install_agent(agent_dir=get_ops("FailoverAgent"),
                                             config_file=primary_config)

    # configure secondary
    secondary_platform = secondary.install_agent(agent_dir=get_services_core("VolttronCentralPlatform"))
    # register with vc
    secondary_listener = secondary.install_agent(agent_dir=get_examples("ListenerAgent"),
                                                 vip_identity="listener",
                                                 start=False)

    secondary_config["remote_vip"] = tcp_to(primary)
    secondary_failover = secondary.install_agent(agent_dir=get_ops("FailoverAgent"),
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


def baseline_check(vc, primary, secondary):
    assert all_agents_running(vc)
    assert all_agents_running(primary)
    assert not all_agents_running(secondary)


@contextmanager
def stop_start(platform, uuid):
    platform.stop_agent(uuid)
    gevent.sleep(1)
    yield
    platform.start_agent(uuid)
    gevent.sleep(1)


@pytest.mark.xfail(reason='Coordination with VC not implemted')
def test_vc_death_behavior(failover):
    global vc_uuid
    primary, secondary, vc = failover

    baseline_check(vc, primary, secondary)

    with stop_start(vc, vc_uuid):
        gevent.sleep(SLEEP_TIME)
        assert all_agents_running(primary)
        assert not all_agents_running(secondary)

    baseline_check(vc, primary, secondary)


@pytest.mark.xfail(reason='Coordination with VC not implemted')
def test_primary_death_behavior(failover):
    global primary_failover
    primary, secondary, vc = failover

    baseline_check(vc, primary, secondary)

    with stop_start(primary, primary_failover):
        gevent.sleep(SLEEP_TIME)
        assert all_agents_running(vc)
        assert  all_agents_running(secondary)

    baseline_check(vc, primary, secondary)


@pytest.mark.xfail(reason='Coordination with VC not implemted')
def test_secondary_death_behavior(failover):
    global secondary_failover
    primary, secondary, vc = failover

    baseline_check(vc, primary, secondary)

    with stop_start(secondary, secondary_failover):
        gevent.sleep(SLEEP_TIME)
        assert all_agents_running(vc)
        assert all_agents_running(primary)

    baseline_check(vc, primary, secondary)


@pytest.mark.xfail(reason='Coordination with VC not implemted')
def test_primary_when_others_dead(failover):
    global vc_uuid
    global secondary_failover
    primary, secondary, vc = failover

    baseline_check(vc, primary, secondary)

    with stop_start(vc, vc_uuid), stop_start(secondary, secondary_failover):
        gevent.sleep(SLEEP_TIME)
        assert not all_agents_running(vc)
        assert not all_agents_running(primary)
        assert not all_agents_running(secondary)

    baseline_check(vc, primary, secondary)


@pytest.mark.xfail(reason='Coordination with VC not implemted')
def test_secondary_when_others_dead(failover):
    global vc_uuid
    global primary_failover
    primary, secondary, vc = failover

    baseline_check(vc, primary, secondary)
    with stop_start(vc, vc_uuid), stop_start(primary, primary_failover):
        gevent.sleep(SLEEP_TIME)
        assert not all_agents_running(vc)
        assert not all_agents_running(primary)
        assert not all_agents_running(secondary)

    baseline_check(vc, primary, secondary)
