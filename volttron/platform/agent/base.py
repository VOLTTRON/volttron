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

# pylint: disable=W0142,W0403
#}}}

'''VOLTTRON platform™ base agent and helper classes/functions.'''

from abc import ABCMeta, abstractmethod
from collections import (OrderedDict, defaultdict)
import logging
import random
import string
import time as time_mod

# XXX find a way to quiet pylint errors about dynamic attributes
import zmq
from zmq import POLLIN, POLLOUT
from zmq.utils import jsonapi

import clock

from . import sched
from .matching import iter_match_tests
from .. import messaging
from ..messaging import topics


__all__ = ['periodic', 'BaseAgent', 'PublishMixin', 'AbstractDrivenAgent',
           'Results', 'ConversionMapper']

__author__ = 'Brandon Carpenter <brandon.carpenter@pnnl.gov>'
__copyright__ = 'Copyright (c) 2013, Battelle Memorial Institute'
__license__ = 'FreeBSD'


_COOKIE_CHARS = string.ascii_letters + string.digits


def random_cookie(length=40, choices=_COOKIE_CHARS):
    return ''.join(random.choice(choices) for i in xrange(length))


def remove_matching(test, items):
    '''Remove all elements in items for which test returns true.

    test must be a function accepting a single argument and must return
    True if the item should be deleted or False if it should remain.
    items must be a list or an object supporting index-based deletion.
    '''
    remove = [i for i, item in enumerate(items) if test(item)]
    remove.reverse()
    for i in remove:
        del items[i]


def periodic(period, *args, **kwargs):
    '''Decorator to set a method up as a periodic callback.

    The decorated method will be called with the given arguments every
    period seconds while the agent is executing its run loop.
    '''
    def decorator(func):
        # pylint: disable=C0111
        try:
            periodics = func._periodics
        except AttributeError:
            func._periodics = periodics = []
        periodics.append((period, args, kwargs))
        return func
    return decorator


def iter_periodics(obj):
    '''Iterate the periodic decorated methods of an object.'''
    for name in dir(obj):
        try:
            method = getattr(obj, name)
            periodics = method._periodics
        except AttributeError:
            continue
        for period, args, kwargs in periodics:
            yield period, method, args, kwargs


class Reactor(object):
    '''Implements the reactor pattern around a Poller instance.'''

    def __init__(self):
        self._poller = zmq.Poller()
        self._callbacks = {}

    def modify(self, sock, incoming=None, outgoing=None):
        '''Update callbacks for a registered socket.'''
        self.register(sock, incoming, outgoing)

    def register(self, sock, incoming=None, outgoing=None):
        '''Register callbacks for socket events.

        incoming is a callback for POLLIN events on sock and outgoing
        for POLLOUT events. If both are None, the socket is completely
        unregistered.
        '''
        try:
            fd = sock.fileno()
        except AttributeError:
            fd = sock
        flags = ((POLLIN if incoming else 0) |
                 (POLLOUT if outgoing else 0))
        self._poller.register(fd, flags)
        if flags:
            self._callbacks[fd] = (sock, incoming, outgoing)
        else:
            self._callbacks.pop(fd, None)

    def unregister(self, sock):
        '''Unregister all callbacks for sock.'''
        self.register(sock)

    def _poll(self, timeout=None):
        for fd, event in self._poller.poll(timeout * 1000):
            try:
                sock, incoming, outgoing = self._callbacks.get(fd)
            except KeyError:
                continue
            if event & POLLIN and incoming:
                yield (sock, POLLIN, incoming)
            if event & POLLOUT and outgoing:
                yield (sock, POLLOUT, outgoing)

    def poll(self, timeout=None):
        '''Wait for sockets to become ready.

        Wait for up to timeout seconds for registered sockets to be
        ready and return a list of 3-tuples (socket, event, callback) or
        an empty list if no sockets are ready within the timeout period.
        '''
        return list(self._poll(timeout))


class AgentBase(object):
    '''Base agent to consume standard arguments.'''
    def __init__(self, subscribe_address=None, publish_address=None,
                 config_path=None, **kwargs):
        super(AgentBase, self).__init__(**kwargs)


