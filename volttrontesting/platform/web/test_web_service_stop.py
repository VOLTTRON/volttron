"""onstop must cope with a service that never finished starting, and must actually stop the server."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import gevent

from volttron.platform.web.platform_web_service import PlatformWebService


def _service(server=None, greenlet=None, manager=None):
    return SimpleNamespace(_server=server, _server_greenlet=greenlet,
                           _vui_endpoints=None if manager is None else SimpleNamespace(pubsub_manager=manager),
                           STOP_TIMEOUT=PlatformWebService.STOP_TIMEOUT)


def test_onstop_before_startup_finished_does_not_raise():
    svc = _service()
    PlatformWebService.onstop(svc, None)
    assert svc._server is None and svc._server_greenlet is None


def test_onstop_stops_the_server_and_lets_serve_forever_return():
    stopped = gevent.event.Event()
    server = MagicMock()
    server.stop.side_effect = lambda timeout=None: stopped.set()
    greenlet = gevent.spawn(stopped.wait)    # stands in for serve_forever: returns only once stop() ran
    manager = MagicMock()
    svc = _service(server, greenlet, manager)

    PlatformWebService.onstop(svc, None)

    manager.shutdown.assert_called_once_with()
    server.stop.assert_called_once_with(timeout=PlatformWebService.STOP_TIMEOUT)
    assert greenlet.dead and svc._server is None and svc._server_greenlet is None


def test_onstop_kills_a_server_greenlet_that_will_not_exit(monkeypatch):
    monkeypatch.setattr(PlatformWebService, 'STOP_TIMEOUT', 0.05)
    server = MagicMock()
    greenlet = gevent.spawn(gevent.sleep, 3600)
    svc = _service(server, greenlet)
    svc.STOP_TIMEOUT = 0.05

    PlatformWebService.onstop(svc, None)
    gevent.sleep(0)

    assert greenlet.dead


def test_onstop_survives_a_failing_server_stop():
    server = MagicMock()
    server.stop.side_effect = RuntimeError('boom')
    greenlet = gevent.spawn(lambda: None)
    greenlet.join()
    PlatformWebService.onstop(_service(server, greenlet), None)


def test_startup_failure_is_logged_and_sets_bad_health(caplog):
    import logging
    svc = SimpleNamespace(_start_web_server=MagicMock(side_effect=FileNotFoundError('web.crt')),
                          vip=SimpleNamespace(health=MagicMock()))
    with caplog.at_level(logging.ERROR, logger='volttron.platform.web.platform_web_service'):
        PlatformWebService.startupagent(svc, None)
    assert 'failed to start' in caplog.text and 'web.crt' in caplog.text
    status, context = svc.vip.health.set_status.call_args.args
    assert status == 'BAD' and 'FileNotFoundError' in context and 'web.crt' in context


def test_require_files_names_every_missing_path(tmp_path):
    present = tmp_path / 'web.crt'
    present.write_text('x')
    PlatformWebService._require_files(web_ssl_cert=str(present), web_ssl_key=None)
    import pytest
    with pytest.raises(FileNotFoundError) as exc:
        PlatformWebService._require_files(web_ssl_cert='/etc/volttron/web.crt', web_ssl_key='/etc/volttron/web.key')
    assert '/etc/volttron/web.crt' in str(exc.value) and '/etc/volttron/web.key' in str(exc.value)
