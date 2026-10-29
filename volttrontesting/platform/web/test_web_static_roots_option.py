"""The web-static-roots platform option is a comma-separated list of directories."""
import pytest

from volttron.platform.main import parse_web_static_roots


@pytest.mark.parametrize('value, expected', [
    (None, []),
    ('', []),
    ('/srv/a', ['/srv/a']),
    ('/srv/a,/srv/b', ['/srv/a', '/srv/b']),
    (' /srv/a , /srv/b ', ['/srv/a', '/srv/b']),
    ('/srv/a,,/srv/b,', ['/srv/a', '/srv/b']),
    (',', []),
])
def test_entries_are_split_on_commas_and_trimmed(value, expected):
    assert parse_web_static_roots(value) == expected


def test_entries_expand_the_home_directory_and_variables(monkeypatch):
    monkeypatch.setenv('HOME', '/home/probe')
    monkeypatch.setenv('PROBE_SITE', '/srv/site')
    assert parse_web_static_roots('~/www,$PROBE_SITE/www') == ['/home/probe/www',
                                                                  '/srv/site/www']