class BaseAgent(AgentBase):
    '''Base class for creating VOLTTRON platform™ agents.

    This class can be used as is, but it won't do much.  It will sit and
    do nothing but listen for messages and exit when the platform
    shutdown message is received.  That is it.
    '''

    LOOP_INTERVAL = 60

    def __init__(self, subscribe_address, **kwargs):
        # pylint: disable=W0613
        super(BaseAgent, self).__init__(**kwargs)
        self._subscriptions = {}
        self._mono = sched.Queue()
        self._wall = sched.Queue()
        self._sub = messaging.Socket(zmq.SUB)
        self.connect = lambda: self._sub.connect(subscribe_address)
        self.disconnect = lambda: (self._sub.closed or
                                   self._sub.disconnect(subscribe_address))
        self.reactor = Reactor()
        self.reactor.register(self._sub,
                              lambda sock: self.handle_sub_message())
        for prefix, callback, test in iter_match_tests(self):
            self.subscribe(prefix, callback, test)
        self._sub.subscribe = topics.PLATFORM_SHUTDOWN.encode('utf-8')

    @property
    def closed(self):
        '''Return whether the subscription channel is closed.'''
        return self._sub.closed

    def run(self):
        '''Entry point for running agent.

        Subclasses should not override this method.  Instead, the setup,
        step, and finish methods should be overridden to customize
        behavior.
        '''
        self.setup()
        try:
            self.loop()
        finally:
            self.finish()

    def _setup_periodics(self):
        for period, method, args, kwargs in iter_periodics(self):
            self.periodic_timer(period, method, *args, **kwargs)

    def setup(self):
        '''Setup for the agent execution loop.

        Extend this method with code that must run once before the main
        loop.  Be sure to call the base class implementation from the
        overridden method.
        '''
        self._setup_periodics()
        self.connect()

    def finish(self):
        '''Finish for the agent execution loop.

        Extend this method with code that must run once after the main
        loop.  Be sure to call the base class implementation from the
        overridden method.
        '''
        self.disconnect()

    def loop(self):
        '''Main agent execution loop.

        This method should rarely need to be overridden.  Instead,
        override the step method to customize execution behavior.  The
        default implementation loops until self.closed() returns True
        calling self.step() each iteration.
        '''
        while not self.closed:
            self.step()

    def step(self, timeout=None):
        '''Performs a single step in the main agent loop.

        Override this method to customize agent behavior.  The default
        method blocks indefinitely until at least one socket in the
        reactor is ready and then run each associated callback.  The
        method can be called from the overridden method in a subclass
        with the behavior customized by passing in different timeout.
        timeout is the maximum number of seconds (can be fractional) to
        wait or None to wait indefinitely.  Returns the number of events
        fired or zero if a timeout occured.
        '''
        events = self.poll(timeout)
        for sock, event, callback in events:
            callback(sock)
        return len(events)

    def poll(self, timeout=None):
        '''Polls for events while handling timers.

        poll() will wait up to timeout seconds for sockets or files
        registered with self.reactor to become ready.  A timeout of None
        will cause poll to wait an infinite amount of time.  While
        waiting for poll events, scheduled events will be handled,
        potentially causing the wait time to slip a bit.
        '''
        elapsed = 0.0
        mono_time = clock.monotonic()
        while True:
            wall_time = time_mod.time()
            self._mono.execute(mono_time)
            self._wall.execute(wall_time)
            delays = [self.LOOP_INTERVAL if timeout is None
                      else min(timeout - elapsed, self.LOOP_INTERVAL),
                      self._mono.delay(mono_time), self._wall.delay(wall_time)]
            delay = min(d for d in delays if d is not None)
            events = self.reactor.poll(delay)
            if events:
                return events
            last_time, mono_time = mono_time, clock.monotonic()
            elapsed += mono_time - last_time
            if timeout is not None and elapsed >= timeout:
                return []

    def handle_sub_message(self, block=False):
        '''Handle incoming messages on the subscription socket.

        Receives a multipart message containing a topic, headers,
        and zero or more message parts.  For each prefix (key) in
        subscriptions map matching the beginning of the topic, the
        associated callback will be called if either no test is
        associated with the callback or the test function returns
        a value evaluating to True.

        See the class documentation for more information on the
        signature for test and callback functions.
        '''
        try:
            topic, headers, message = self._sub.recv_message(
                    0 if block else zmq.NOBLOCK)
        except zmq.error.Again:
            return
        try:
            for prefix, handlers in self._subscriptions.iteritems():
                if topic.startswith(prefix):
                    for callback, test in handlers:
                        if not callback:
                            continue
                        if test:
                            matched = test(topic, prefix)
                            if not matched:
                                continue
                        else:
                            matched = None
                        callback(topic, headers, message, matched)
        finally:
            if topic == topics.PLATFORM_SHUTDOWN:
                self._sub.close()

    def subscribe(self, prefix, callback=None, test=None):
        '''Subscribe to topic and register callback.

        Subscribes to topics beginning with prefix.  If callback is
        supplied, it should be a function taking four arguments,
        callback(topic, headers, message, match), where topic is the
        full message topic, headers is a case-insensitive dictionary
        (mapping) of message headers, message is a possibly empty list
        of message parts, and match is the return value of the test
        function or None if test is None.

        If test is given, it should be a function taking two arguments,
        test(topic, prefix), where topic is the complete topic of the
        incoming message and prefix is the string which caused the
        subscription match.  The test function should return a true
        value if the callback should be called or a false value
        otherwise.  The result of the test will be passed into the
        callback function where the results can be used.

        Returns and ID number which can be used later to unsubscribe.
        '''
        self._sub.subscribe = prefix.encode('utf-8')
        try:
            handlers = self._subscriptions[prefix]
        except KeyError:
            self._subscriptions[prefix] = handlers = set()
        handler = (callback, test)
        handlers.add(handler)
        return id(handler)

    def unsubscribe(self, handler_id, prefix=None):
        '''Remove subscription handler by its ID.

        Remove all handlers matching the given handler ID, which is the
        ID returned by the subscribe method.  If all handlers for a
        topic prefix are removed, the topic is also unsubscribed.
        '''
        def remove_handler(key, handlers):
            # pylint: disable=C0111
            remove_matching(lambda item: id(item) == handler_id, handlers)
            if not handlers:
                del self._subscriptions[key]
                self._sub.unsubscribe = key.encode('utf-8')
        if prefix:
            handlers = self._subscriptions.get(prefix)
            if handlers:
                remove_handler(prefix, handlers)
        else:
            for prefix, handlers in self._subscriptions.iteritems():
                remove_handler(prefix, handlers)

    def unsubscribe_all(self, prefix):
        '''Remove all handlers for the given prefix and unsubscribe.

        If prefix is None, unsubscribe from all topics and remove all
        handlers.  Otherwise, unsubscribe from the given topic and
        remove all handlers for that topic prefix.
        '''
        if prefix is None:
            for key in self._subscriptions:
                self._sub.unsubscribe = key.encode('utf-8')
            self._subscriptions.clear()
        else:
            self._sub.unsubscribe = prefix.encode('utf-8')
            del self._subscriptions[prefix]

    def schedule(self, time, event):
        '''Schedule an event to run at the given wall time.

        time must be a datetime object or a Unix time value as returned
        by time.time().  event must be a callable accepting a single
        argument, the time the event was scheduled to run, and must
        return a time to be scheduled next or None to not reschedule.
        sched.Event and sched.RecurringEvent are examples of this
        interface and may be used here.  Generators send functions are
        also be good candidates for event functions.
        '''
        if hasattr(time, 'timetuple'):
            time = time_mod.mktime(time.timetuple())
        self._wall.schedule(time, event)

    def timer(self, interval, function, *args, **kwargs):
        '''Create a timer to call function after interval seconds.

        interval is specified in seconds and can include fractional part.
        function is a function that takes the optional args and kwargs.
        Returns a timer object that can be used to modify the callback
        parameters or to cancel using the cancel() method.
        '''
        timer = sched.Event(function, args, kwargs)
        self._mono.schedule(clock.monotonic() + interval, timer)
        return timer

    def periodic_timer(self, period, function, *args, **kwargs):
        '''Create a periodic timer to call function every period seconds.

        Like the timer method except that the timer is automatically
        rearmed after the function completes.
        '''
        timer = sched.RecurringEvent(period, function, args, kwargs)
        self._mono.schedule(clock.monotonic() + period, timer)
        return timer


