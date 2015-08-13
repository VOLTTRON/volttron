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

'''Interface to Linux rlimit system calls.

This module provides the getrlimit() and setrlimit() calls to get and
set process resource limits. See the getrlimit(3P) man page for full
documentation on the usage of these two functions.
'''

from __future__ import absolute_import, print_function

from collections import namedtuple
import ctypes
from ctypes import c_int, c_long, POINTER
import os


__all__ = ['getrlimit', 'setrlimit', 'rlimit']

__author__ = 'Brandon Carpenter <brandon.carpenter@pnnl.gov>'
__version__ = '1.0'


# --- Constants and descriptions lifted from <sys/resource.h> ---

RLIMIT_CPU = 0   # Per-process CPU limit, in seconds.
RLIMIT_FSIZE = 1   # Largest file that can be created, in bytes.
RLIMIT_DATA = 2   # Maximum size of data segment, in bytes.
RLIMIT_STACK = 3   # Maximum size of stack segment, in bytes.
RLIMIT_CORE = 4   # Largest core file that can be created, in bytes.
# Largest resident set size, in bytes. This affects swapping; processes
# that are exceeding their resident set size will be more likely to
# have physical memory taken from them.
RLIMIT_RSS = 5
RLIMIT_NPROC = 6   # Number of processes.
RLIMIT_NOFILE = 7   # Number of open files.
RLIMIT_OFILE = RLIMIT_NOFILE   # BSD name for same.
RLIMIT_MEMLOCK = 8   # Locked-in-memory address space.
RLIMIT_AS = 9   # Address space limit.
RLIMIT_LOCKS = 10   # Maximum number of file locks.
RLIMIT_SIGPENDING = 11   # Maximum number of pending signals.
RLIMIT_MSGQUEUE = 12   # Maximum bytes in POSIX message queues.
# Maximum nice priority allowed to raise to. Nice levels 19 .. -20
# correspond to 0 .. 39 values of this resource limit.
RLIMIT_NICE = 13
# Maximum realtime priority allowed for non-priviledged processes.
RLIMIT_RTPRIO = 14
# Maximum CPU time in µs that a process scheduled under a real-time
# scheduling policy may consume without making a blocking system
# call before being forcibly descheduled.  */
RLIMIT_RTTIME = 15
RLIMIT_NLIMITS = 16
RLIM_NLIMITS = RLIMIT_NLIMITS

RLIM_INFINITY = -1   # Value to indicate that there is no limit.

# We can represent all limits.
RLIM_SAVED_MAX = RLIM_INFINITY
RLIM_SAVED_CUR = RLIM_INFINITY


__all__.extend(name for name in dir() if name.startswith('RLIM'))


_libc = ctypes.CDLL(None)
_getrlimit = ctypes.CFUNCTYPE(c_int, c_int, POINTER(c_long*2), use_errno=True)(
    ('getrlimit', _libc), ((1, 'resource'), (2, 'rlimit')))
_setrlimit = ctypes.CFUNCTYPE(c_int, c_int, POINTER(c_long*2), use_errno=True)(
    ('setrlimit', _libc), ((1, 'resource'), (1, 'rlimit')))

def _errcheck(result, func, args):
    if result:
        errnum = ctypes.get_errno()
        raise OSError(errnum, os.strerror(errnum))
    if func == _getrlimit:
        return tuple(args[1])

_getrlimit.errcheck = _errcheck
_setrlimit.errcheck = _errcheck


rlimit = namedtuple('rlimit', 'cur max')


def getrlimit(resource):
    '''Return the soft and hard limits on process resource consumption.

    The only argument, resource, should be one of the RLIMIT_* constants
    defined in this module (or an integer equivalent) or a string
    containing the name of the constant, minus the RLIMIT_ (and
    case-insensitive). A named 2-tuple is returned containing the
    current soft (cur) limit followed by the hard maximum (max) limit.

    Example:
        >>> getrlimit(RLIMIT_NOFILE)
        rlimit(cur=1024L, max=4096L)
        >>> getrlimit('nofile')
        rlimit(cur=1024L, max=4096L)

    See the getrlimit(3P) man page for more information
    '''
    if isinstance(resource, basestring):
        resource = globals()['RLIMIT_' + resource.upper()]
    return rlimit(*_getrlimit(resource))


def setrlimit(resource, (soft, hard)):
    '''Set the soft and hard limits on process resource consumption.

    The first argument, resource, should be one of the RLIMIT_*
    constants defined in this module (or an integer equivalent) or a
    string containing the name of the constant, minus the RLIMIT_ (and
    case-insensitive). The second argument must be a 2-tuple containing
    the soft (current) and hard (maximum) limits to set, in that order.
    An rlimit named tuple may be used.

    Example:
        >>> setrlimit(RLIMIT_NOFILE, (2048, 4096))
        >>> setrlimit('nofile', (2048, 2048))

    See the getrlimit(3P) man page for more information
    '''
    if isinstance(resource, basestring):
        resource = globals()['RLIMIT_' + resource.upper()]
    rlp = (c_long*2)(soft, hard)
    _setrlimit(resource, rlp)
