import logging

import gevent
import pytest
from dateutil.parser import parse as dateparse
from zmq.utils import jsonapi as json

logging.basicConfig(level=logging.DEBUG)
from volttron.platform.vip.agent import Agent, Core, RPC
from volttron.platform.messaging.health import STATUS_GOOD, STATUS_BAD, \
    STATUS_UNKNOWN

# TODO Craig: What do the initial export statements do?
@pytest.fixture
def example_agent(volttron_instance1):
    class ExampleAgent(Agent):
        @Core.receiver('onsetup')
        def setup(self, sender, **kwargs):
            self.vip.rpc.export(self.foo)
            self.vip.rpc.export(self.baz, 'bar')
            self.vip.rpc.export('meh')
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
            print(
                'received: peer=%r, sender=%r, bus=%r, topic=%r, headers=%r, '
                'message=%r' % (
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

        def changestatusunknown(self, context):
            self.core._set_status(STATUS_UNKNOWN, context)

        def changestatusbad(self, context):
            self.core._set_status(STATUS_BAD, context)

    return ExampleAgent(address=volttron_instance1.vip_address)

# TODO
@pytest.mark.xfail(
    reason="Question for Craig. Does status method need to be moved?")
@pytest.mark.agent
def test_agent_status_set_when_created(example_agent):
    assert example_agent.core.status() is not None
    assert isinstance(example_agent.core.status(), str)
    l = json.loads(example_agent.core.status())
    assert l['status'] == STATUS_GOOD
    assert l['context'] is not None


# TODO
@pytest.mark.xfail(
    reason="Question for Craig. Does status method need to be moved?")
@pytest.mark.agent
def test_agent_status_changes(example_agent):
    unknown_message = "This is unknown"
    bad_message = "Bad kitty"
    example_agent.changestatusunknown(unknown_message)
    r = json.loads(example_agent.core.status())
    assert unknown_message == r['context']
    assert STATUS_UNKNOWN == r['status']

    example_agent.changestatusbad(bad_message)
    r = json.loads(example_agent.core.status())
    assert bad_message == r['context']
    assert STATUS_BAD == r['status']


# TODO
@pytest.mark.xfail(
    reason="Question for Craig. Does status method need to be moved?")
@pytest.mark.agent
def test_agent_last_update_increses(example_agent):
    s = json.loads(example_agent.core.status())
    dt = dateparse(s['last_updated'], fuzzy=True)
    example_agent.changestatusunknown('Unknown now!')
    gevent.sleep(1)
    s = json.loads(example_agent.core.status())
    dt2 = dateparse(s['last_updated'], fuzzy=True)
    assert dt < dt2
