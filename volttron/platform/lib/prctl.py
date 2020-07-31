# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

'''Python interface to Linux process control mechanism.

Exports prctl system call.

See also prctl(2).
'''

import ctypes
from ctypes import c_int, c_ulong, c_char, c_char_p, POINTER
import functools
import os


__all__ = ['prctl']

__author__ = 'Brandon Carpenter <brandon.carpenter@pnnl.gov>'
__version__ = '2.0'


def _prctl(option, *argtypes, **kwargs):
    use_result = kwargs.pop('use_result', False)
    assert not kwargs
    global _libc
    try:
        _libc
    except NameError:
        _libc = ctypes.CDLL(None)

    typeargs = [c_ulong]
    paramflags = [(1, 'option')]
    for i, argtype in enumerate(argtypes, 2):
        assert 0 < len(argtype) <= 4
        typeargs.append(argtype[0])
        if len(argtype) == 1:
            paramflags.append((1, 'arg%d' % i))
        elif len(argtype) == 2:
            paramflags.append((argtype[1], 'arg%d' % i))
        else:
            paramflags.append(argtype[1:])

    def errcheck(result, func, args):
        if result == -1:
            errnum = ctypes.get_errno()
            raise OSError(errnum, os.strerror(errnum))
        if use_result:
            return result
        elif use_result is None:
            return result, args
        result = tuple(value.value for i, value in enumerate(args)
                       if paramflags[i][0] & 2)
        if len(result) == 1:
            return result[0]
        return result or None

    func = ctypes.CFUNCTYPE(c_int, *typeargs, use_errno=True)(
        ('prctl', _libc), tuple(paramflags))
    func.errcheck = errcheck
    return functools.partial(func, option)


def prctl(option, *args):
    '''Perform control operations on a process using prctl(2).

    Perform control operations on a process by passing in one of the
    PR_GET_* or PR_SET_* options and any additional arguments as
    specified by the prctl documentation.  The result varies based on
    the option.  An OSError exception is raised on error.

    See also prctl(2).
    '''
    return _prototypes[option](*args)


_prototypes = {}
def _prototype(name, number, *argtypes, **kwargs):
    globs = globals()
    option = 'PR_%s' % (name.upper(),)
    func = _prctl(number, *argtypes, **kwargs)
    func.__name__ = name
    globs[option] = number
    _prototypes[number] = globs[name] = func
    __all__.extend([name, option])


# ---- Comments and values below were taken from <sys/prctl.h> ----

# Values to pass as first argument to prctl()

_prototype('set_pdeathsig', 1, (c_ulong,))
_prototype('get_pdeathsig', 2, (POINTER(c_int), 2))

# Get/set current->mm->dumpable
_prototype('get_dumpable', 3, use_result=True)
_prototype('set_dumpable', 4, (c_ulong,))

# Get/set unaligned access control bits (if meaningful)
_prototype('get_unalign', 5, (POINTER(c_int), 2))
_prototype('set_unalign', 6, (c_ulong,))
PR_UNALIGN_NOPRINT = 1   # silently fix up unaligned user accesses
PR_UNALIGN_SIGBUS = 2    # generate SIGBUS on unaligned user access

# Get/set whether or not to drop capabilities on setuid() away from
# uid 0 (as per security/commoncap.c)
_prototype('get_keepcaps', 7, use_result=True)
_prototype('set_keepcaps', 8, (c_ulong,))

# Get/set floating-point emulation control bits (if meaningful)
_prototype('get_fpemu', 9, (POINTER(c_int), 2))
_prototype('set_fpemu', 10, (c_ulong,))
PR_FPEMU_NOPRINT = 1    # silently emulate fp operations accesses
PR_FPEMU_SIGFPE = 2     # don't emulate fp operations, send SIGFPE instead

# Get/set floating-point exception mode (if meaningful)
_prototype('get_fpexc', 11, (POINTER(c_int), 2))
_prototype('set_fpexc', 12, (c_ulong,))
PR_FP_EXC_SW_ENABLE = 0x80   # Use FPEXC for FP exception enables
PR_FP_EXC_DIV = 0x010000     # floating point divide by zero
PR_FP_EXC_OVF = 0x020000     # floating point overflow
PR_FP_EXC_UND = 0x040000     # floating point underflow
PR_FP_EXC_RES = 0x080000     # floating point inexact result
PR_FP_EXC_INV = 0x100000     # floating point invalid operation
PR_FP_EXC_DISABLED = 0       # FP exceptions disabled
PR_FP_EXC_NONRECOV = 1       # async non-recoverable exc. mode
PR_FP_EXC_ASYNC = 2          # async recoverable exception mode
PR_FP_EXC_PRECISE = 3        # precise exception mode

