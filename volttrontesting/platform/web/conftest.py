from unittest import mock
from unittest.mock import MagicMock

import pytest

from volttron.platform.agent.known_identities import PLATFORM_WEB
from volttrontesting.fixtures.volttron_platform_fixtures import (build_wrapper, ci_skipif,
                                                                 cleanup_wrapper)
from volttrontesting.utils.utils import (get_hostname_and_random_port, get_rand_ip_and_port,
                                         get_rand_vip)
from volttron.platform.web.platform_web_service import PlatformWebService


def set_caller(service, user, peer=None):
    """Make the next export call look as if it came from this agent."""
    message = service.vip.rpc.context.vip_message
    message.user = user
    message.peer = user if peer is None else peer


def build_web_service(tmp_path, monkeypatch, start=True, enable_auth=True, home=None,
                      static_roots=None, **service_kwargs):
    """A PlatformWebService whose bus and web server are mocks.

    With start, startupagent builds the real built-in route table; nothing
    listens on a socket and no file watcher runs. VOLTTRON_HOME is home, by
    default a sibling of tmp_path, and the configured static roots are
    static_roots, by default tmp_path alone.
    """
    if home is None:
        home = tmp_path.with_name(tmp_path.name + '-home')
        home.mkdir(exist_ok=True)
    monkeypatch.setenv('VOLTTRON_HOME', str(home))
    service = PlatformWebService.__new__(PlatformWebService)
    # Some tests in this package replace the class's base with a mock, so
    # patch whichever base is in place rather than Agent itself.
    base = PlatformWebService.__mro__[1]
    with mock.patch.object(base, '__init__', lambda self, *args, **kwargs: None):
        PlatformWebService.__init__(service, serverkey='serverkey', identity=PLATFORM_WEB,
                                    address='inproc://web-test',
                                    bind_web_address='http://127.0.0.1:8080',
                                    web_secret_key='not-a-real-secret',
                                    web_static_roots=([str(tmp_path)] if static_roots is None
                                                      else static_roots),
                                    **service_kwargs)
    service.vip = MagicMock()
    service.core = MagicMock()
    service.core.messagebus = 'zmq'
    service.core.enable_auth = enable_auth
    if start:
        start_web_service(service)
    return service


def start_web_service(service, server=None):
    """Run startupagent with the web server class replaced by server."""
    query = MagicMock()
    query.return_value.query.return_value.get.return_value = 'test-instance'
    with mock.patch('volttron.platform.web.vui_endpoints.Query', query), \
            mock.patch('volttron.platform.web.admin_endpoints.Observer'), \
            mock.patch('volttron.platform.web.authenticate_endpoint.Observer'), \
            mock.patch('volttron.platform.web.platform_web_service.WSGIServer',
                       server or MagicMock()), \
            mock.patch('volttron.platform.web.platform_web_service.gevent.spawn'):
        service.startupagent(sender='test')


@pytest.fixture()
def web_service(tmp_path, monkeypatch):
    return build_web_service(tmp_path, monkeypatch)


@pytest.fixture(scope='module', params=[
    pytest.param(False, id='http'),
    pytest.param(True, id='https', marks=ci_skipif),
])
def web_instance_with_static_root(request, tmp_path_factory):
    """A web platform with two web-static-roots entries outside
    VOLTTRON_HOME; tests serve from the last, web_static_roots[-1]."""
    if request.param:
        hostname, port = get_hostname_and_random_port()
        web_address = f'https://{hostname}:{port}'
    else:
        web_address = f'http://{get_rand_ip_and_port()}'
    roots = [tmp_path_factory.mktemp('web-static-extra'), tmp_path_factory.mktemp('web-static-root')]
    wrapper = build_wrapper(get_rand_vip(), ssl_auth=request.param, bind_web_address=web_address,
                            volttron_central_address=web_address, instance_name='volttron1',
                            web_static_roots=[str(root) for root in roots])
    yield wrapper
    cleanup_wrapper(wrapper)
