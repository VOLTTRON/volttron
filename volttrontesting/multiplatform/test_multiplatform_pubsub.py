import os

import gevent
import pytest

from volttron.platform import jsonapi
from volttron.platform import get_ops
from volttrontesting.utils.utils import (poll_gevent_sleep,
                                         messages_contains_prefix)

from volttrontesting.fixtures.volttron_platform_fixtures import get_rand_vip, \
    build_wrapper, get_rand_ip_and_port
from volttrontesting.utils.platformwrapper import PlatformWrapper
from volttron.platform.agent.known_identities import PLATFORM_DRIVER, CONFIGURATION_STORE

subscription_results = {}
count = 0


def onmessage(peer, sender, bus, topic, headers, message):
    global subscription_results
    subscription_results[topic] = {'headers': headers, 'message': message}
    print("subscription_results[{}] = {}".format(topic, subscription_results[topic]))


@pytest.fixture(scope="module")
def get_volttron_instances(request):
    """ Fixture to get more than 1 volttron instance for test
    Use this fixture to get more than 1 volttron instance for test. This
    returns a function object that should be called with number of instances
    as parameter to get a list of volttron instnaces. The fixture also
    takes care of shutting down all the instances at the end

    Example Usage:

    def test_function_that_uses_n_instances(get_volttron_instances):
        instance1, instance2, instance3 = get_volttron_instances(3)

    @param request: pytest request object
    @return: function that can used to get any number of
        volttron instances for testing.
    """
    all_instances = []

    def get_n_volttron_instances(n, should_start=True, address_file=True):
        get_n_volttron_instances.count = n
        instances = []
        vip_addresses = []
        web_addresses = []
        instances = []
        addr_config = dict()
        names = []

        for i in range(0, n):
            address = get_rand_vip()
            web_address = "http://{}".format(get_rand_ip_and_port())
            vip_addresses.append(address)
            web_addresses.append(web_address)
            nm = 'platform{}'.format(i + 1)
            names.append(nm)

        for i in range(0, n):
            address = vip_addresses[i]
            web_address = web_addresses[i]
            wrapper = PlatformWrapper(messagebus='zmq', ssl_auth=False)

            addr_file = os.path.join(wrapper.volttron_home, 'external_address.json')
            if address_file:
                with open(addr_file, 'w') as f:
                    jsonapi.dump(web_addresses, f)
                    gevent.sleep(.1)
            wrapper.startup_platform(address, bind_web_address=web_address, setupmode=True)
            wrapper.skip_cleanup = True
            instances.append(wrapper)

        gevent.sleep(30)
        for i in range(0, n):
            instances[i].shutdown_platform()

        gevent.sleep(1)
        # del instances[:]
        for i in range(0, n):
            address = vip_addresses.pop(0)
            web_address = web_addresses.pop(0)
            print(address, web_address)
            instances[i].startup_platform(address, bind_web_address=web_address)
            instances[i].allow_all_connections()
        gevent.sleep(11)
        instances = instances if n > 1 else instances[0]

        get_n_volttron_instances.instances = instances
        return instances

    return get_n_volttron_instances


