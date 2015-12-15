import gevent
import pytest

from volttron.platform.vip.agent import Agent, PubSub, Core

class PlatormTestAgent(Agent):
    ''' A standalone version of the ListenerAgent'''

    def onmessage(self, peer, sender, bus, topic, headers, message):
        '''Handle incoming messages on the bus.'''
        d = {'topic': topic, 'headers': headers, 'message': message}
        sys.stdout.write(json.dumps(d)+'\n')

    @Core.receiver('onstart')
    def start(self, sender, **kwargs):
        '''Handle the starting of the agent.

        Subscribe to all points in the topics_prefix_to_watch tuple
        defined in settings.py.
        '''
        self.vip.pubsub.subscribe(peer='pubsub', prefix='',
            callback=self.onmessage).get(timeout=5)

    # Demonstrate periodic decorator and settings access
    @Core.periodic(1)
    def publish_heartbeat(self):
        '''Send heartbeat message every heartbeat_period seconds.

        heartbeat_period is set and can be adjusted in the settings module.
        '''
        sys.stdout.write('publishing heartbeat.\n')
        now = datetime.utcnow().isoformat(' ') + 'Z'
        headers = {
            #'AgentID': self._agent_id,
            headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
            headers_mod.DATE: now,
        }
        self.vip.pubsub.publish(
            'pubsub', 'heartbeat/standalonelistener', headers,
            now).get(timeout=5)


def test_can_connect_to_instance(volttron_instance1):
    assert volttron_instance1 is not None
    assert volttron_instance1.is_running()
    message = 'Pinging Hello'
    agent = volttron_instance1.build_agent()
    response = agent.vip.ping('', message).get(timeout=3)
    agent.core.stop()
    assert response[0] == message

def test_can_publish_messages(volttron_instance1):
    amessage = [None]
    def onmessage(peer, sender, bus, topic, headers, message):
        amessage[0] = message

    agent_publisher = volttron_instance1.build_agent()
    response = agent_publisher.vip.ping('', 'woot').get(timeout=3)
    assert response[0] == 'woot'
    agent_subscriber = volttron_instance1.build_agent()
    response = agent_subscriber.vip.ping('', 'woot2').get(timeout=3)
    assert response[0] == 'woot2'
    print('ADDRESS IS: ',agent_publisher.core.address)
    agent_subscriber.vip.pubsub.subscribe(peer='pubsub',
        prefix='test/data', callback=onmessage).get(timeout=5)
    themessage = 'I am a fish!'
    agent_publisher.vip.pubsub.publish(peer='pubsub',
        topic='test/data', message=themessage).get(timeout=5)

    agent_subscriber.core.stop()
    agent_publisher.core.stop()

    assert themessage == amessage[0]


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
