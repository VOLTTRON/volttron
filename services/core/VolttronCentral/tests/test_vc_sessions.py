from services.core.VolttronCentral.volttroncentral.sessions import (
    ABSOLUTE_TIMEOUT, IDLE_TIMEOUT, SessionHandler)


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def _handler():
    clock = FakeClock()
    ended = []
    handler = SessionHandler(on_end=ended.append, clock=clock)
    return handler, clock, ended


def test_limits_are_thirty_minutes_idle_and_four_hours_absolute():
    assert IDLE_TIMEOUT == 30 * 60
    assert ABSOLUTE_TIMEOUT == 240 * 60


def test_new_session_has_distinct_random_session_id_and_channel_id():
    handler, _, _ = _handler()
    session_id, channel = handler._add_session('admin', '10.0.0.1', ['admin'])
    other_id, other_channel = handler._add_session('reader', '10.0.0.2', ['reader'])

    assert len({session_id, channel, other_id, other_channel}) == 4
    # token_urlsafe(32) is 43 characters and token_urlsafe(16) is 22.
    assert len(session_id) == 43
    assert len(channel) == 22


def test_check_session_returns_user_groups_ip_and_channel_but_not_the_session_id():
    handler, _, _ = _handler()
    session_id, channel = handler._add_session('admin', '10.0.0.1', ['admin', 'x'])

    session = handler.check_session(session_id, '10.0.0.1')

    assert session == {'user': 'admin', 'groups': ['admin', 'x'],
                       'ip': '10.0.0.1', 'channel': channel}


def test_check_session_returns_a_copy():
    handler, _, _ = _handler()
    session_id, _ = handler._add_session('admin', '10.0.0.1', ['admin'])

    handler.check_session(session_id, '10.0.0.1')['groups'].append('root')

    assert handler.check_session(session_id, '10.0.0.1')['groups'] == ['admin']


def test_check_session_refuses_unknown_id_and_other_ip():
    handler, _, _ = _handler()
    session_id, _ = handler._add_session('admin', '10.0.0.1', ['admin'])

    assert handler.check_session('nope', '10.0.0.1') is False
    assert handler.check_session(None, '10.0.0.1') is False
    assert handler.check_session(session_id, '10.0.0.9') is False
    assert handler.check_session(session_id, '10.0.0.1')


def test_check_session_with_channel_requires_the_pair():
    handler, _, _ = _handler()
    session_id, channel = handler._add_session('admin', '10.0.0.1', ['admin'])
    other_id, other_channel = handler._add_session('reader', '10.0.0.1', ['reader'])

    assert handler.check_session(session_id, '10.0.0.1', channel=channel)
    assert handler.check_session(session_id, '10.0.0.1', channel=other_channel) is False
    assert handler.check_session(session_id, '10.0.0.1', channel=None) is False
    assert handler.check_session(session_id, '10.0.0.1', channel=5) is False
    assert handler.check_session(other_id, '10.0.0.1', channel=other_channel)


def test_session_ends_after_thirty_idle_minutes_and_reports_the_channel():
    handler, clock, ended = _handler()
    session_id, channel = handler._add_session('admin', '10.0.0.1', ['admin'])

    clock.advance(IDLE_TIMEOUT - 1)
    assert handler.check_session(session_id, '10.0.0.1')
    clock.advance(IDLE_TIMEOUT)

    assert handler.check_session(session_id, '10.0.0.1') is False
    assert ended == [channel]
    assert handler._session_tokens == {}
    assert handler._sessions == {}


def test_activity_keeps_a_session_alive_until_the_absolute_limit():
    handler, clock, ended = _handler()
    session_id, channel = handler._add_session('admin', '10.0.0.1', ['admin'])

    # A request every 20 minutes never idles out.
    for _ in range(11):
        clock.advance(20 * 60)
        assert handler.check_session(session_id, '10.0.0.1')
    clock.advance(20 * 60)

    assert clock.now - 1000.0 == 12 * 20 * 60
    assert handler.check_session(session_id, '10.0.0.1') is False
    assert ended == [channel]


def test_expire_ends_idle_sessions_without_a_request():
    handler, clock, ended = _handler()
    _, idle_channel = handler._add_session('admin', '10.0.0.1', ['admin'])
    clock.advance(IDLE_TIMEOUT - 5)
    live_id, _ = handler._add_session('reader', '10.0.0.2', ['reader'])
    clock.advance(10)

    handler.expire()

    assert ended == [idle_channel]
    assert handler.check_session(live_id, '10.0.0.2')


def test_login_again_removes_the_old_session_and_reports_it():
    handler, _, ended = _handler()
    old_id, old_channel = handler._add_session('admin', '10.0.0.1', ['admin'])

    new_id, new_channel = handler._add_session('admin', '10.0.0.1', ['admin'])

    assert handler.check_session(old_id, '10.0.0.1') is False
    assert handler.check_session(new_id, '10.0.0.1')
    assert ended == [old_channel]
    assert new_channel != old_channel
    assert len(handler._session_tokens) == 1


def test_clear_ends_every_session():
    handler, _, ended = _handler()
    _, first = handler._add_session('admin', '10.0.0.1', ['admin'])
    _, second = handler._add_session('reader', '10.0.0.2', ['reader'])

    handler.clear()

    assert sorted(ended) == sorted([first, second])
    assert handler._sessions == {} and handler._session_tokens == {}


def test_check_channel_matches_the_ip_and_does_not_extend_the_session():
    handler, clock, ended = _handler()
    session_id, channel = handler._add_session('admin', '10.0.0.1', ['admin'])

    assert handler.check_channel(channel, '10.0.0.1') is True
    assert handler.check_channel(channel, '10.0.0.9') is False
    assert handler.check_channel('unknown', '10.0.0.1') is False
    assert handler.check_channel(None, '10.0.0.1') is False

    clock.advance(IDLE_TIMEOUT - 1)
    assert handler.check_channel(channel, '10.0.0.1') is True
    clock.advance(2)
    assert handler.check_channel(channel, '10.0.0.1') is False
    assert ended == [channel]
    assert handler.check_session(session_id, '10.0.0.1') is False
