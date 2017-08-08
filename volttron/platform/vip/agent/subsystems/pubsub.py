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

from __future__ import absolute_import

from base64 import b64encode, b64decode
import inspect
import logging
import random
import re
import weakref

import gevent
from zmq import green as zmq
from zmq import SNDMORE

from .base import SubsystemBase
from ..decorators import annotate, annotations, dualmethod, spawn
from ..errors import Unreachable, VIPError, UnknownSubsystem
from .... import jsonrpc
from volttron.platform.agent import utils
from ..results import ResultsDictionary
from gevent.queue import Queue, Empty
from collections import defaultdict
from datetime import timedelta
from volttron.platform.agent import json as jsonapi

__all__ = ['PubSub']
min_compatible_version = '3.0'
max_compatible_version = ''

#utils.setup_logging()
_log = logging.getLogger(__name__)

def encode_peer(peer):
    if peer.startswith('\x00'):
        return peer[:1] + b64encode(peer[1:])
    return peer

def decode_peer(peer):
    if peer.startswith('\x00'):
        return peer[:1] + b64decode(peer[1:])
    return peer


class PubSub(SubsystemBase):
    def __init__(self, core, rpc_subsys, peerlist_subsys, owner):
        self.core = weakref.ref(core)
        self.rpc = weakref.ref(rpc_subsys)
        self.peerlist = weakref.ref(peerlist_subsys)
        self._owner = owner
        self._pubsubwithrpc = PubSubWithRPC(self.core, self.rpc)
        self._send_via_rpc = False
        self._parameters_needed = True

        def subscriptions():
            return defaultdict(set)

        self._my_subscriptions = defaultdict(subscriptions)
        self.protected_topics = ProtectedPubSubTopics()
        core.register('pubsub', self._handle_subsystem, self._handle_error)
        self.rpc().export(self._peer_push, 'pubsub.push')
        self.vip_socket = None
        self._results = ResultsDictionary()
        self._event_queue = Queue()
        self._retry_period = 300.0
        self._processgreenlet = None

        def setup(sender, **kwargs):
            # pylint: disable=unused-argument
            self._processgreenlet = gevent.spawn(self._process_loop)
            core.onconnected.connect(self._connected)
            self.vip_socket = self.core().socket
            def subscribe(member):   # pylint: disable=redefined-outer-name
                for peer, bus, prefix in annotations(
                        member, set, 'pubsub.subscriptions'):
                    # XXX: needs updated in light of onconnected signal
                    self._add_subscription(prefix, member, bus)
            inspect.getmembers(owner, subscribe)
        core.onsetup.connect(setup, self)

    def _connected(self, sender, **kwargs):
        """
        Synchronize local subscriptions with PubSubService upon receiving connected signal.
        param sender: identity of sender
        type sender: str
        param kwargs: optional arguments
        type kwargs: pointer to arguments
        """
        self.synchronize()

    def _process_callback(self, sender, bus, topic, headers, message):
        """Handle incoming subscription pushes from PubSubService. It iterates over all subscriptions to find the
        subscription matching the topic and bus. It then calls the corresponding callback on finding a match.
        param sender: identity of the publisher
        type sender: str
        param bus: bus
        type bus: str
        param topic: publishing topic
        type topic: str
        param headers: header information for the incoming message
        type headers: dict
        param message: actual message
        type message: dict
        """
        peer = 'pubsub'
        handled = 0
        if bus in self._my_subscriptions:
            subscriptions = self._my_subscriptions[bus]
            for prefix, callbacks in subscriptions.iteritems():
                if topic.startswith(prefix):
                    handled += 1
                    for callback in callbacks:
                        callback(peer, sender, bus, topic, headers, message)
        if not handled:
            # No callbacks for topic; synchronize with sender
            self.synchronize()

    def synchronize(self):
        """Synchronize local subscriptions with the PubSubService.
        """
        result = next(self._results)

        items = [{bus: subscriptions.keys()
                         for bus, subscriptions in self._my_subscriptions.items()}]
        for subscriptions in items:
            sync_msg = jsonapi.dumps(dict(subscriptions=subscriptions))
            frames = [b'synchronize', b'connected', sync_msg]
            # For backward compatibility with old pubsub
            if self._send_via_rpc:
                delay = random.random()
                self.core().spawn_later(delay, self.rpc().notify, 'pubsub', 'pubsub.sync', subscriptions)
            else:
                # Parameters are stored initially, in case remote agent/platform is using old pubsub
                if self._parameters_needed:
                    kwargs = dict(op='synchronize', subscriptions=subscriptions)
                    self._save_parameters(result.ident, **kwargs)
                self.vip_socket.send_vip(b'', 'pubsub', frames, result.ident, copy=False)

    def list(self, peer, prefix='', bus='', subscribed=True, reverse=False):
        """Gets list of subscriptions matching the prefix and bus for the specified peer.
        param peer: peer
        type peer: str
        param prefix: prefix of a topic
        type prefix: str
        param bus: bus
        type bus: bus
        param subscribed: subscribed or not
        type subscribed: boolean
        param reverse: reverse
        type reverse:
        :returns: List of subscriptions, i.e, list of tuples of bus, topic and flag to indicate if peer is a
        subscriber or not
        :rtype: list of tuples

        :Return Values:
        List of tuples [(topic, bus, flag to indicate if peer is a subscriber or not)]
        """
        # For backward compatibility with old pubsub
        if self._send_via_rpc:
            return self.rpc().call(peer, 'pubsub.list', prefix,
                                   bus, subscribed, reverse)
        else:
            result = next(self._results)
            # Parameters are stored initially, in case remote agent/platform is using old pubsub
            if self._parameters_needed:
                kwargs = dict(op='list', prefix=prefix, subscribed=subscribed, reverse=reverse, bus=bus)
                self._save_parameters(result.ident, **kwargs)

            list_msg = jsonapi.dumps(dict(prefix=prefix, subscribed=subscribed, reverse=reverse, bus=bus))
            frames = [b'list', list_msg]
            self.vip_socket.send_vip(b'', 'pubsub', frames, result.ident, copy=False)
            return result

    def _add_subscription(self, prefix, callback, bus=''):
        if not callable(callback):
            raise ValueError('callback %r is not callable' % (callback,))
        try:
            self._my_subscriptions[bus][prefix].add(callback)
        except KeyError:
            _log.error("PUBSUB something went wrong in add subscriptions")

    @dualmethod
    @spawn
    def subscribe(self, peer, prefix, callback, bus=''):
        """Subscribe to topic and register callback.

        Subscribes to topics beginning with prefix. If callback is
        supplied, it should be a function taking four arguments,
        callback(peer, sender, bus, topic, headers, message), where peer
        is the ZMQ identity of the bus owner sender is identity of the
        publishing peer, topic is the full message topic, headers is a
        case-insensitive dictionary (mapping) of message headers, and
        message is a possibly empty list of message parts.
        :param peer
        :type peer
        :param prefix prefix to the topic
        :type prefix str
        :param callback callback method
        :type callback method
        :param bus bus
        :type bus str
        :returns: Subscribe is successful or not
        :rtype: boolean

        :Return Values:
        Success or Failure
        """
        # For backward compatibility with old pubsub
        if self._send_via_rpc == True:
            self._add_subscription(prefix, callback, bus)
            return self.rpc().call(peer, 'pubsub.subscribe', prefix, bus=bus)
        else:

            result = self._results.next()
            # Parameters are stored initially, in case remote agent/platform is using old pubsub
            if self._parameters_needed:
                kwargs = dict(op='subscribe', prefix=prefix, bus=bus)
                self._save_parameters(result.ident, **kwargs)

            self._add_subscription(prefix, callback, bus)
            sub_msg = jsonapi.dumps(dict(prefix=prefix, bus=bus))
            frames = [b'subscribe', sub_msg]
            self.vip_socket.send_vip(b'', 'pubsub', frames, result.ident, copy=False)
            return result

    @subscribe.classmethod
    def subscribe(cls, peer, prefix, bus=''):
        def decorate(method):
            annotate(method, set, 'pubsub.subscriptions', (peer, bus, prefix))
            return method
        return decorate

    def _peer_push(self, sender, bus, topic, headers, message):
        """
            Added for backward compatibility with old pubsub
            param sender: publisher
            type sender: str
            param bus: bus
            type callback: str
            param topic: topic for the message
            type topic: str
            param headers: header for the message
            type headers: dict
            param message: actual message
            type message: dict
        """
        peer = bytes(self.rpc().context.vip_message.peer)
        handled = 0
        sender = decode_peer(sender)
        self._process_callback(sender, bus, topic, headers, message)

    def _drop_subscription(self, prefix, callback, bus=''):
        """
        Drop the subscription for the specified prefix, callback and bus.
        param prefix: prefix to be removed
        type prefix: str
        param callback: callback method
        type callback: method
        param bus: bus
        type bus: bus
        return: list of topics/prefixes
        :rtype: list

        :Return Values:
        List of prefixes
        """
        topics = []
        if prefix is None:
            if callback is None:
                if bus in self._my_subscriptions:
                    subscriptions = self._my_subscriptions.pop(bus)
                    topics = subscriptions.keys()
            else:
                if bus in self._my_subscriptions:
                    subscriptions = self._my_subscriptions[bus]
                    remove = []
                    for topic, callbacks in subscriptions.iteritems():
                        try:
                            callbacks.remove(callback)
                        except KeyError:
                            pass
                        else:
                            topics.append(topic)
                        if not callbacks:
                            remove.append(topic)
                    for topic in remove:
                        del subscriptions[topic]
                    if not subscriptions:
                        del self._my_subscriptions[bus]
            if not topics:
                raise KeyError('no such subscription')
        else:
            if bus in self._my_subscriptions:
                subscriptions = self._my_subscriptions[bus]
                if callback is None:
                    del subscriptions[prefix]
                else:
                    callbacks = subscriptions[prefix]
                    try:
                        callbacks.remove(callback)
                    except KeyError:
                        pass
                    if not callbacks:
                        del subscriptions[prefix]
                topics = [prefix]
                if not subscriptions:
                    del self._my_subscriptions[bus]
        return topics

    def unsubscribe(self, peer, prefix, callback, bus=''):
        """Unsubscribe and remove callback(s).

        Remove all handlers matching the given info - peer, callback and bus, which was used earlier to subscribe as
        well. If all handlers for a topic prefix are removed, the topic is also unsubscribed.
        param peer: peer
        type peer: str
        param prefix: prefix that needs to be unsubscribed
        type prefix: str
        param callback: callback method
        type callback: method
        param bus: bus
        type bus: bus
        return: success or not
        :rtype: boolean

        :Return Values:
        success or not
        """
        # For backward compatibility with old pubsub
        if self._send_via_rpc == True:
            topics = self._drop_subscription(prefix, callback, bus)
            return self.rpc().call(peer, 'pubsub.unsubscribe', topics, bus=bus)
        else:
            result = next(self._results)
            topics = self._drop_subscription(prefix, callback, bus)
            # Parameters are stored initially, in case remote agent/platform is using old pubsub
            if self._parameters_needed:
                kwargs = dict(op='unsubscribe', prefix=topics, bus=bus)
                self._save_parameters(result.ident, **kwargs)

            unsub_msg = jsonapi.dumps(
                dict(prefix=topics, bus=bus)
            )
            frames = [b'unsubscribe', unsub_msg]
            self.vip_socket.send_vip(b'', 'pubsub', frames, result.ident, copy=False)
            return result

    def publish(self, peer, topic, headers=None, message=None, bus=''):
        """Publish a message to a given topic via a peer.

        Publish headers and message to all subscribers of topic on bus.
        If peer is None, use self. Adds volttron platform version
        compatibility information to header as variables
        min_compatible_version and max_compatible version
        param peer: peer
        type peer: str
        param topic: topic for the publish message
        type topic: str
        param headers: header info for the message
        type headers: None or dict
        param message: actual message
        type message: None or any
        param bus: bus
        type bus: str
        return: Number of subscribers the message was sent to.
        :rtype: int

        :Return Values:
        Number of subscribers
        """
        if headers is None:
            headers = {}
        headers['min_compatible_version'] = min_compatible_version
        headers['max_compatible_version'] = max_compatible_version

        if peer is None:
            peer = 'pubsub'

        # For backward compatibility with old pubsub
        if self._send_via_rpc:
            return self.rpc().call(
                peer, 'pubsub.publish', topic=topic, headers=headers,
                message=message, bus=bus)
        else:
            result = next(self._results)
            # Parameters are stored initially, in case remote agent/platform is using old pubsub
            if self._parameters_needed:
                kwargs = dict(op='publish', peer=peer, topic=topic, bus=bus,
                                                                headers=headers, message=message)
                self._save_parameters(result.ident, **kwargs)

            json_msg = jsonapi.dumps(dict(bus=bus, headers=headers, message=message))
            #_log.debug("AGENT PUBSUB: Publish msg: {}".format(json_msg))
            frames = [zmq.Frame(b'publish'), zmq.Frame(str(topic)), zmq.Frame(str(json_msg))]
            #<recipient, subsystem, args, msg_id, flags>
            self.vip_socket.send_vip(b'', 'pubsub', frames, result.ident, copy=False)
            return result

    def _check_if_protected_topic(self, topic):
        required_caps = self.protected_topics.get(topic)
        if required_caps:
            user = str(self.rpc().context.vip_message.user)
            caps = self._owner.vip.auth.get_capabilities(user)
            if not set(required_caps) <= set(caps):
                msg = ('to publish to topic "{}" requires capabilities {},'
                      ' but capability list {} was'
                      ' provided').format(topic, required_caps, caps)
                raise jsonrpc.exception_from_json(jsonrpc.UNAUTHORIZED, msg)

    def _handle_subsystem(self, message):
        """Handler for incoming messages
        param message: VIP message from PubSubService
        type message: dict
        """
        self._event_queue.put(message)

    def _process_incoming_message(self, message):
        """Process incoming messages
        param message: VIP message from PubSubService
        type message: dict
        """
        op = message.args[0].bytes
        if op == 'request_response':
            try:
                result = self._results.pop(bytes(message.id))
            except KeyError:
                return
            if self._parameters_needed:
                self._send_via_rpc = False
                self._parameters_needed = False
                self._pubsubwithrpc.clear_parameters()
                del self._pubsubwithrpc
            response = message.args[1].bytes
            #_log.debug("Message result: {}".format(response))
            result.set(response)
        elif op == 'publish':
            try:
                topic = topic = message.args[1].bytes
                data = message.args[2].bytes
            except IndexError:
                return
            msg = jsonapi.loads(data)
            headers = msg['headers']
            message = msg['message']
            sender = msg['sender']
            bus = msg['bus']
            self._process_callback(sender, bus, topic, headers, message)
        else:
            _log.error("Unknown operation")

    def _process_loop(self):
        """Incoming message processing loop"""
        for msg in self._event_queue:
            self._process_incoming_message(msg)

    def _handle_error(self, sender, message, error, **kwargs):
        """Error handler. If UnknownSubsystem error is received, it implies that agent is connected to platform that has
        OLD pubsub implementation. So messages are resent using RPC method.
        param message: Error message
        type message: dict
        param error: indicates error type
        type error: error class
        param **kwargs: variable arguments
        type **kwargs: dict
        """
        if isinstance(error, UnknownSubsystem):
            #Must be connected to OLD pubsub. Try sending using RPC
            self._send_via_rpc = True
            self._pubsubwithrpc.send(self._results, message)
        else:
            try:
                result = self._results.pop(bytes(message.id))
            except KeyError:
                return
            result.set_exception(error)

    def _save_parameters(self, result_id, **kwargs):
        """Save the parameters for later use.
        param result_id: asyn result id
        type result_id: float
        param **kwargs: parameters to be stored
        type **kwargs: dict
        """
        end_time = utils.get_aware_utc_now() + timedelta(seconds=60)
        event = self.core().schedule(end_time, self._cancel_event, result_id)
        if kwargs is not None:
            kwargs['event'] = event
            self._pubsubwithrpc.parameters[result_id] = kwargs

    def _cancel_event(self, ident):
        """Cancel event
            param ident: event id
            param ident: float
        """
        try:
            parameters = self._pubsubwithrpc.parameters.pop(id)
            event = parameters['event']
            event.cancel()
        except KeyError:
            return

        try:
            result = self._results.parameters.pop(id)
            result.set_exception(gevent.Timeout)
        except KeyError:
            return


