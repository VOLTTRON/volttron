"""Unit tests for malformed JSON-RPC error replies (#3324).

Only a peer outside this repository can send these shapes, so they are
built by hand rather than through a platform.
"""
import pytest

from volttron.platform import jsonrpc
from volttron.platform.vip.agent.subsystems.rpc import Dispatcher

MESSAGE = "server said no"
DETAIL = "detail text"
EXC = {"exc_type": "ValueError", "exc_args": ["bad"]}

# id -> (data, expected RemoteError.message)
SHAPES = {
    "well_formed": ({"detail": DETAIL, "exception.py": EXC}, DETAIL),
    "null_data": (None, MESSAGE),
    "null_exc_args": (
        {"exception.py": {"exc_type": "ValueError", "exc_args": None}},
        MESSAGE,
    ),
    "null_exception_py": ({"exception.py": None}, MESSAGE),
    "message_key_in_exception_py": (
        {"exception.py": dict(EXC, message="clash")},
        MESSAGE,
    ),
}


@pytest.fixture(params=list(SHAPES), ids=list(SHAPES))
def shape(request):
    return SHAPES[request.param]


def test_well_formed_reply_text():
    err = jsonrpc.exception_from_json(
        jsonrpc.UNHANDLED_EXCEPTION, MESSAGE, SHAPES["well_formed"][0])
    assert str(err) == "ValueError('bad')"
    assert repr(err) == "ValueError('bad')"


def test_null_data_text():
    err = jsonrpc.exception_from_json(
        jsonrpc.UNHANDLED_EXCEPTION, MESSAGE, None)
    assert str(err) == MESSAGE
    assert repr(err) == "<unknown>: " + MESSAGE


def test_null_exc_args_text():
    data, _ = SHAPES["null_exc_args"]
    err = jsonrpc.exception_from_json(
        jsonrpc.UNHANDLED_EXCEPTION, MESSAGE, data)
    assert str(err) == MESSAGE
    assert "ValueError" in repr(err)


def test_error_reply_gives_remote_error_with_message(shape):
    data, expected_message = shape
    err = jsonrpc.exception_from_json(
        jsonrpc.UNHANDLED_EXCEPTION, MESSAGE, data)
    assert isinstance(err, jsonrpc.RemoteError)
    assert err.message == expected_message
    assert isinstance(str(err), str)
    assert isinstance(repr(err), str)


def test_dispatcher_completes_pending_result_with_error(shape):
    data, expected_message = shape
    dispatcher = Dispatcher({}, None)
    pending = next(dispatcher._results)
    dispatcher.error(
        None, pending.ident, jsonrpc.UNHANDLED_EXCEPTION, MESSAGE, data)
    assert pending.ready()
    with pytest.raises(jsonrpc.RemoteError) as excinfo:
        pending.get(timeout=1)
    assert excinfo.value.message == expected_message
