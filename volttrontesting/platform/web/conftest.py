from unittest import mock
from unittest.mock import MagicMock

import pytest

from volttron.platform.agent.known_identities import PLATFORM_WEB
from volttron.platform.web.platform_web_service import PlatformWebService


def set_caller(service, user, peer=None):
    """Make the next export call look as if it came from this agent."""
    message = service.vip.rpc.context.vip_message
    message.user = user
    message.peer = user if peer is None else peer


def build_web_service(tmp_path, monkeypatch, start=True, enable_auth=True):
    """A PlatformWebService whose bus and web server are mocks.

    With start, startupagent builds the real built-in route table; nothing
    listens on a socket and no file watcher runs.
    """
    monkeypatch.setenv('VOLTTRON_HOME', str(tmp_path))
    service = PlatformWebService.__new__(PlatformWebService)
    # Some tests in this package replace the class's base with a mock, so
    # patch whichever base is in place rather than Agent itself.
    base = PlatformWebService.__mro__[1]
    with mock.patch.object(base, '__init__', lambda self, *args, **kwargs: None):
        PlatformWebService.__init__(service, serverkey='serverkey', identity=PLATFORM_WEB,
                                    address='inproc://web-test',
                                    bind_web_address='http://127.0.0.1:8080',
                                    web_secret_key='not-a-real-secret')
    service.vip = MagicMock()
    service.core = MagicMock()
    service.core.messagebus = 'zmq'
    service.core.enable_auth = enable_auth
    if start:
        query = MagicMock()
        query.return_value.query.return_value.get.return_value = 'test-instance'
        with mock.patch('volttron.platform.web.vui_endpoints.Query', query), \
                mock.patch('volttron.platform.web.admin_endpoints.Observer'), \
                mock.patch('volttron.platform.web.authenticate_endpoint.Observer'), \
                mock.patch('volttron.platform.web.platform_web_service.WSGIServer'), \
                mock.patch('volttron.platform.web.platform_web_service.gevent.spawn'):
            service.startupagent(sender='test')
    return service


@pytest.fixture()
def web_service(tmp_path, monkeypatch):
    return build_web_service(tmp_path, monkeypatch)
