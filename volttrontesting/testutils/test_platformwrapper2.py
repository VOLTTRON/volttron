import gevent
import pytest
import time
import warnings

from volttron.platform import get_examples
from volttrontesting.fixtures.volttron_platform_fixtures import get_rand_port
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

    address="tcp://127.0.0.1:{}".format(get_rand_port())
    wrapper.startup_platform(address)

    assert wrapper is not None
    assert wrapper.is_running()

    auuid = wrapper.install_agent(agent_dir=get_examples("ListenerAgent"),
                                  vip_identity="listener",
                                  start=False)
    assert auuid is not None
    started = wrapper.start_agent(auuid)
    assert isinstance(started, int)
    assert psutil.pid_exists(started)

    wrapper.shutdown_platform()
    # give operating system enough time to update pids.
    gevent.sleep(0.1)
    assert not psutil.pid_exists(started)
