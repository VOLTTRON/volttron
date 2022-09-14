import pytest

from volttron.platform import is_rabbitmq_available, is_web_available

HAS_RMQ = is_rabbitmq_available()
HAS_WEB = is_web_available()

rmq_skipif = pytest.mark.skipif(not HAS_RMQ,
                                reason='RabbitMQ is not setup and/or SSL does not work in CI')
web_skipif = pytest.mark.skipif(not HAS_WEB, reason='Web libraries are not installed')
