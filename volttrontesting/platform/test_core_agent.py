import logging

import gevent
from zmq.utils import jsonapi as json
import pytest
import requests

logging.basicConfig(level=logging.DEBUG)
from volttrontesting.utils.build_agent import build_agent, build_agent_with_key
from volttron.platform.vip.agent import Agent, Core, RPC
from volttron.platform.vip.agent.core import STATUS_GOOD, STATUS_BAD, STATUS_UNKNOWN

@pytest.fixture
def example_agent(volttron_instance1):
    class ExampleAgent(Agent):
        @Core.receiver('onsetup')
        def setup(self, sender, **kwargs):
            self.vip.rpc.export(self.foo)
            self.vip.rpc.export(self.baz, 'bar')
            self.vip.rpc.export(meh)
            self.vip.pubsub.add_bus('')
            self.core.onfinish.connect(self.finish)
            self.core.periodic(5, self.saybye, wait=None)

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

        @Core.periodic(3)
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

        def set_status(state, context):
            self._set_status(state, context)

    return ExampleAgent(address=volttron_instance1.vip_address)

@pytest.mark.agent
def test_agent_status_set_when_created(example_agent):
    assert example_agent.core.status() is not None
    assert isinstance(example_agent.core.status(), str)
    l = json.loads(example_agent.core.status())
    assert l['state'] == STATUS_GOOD
    assert l['context'] is not None
