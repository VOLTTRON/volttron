import gevent
import pytest

from volttron.platform.messaging import headers as headers_mod
from volttrontesting.utils.core_service_installs import add_forward_historian
from volttrontesting.utils.platformwrapper import PlatformWrapper, \
    start_wrapper_platform
from volttrontesting.utils.utils import build_devices_header_and_message, \
    publish_device_messages


@pytest.fixture(scope="module")
def setup_instances():

    inst1 = PlatformWrapper()
    inst2 = PlatformWrapper()

    start_wrapper_platform(inst1)
    start_wrapper_platform(inst2)

    yield inst1, inst2

    inst1.shutdown_platform()
    inst2.shutdown_platform()


def instance_reset(wrapper):
    if not wrapper.is_running():
        wrapper.restart_platform()

    wrapper.remove_all_agents()


def test_target_shutdown(setup_instances):

    inst_forward, inst_target = setup_instances
    inst_target.allow_all_connections()
    instance_reset(inst_forward)
    instance_reset(inst_target)

    listener_vip = "testforwarder"
    forward_config = {
        "destination-vip": inst_target.vip_address,
        "destination-serverkey": inst_target.serverkey
        # ,
        # "required_target_agents": listener_vip
    }

    forwarder_uuid = add_forward_historian(inst_forward,
                                           config=forward_config)

    pubsub_retrieved = []

    def _device_capture(peer, sender, bus, topic, headers, message):
        pubsub_retrieved.append((topic, headers, message))

    pub_listener = inst_target.build_agent()
    pub_listener.vip.pubsub.subscribe(peer="pubsub",
                                      prefix="devices",
                                      callback=_device_capture)

    gevent.sleep(0.1)

    all_topic = 'devices/campus/building/all'
    headers, message = publish_device_messages(inst_forward, all_topic=all_topic)

    assert len(pubsub_retrieved) == 1
    assert all_topic == pubsub_retrieved[0][0]
    assert headers[headers_mod.DATE] == pubsub_retrieved[0][1][headers_mod.DATE]

    for k, v in pubsub_retrieved[0][2][0].items():
        assert k in message[0]
        # pytest.approx gives 10^-6 (one millionth accuracy)
        assert message[0][k] == pytest.approx(v)

    pub_listener.core.stop()
    inst_target.stop_platform()

    assert not inst_target.is_running()
    assert inst_forward.is_agent_running(forwarder_uuid)

    pubsub_retrieved = []

    inst_target.restart_platform()
    assert inst_target.is_running()

    pub_listener = inst_target.build_agent()
    pub_listener.vip.pubsub.subscribe(peer="pubsub",
                                      prefix="devices",
                                      callback=_device_capture)

    gevent.sleep(0.1)

    all_topic = 'devices/campus/building/all'
    headers, message = publish_device_messages(inst_forward,
                                               all_topic=all_topic)
    assert len(pubsub_retrieved) == 1
    assert all_topic == pubsub_retrieved[0][0]
    assert headers[headers_mod.DATE] == pubsub_retrieved[0][1][headers_mod.DATE]

    for k, v in pubsub_retrieved[0][2][0].items():
        assert k in message[0]
        # pytest.approx gives 10^-6 (one millionth accuracy)
        assert message[0][k] == pytest.approx(v)


def test_can_configure(setup_instances):
    pass