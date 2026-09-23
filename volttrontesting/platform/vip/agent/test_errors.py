"""Unit tests for VIPError.from_errno (#3273).

The wire can deliver errnum as either an int or the string form
'Errno.<NAME>' produced by str(IntEnum member). from_errno must accept
both and construct the same, correctly typed error either way.
"""
import errno

import pytest

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
