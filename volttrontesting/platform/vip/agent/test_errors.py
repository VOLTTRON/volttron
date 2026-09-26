"""Unit tests for VIPError.from_errno (#3273) and RemoteError (#3254).

VIPError.from_errno: The wire can deliver errnum as either an int or the
string form 'Errno.<NAME>' produced by str(IntEnum member). from_errno must
accept both and construct the same, correctly typed error either way.

RemoteError: construct with message only and with exc_info; message-only
must not raise UnboundLocalError.
"""
import errno

import pytest

from volttron.platform.jsonrpc import RemoteError
from volttron.platform.vip.agent.errors import (
    Again,
    UnknownSubsystem,
    Unreachable,
    VIPError,
)

PEER = 'some.peer'
SUBSYSTEM = 'some.subsystem'

MAPPED = [
    (errno.EHOSTUNREACH, Unreachable),
    (errno.EAGAIN, Again),
    (errno.EPROTONOSUPPORT, UnknownSubsystem),
]


@pytest.mark.parametrize('errnum,expected_cls', MAPPED)
def test_from_errno_int_maps_to_expected_class(errnum, expected_cls):
    err = VIPError.from_errno(errnum, 'boom', PEER, SUBSYSTEM)

    assert isinstance(err, expected_cls)
    assert err.errno == errnum
    assert err.msg == 'boom'
    assert err.peer == PEER
    assert err.subsystem == SUBSYSTEM


def test_from_errno_unmapped_int_falls_back_to_base_class():
    # errno.ENOENT is not one of the three mapped codes in errors.py.
    err = VIPError.from_errno(errno.ENOENT, 'missing', PEER, SUBSYSTEM)

    assert type(err) is VIPError
    assert err.errno == errno.ENOENT
    assert err.msg == 'missing'


@pytest.mark.parametrize('errnum,expected_cls', MAPPED)
def test_from_errno_string_form_matches_int_form(errnum, expected_cls):
    # Regression for #3273: the wire delivers 'Errno.EHOSTUNREACH' style
    # strings, and int() on that string raises ValueError, which kills the
    # agent's vip_loop greenlet. The string form must produce the identical
    # result as the int form.
    wire_name = 'Errno.' + errno.errorcode[errnum]

    err = VIPError.from_errno(wire_name, 'boom', PEER, SUBSYSTEM)

    assert isinstance(err, expected_cls)
    assert err.errno == errnum
    assert err.msg == 'boom'
    assert err.peer == PEER
    assert err.subsystem == SUBSYSTEM


def test_remote_error_with_message_only():
    # Issue #3254: RemoteError("text") must construct without raising
    # UnboundLocalError when no exc_info is supplied.
    msg_text = 'something went wrong'
    err = RemoteError(msg_text)

    assert isinstance(err, RemoteError)
    assert str(err) == msg_text
    assert err.message == msg_text
    assert err.exc_info == {}


def test_remote_error_with_exc_info_preserves_existing_behavior():
    # Existing behavior: when exc_info contains exc_type and exc_args, msg
    # is formatted as 'exc_type(args)'.
    msg_text = 'remote error'
    exc_info = {
        'exc_type': 'ValueError',
        'exc_args': ['invalid value', 42],
    }
    err = RemoteError(msg_text, **exc_info)

    assert isinstance(err, RemoteError)
    assert str(err) == "ValueError('invalid value', 42)"
    assert err.message == msg_text
    assert err.exc_info == exc_info


def test_remote_error_with_exc_info_missing_exc_type_falls_back_to_message():
    # When exc_info is present but lacks exc_type or exc_args, msg is the
    # original message.
    msg_text = 'remote error'
    exc_info = {'exc_tb': 'some traceback'}
    err = RemoteError(msg_text, **exc_info)

    assert isinstance(err, RemoteError)
    assert str(err) == msg_text
    assert err.message == msg_text
    assert err.exc_info == exc_info


def test_remote_error_repr_with_message_only():
    # When RemoteError has no exc_type, repr includes the message so that
    # logs and error reports show the actual error, not '<unknown>(...)'.
    msg_text = 'connection failed'
    err = RemoteError(msg_text)

    assert msg_text in repr(err)


def test_remote_error_repr_with_exc_type_unchanged():
    # When exc_type is present, repr format is unchanged to preserve
    # compatibility with code that parses the exc_type(exc_args) format.
    msg_text = 'remote error'
    exc_info = {
        'exc_type': 'RuntimeError',
        'exc_args': ['failed to initialize'],
    }
    err = RemoteError(msg_text, **exc_info)

    assert repr(err) == "RuntimeError('failed to initialize')"
    assert msg_text not in repr(err)
