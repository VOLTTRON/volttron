import pytest
import gevent
from gevent.queue import Queue
#from gevent.queue import StopIteration
#from gevent.queue import Queue

@pytest.fixture(scope='module')
def messages():
    return Queue()

def fun1(messages):
    messages.put("fun1-1")
    gevent.sleep(0)
    messages.put('fun1-2')

def fun2(messages):
    messages.put("fun2-1")
    gevent.sleep(0)
    messages.put('fun2-2')

@pytest.mark.gevent
def test_yielding(messages):
    gevent.joinall([
        gevent.spawn(fun1, messages),
        gevent.spawn(fun2, messages)
    ])
    messages.put(StopIteration)

    assert messages.get() == 'fun1-1'
    assert messages.get() == 'fun2-1'
    assert messages.get() == 'fun1-2'
    assert messages.get() == 'fun2-2'
