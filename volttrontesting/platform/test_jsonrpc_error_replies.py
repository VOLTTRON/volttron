"""Unit tests for malformed JSON-RPC error replies (#3324, #3341).

Only a peer outside this repository can send these shapes, so they are
built by hand rather than through a platform.
"""
import logging

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
    "string_data": ("oops", MESSAGE),
    "list_data": ([1, 2], MESSAGE),
    "non_iterable_exc_args": (
        {"exception.py": {"exc_type": "ValueError", "exc_args": 5}},
        MESSAGE,
    ),
    # A 'self' key makes RemoteError(...) raise, which reaches the fallback.
    "self_key_with_detail": (
        {"detail": DETAIL, "exception.py": dict(EXC, self=1)},
        DETAIL,
    ),
    "self_key_without_detail": (
        {"exception.py": dict(EXC, self=1)},
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


def _warnings(caplog):
    return [r for r in caplog.records
            if r.name == jsonrpc.__name__ and r.levelno == logging.WARNING]


@pytest.mark.parametrize("name", ["self_key_with_detail",
                                  "self_key_without_detail"])
def test_fallback_logs_one_warning_without_payload(name, caplog):
    data, _ = SHAPES[name]
    with caplog.at_level(logging.WARNING, logger=jsonrpc.__name__):
        jsonrpc.exception_from_json(
            jsonrpc.UNHANDLED_EXCEPTION, MESSAGE, data)
    records = _warnings(caplog)
    assert len(records) == 1
    text = records[0].getMessage()
    assert "TypeError" in text
    assert DETAIL not in text
    assert "ValueError" not in text


@pytest.mark.parametrize("data, type_name", [
    ("oops", "str"), ([1, 2], "list"), (5, "int")])
def test_non_object_data_logs_one_warning(data, type_name, caplog):
    with caplog.at_level(logging.WARNING, logger=jsonrpc.__name__):
        jsonrpc.exception_from_json(
            jsonrpc.UNHANDLED_EXCEPTION, MESSAGE, data)
    records = _warnings(caplog)
    assert len(records) == 1
    text = records[0].getMessage()
    assert type_name in text
    assert "oops" not in text and "1, 2" not in text


@pytest.mark.parametrize("name", ["well_formed", "null_data",
                                  "null_exception_py",
                                  "message_key_in_exception_py"])
def test_object_or_absent_data_logs_no_warning(name, caplog):
    data, _ = SHAPES[name]
    with caplog.at_level(logging.WARNING, logger=jsonrpc.__name__):
        jsonrpc.exception_from_json(
            jsonrpc.UNHANDLED_EXCEPTION, MESSAGE, data)
    assert _warnings(caplog) == []
