import tempfile

import pytest
import gevent

from volttron.platform import get_examples, get_ops, jsonapi
from volttrontesting.utils.agent_additions import add_listener

simple_primary_config = {
    "agent_id": "primary",
    "simple_behavior": True,
    # "remote_vip": "",
    # "remote_serverkey":"",
    "agent_vip_identity": "listener",
    "heartbeat_period": 1,
    "timeout": 2
}

simple_secondary_config = {
    "agent_id": "secondary",
    "simple_behavior": True,
    # "remote_vip": "",
    # "remote_serverkey": "",
    "agent_vip_identity": "listener",
    "heartbeat_period": 1,
    "timeout": 2
}

SLEEP_TIME = 3

uuid_primary = None
uuid_secondary = None
listener_primary = None
listener_secondary = None

def all_agents_running(instance):
    agents = instance.list_agents()
    uuids = [a['uuid'] for a in agents]
    return all([instance.is_agent_running(uuid) for uuid in uuids])


@pytest.fixture(scope="module")
def simple_failover(request, get_volttron_instances):
    global simple_primary_config
    global simple_secondary_config
    global uuid_primary
    global uuid_secondary
    global listener_primary
    global listener_secondary


    primary, secondary = get_volttron_instances(2)

    if primary.messagebus != 'zmq':
        pytest.skip("Failover only valid for zmq instances.")
        return

    primary.allow_all_connections()
    secondary.allow_all_connections()

    # configure primary
    listener_primary = add_listener(primary, start=True, vip_identity="listener")
    # primary.install_agent(agent_dir=get_examples("ListenerAgent"),
    #                                          vip_identity="listener",
    #                                          start=False)

    simple_primary_config["remote_vip"] = secondary.vip_address
    simple_primary_config["remote_serverkey"] = secondary.serverkey
    uuid_primary = primary.install_agent(agent_dir=get_ops("FailoverAgent"),
                                         config_file=simple_primary_config)

    # configure secondary
    listener_secondary = add_listener(secondary, start=False, vip_identity="listener")
    # listener_secondary = secondary.install_agent(agent_dir=get_examples("ListenerAgent"),
    #                                              vip_identity="listener",
    #                                              start=False)

    simple_secondary_config["remote_vip"] = primary.vip_address
    simple_secondary_config["remote_serverkey"] = primary.serverkey
    uuid_secondary = secondary.install_agent(agent_dir=get_ops("FailoverAgent"),
                                             config_file=simple_secondary_config)

    gevent.sleep(SLEEP_TIME)

    assert all_agents_running(primary)
    assert not all_agents_running(secondary)
    assert not secondary.is_agent_running(listener_secondary)

    def cleanup():
        primary.stop_agent(uuid_primary)
        primary.stop_agent(listener_primary)
        primary.shutdown_platform()

        secondary.stop_agent(uuid_secondary)
        secondary.stop_agent(listener_secondary)
        secondary.shutdown_platform()

    request.addfinalizer(cleanup)
    return primary, secondary


def test_simple_failover(simple_failover):
    global uuid_primary
    global listener_secondary
    alert_messages = {}

    primary, secondary = simple_failover

    # Listen for alerts from state changes
    def onmessage(peer, sender, bus, topic, headers, message):
        alert = jsonapi.loads(message)["context"]

        try:
            alert_messages[alert] += 1
        except KeyError:
            alert_messages[alert] = 1

    assert not secondary.is_agent_running(listener_secondary)
    listen1 = primary.build_agent()
    listen1.vip.pubsub.subscribe(peer='pubsub',
                                 prefix='alert',
                                 callback=onmessage).get()

    listen2 = secondary.build_agent()
    listen2.vip.pubsub.subscribe(peer='pubsub',
                                 prefix='alert',
                                 callback=onmessage).get()

    assert not secondary.is_agent_running(listener_secondary)
    # make sure the secondary will take over
    primary.stop_agent(uuid_primary)
    gevent.sleep(SLEEP_TIME)
    assert not all_agents_running(primary)
    assert all_agents_running(secondary)
    assert 'Primary is inactive starting agent listener' in alert_messages

    # secondary should stop its listener
    primary.start_agent(uuid_primary)
    gevent.sleep(SLEEP_TIME)
    assert all_agents_running(primary)
    assert not all_agents_running(secondary)
    assert 'Primary is active stopping agent listener' in alert_messages
    assert 'Starting agent listener' in alert_messages
    listen1.core.stop()
    listen2.core.stop()


def test_primary_on_secondary_crash(simple_failover):
    global uuid_secondary
    primary, secondary = simple_failover

    secondary.skip_cleanup = True
    secondary.shutdown_platform()
    gevent.sleep(SLEEP_TIME)
    assert all_agents_running(primary)

    secondary.startup_platform(secondary.vip_address)
    secondary.start_agent(uuid_secondary)

    gevent.sleep(SLEEP_TIME)
    assert all_agents_running(primary)
    assert not all_agents_running(secondary)
    secondary.skip_cleanup = False


def test_secondary_on_primary_crash(simple_failover):
    global uuid_primary
    primary, secondary = simple_failover

    primary.skip_cleanup = True
    primary.shutdown_platform()
    gevent.sleep(SLEEP_TIME)
    assert all_agents_running(secondary)

    primary.startup_platform(primary.vip_address)

    # primary.startup_platform(vip_address, **args)
    primary.start_agent(uuid_primary)

    gevent.sleep(SLEEP_TIME)
    assert all_agents_running(primary)
    assert not all_agents_running(secondary)

    primary.skip_cleanup = False


def test_can_handle_agent_upgrade(simple_failover):
    global listener_primary
    primary, secondary = simple_failover

    primary.remove_agent(listener_primary)
    listener_primary = primary.install_agent(agent_dir=get_examples("ListenerAgent"),
                                             vip_identity="listener",
                                             start=False)

    gevent.sleep(SLEEP_TIME)
    assert all_agents_running(primary)
    assert not all_agents_running(secondary)
