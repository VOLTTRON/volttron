import gevent
import pytest
import time
import warnings

from volttrontesting.utils.platformwrapper import PlatformWrapper
from volttron.platform.vip.agent import Agent, PubSub, Core

@pytest.mark.wrapper
def test_can_cleanup_installed_listener():
    try:
        import psutil
    except:
        warnings.warn('No psutil module present for this test')
        return
    wrapper = PlatformWrapper()
    address="tcp://127.0.0.1:4848"
    wrapper.startup_platform(address)

    assert wrapper is not None
    assert wrapper.is_running()

    auuid = wrapper.install_agent(agent_dir="examples/ListenerAgent",
        start=False)
    assert auuid is not None
    started = wrapper.start_agent(auuid)
    assert isinstance(started[0], int)
    assert psutil.pid_exists(started[0])
    
    wrapper.shutdown_platform()
    # give operating system enough time to update pids.
    gevent.sleep(0.1)
    assert not psutil.pid_exists(started[0])
