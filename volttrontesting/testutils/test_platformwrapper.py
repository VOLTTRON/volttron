import gevent
import pytest
import time

from zmq import curve_keypair

from volttron.platform.vip.agent import Agent, PubSub, Core
from volttron.platform.vip.socket import encode_key
from volttrontesting.utils.platformwrapper import PlatformWrapper

@pytest.mark.wrapper
def test_can_connect_to_instance(volttron_instance1):
    assert volttron_instance1 is not None
    assert volttron_instance1.is_running()
    assert not volttron_instance1.list_agents()
    message = 'Pinging Hello'
    agent = volttron_instance1.build_agent()
    response = agent.vip.ping('', message).get(timeout=3)
    agent.core.stop()
    assert response[0] == message

@pytest.mark.wrapper
def test_can_install_listener(volttron_instance1):
    clear_messages()
    vi = volttron_instance1
    assert vi is not None
    assert vi.is_running()

    auuid = vi.install_agent(agent_dir="examples/ListenerAgent",
        start=False)
    assert auuid is not None
    started = vi.start_agent(auuid)
    print('STARTED: ', started)
    listening = vi.build_agent()
    listening.vip.pubsub.subscribe(peer='pubsub',
        prefix='heartbeat/listeneragent', callback=onmessage)
    # sleep for 10 seconds and at least one heartbeat should have been published
    # because it's set to 5 seconds.
    time_start = time.time()

    print('Awaiting heartbeat response.')
    while not 'heartbeat/listeneragent' in messages.keys() and \
        time.time() < time_start + 10:
        gevent.sleep(0.2)

    assert 'heartbeat/listeneragent' in messages.keys()

    stopped = vi.stop_agent(auuid)
    print('STOPPED: ', stopped)
    removed = vi.remove_agent(auuid)
    print('REMOVED: ', removed)

@pytest.mark.wrapper
def test_can_ping_pubsub(volttron_instance1):
    vi = volttron_instance1
    agent = vi.build_agent()
    resp = agent.vip.ping('', 'hello').get(timeout=5)
    print('ROUTER RESP: ', resp)
    resp = agent.vip.ping('pubsub', 'hello').get(timeout=5)
    print('PUBSUB RESP: ', resp)

@pytest.mark.wrapper
def test_can_call_rpc_method(volttron_instance1):
    config = dict(agentid="Central Platform", report_status_period=15)
    agent_uuid = volttron_instance1.install_agent(agent_dir='services/core/Platform',
                                                  config_file=config,
                                                  start=True)
    assert agent_uuid is not None
    assert volttron_instance1.is_agent_running(agent_uuid)

    agent = volttron_instance1.build_agent()

    agent_list = agent.vip.rpc.call('platform.agent', method='list_agents').get(timeout=5)

    print('The agent list is: {}'.format(agent_list))
    assert agent_list is not None


messages = {}
def onmessage(peer, sender, bus, topic, headers, message):
    messages[topic] = {'headers': headers, 'message': message}

def clear_messages():
    global messages
    messages = {}

@pytest.mark.wrapper
def test_can_publish(volttron_instance1):
    global messages
    clear_messages()
    vi = volttron_instance1
    agent = vi.build_agent()
#    gevent.sleep(0)
    agent.vip.pubsub.subscribe(peer='pubsub', prefix='test/world',
        callback=onmessage).get(timeout=5)

    agent_publisher = vi.build_agent()
#    gevent.sleep(0)
    agent_publisher.vip.pubsub.publish(peer='pubsub', topic='test/world',
        message='got data')
    # sleep so that the message bus can actually do some work before we
    # eveluate the global messages.
    gevent.sleep(0.1)
    assert messages['test/world']['message'] == 'got data'

def test_can_ping_router(volttron_instance1):
    vi = volttron_instance1
    agent = vi.build_agent()
    resp = agent.vip.ping('', 'router?').get(timeout=4)
    #resp = agent.vip.hello().get(timeout=1)
    print("HELLO RESPONSE!",resp)

@pytest.mark.wrapper
def test_can_install_listener_on_two_platforms(volttron_instance1, volttron_instance2):
    global messages
    clear_messages()
    auuid = volttron_instance1.install_agent(agent_dir="examples/ListenerAgent",
        start=False)
    assert auuid is not None
    started = volttron_instance1.start_agent(auuid)
    print('STARTED: ', started)
    listening = volttron_instance1.build_agent()
    listening.vip.pubsub.subscribe(peer='pubsub',
        prefix='heartbeat/listeneragent', callback=onmessage)

    # sleep for 10 seconds and at least one heartbeat should have been published
    # because it's set to 5 seconds.
    time_start = time.time()

    print('Awaiting heartbeat response for platform1.')
    while not 'heartbeat/listeneragent' in messages.keys() and \
        time.time() < time_start + 10:
        gevent.sleep(0.2)

    assert 'heartbeat/listeneragent' in messages.keys()

    clear_messages()
    auuid2 = volttron_instance2.install_agent(agent_dir="examples/ListenerAgent",
        start=True)
    assert auuid2 is not None
    started2 = volttron_instance2.start_agent(auuid2)
    print('STARTED: ', started2)
    listening = volttron_instance2.build_agent()
    listening.vip.pubsub.subscribe(peer='pubsub',
        prefix='heartbeat/listeneragent', callback=onmessage)

    # sleep for 10 seconds and at least one heartbeat should have been published
    # because it's set to 5 seconds.
    time_start = time.time()

    print('Awaiting heartbeat response for platform2.')
    while not 'heartbeat/listeneragent' in messages.keys() and \
        time.time() < time_start + 10:
        gevent.sleep(0.2)

    assert 'heartbeat/listeneragent' in messages.keys()