class PublishMixin(AgentBase):
    '''Agent mix-in for publishing to the VOLTTRON publish socket.

    Connects the agent to the publish channel and provides several
    publish methods.

    Include before BaseAgent class in subclass list.
    '''

    def __init__(self, publish_address, **kwargs):
        '''Add a publishing socket to the agent.

        Expects a publish_address keyword argument containing the ØMQ
        publish address.
        '''
        super(PublishMixin, self).__init__(**kwargs)
        self._setup(publish_address)

    def _setup(self, publish_address):
        self._pub = messaging.Socket(zmq.PUSH)
        self._pub.delay_attach_on_connect = 1
        self._pub.connect(publish_address)

    def ping_back(self, callback, timeout=None, period=1):
        if timeout is not None:
            start = clock.monotonic()
        ping = topics.AGENT_PING(cookie=random_cookie())
        state = {}
        def finish(success):
            state['timer'].cancel()
            self.unsubscribe(state['subscription'])
            callback(success)
        def send_ping():
            if timeout is not None:
                if (clock.monotonic() - start) >= timeout:
                    finish(False)
            self.publish(ping, {})
        def on_ping(topic, headers, msg, match):
            finish(True)
        state['subscription'] = self.subscribe(ping, on_ping, None)
        state['timer'] = self.periodic_timer(period, send_ping)
        send_ping()

    def publish(self, topic, headers, *msg_parts, **kwargs):
        '''Publish a message to the publish channel.'''
        self._pub.send_message(topic, headers, *msg_parts, **kwargs)

    def publish_json(self, topic, headers, *msg_parts, **kwargs):
        '''Publish JSON encoded message.'''
        msg = [('application/json', jsonapi.dumps(msg)) for msg in msg_parts]
        self._pub.send_message_ex(topic, headers, *msg, **kwargs)

    def publish_ex(self, topic, headers, *msg_tuples, **kwargs):
        '''Publish messages given as (content-type, message) tuples.'''
        self._pub.send_message_ex(topic, headers, *msg_tuples, **kwargs)

