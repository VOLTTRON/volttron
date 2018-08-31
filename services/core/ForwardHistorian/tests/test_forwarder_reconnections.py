import gevent
import pytest

from volttrontesting.utils.agent_additions import add_forward_historian
from volttrontesting.utils.platformwrapper import PlatformWrapper, \
    start_wrapper_platform
from volttrontesting.utils.utils import (publish_device_messages,
                                         validate_published_device_data,
                                         publish_message)


@pytest.fixture(scope="module")
def setup_instances(request):

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


@pytest.mark.parametrize('topic_root,topic,replace,headers', [
    ('devices', 'campus/building/unit/all', None, None),
    ('devices', 'campus/building/unit/all', [{'from': 'building', 'to': 'woot'}], None),
    ('record', 'building/data', None, None),
    ('record', 'building/data', [{'from': 'building', 'to': 'woot'}], None),
    ('actuator', 'foo/bar', None, None)
])
def test_topic_forwarding(setup_instances, topic_root, topic, replace, headers):
    inst_forward, inst_target = setup_instances
    inst_target.allow_all_connections()
    instance_reset(inst_forward)
    instance_reset(inst_target)
    forward_config = {
        "destination-vip": inst_target.vip_address,
        "destination-serverkey": inst_target.serverkey
    }

    if replace:
        forward_config['topic_replace_list'] = replace

    if topic_root not in ('devices', 'record', 'analysis', 'datalogger'):
        forward_config['custom_topic_list'] = [topic_root]

    forwarder_uuid = add_forward_historian(inst_forward,
                                           config=forward_config)

    pubsub_retrieved = []

    def _device_capture(peer, sender, bus, topic, headers, message):
        pubsub_retrieved.append((topic, headers, message))

    pub_listener = inst_target.build_agent()
    pub_listener.vip.pubsub.subscribe(peer="pubsub",
                                      prefix=topic_root,
                                      callback=_device_capture).get()

    gevent.sleep(0.5)

    full_topic = '/'.join([topic_root, topic])

    if topic_root == 'devices':
        headers, message = publish_device_messages(inst_forward,
                                                   all_topic=full_topic)
        validate_published_device_data(headers, message,
                                       pubsub_retrieved[0][1],
                                       pubsub_retrieved[0][2])

    elif topic_root == 'record':
        headers, message = publish_message(inst_forward, full_topic,
                                           headers=dict(foo='bar'),
                                           message=dict(bim='baz'))
        for k, v in headers.items():
            assert k in pubsub_retrieved[0][1]
            assert v == pubsub_retrieved[0][1][k]
        for k, v in message.items():
            assert k in pubsub_retrieved[0][2]
            assert v == pubsub_retrieved[0][2][k]

    elif topic_root == 'datalogger':
        raise ValueError('not implemented yet')
    else:
        headers, message = publish_message(inst_forward, full_topic,
                                           headers=dict(foo='bar'),
                                           message='A simple string')
        for k, v in headers.items():
            assert k in pubsub_retrieved[0][1]
            assert v == pubsub_retrieved[0][1][k]
        assert message == pubsub_retrieved[0][2]
        assert full_topic == pubsub_retrieved[0][0]

    if replace:
        new_topic = full_topic
        for item in replace:
            new_topic = new_topic.replace(item['from'], item['to'])
        assert new_topic == pubsub_retrieved[0][0]


    # Stop the listener
    pub_listener.core.stop()


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

    validate_published_device_data(headers, message,
                                   pubsub_retrieved[0][1], pubsub_retrieved[0][2])

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
    validate_published_device_data(headers, message,
                                   pubsub_retrieved[0][1],
                                   pubsub_retrieved[0][2])
