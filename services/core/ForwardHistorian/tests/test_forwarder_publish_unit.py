from unittest import mock

from zmq.green import EAGAIN, ENOTSOCK, ZMQError

from forwarder import agent as forwarder_agent
from forwarder.agent import ForwardHistorian


def _make_forwarder(first_target, second_target):
    """Build a forwarder without a platform; historian_setup hands out the
    second target connection after the first one has been torn down. A
    second historian_setup call raises AssertionError, so a test that
    reconnects more than once fails at once instead of looping."""
    fwd = object.__new__(ForwardHistorian)
    fwd.cache_only = False
    fwd.destination_vip = "tcp://127.0.0.1:22916"
    fwd.destination_address = None
    fwd.required_target_agents = []
    fwd.gather_timing_data = False
    fwd.instance_name = "forwarder-test"
    fwd._last_timeout = 0
    fwd._num_failures = 0
    fwd._target_platform = first_target
    fwd.core = mock.Mock(address="ipc://@/unused")
    fwd.vip = mock.Mock()
    fwd.report_handled = mock.Mock()
    fwd.timestamp = lambda: 1000.0

    def _setup():
        if fwd.historian_setup.call_count > 1:
            raise AssertionError("historian_setup called more than once")
        fwd._target_platform = second_target

    fwd.historian_setup = mock.Mock(side_effect=_setup)
    return fwd


def _record(n):
    return {"topic": f"devices/campus/building/{n}",
            "value": {"headers": {}, "message": {"n": n}}}


def test_publish_reconnects_after_target_socket_closed():
    dead = mock.Mock()
    dead.vip.pubsub.publish.return_value.get.side_effect = ZMQError(ENOTSOCK)
    live = mock.Mock()
    fwd = _make_forwarder(dead, live)
    records = [_record(1), _record(2)]

    fwd.publish_to_historian(records)

    assert fwd.historian_setup.call_count == 1
    dead.core.stop.assert_called_once()
    assert live.vip.pubsub.publish.call_count == 2
    published = [c.kwargs["topic"] for c in live.vip.pubsub.publish.call_args_list]
    assert published == [r["topic"] for r in records]
    fwd.report_handled.assert_called_once_with(records)
    assert fwd._target_platform is live


def _dead():
    target = mock.Mock()
    target.vip.pubsub.publish.return_value.get.side_effect = ZMQError(ENOTSOCK)
    return target


def _statuses(fwd):
    return [c.args[1] for c in fwd.vip.health.set_status.call_args_list]


def test_publish_gives_up_when_reconnect_fails():
    fwd = _make_forwarder(_dead(), None)
    records = [_record(1)]

    fwd.publish_to_historian(records)

    assert fwd.historian_setup.call_count == 1
    assert fwd._target_platform is None
    fwd.report_handled.assert_called_once_with([])
    statuses = _statuses(fwd)
    assert statuses[0] == "Target platform disconnected"
    assert statuses[-1] == "Target platform disconnected"
    assert not any(m.startswith("published") for m in statuses)
    assert not any(m.startswith("Unhandled error") for m in statuses)


def test_failed_reconnect_stops_the_batch_without_an_attribute_error():
    dead = _dead()
    fwd = _make_forwarder(dead, None)

    fwd.publish_to_historian([_record(1), _record(2)])

    assert dead.vip.pubsub.publish.call_count == 1
    assert fwd.historian_setup.call_count == 1
    fwd.report_handled.assert_called_once_with([])
    statuses = _statuses(fwd)
    assert not any(m.startswith("Unhandled error") for m in statuses)
    assert statuses[-1] == "Target platform disconnected"


def test_publish_retries_a_dead_connection_once():
    also_dead = _dead()
    fwd = _make_forwarder(_dead(), also_dead)

    fwd.publish_to_historian([_record(1)])

    assert also_dead.vip.pubsub.publish.call_count == 1
    assert fwd.historian_setup.call_count == 1
    fwd.report_handled.assert_called_once_with([])


def test_second_dead_connection_stops_the_batch_and_fails_cleanly():
    second = mock.Mock()
    second.vip.pubsub.publish.return_value.get.side_effect = [
        ZMQError(ENOTSOCK), AssertionError("resent twice")]
    fwd = _make_forwarder(_dead(), second)

    fwd.publish_to_historian([_record(1), _record(2)])

    assert second.vip.pubsub.publish.call_count == 1
    assert fwd.historian_setup.call_count == 1
    fwd.report_handled.assert_called_once_with([])
    assert fwd._target_platform is None
    assert not any(m.startswith("Unhandled error") for m in _statuses(fwd))


def test_publish_reconnects_at_most_once_per_batch():
    second = mock.Mock()
    second.vip.pubsub.publish.return_value.get.side_effect = [
        None, ZMQError(ENOTSOCK)]
    fwd = _make_forwarder(_dead(), second)
    records = [_record(1), _record(2)]

    fwd.publish_to_historian(records)

    assert fwd.historian_setup.call_count == 1
    assert second.vip.pubsub.publish.call_count == 2
    handled = fwd.report_handled.call_args.args[0]
    assert [r["topic"] for r in handled] == [records[0]["topic"]]
    assert _statuses(fwd)[-1] == "published 1 items"


def test_other_zmq_errors_are_logged():
    target = mock.Mock()
    target.vip.pubsub.publish.return_value.get.side_effect = ZMQError(EAGAIN)
    fwd = _make_forwarder(target, None)

    with mock.patch.object(forwarder_agent, "_log") as log:
        fwd.publish_to_historian([_record(1)])

    fwd.historian_setup.assert_not_called()
    assert log.error.call_count == 1
    assert "ZMQ error" in log.error.call_args.args[0]
    fwd.report_handled.assert_called_once_with([])
    assert not any(m.startswith("published") for m in _statuses(fwd))


class _FakeTimeout(Exception):
    active = 0

    def __init__(self, *args):
        super().__init__(*args)

    def __enter__(self):
        _FakeTimeout.active += 1
        return self

    def __exit__(self, *exc):
        _FakeTimeout.active -= 1
        return False


def test_reconnect_runs_outside_the_publish_timer():
    live = mock.Mock()
    fwd = _make_forwarder(_dead(), live)
    inside = []
    real_setup = fwd.historian_setup.side_effect

    def _setup():
        inside.append(_FakeTimeout.active)
        real_setup()

    fwd.historian_setup.side_effect = _setup
    _FakeTimeout.active = 0
    with mock.patch.object(forwarder_agent.gevent, "Timeout", _FakeTimeout):
        fwd.publish_to_historian([_record(1)])

    assert inside == [0]
    assert live.vip.pubsub.publish.call_count == 1
    handled = fwd.report_handled.call_args.args[0]
    assert [r["topic"] for r in handled] == [_record(1)["topic"]]