# Get/set whether we use statistical process timing or accurate timestamp
# based process timing
_prototype('get_timing', 13, use_result=True)
_prototype('set_timing', 14, (c_ulong,))
PR_TIMING_STATISTICAL = 0  # Normal, traditional, statistical process timing
PR_TIMING_TIMESTAMP = 1    # Accurate timestamp based process timing

# Get/set process name
_prototype('set_name', 15, (c_char_p,))
_prototype('get_name', 16, (POINTER(c_char*16), 2))

# Get/set process endian
_prototype('get_endian', 19, (POINTER(c_int), 2))
_prototype('set_endian', 20, (c_ulong,))
PR_ENDIAN_BIG = 0
PR_ENDIAN_LITTLE = 1       # True little endian mode
PR_ENDIAN_PPC_LITTLE = 2   # "PowerPC" pseudo little endian

# Get/set process seccomp mode
_prototype('get_seccomp', 21, use_result=True)
_prototype('set_seccomp', 22, (c_ulong,))

# Get/set the capability bounding set (as per security/commoncap.c)
_prototype('capbset_read', 23, (c_ulong,), use_result=True)
_prototype('capbset_drop', 24, (c_ulong,))

# Get/set the process' ability to use the timestamp counter instruction
_prototype('get_tsc', 25, (POINTER(c_int), 2))
_prototype('set_tsc', 26, (c_ulong,))
PR_TSC_ENABLE = 1     # allow the use of the timestamp counter
PR_TSC_SIGSEGV = 2    # throw a SIGSEGV instead of reading the TSC

# Get/set securebits (as per security/commoncap.c)
_prototype('get_securebits', 27, use_result=True)
_prototype('set_securebits', 28, (c_ulong,))

# Get/set the timerslack as used by poll/select/nanosleep
# A value of 0 means "use default"
_prototype('set_timerslack', 29, (c_ulong,))
_prototype('get_timerslack', 30, use_result=True)

_prototype('task_perf_events_disable', 31)
_prototype('task_perf_events_enable', 32)

# Set early/late kill mode for hwpoison memory corruption.
# This influences when the process gets killed on a memory corruption.
_prototype('mce_kill', 33, (c_ulong,), (c_ulong,))
PR_MCE_KILL_CLEAR = 0
PR_MCE_KILL_SET = 1

PR_MCE_KILL_LATE = 0
PR_MCE_KILL_EARLY = 1
PR_MCE_KILL_DEFAULT = 2

_prototype('mce_kill_get', 34, use_result=True)

# Tune up process memory map specifics.
_prototype('set_mm', 35, (c_ulong,), (c_ulong,), (c_ulong, 1, 'arg4', 0))
PR_SET_MM_START_CODE = 1
PR_SET_MM_END_CODE = 2
PR_SET_MM_START_DATA = 3
PR_SET_MM_END_DATA = 4
PR_SET_MM_START_STACK = 5
PR_SET_MM_START_BRK = 6
PR_SET_MM_BRK = 7
PR_SET_MM_ARG_START = 8
PR_SET_MM_ARG_END = 9
PR_SET_MM_ENV_START = 10
PR_SET_MM_ENV_END = 11
PR_SET_MM_AUXV = 12
PR_SET_MM_EXE_FILE = 13
PR_SET_MM_MAP = 14
PR_SET_MM_MAP_SIZE = 15

# Set specific pid that is allowed to ptrace the current task.
# A value of 0 mean "no process".
_prototype('set_ptracer', 0x59616d61, (c_ulong,))
PR_SET_PTRACER_ANY = -1

_prototype('set_child_subreaper', 36, (c_ulong,))
_prototype('get_child_subreaper', 37, (POINTER(c_int), 2))

# If no_new_privs is set, then operations that grant new privileges (i.e.
# execve) will either fail or not grant them.  This affects suid/sgid,
# file capabilities, and LSMs.
#
# Operations that merely manipulate or drop existing privileges (setresuid,
# capset, etc.) will still work.  Drop those privileges if you want them gone.
#
# Changing LSM security domain is considered a new privilege.  So, for example,
# asking selinux for a specific new context (e.g. with runcon) will result
# in execve returning -EPERM.
#
# See Documentation/prctl/no_new_privs.txt for more details.
_prototype('set_no_new_privs', 38, (c_ulong,))
_prototype('get_no_new_privs', 39, use_result=True)

_prototype('get_tid_address', 40, (POINTER(c_ulong), 2))

_prototype('set_thp_disable', 41, (c_ulong,))
_prototype('get_thp_disable', 42, use_result=True)

# Tell the kernel to start/stop helping userspace manage bounds tables.
_prototype('mpx_enable_management', 43)
_prototype('mpx_disable_management', 44)

_prototype('set_fp_mode', 45, (c_ulong,))
_prototype('get_fp_mode', 46, use_result=True)
PR_FP_MODE_FR = (1 << 0)   # 64b FP registers
PR_FP_MODE_FRE = (1 << 1)   # 32b compatibility