@pytest.fixture(scope="module")
def build_instances(request):
    """ Fixture to get more than 1 volttron instance for test
    Use this fixture to get more than 1 volttron instance for test. This
    returns a function object that should be called with number of instances
    as parameter to get a list of volttron instnaces. The fixture also
    takes care of shutting down all the instances at the end

    Example Usage:

    def test_function_that_uses_n_instances(get_volttron_instances):
        instance1, instance2, instance3 = get_volttron_instances(3)

    @param request: pytest request object
    @return: function that can used to get any number of
        volttron instances for testing.
    """
    all_instances = []

    def build_n_volttron_instances(n, bad_config=False, add_my_address=True):
        build_n_volttron_instances.count = n
        instances = []
        vip_addresses = []
        instances = []
        addr_config = dict()

        for i in range(0, n):
            address = get_rand_vip()
            vip_addresses.append(address)

        for i in range(0, n):
            address = vip_addresses[i]
            wrapper = PlatformWrapper(messagebus='zmq', ssl_auth=False)
            wrapper.startup_platform(address)
            wrapper.skip_cleanup = True
            instances.append(wrapper)

        gevent.sleep(1)
        for i in range(0, n):
            instances[i].shutdown_platform()

        for i in range(0, n):
            addr_config.clear()
            for j in range(0, n):
                if j != i or (j==i and add_my_address):
                    name = instances[j].instance_name
                    addr_config[name] = dict()
                    addr_config[name]['instance-name'] = name
                    if bad_config:
                        addr_config[name]['vip-address123'] = vip_addresses[j]
                    else:
                        addr_config[name]['vip-address'] = vip_addresses[j]
                    addr_config[name]['serverkey'] = instances[j].serverkey

            address_file = os.path.join(instances[i].volttron_home, 'external_platform_discovery.json')
            if address_file:
                with open(address_file, 'w') as f:
                    jsonapi.dump(addr_config, f)

        gevent.sleep(1)
        for i in range(0, n):
            address = vip_addresses.pop(0)
            instances[i].startup_platform(address)
            instances[i].allow_all_connections()
        gevent.sleep(11)
        instances = instances if n > 1 else instances[0]

        build_n_volttron_instances.instances = instances
        return instances

    return build_n_volttron_instances


@pytest.fixture(scope="module")
def multi_platform_connection(request, get_volttron_instances):
    """
    Adds the volttron-central-address and volttron-central-serverkey to the
    main instance configuration file before starting the platform
    """
    p1, p2, p3 = get_volttron_instances(3)

    gevent.sleep(5)

    # configure vc
    agent1 = p1.dynamic_agent
    agent2 = p2.dynamic_agent
    agent3 = p3.build_agent()

    def stop():
        agent3.core.stop()
        p1.shutdown_platform()
        p2.shutdown_platform()
        p3.shutdown_platform()

    request.addfinalizer(stop)

    return agent1, agent2, agent3


@pytest.fixture(scope="module")
def five_platform_connection(request, get_volttron_instances):
    """
    Adds the volttron-central-address and volttron-central-serverkey to the
    main instance configuration file before starting the platform
    """
    p1, p2, p3, p4, p5 = get_volttron_instances(5)

    gevent.sleep(5)

    # configure vc
    agent1 = p1.dynamic_agent
    agent2 = p2.dynamic_agent
    agent3 = p3.dynamic_agent
    agent4 = p4.dynamic_agent
    agent5 = p5.dynamic_agent

    def stop():
        p1.shutdown_platform()
        p2.shutdown_platform()
        p3.shutdown_platform()
        p4.shutdown_platform()
        p5.shutdown_platform()

    request.addfinalizer(stop)

    return agent1, agent2, agent3, agent4, agent5


@pytest.mark.multiplatform
def test_multiplatform_pubsub(request, multi_platform_connection):
    p1_publisher, p2_listener, p3_listener = multi_platform_connection

    p2_listener.vip.pubsub.subscribe(peer='pubsub',
                                     prefix='devices',
                                     callback=onmessage,
                                     all_platforms=True)
    p3_listener.vip.pubsub.subscribe(peer='pubsub',
                                     prefix='devices',
                                     callback=onmessage)
    gevent.sleep(1)

    prefix = 'devices'
    for i in range(10):
        p1_publisher.vip.pubsub.publish(peer='pubsub',
                                        topic='devices/campus/building1',
                                        message=[{'point': 'value'}])
        poll_gevent_sleep(5, lambda: messages_contains_prefix(prefix,
                                                              subscription_results))

        message = subscription_results['devices/campus/building1']['message']
        assert message == [{'point': 'value'}]


