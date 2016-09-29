# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
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

'''Run gevent Greenlets in their own threads.

Supports killing threads and executing callbacks from other threads.
'''

from __future__ import absolute_import, print_function

import functools
import sys
import threading

import gevent
from gevent import GreenletExit


__all__ = ['AsyncCall', 'Threadlet', 'GreenletExit']

__author__ = 'Brandon Carpenter <brandon.carpenter@pnnl.gov>'


class Threadlet(threading.Thread):
    '''A subclass of threading.Thread supporting gevent Greenlets.

    The run method is executed in the thread's main greenlet and the
    thread will exit when that method returns. Other threads may run
    callbacks within this thread using the send() method. Unlike the
    base class, threading.Thread, *daemon* is set by default.
    '''

    def __init__(self, *args, **kwargs):
        '''This subclass adds three additional keyword arguents:

        *daemon* sets the *daemon* property on the object to the given
        value. It defaults to True.

        *ignore_exit* is a flag indicating whether uncaught GreenletExit
        exceptions will be silently ignored. It defaults to True.

        *send_errors* is a flag indicating whether uncaught exceptions
        occuring in callbacks run via send() should be sent to and
        raised in the main greenlet. If False (the default), uncaught
        exceptions will still cause tracebacks to be printed to
        sys.stderr.
        '''
        daemon = kwargs.pop('daemon', True)
        ignore = kwargs.pop('ignore_exit', True)
        fatal = kwargs.pop('send_errors', False)
        super(Threadlet, self).__init__(*args, **kwargs)
        self.daemon = daemon
        self.ignore_exit = ignore
        self.send_errors = fatal
        self.__async = None
        self.__callbacks = []
    __init__.__doc__ = threading.Thread.__init__.__doc__ + __init__.__doc__

    def kill(self, exception=GreenletExit):
        '''Raise GreenletExit or other exception in the main greenlet.'''
        assert self.is_alive(), 'thread is not running'
        self.send(gevent.kill, self.__greenlet, exception)

    def send(self, callback, *args, **kwargs):
        '''Execute callback in this thread's hub.'''
        assert self.is_alive(), 'thread is not running'
        self.__callbacks.append((callback, args, kwargs))
        self.__async.send()

    def __run_callbacks(self):
        '''Execute pending callbacks.'''
        hub = self.__hub
        while self.__callbacks:
            callback, args, kwargs = self.__callbacks.pop()
            try:
                callback(*args, **kwargs)   # pylint: disable=star-args
            except Exception:   # pylint: disable=broad-except
                context = None if self.send_errors else callback
                hub.handle_error(context, *sys.exc_info())

    # pylint: disable=no-member,invalid-name,missing-docstring
    # pylint: disable=assignment-from-none,attribute-defined-outside-init

    @functools.wraps(threading.Thread._Thread__bootstrap_inner)
    def _Thread__bootstrap_inner(self):
        run_func = self.run
        def run():
            self.run = run_func
            try:
                run_func()
            except GreenletExit:
                # Only raise if self.ignore_exit is False
                if not getattr(self, 'ignore_exit', True):
                    raise
        self.run = functools.wraps(run_func)(run)

        # Override inner bootstrap to get thread-specific attributes
        self.__greenlet = gevent.getcurrent()
        self.__hub = gevent.get_hub()
        self.__async = self.__hub.loop.async()
        self.__async.start(self.__run_callbacks)
        try:
            threading.Thread._Thread__bootstrap_inner(self)
        finally:
            self.__async.stop()


class AsyncCall(object):
    '''Send functions to another thread's gevent hub for execution.'''

    def __init__(self, hub=None):
        '''Install this async handler in a hub.

        If hub is None, the current thread's hub is used.
        '''
        if hub is None:
            hub = gevent.get_hub()
        self.calls = calls = []
        self.async = hub.loop.async()
        self.async.start(functools.partial(self._run_calls, calls))

    def __del__(self):
        '''Stop the async handler on deletion.'''
        print('deleted')
        self.async.stop()

    def send(self, receiver, func, *args, **kwargs):
        '''Send a function to the hub to be called there.

        All the arguments to this method are placed in a queue and the
        hub is signaled that a function is ready. When the hub switches
        to this handler, the functions are iterated over, each being
        called with its results sent to the receiver.

        func is called with args and kwargs in the thread of the
        associated hub. If receiver is None, results are ignored and
        errors are printed when exceptions occur. Otherwise, receiver is
        called with the 2-tuple (exc_info, result). If an unhandled
        exception occurred, exc_info is the 3-tuple returned by
        sys.exc_info() and result is None. Otherwise exc_info is None
        and the result is func's return value.

        Note that receiver is called from the hub's thread and may
        need to be injected into the thread of the receiver.
        '''
        self.calls.append((receiver, func, args, kwargs))
        self.async.send()

    @staticmethod
    def _run_call(receiver, func, args, kwargs):
        '''Run a pending call in its own greenlet.'''
        try:
            exc_info, result = None, func(*args, **kwargs)   # pylint: disable=star-args
        except Exception:   # pylint: disable=broad-except
            exc_info, result = sys.exc_info(), None
        if receiver is not None:
            receiver((exc_info, result))
        elif exc_info:
            hub = gevent.get_hub()
            hub.handle_error(func, *exc_info)   # pylint: disable=star-args

    # This method is static to prevent a reference loop so the object
    # can be garbage collected without stopping the async handler.
    @classmethod
    def _run_calls(cls, calls):
        '''Execute pending calls.'''
        while calls:
            args = calls.pop()
            gevent.spawn(cls._run_call, *args)   # pylint: disable=star-args
