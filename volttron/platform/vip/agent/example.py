


import gevent

from volttron.platform.vip.agent import *
from volttron.platform.scheduling import periodic


def meh():
    return 'meh'


class ExampleAgent(Agent):
    @Core.receiver('onsetup')
    def setup(self, sender, **kwargs):
        self.vip.rpc.export(self.foo)
        self.vip.rpc.export(self.baz, 'bar')
        self.vip.rpc.export(meh)
        self.vip.pubsub.add_bus('')
        self.core.onfinish.connect(self.finish)
        self.core.schedule(periodic(5), self.saybye)

    @Core.receiver('onstart')
    def starting(self, sender, **kwargs):
        print('agent starting')
        _, _, my_id = self.vip.hello().get(timeout=3)
        print('I am', my_id)
        self.vip.pubsub.subscribe(my_id, 'this/topic', self.onmessage)

    def onmessage(self, peer, sender, bus, topic, headers, message):
        print('received: peer=%r, sender=%r, bus=%r, topic=%r, headers=%r, message=%r' % (
            peer, sender, bus, topic, headers, message))

    @Core.receiver('onstop')
    def stopping(self, sender, **kwargs):
        print('agent stopping')

    def finish(self, sender, **kwargs):
        print('agent finished')

    @Core.schedule(periodic(3))
    def sayhi(self):
        print('hello')

    def saybye(self):
        print('bye')

    @RPC.export
    def hello(self, name):
        return 'Hello, %s!' % (name,)

    @RPC.export('bye')
    def goodbye(self, name):
        return 'Bye, %s!' % (name,)

    def foo(self):
        return 'foo'

    def baz(self):
        return 'baz'


if __name__ == '__main__':
    agent = ExampleAgent('example')
    print('1  ===========================')
    greenlet = gevent.spawn(agent.core.run)
    gevent.sleep(10)
    print('2  ===========================')
    print(agent.vip.ping('example', 'Are you hearing this?').get(timeout=3))
    try:
        print(agent.vip.ping('doah', 'hear me!').get(timeout=3))
    except Unreachable as e:
        print("It was unreachable!")
    print('3  ===========================')
    print(agent.vip.rpc.call('example', 'hello', 'world').get(timeout=3))
    print(agent.vip.rpc.call('example', 'meh').get(timeout=3))
    print(agent.vip.rpc.call('example', 'inspect').get(timeout=3))
    print(agent.vip.rpc.call('example', 'hello.inspect').get(timeout=3))
    print('4  ===========================')
    print(agent.vip.pubsub.publish('example', 'this/topic/here', {'key': 'value'},
                             'Are you the Walrus?').get(timeout=3))
    print('5  ===========================')
    sock = agent.vip.channel('example', 'testing')
    sock.send('Oh say can you see?')
    print(sock.recv())
    print('6  ===========================')
    agent.core.stop()
    gevent.sleep(5)