class PubSubWithRPC(object):
    """For backward compatibility with old PubSub. The input parameters for each pubsub call is stored for short period
    till we establish that the agent is connected to platform with old pubsub or not. Once this is established, the
    parameters are no longer stored and this class is longer used."""
    def __init__(self, core, rpc):
        self.parameters = dict()
        self._rpc = rpc
        self._core = core

    def send(self, results, message):
        """Check the message id to determine the type of call: subscribe or publish or list or unsubscribe.
            Retrieve the corresponding input parameters and make the correct RPC call.
            param results: Async results dictionary
            type results: Weak dictionary
            param message: Error message
            type:
        """
        id = bytes(message.id)

        try:
            parameters = self.parameters.pop(id)
        except KeyError:
            _log.error("Missing key {}".format(id))
            return
        try:
            if parameters['op'] == 'synchronize':
                self._core().spawn(self._synchronize, id, results, parameters)
            if parameters['op'] == 'subscribe':
                self._core().spawn(self._subscribe, id, results, parameters)
            elif parameters['op'] == 'publish':
                self._core().spawn(self._publish, id, results, parameters)
            elif parameters['op'] == 'list':
                self._core().spawn(self._list, id, results, parameters)
            elif parameters['op'] == 'unsubscribe':
                self._core().spawn(self._unsubscribe, id, results, parameters)
            else:
                _log.error("Error: Unknown operation")
        except KeyError:
            _log.error("Error: Missing KEY message")

    def _synchronize(self, results_id, results, parameters):
        """Unsubscribe call using RPC
            param results_id: Asynchronous result ID required to the set response for the caller
            type results_id: float (hash value)
            param results: Async results dictionary
            type results: Weak dictionary
            param parameters: Input parameters for the unsubscribe call
        """
        try:
            subscriptions = parameters['subscriptions']
            event = parameters['event']
            event.cancel()
        except KeyError:
            return
        self._rpc().notify('pubsub', 'pubsub.sync', subscriptions)

    def _subscribe(self, results_id, results, parameters):
        """Subscribe call using RPC
            param results_id: Asynchronous result ID required to the set response for the caller
            type results_id: float (hash value)
            param results: Async results dictionary
            type results: Weak dictionary
            param parameters: Input parameters for the subscribe call
        """
        try:
            result = results.pop(bytes(results_id))
        except KeyError:
            result = None

        try:
            prefix = parameters['prefix']
            bus = parameters['bus']
            event = parameters['event']
            event.cancel()
        except KeyError:
            return
        try:
            response = self._rpc().call('pubsub', 'pubsub.subscribe', prefix, bus=bus).get(timeout=5)
            if result is not None:
                result.set(response)
        except gevent.Timeout as exc:
            if result is not None:
                result.set_exception(exc)

    def _list(self, results_id, results, parameters):
        """List call using RPC
            param results_id: Asynchronous result ID required to the set response for the caller
            type results_id: float (hash value)
            param results: Async results dictionary
            type results: Weak dictionary
            param parameters: Input parameters for the list call
        """
        try:
            result = results.pop(bytes(results_id))
        except KeyError:
            result = None

        try:
            prefix = parameters['prefix']
            subscribed = parameters['subscribed']
            reverse = parameters['reverse']
            bus = parameters['bus']
            event = parameters['event']
            event.cancel()
        except KeyError:
            return
        try:
            response = self._rpc().call('pubsub', 'pubsub.list', prefix,
                                  bus, subscribed, reverse).get(timeout=5)
            if result is not None:
                result.set(response)
        except gevent.Timeout as exc:
            if result is not None:
                result.set_exception(exc)

    def _publish(self, results_id, results, parameters):
        """Publish call using RPC
            param results_id: Asynchronous result ID required to the set response for the caller
            type results_id: float (hash value)
            param results: Async results dictionary
            type results: Weak dictionary
            param parameters: Input parameters for the publish call
        """
        try:
            result = results.pop(bytes(results_id))
        except KeyError:
            result = None
        try:
            topic = parameters['topic']
            headers = parameters['headers']
            message = parameters['message']
            bus = parameters['bus']
            event = parameters['event']
            event.cancel()
        except KeyError:
            return
        try:
            response = self._rpc().call(
                'pubsub', 'pubsub.publish', topic=topic, headers=headers,
                message=message, bus=bus).get(timeout=5)
            if result is not None:
                result.set(response)
        except gevent.Timeout as exc:
            if result is not None:
                result.set_exception(exc)


    def _unsubscribe(self, results_id, results, parameters):
        """Unsubscribe call using RPC
            param results_id: Asynchronous result ID required to the set response for the caller
            type results_id: float (hash value)
            param results: Async results dictionary
            type results: Weak dictionary
            param parameters: Input parameters for the unsubscribe call
        """
        try:
            result = results.pop(bytes(results_id))
        except KeyError:
            result = None
        try:
            topics = parameters['prefix']
            bus = parameters['bus']
            event = parameters['event']
            event.cancel()
        except KeyError:
            return
        try:
            response = self._rpc().call('pubsub', 'pubsub.unsubscribe', topics, bus=bus).get(timeout=5)
            if result is not None:
                result.set(response)
        except gevent.Timeout as exc:
            if result is not None:
                result.set_exception(exc)

    def clear_parameters(self):
        """Clear all the saved parameters.
        """
        try:
            for ident, param in self.parameters.iteritems():
                param['event'].cancel()
            self.parameters.clear()
        except KeyError:
            return

class ProtectedPubSubTopics(object):
    """Simple class to contain protected pubsub topics"""
    def __init__(self):
        self._dict = {}
        self._re_list = []

    def add(self, topic, capabilities):
        if isinstance(capabilities, basestring):
            capabilities = [capabilities]
        if len(topic) > 1 and topic[0] == topic[-1] == '/':
            regex = re.compile('^' + topic[1:-1] + '$')
            self._re_list.append((regex, capabilities))
        else:
            self._dict[topic] = capabilities

    def get(self, topic):
        if topic in self._dict:
            return self._dict[topic]
        for regex, capabilities in self._re_list:
            if regex.match(topic):
                return capabilities
        return None
