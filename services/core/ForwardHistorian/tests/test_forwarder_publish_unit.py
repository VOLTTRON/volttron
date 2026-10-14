from unittest import mock

from zmq.green import ENOTSOCK, ZMQError

from forwarder.agent import ForwardHistorian


def _make_forwarder(first_target, second_target):
    """Build a forwarder without a platform; historian_setup hands out the
    second target connection after the first one has been torn down."""
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


def test_publish_gives_up_when_reconnect_fails():
    dead = mock.Mock()
    dead.vip.pubsub.publish.return_value.get.side_effect = ZMQError(ENOTSOCK)
    fwd = _make_forwarder(dead, None)
    records = [_record(1)]

    fwd.publish_to_historian(records)

    assert fwd.historian_setup.call_count == 1
    assert fwd._target_platform is None
    fwd.report_handled.assert_called_once_with([])
    statuses = [c.args[1] for c in fwd.vip.health.set_status.call_args_list]
    assert statuses[0] == "Target platform disconnected"
    assert not any(m.startswith("Unhandled error") for m in statuses)


def test_publish_retries_a_dead_connection_once_per_record():
    dead = mock.Mock()
    dead.vip.pubsub.publish.return_value.get.side_effect = ZMQError(ENOTSOCK)
    also_dead = mock.Mock()
    also_dead.vip.pubsub.publish.return_value.get.side_effect = ZMQError(ENOTSOCK)
    fwd = _make_forwarder(dead, also_dead)

    fwd.publish_to_historian([_record(1)])

    assert also_dead.vip.pubsub.publish.call_count == 1
    assert fwd.historian_setup.call_count == 1
    fwd.report_handled.assert_called_once_with([])