@pytest.mark.multiplatform
def test_multiplatform_2_publishers(request, five_platform_connection):
    subscription_results2 = {}
    subscription_results3 = {}
    subscription_results4 = {}
    subscription_results5 = {}

    p1_publisher, p2_listener, p3_listener, p4_listener, p5_publisher = five_platform_connection

    def callback2(peer, sender, bus, topic, headers, message):
        subscription_results2[topic] = {'headers': headers, 'message': message}
        print("platform2 sub results [{}] = {}".format(topic, subscription_results2[topic]))

    def callback3(peer, sender, bus, topic, headers, message):
        subscription_results3[topic] = {'headers': headers, 'message': message}
        print("platform3 sub results [{}] = {}".format(topic, subscription_results3[topic]))

    def callback4(peer, sender, bus, topic, headers, message):
        subscription_results4[topic] = {'headers': headers, 'message': message}
        print("platform4 sub results [{}] = {}".format(topic, subscription_results4[topic]))

    def callback5(peer, sender, bus, topic, headers, message):
        subscription_results5[topic] = {'headers': headers, 'message': message}
        print("platform4 sub results [{}] = {}".format(topic, subscription_results5[topic]))

    p2_listener.vip.pubsub.subscribe(peer='pubsub',
                                     prefix='devices/campus/building1',
                                     callback=callback2,
                                     all_platforms=True)

    p3_listener.vip.pubsub.subscribe(peer='pubsub',
                                     prefix='devices/campus/building1',
                                     callback=callback3,
                                     all_platforms=True)

    p4_listener.vip.pubsub.subscribe(peer='pubsub',
                                     prefix='analysis',
                                     callback=callback4,
                                     all_platforms=True)

    p5_publisher.vip.pubsub.subscribe(peer='pubsub',
                                      prefix='analysis',
                                      callback=callback5)
    gevent.sleep(5)
    prefix = 'devices'
    for i in range(5):
        p1_publisher.vip.pubsub.publish(peer='pubsub', topic='devices/campus/building1', message=[{'point': 'value'}])
        gevent.sleep(1)
        message = subscription_results2['devices/campus/building1']['message']
        assert message == [{'point': 'value'}]
        message = subscription_results3['devices/campus/building1']['message']
        assert message == [{'point': 'value'}]

    prefix = 'analysis'
    for i in range(5):
        p5_publisher.vip.pubsub.publish(peer='pubsub',
                                        topic='analysis/airside/campus/building1',
                                        message=[{'result': 'pass'}])
        poll_gevent_sleep(2, lambda: messages_contains_prefix(prefix,
                                                              subscription_results4))
        message = subscription_results4['analysis/airside/campus/building1']['message']
        assert message == [{'result': 'pass'}]
        message = subscription_results5['analysis/airside/campus/building1']['message']
        assert message == [{'result': 'pass'}]


@pytest.mark.multiplatform
def test_multiplatform_subscribe_unsubscribe(request, multi_platform_connection):
    subscription_results2 = {}
    subscription_results3 = {}
    p1_publisher, p2_listener, p3_listener = multi_platform_connection

    def callback2(peer, sender, bus, topic, headers, message):
        subscription_results2[topic] = {'headers': headers, 'message': message}
        print("platform2 sub results [{}] = {}".format(topic, subscription_results2[topic]))

    def callback3(peer, sender, bus, topic, headers, message):
        subscription_results3[topic] = {'headers': headers, 'message': message}
        print("platform3 sub results [{}] = {}".format(topic, subscription_results3[topic]))

    p2_listener.vip.pubsub.subscribe(peer='pubsub',
                                     prefix='devices',
                                     callback=callback2,
                                     all_platforms=True)

    p3_listener.vip.pubsub.subscribe(peer='pubsub',
                                     prefix='devices',
                                     callback=callback3,
                                     all_platforms=True)
    gevent.sleep(2)

    prefix = 'devices'
    i = 0
    for i in range(2):
        p1_publisher.vip.pubsub.publish(peer='pubsub', topic='devices/campus/building1',
                                        message=[{'point': 'value' + str(i)}])
        gevent.sleep(0.5)
        message = subscription_results2['devices/campus/building1']['message']
        assert message == [{'point': 'value' + str(i)}]

        message = subscription_results3['devices/campus/building1']['message']
        assert message == [{'point': 'value' + str(i)}]
        print("pass")

    # Listener agent on platform 2 unsubscribes frm prefix='devices'
    p2_listener.vip.pubsub.unsubscribe(peer='pubsub', prefix='devices', callback=callback2, all_platforms=True)
    gevent.sleep(0.2)
    subscription_results2.clear()
    p1_publisher.vip.pubsub.publish(peer='pubsub', topic='devices/campus/building1',
                                    message=[{'point': 'value' + str(2)}])
    gevent.sleep(0.4)
    assert not subscription_results2
    gevent.sleep(0.4)
    message = subscription_results3['devices/campus/building1']['message']
    assert message == [{'point': 'value2'}]