class AbstractDrivenAgent:
    __metaclass__ = ABCMeta

    def __init__(self, out=None,**kwargs):
        """
        When applications extend this base class, they need to make
        use of any kwargs that were setup in config_param
        """
        super().__init__(**kwargs)
        self.out = out
        self.data = {}

    @classmethod
    @abstractmethod
    def output_format(cls, input_object):
        """
        The output object takes the resulting input object as a argument
        so that it may give correct topics to it's outputs if needed.

        output schema description
            {TableName1: {name1:OutputDescriptor1, name2:OutputDescriptor2,...},....}

            eg: {'OAT': {'Timestamp':OutputDescriptor('timestamp', 'foo/bar/timestamp'),'OAT':OutputDescriptor('OutdoorAirTemperature', 'foo/bar/oat')},
                'Sensor': {'SomeValue':OutputDescriptor('integer', 'some_output/value'),
                'SomeOtherValue':OutputDescriptor('boolean', 'some_output/value),
                'SomeString':OutputDescriptor('string', 'some_output/string)}}

        Should always call the parent class output_format and update the dictionary returned from
        the parent.

        result = super().output_format(input_object)
        my_output = {...}
        result.update(my_output)
        return result
        """
        return {}

    @abstractmethod
    def run(self, time, inputs):
        '''Do work for each batch of timestamped inputs
           time- current time
           inputs - dict of point name -> value

           Must return a results object.'''
        pass

    def shutdown(self):
        '''Override this to add shutdown routines.'''
        return Results()

class Results:
    def __init__(self, terminate=False):
        self.commands = OrderedDict()
        self.log_messages = []
        self._terminate = terminate
        self.table_output = defaultdict(list)

    def command(self, point, value):
        self.commands[point]=value

    def log(self, message, level=logging.DEBUG):
        self.log_messages.append((level, message))

    def terminate(self, terminate):
        self._terminate = bool(terminate)

    def insert_table_row(self, table, row):
        self.table_output[table].append(row)

import re
from collections import defaultdict
from . import utils
class ConversionMapper:

    def __init__(self, **kwargs):
        self.initialized = False
        utils.setup_logging()
        self._log = logging.getLogger(__name__)
        self.conversion_map = {}

    def setup_conversion_map(self, conversion_map_config, field_names):
        #time_format = conversion_map_config.pop(TIME_STAMP_COLUMN)
        re_exp_list = conversion_map_config.keys()
        re_exp_list.sort(cmp=lambda x,y: cmp(len(x), len(y)))
        re_exp_list.reverse()
        re_list = [re.compile(x) for x in re_exp_list]

        def default_handler():
            return lambda x:x
        self.conversion_map = defaultdict(default_handler)
        def handle_time(item):
            return datetime.datetime.strptime(item, time_format)
        #self.conversion_map[TIME_STAMP_COLUMN] = handle_time

        def handle_bool(item):
            item_lower = item.lower()
            if (item_lower == 'true' or
                item_lower == 't' or
                item_lower == '1'):
                return True
            return False
        type_map = {'int':int,
                    'float':float,
                    'bool':handle_bool}


        for name in field_names:
            for field_re in re_list:
                if field_re.match(name):
                    pattern = field_re.pattern
                    self._log.debug('Pattern {pattern} used to process {name}.' \
                                    .format(pattern=pattern, name=name))
                    type_string = conversion_map_config[pattern]
                    self.conversion_map[name] = type_map[type_string]
                    break
                #else:
                #    if name != TIME_STAMP_COLUMN:
                #        self.log_message(logging.ERROR, 'FILE CONTROLLER', 'No matching map for column {name}. Will return raw string.'.format(name=name))
        self.initialized = True

    def process_row(self, row_dict):
        null_values = {'NAN', 'NA', '#NA', 'NULL', 'NONE',
                       'nan', 'na', '#na', 'null', 'none',
                       '', None}
        return dict((c,self.conversion_map[c](v)) if v not in null_values else (c,None) for c,v in row_dict.iteritems())