# def test_can_ping_control(volttron_instance2):
#     agent = volttron_instance2.build_agent()
#     res = agent.vip.ping('aip', 'hello').get(timeout=5)
#     assert res[0] == 'hello'

# def test_can_publish_messages(volttron_instance1):
#     amessage = [None]
#     def onmessage(peer, sender, bus, topic, headers, message):
#         amessage[0] = message
#
#     agent_publisher = volttron_instance1.build_agent()
#     response = agent_publisher.vip.ping('', 'woot').get(timeout=3)
#     assert response[0] == 'woot'
#     agent_subscriber = volttron_instance1.build_agent()
#     response = agent_subscriber.vip.ping('', 'woot2').get(timeout=3)
#     assert response[0] == 'woot2'
#
#     agent_subscriber.vip.pubsub.subscribe(peer='pubsub',
#         prefix='test/data', callback=onmessage).get(timeout=5)
#     themessage = 'I am a fish!'
#     agent_publisher.vip.pubsub.publish(peer='pubsub',
#         topic='test/data', message=themessage).get(timeout=5)
#
#     agent_subscriber.core.stop()
#     agent_publisher.core.stop()
#
#     assert themessage == amessage[0]


# def test_volttron_fixtures(volttron_instance1, volttron_instance2):
#     assert volttron_instance1 is not None
#     assert volttron_instance2 is not None
#     assert volttron_instance1 != volttron_instance2
#     assert volttron_instance2.is_running()
#     assert volttron_instance1.is_running()
#     print('VIP ADDRESS')
#     print(volttron_instance1.vip_address)
#     ipc = "ipc://"+volttron_instance1.volttron_home+"/run/vip.socket"
#     agent = Agent(address='tcp://127.0.0.1:22916')
#     gevent.spawn(agent.core.run)
#     gevent.sleep(0)
#     print('AFTER SLEEPING')
#     response = agent.vip.hello('Hello World!').get(timeout=5)
#     print(response)
#     agent.core.stop()
#
#     agent = PlatormTestAgent(address=volttron_instance1.vip_address[0],
#                              identity='Listener Found')
#     task = gevent.spawn(agent.core.run)
#     gevent.sleep(10)
#     response = agent.vip.ping('doah', 'hear me!').get(timeout=3)
#     print("PINGING")
#     print(response)
#     agent.core.stop()
#
#
#
#
#
# def test_instance_enviornment(volttron_instance1, volttron_instance2):
#     assert volttron_instance1.env['VOLTTRON_HOME'] != \
#         volttron_instance2.env['VOLTTRON_HOME']
#
# def test_platform_startup(volttron_instance1, volttron_instance2):
#     assert volttron_instance1.is_running()
#     assert volttron_instance2.is_running()
#     assert not volttron_instance1.twistd_is_running()
#     assert not volttron_instance2.twistd_is_running()
#
# def test_install_listener(volttron_instance1, listener_agent_wheel):
#     uuid = volttron_instance1.install_agent(agent_dir='examples/ListenerAgent')
#     assert uuid
#     status = volttron_instance1.agent_status(uuid)
#     assert status != (None, None)
#     assert volttron_instance1.confirm_agent_running("listeneragent-3.0")

@pytest.mark.wrapper
def test_encryption():
    addr = 'tcp://127.0.0.1:55055'
    pub, sec = curve_keypair()
    publickey, secretkey = encode_key(pub), encode_key(sec)
    auth = {'allow': [{'credentials': 'CURVE:{}'.format(publickey)}]}

    plat = PlatformWrapper()
    plat.startup_platform(vip_address=addr, auth_dict=auth, encrypt=True)

    agent_addr = '{}?serverkey={}&publickey={}&secretkey=' \
                 '{}'.format(addr, plat.publickey, publickey, secretkey)

    agent1 = plat.build_agent(agent_addr, identity='agent1')
    peers = agent1.vip.peerlist.list().get(timeout=2)
    plat.shutdown_platform(True)
    print('PEERS: ', peers)
    assert len(peers) > 0