@pytest.mark.multiplatform
def test_multiplatform_stop_subscriber(request, multi_platform_connection):
    subscription_results2 = {}
    subscription_results3 = {}
    message_count = 0
    p1_publisher, p2_listener, p3_listener = multi_platform_connection

    def callback2(peer, sender, bus, topic, headers, message):
        subscription_results2[topic] = {'headers': headers, 'message': message}
        print("platform2 sub results [{}] = {}".format(topic, subscription_results2[topic]))

    def callback3(peer, sender, bus, topic, headers, message):
        subscription_results3[topic] = {'headers': headers, 'message': message}
        print("platform3 sub results [{}] = {}".format(topic, subscription_results3[topic]))

    p2_listener.vip.pubsub.subscribe(peer='pubsub',
                                     prefix='devices',
                                     callback=callback2,
                                     all_platforms=True)

    p3_listener.vip.pubsub.subscribe(peer='pubsub',
                                     prefix='devices/campus/building1',
                                     callback=callback3,
                                     all_platforms=True)
    gevent.sleep(1)

    prefix = 'devices'
    i = 0
    for i in range(2):
        p1_publisher.vip.pubsub.publish(peer='pubsub', topic='devices/campus/building1',
                                        message=[{'point': 'value' + str(i)}])
        gevent.sleep(0.5)
        message = subscription_results2['devices/campus/building1']['message']
        assert message == [{'point': 'value' + str(i)}]
        message = subscription_results3['devices/campus/building1']['message']
        assert message == [{'point': 'value' + str(i)}]

    subscription_results2.clear()
    print("pass")

    # Stop listener agent on platform 2
    p2_listener.core.stop()
    gevent.sleep(0.2)

    p1_publisher.vip.pubsub.publish(peer='pubsub', topic='devices/campus/building1',
                                    message=[{'point': 'value' + str(2)}])
    gevent.sleep(1)
    # check that new message is received by only listener 3
    assert not subscription_results2
    message = subscription_results3['devices/campus/building1']['message']
    assert message == [{'point': 'value2'}]


@pytest.mark.multiplatform
def test_missing_address_file(request, get_volttron_instances):
    p1 = get_volttron_instances(1, address_file=False)
    gevent.sleep(1)
    p1.shutdown_platform()


@pytest.mark.multiplatform
def test_multiplatform_without_setup_mode(request, build_instances):
    subscription_results1 = {}
    subscription_results3 = {}
    p1, p2, p3 = build_instances(3)
    gevent.sleep(1)
    # Get three agents
    agent1 = p1.dynamic_agent
    agent2 = p2.dynamic_agent
    agent3 = p3.dynamic_agent

    def stop():
        p1.shutdown_platform()
        p2.shutdown_platform()
        p3.shutdown_platform()
    request.addfinalizer(stop)

    def callback1(peer, sender, bus, topic, headers, message):
        subscription_results1[topic] = {'headers': headers, 'message': message}
        print("platform2 sub results [{}] = {}".format(topic, subscription_results1[topic]))

    def callback3(peer, sender, bus, topic, headers, message):
        subscription_results3[topic] = {'headers': headers, 'message': message}
        print("platform3 sub results [{}] = {}".format(topic, subscription_results3[topic]))

    agent3.vip.pubsub.subscribe(peer='pubsub',
                                 prefix='devices',
                                 callback=callback3,
                                 all_platforms=True)

    gevent.sleep(0.2)
    agent2.vip.pubsub.subscribe(peer='pubsub',
                                 prefix='devices',
                                 callback=callback1,
                                 all_platforms=True)

    gevent.sleep(1)
    for i in range(0, 2):
        agent1.vip.pubsub.publish(peer='pubsub', topic='devices/building1',
                                 message=[{'point': 'value' + str(i)}])
        gevent.sleep(0.5)
        try:
            message = subscription_results3['devices/building1']['message']
            assert message == [{'point': 'value' + str(i)}]

            message = subscription_results1['devices/building1']['message']
            assert message == [{'point': 'value' + str(i)}]
        except KeyError:
            pass


