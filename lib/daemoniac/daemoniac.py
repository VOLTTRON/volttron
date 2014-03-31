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

'''Turn a Python script into SysV-style daemon process.

Daemonize a Python process according to the SysV guidelines at
http://www.freedesktop.org/software/systemd/man/daemon.html.
'''

import atexit
import ctypes
from ctypes import c_int, c_ulong, POINTER
import os
import resource
import signal
import sys


__all__ = ['daemonize', 'dup_open']


#pylint: disable=C0103

SIG_SETMASK = 2

sigset_t = c_ulong * (1024 / (8 * ctypes.sizeof(c_ulong)))

sigprocmask = ctypes.CFUNCTYPE(
        c_int, c_int, POINTER(sigset_t), POINTER(sigset_t), use_errno=True)(
        ('sigprocmask', ctypes.CDLL(None)),
        ((1, 'how', 0), (1, 'set', None), (2,)))


def _close_files(keep_files):
    '''Iterate through and close all open files, except those in keep_files.'''
    try:
        fds = (int(num) for num in os.listdir('/proc/self/fd'))
    except OSError:
        nfiles, = resource.getrlimit(resource.RLIMIT_NOFILE)
        fds = xrange(nfiles)
    for fd in fds:
        if fd in keep_files:
            continue
        try:
            os.close(fd)
        except OSError:
            pass


def _reset_signals():
    '''Reset all signal handlers to sane defaults.'''
    def exit_handler(signum, frame):
        #pylint: disable=C0111,W0613
        sys.exit()
    for signum in xrange(1, signal.NSIG):
        try:
            if signum == signal.SIGINT:
                signal.signal(signum, signal.default_int_handler)
            elif signum in (signal.SIGPIPE, signal.SIGTSTP,
                            signal.SIGTTIN, signal.SIGTTOU):
                signal.signal(signum, signal.SIG_IGN)
            elif signum in (signal.SIGHUP, signal.SIGQUIT, signal.SIGUSR1,
                            signal.SIGUSR2, signal.SIGTERM):
                signal.signal(signum, exit_handler)
            else:
                signal.signal(signum, signal.SIG_DFL)
        except (ValueError, RuntimeError):
            pass


def dup_open(fd, *args):
    '''Open a file and move it to file descriptor fd.'''
    fdnew = os.open(*args)
    os.dup2(fdnew, fd)
    os.close(fdnew)


def daemonize(pid_file=None, delay=False, uid=None, gid=None,
              umask=0, chdir='/', keep_files=(0, 1, 2),
              stdin=os.devnull, stdout=os.devnull, stderr=os.devnull,
              close_files=True, reset_signals=True, remove_pid_file=True):
    '''Daemonize a process.

    Following the SysV guidance at
    http://www.freedesktop.org/software/systemd/man/daemon.html, turn
    the current process into a daemon by double-forking.  The default
    behavior of daemonize can be changed by adjusting the parameters.

     1. If close_files is True (the default), close all open file
        descriptors except those in keep_files.
 
     2. Reset all signal handlers to sane defaults unless reset_signals
        is not True (the default).
 
     3. Reset the signal mask using sigprocmask.
 
     4. The caller is responsible for sanitizing the environment.
 
     5. Call fork() to create a background process.  The parent will
        wait until the daemonize process completes and then exit with
        either a zero return code (indicating success) or a non-zero
        return code (indicating failure).
 
     6. Call setsid() to detach from any terminal and create an
        independent session.
 
     7. Call fork() again to ensure the daemon can never reacquire a
        terminal.
 
     8. Call exit() in the first child to re-parent the daemon to init.
 
     9. Connect stdin, stdout, and stderr to /dev/null unless overridden
        by passing different files via stdin, stdout, and stderr or
        bypassed by setting those parameters to None.

    10. Reset umask to given value (0 by default) or skip if None.

    11. Change directory to chdir ('/' by default) or skip if None.

    12. If pid_file is given, the process ID (PID) will be written to
        the file.  If the file already exists, daemonize will fail and
        the process will exit.  If remove_pid_file is True (the
        default), an attempt will be made to remove pid_file when the
        process terminates.  Abnormal termination, such as from an
        unhandled signal, may prevent the file from being removed.

    13. Drop privileges if uid and/or gid are not None.

    If delay is True, a callable object is returned which should be
    called after the daemon is initialized and ready to serve requests.
    '''
    #pylint: disable=R0912,R0913,R0914
    if pid_file:
        pid_file = os.path.expanduser(pid_file)
        if pid_file[0] != '/':
            pid_file = os.path.join(os.getcwd(), pid_file)
        pid_file = os.path.realpath(pid_file)
    if close_files:
        _close_files(keep_files)
    if reset_signals:
        _reset_signals()
    sigprocmask(SIG_SETMASK, sigset_t())
    # Caller should sanitize environment
    fdr, fdw = os.pipe()
    def complete(success=True):
        os.write(fdw, b'\x00' if success else b'\x03')
        os.close(fdw)
    if os.fork():
        os.close(fdw)
        try:
            status = ord(os.read(fdr, 1))
        except OSError:
            status = 2
        sys.exit(status)
    try:
        os.close(fdr)
        os.setsid()
        if os.fork():
            os.close(fdw)
            sys.exit()
        if stdin is not None:
            dup_open(0, stdin, os.O_RDONLY)
        if stdout is not None:
            dup_open(1, stdout, os.O_APPEND)
        if stderr is not None:
            dup_open(2, stderr, os.O_APPEND)
        if umask is not None:
            os.umask(umask)
        if chdir is not None:
            os.chdir(chdir)
        if pid_file:
            fd = os.open(pid_file, os.O_CREAT|os.O_WRONLY|os.O_EXCL, 0622)
            if remove_pid_file:
                def remove():
                    #pylint: disable=C0111,W0703
                    try:
                        pid = int(open(pid_file, 'r').read())
                    except Exception:
                        pass
                    else:
                        if pid == os.getpid():
                            os.remove(pid_file)
                atexit.register(remove)
            try:
                os.write(fd, '{}\n'.format(os.getpid()))
            finally:
                os.close(fd)
        if gid is not None:
            os.setgid(gid)
        if uid is not None:
            os.setuid(uid)
    except Exception:
        complete(False)
        raise
    if delay:
        class Complete(object):
            def __del__(self):
                self()
            def __call__(self):
                complete()
                self.__class__.__call__ = lambda x: None
        return Complete()
    complete()


#if __name__ == '__main__':
#    import time
#    daemonize('daemon.pid', stderr=None)
#    #dup_open(2, os.devnull, os.O_APPEND)
#    time.sleep(60)

