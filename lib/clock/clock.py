# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2013, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
#}}}

'''Python interface to POSIX clock and time functions.

Exports [clock_]getres, [clock_]gettime, and [clock_]settime system
calls.  Also adds real, monotonic, process, and thread functions as
shorthand calls to clock_gettime.

See also clock_getres(2), clock_gettime(2), and clock_settime(2).
'''

import ctypes
from ctypes import c_long, c_int
import os


__all__ = ['getres', 'gettime', 'settime', 'combine']

__author__ = 'Brandon Carpenter <brandon.carpenter@pnnl.gov>'
__version__ = '1.0'


try:
    _librt = ctypes.CDLL('librt.so.1')
    _getres = ctypes.CFUNCTYPE(c_int, c_int, c_long*2, use_errno=True)(
            ('clock_getres', _librt), ((1, None, 0), (2,)))
    _gettime = ctypes.CFUNCTYPE(c_int, c_int, c_long*2, use_errno=True)(
            ('clock_gettime', _librt), ((1, None, 0), (2,)))
    _settime = ctypes.CFUNCTYPE(c_int, c_int, c_long*2, use_errno=True)(
            ('clock_settime', _librt), ((1, None, 0), (1,)))
except (OSError, AttributeError) as e:
    raise ImportError(*e.args)


def _errcheck(result, func, args):
    if result:
        errnum = ctypes.get_errno()
        raise OSError(errnum, os.strerror(errnum))
    if func is not _settime:
        return tuple(args[1])

_getres.errcheck = _errcheck
_gettime.errcheck = _errcheck
_settime.errcheck = _errcheck


def getres(clock_id=0):
    '''Return the resolution of the given clock.

    Returns the resolution of the specified clock as a 2-tuple where the
    first value is the precision in seconds and the second value is
    additional precision in nanoseconds.  clock_id defaults to REALTIME.

    See also clock.combine().
    '''
    return _getres(clock_id)


def gettime(clock_id=0):
    '''Return the time of the given clock.

    Returns the time of the specified clock as a 2-tuple where the
    first value is the time in seconds and the second value is
    additional time in nanoseconds.  clock_id defaults to REALTIME.

    See also clock.combine().
    '''
    return _gettime(clock_id)


def settime(timespec, clock_id=0):
    '''Set the time of the given clock to timespec.

    Set the time of the specified clock.  If timespec is a 2-tuple,
    the first value is the time in seconds and the second value is
    additional time in nanoseconds.  Otherwise, timespec is assumed
    to be a float indicating the time in seconds.  clock_id
    defaults to REALTIME.
    '''
    try:
        tp0, tp1 = timespec
    except TypeError:
        tp0 = long(timespec)
        tp1 = long(round((timespec - tp0) * 1000000000))
    tp = (c_long*2)(tp0, tp1)
    _settime(clock_id, tp)


def combine(timespec):
    '''Combine the timespec tuple and return as a float.

    Return the combined second and nanosecond components of
    timespec (returned by getres() and gettime()) as a float.
    '''
    return timespec[0] + timespec[1] / 1000000000.0


def __init__():
    clocks = [
        ('REALTIME', 0,
            'System-wide realtime clock.'),
        ('MONOTONIC', 1,
            'Monotonic system-wide clock.'),
        ('PROCESS_CPUTIME', 2,
            'High-resolution timer from the CPU.'),
        ('THREAD_CPUTIME', 3,
            'Thread-specific CPU-time clock.'),
        ('MONOTONIC_RAW', 4,
            'Monotonic system-wide clock, not adjusted for frequency scaling.'),
        ('REALTIME_COARSE', 5,
            'System-wide realtime clock, updated only on ticks.'),
        ('MONOTONIC_COARSE', 6,
            'Monotonic system-wide clock, updated only on ticks.'),
        ('BOOTTIME', 7,
            'Monotonic system-wide clock that includes time spent in suspension.'),
        ('REALTIME_ALARM', 8,
            'Like REALTIME but also wakes suspended system.'),
        ('BOOTTIME_ALARM', 9,
            'Like BOOTTIME but also wakes suspended system.'),
    ]
    _globals = globals()
    def mkclock(clock_id):
        '''Keeps clock_id in local scope preventing it from changing
        value in the loop below.'''
        return lambda: combine(gettime(clock_id))
    for name, clk_id, doc in clocks:
        fn = mkclock(clk_id)
        fn.__doc__ = doc
        lname = name.lower()
        __all__.extend([name, lname])
        _globals[name] = clk_id
        _globals[lname] = fn
    

__init__()
del __init__