@pytest.mark.multiplatform
def test_multiplatform_local_subscription(request, build_instances):
    subscription_results1 = {}
    p1 = build_instances(1, add_my_address=True)
    gevent.sleep(1)
    # Get two agents
    agent1 = p1.dynamic_agent
    agent2 = p1.build_agent()

    def stop():
        p1.shutdown_platform()
    request.addfinalizer(stop)

    def callback1(peer, sender, bus, topic, headers, message):
        global count
        count += 1
        subscription_results1[topic] = {'headers': headers, 'message': message, 'count': count}
        print("platform2 sub results [{}] = {}".format(topic, subscription_results1[topic]))

    agent1.vip.pubsub.subscribe(peer='pubsub',
                                 prefix='devices',
                                 callback=callback1,
                                 all_platforms=True)

    gevent.sleep(1)
    for i in range(1, 5):
        agent2.vip.pubsub.publish(peer='pubsub', topic='devices/building1',
                                 message=[{'point': 'value' + str(i)}])
        gevent.sleep(1)
        try:
            message = subscription_results1['devices/building1']['message']
            assert message == [{'point': 'value' + str(i)}]
            assert i == subscription_results1['devices/building1']['count']
        except KeyError:
            pass


@pytest.mark.multiplatform
def test_multiplatform_bad_discovery_file(request, build_instances):
    p1, p2, p3 = build_instances(3, bad_config=True)
    gevent.sleep(1)
    p1.shutdown_platform()
    p2.shutdown_platform()
    p3.shutdown_platform()


@pytest.mark.xfail(reason="Issue #2107. rpc call to edit config store will fail due to capabilities check")
@pytest.mark.multiplatform
def test_multiplatform_rpc(request, get_volttron_instances):
    p1, p2 = get_volttron_instances(2)
    _default_config = {
        "test_max": {
            "threshold_max": 10
        }
    }
    threshold_detection_uuid = p1.install_agent(
        agent_dir=get_ops("ThresholdDetectionAgent"),
        config_file=_default_config,
        start=True)

    updated_config = {
        "updated_topic": {
            "threshold_max": 10,
            "threshold_min": 2,
        }
    }
    test_agent = p2.build_agent()
    kwargs = {"external_platform": p1.instance_name}
    test_agent.vip.rpc.call(CONFIGURATION_STORE,
                            'manage_store',
                            'platform.thresholddetection',
                            'config',
                            jsonapi.dumps(updated_config),
                            'json',
                            **kwargs).get(timeout=10)
    config = test_agent.vip.rpc.call(CONFIGURATION_STORE,
                                     'manage_get',
                                     'platform.thresholddetection',
                                     'config',
                                     raw=True,
                                     **kwargs).get(timeout=10)
    config = jsonapi.loads(config)
    try:
        assert config == updated_config
    except KeyError:
        pytest.fail("Expecting config change : {}".format(config))

    def stop():
        p1.stop_agent(threshold_detection_uuid)
        p2.remove_agent(threshold_detection_uuid)
        p1.shutdown_platform()
        test_agent.core.stop()
        p1.shutdown_platform()

    request.addfinalizer(stop)
