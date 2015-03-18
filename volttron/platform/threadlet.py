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

'''Run gevent Greenlets in their own threads.

Supports killing threads and executing callbacks from other threads.
'''

from __future__ import absolute_import, print_function

import functools
import sys
import threading

import gevent
from gevent import GreenletExit


__all__ = ['Threadlet', 'GreenletExit']

__author__ = 'Brandon Carpenter <brandon.carpenter@pnnl.gov>'


class IgnoreGreenletExitMeta(type):
    '''Metaclass to ignore GreenletExit exceptins raised in thread.'''

    def __new__(mcs, cls, bases, attrs):
        '''Wrap run method defined on class or base classes.'''
        try:
            run = attrs['run']
        except KeyError:
            for base in bases:
                try:
                    run = base.run
                except AttributeError:
                    continue
                break
            else:
                raise AttributeError(
                    "'{}' object has no method 'run'".format(cls))
        @functools.wraps(run)
        def wrapper(self):
            # pylint: disable=missing-docstring
            try:
                run(self)
            except GreenletExit:
                # Only raise if self.ignore_exit is False
                if not getattr(self, 'ignore_exit', True):
                    raise
        attrs['run'] = wrapper
        return super(IgnoreGreenletExitMeta, mcs).__new__(
            mcs, cls, bases, attrs)


class Threadlet(threading.Thread):
    '''A subclass of threading.Thread supporting gevent.

    The run method is executed in the thread's main greenlet and the
    thread will exit when that method returns. Other threads may run
    callbacks within this thread using the send() method. Unlike the
    base class, threading.Thread, *daemon* is set by default.
    '''

    __metaclass__ = IgnoreGreenletExitMeta

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
        # Override inner bootstrap to get thread-specific attributes
        self.__greenlet = gevent.getcurrent()
        self.__hub = gevent.get_hub()
        self.__async = self.__hub.loop.async()
        self.__async.start(self.__run_callbacks)
        threading.Thread._Thread__bootstrap_inner(self)

    # pylint: enable=no-member,invalid-name,missing-docstring
    # pylint: enable=assignment-from-none,attribute-defined-outside-init
