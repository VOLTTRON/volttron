import pytest

from volttron.platform import is_rabbitmq_available, is_web_available
from volttrontesting.utils.platformwrapper import PlatformWrapper

HAS_RMQ = is_rabbitmq_available()
HAS_WEB = is_web_available()

rmq_skipif = pytest.mark.skipif(not HAS_RMQ,
                                reason='RabbitMQ is not setup and/or SSL does not work in CI')
web_skipif = pytest.mark.skipif(not HAS_WEB, reason='Web libraries are not installed')


def skip_zmq(platform_wrapper: PlatformWrapper):
    if platform_wrapper.messagebus == 'zmq':
        pytest.skip("ZMQ not available for test.")
