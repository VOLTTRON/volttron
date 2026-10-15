"""A VolttronCentralAgent with a mocked VIP, for tests that need no platform."""
from unittest import mock

from services.core.VolttronCentral.volttroncentral import agent as vc_agent

IP = '10.0.0.1'
PASSWORD = 'sekrit-pw-4829'


def make_agent(monkeypatch, login=None):
    """Return a configured agent.

    `login` is what the platform's authenticate_web_user answers: a dict, or an
    exception instance to raise. Greenlets spawned for socket cleanup run
    inline so a test can read the result.
    """
    agent = vc_agent.VolttronCentralAgent.__new__(vc_agent.VolttronCentralAgent)
    agent._default_config = {'webroot': '/tmp/webroot', 'users': {},
                             'topic_replace_list': []}
    agent._authenticated_sessions = None
    agent._websocket_endpoints = set()
    agent.vip = mock.Mock()
    agent._platforms = mock.Mock()
    monkeypatch.setattr(vc_agent.gevent, 'spawn_later', lambda *a, **k: None)
    monkeypatch.setattr(vc_agent.gevent, 'spawn',
                        lambda fn, *a, **k: fn(*a, **k))
    monkeypatch.setattr(vc_agent.gevent, 'sleep', lambda *a, **k: None)
    agent._configure('config', 'NEW', {})
    set_login_answer(agent, login)
    return agent


def set_login_answer(agent, login):
    result = agent.vip.rpc.call.return_value
    if isinstance(login, BaseException):
        result.get.side_effect = login
    else:
        result.get.side_effect = None
        result.get.return_value = login


def env(cookie=None, ip=IP, scheme='http'):
    environment = {'REQUEST_METHOD': 'POST', 'wsgi.url_scheme': scheme,
                   'HTTP_HOST': 'localhost:8443', 'REMOTE_ADDR': ip}
    if cookie is not None:
        environment['HTTP_COOKIE'] = cookie
    return environment


def rpc(method, params=None, authorization=None, id='1'):
    data = {'jsonrpc': '2.0', 'id': id, 'method': method, 'params': params}
    if authorization is not None:
        data['authorization'] = authorization
    return data


def login(agent, user='admin', groups=('admin',), ip=IP, scheme='http'):
    """Log in through jsonrpc; returns (cookie header value, channel id)."""
    set_login_answer(agent, {'user': user, 'groups': list(groups)})
    status, body, headers = agent.jsonrpc(
        env(ip=ip, scheme=scheme),
        rpc('get_authorization', {'username': user, 'password': PASSWORD}))
    assert status == '200 OK'
    cookie = dict(headers)['Set-Cookie'].split(';')[0]
    channel = vc_agent.jsonapi.loads(body)['result']
    return cookie, channel
