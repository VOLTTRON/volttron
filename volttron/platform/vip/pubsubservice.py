# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2015, Battelle Memorial Institute
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

from __future__ import print_function, absolute_import

import argparse
import errno
import logging
from logging import handlers
import logging.config
from urlparse import urlparse

import os
import sys
import threading
import uuid
import re

import gevent
from gevent.fileobject import FileObject
import zmq
from zmq import SNDMORE, EHOSTUNREACH, ZMQError, EAGAIN, NOBLOCK
from zmq import green
from collections import defaultdict
from volttron.platform.agent import json as jsonapi

# Create a context common to the green and non-green zmq modules.
green.Context._instance = green.Context.shadow(zmq.Context.instance().underlying)

from volttron.platform.agent.utils import watch_file, create_file_if_missing
from .agent.subsystems.pubsub import ProtectedPubSubTopics
from .. import jsonrpc

# Optimizing by pre-creating frames
_ROUTE_ERRORS = {
    errnum: (zmq.Frame(str(errnum).encode('ascii')),
             zmq.Frame(os.strerror(errnum).encode('ascii')))
    for errnum in [zmq.EHOSTUNREACH, zmq.EAGAIN]
}

class PubSubService(object):
    def __init__(self, socket, protected_topics, *args, **kwargs):
        self._logger = logging.getLogger(__name__)
        # if self._logger.level == logging.NOTSET:
        #     self._logger.setLevel(logging.WARNING)

        def subscriptions():
            return defaultdict(set)

        self._peer_subscriptions = defaultdict(subscriptions)
        self._vip_sock = socket
        self._user_capabilities = {}
        self._protected_topics = ProtectedPubSubTopics()
        self._load_protected_topics(protected_topics)


    def _add_peer_subscription(self, peer, bus, prefix):
        """
        This maintains subscriptions for specified peer (subscriber), bus and prefix.
        :param peer identity of the subscriber
        :type peer str
        :param bus bus.
        :type str
        :param prefix subscription prefix (peer is subscribing to all topics matching the prefix)
        :type str
        """
        self._peer_subscriptions[bus][prefix].add(peer)

    def peer_drop(self, peer, **kwargs):
        """
        Drop/Remove subscriptions related to the peer as it is no longer reachable/available.
        :param peer agent to be dropped
        :type peer str
        :param **kwargs optional arguments
        :type pointer to arguments
        """
        self._sync(peer, {})

    def _sync(self, peer, items):
        """
        Synchronize the subscriptions with calling agent (peer) when it gets newly connected. OR Unsubscribe from
        stale/forgotten/unsolicited subscriptions when the peer is dropped.
        :param peer
        :type peer str
        :param items subcription items or empty dict
        :type dict
        """
        items = {(bus, prefix) for bus, topics in items.iteritems()
                 for prefix in topics}
        remove = []
        for bus, subscriptions in self._peer_subscriptions.iteritems():
            for prefix, subscribers in subscriptions.iteritems():
                item = bus, prefix
                try:
                    items.remove(item)
                except KeyError:
                    subscribers.discard(peer)
                    if not subscribers:
                        remove.append(item)
                else:
                    subscribers.add(peer)
        for bus, prefix in remove:
            subscriptions = self._peer_subscriptions[bus]
            assert not subscriptions.pop(prefix)
        for bus, prefix in items:
            self._add_peer_subscription(peer, bus, prefix)

    def _peer_sync(self, frames):
        """
        Synchronizes the subscriptions with the calling agent.
        :param frames list of frames
        :type frames list
        """
        if len(frames) > 8:
            conn = frames[7].bytes
            if conn == b'connected':
                data = frames[8].bytes
                msg = jsonapi.loads(data)
                peer = frames[0].bytes
                items = msg['subscriptions']
                assert isinstance(items, dict)
                self._sync(peer, items)

    def _peer_subscribe(self, frames):
        """It stores the subscription information sent by the agent. It unpacks the frames to get identity of the
        subscriber, prefix and bus and saves it for future use.
        :param frames list of frames
        :type frames list
        """
        if len(frames) < 8:
            return False
        else:
            data = frames[7].bytes
            msg = jsonapi.loads(data)
            peer = frames[0].bytes
            prefix = msg['prefix']
            bus = msg['bus']
            for prefix in prefix if isinstance(prefix, list) else [prefix]:
                self._add_peer_subscription(peer, bus, prefix)
            return True

    def _peer_unsubscribe(self, frames):
        """
        It removes the subscription for the agent (peer) for the specified bus and prefix.
        :param frames list of frames
        :type frames list
        :returns: success or failure
        :rtype: boolean

        :Return Values:
        Return success or not
        """
        if len(frames) < 8:
            return False
        else:
            data = frames[7].bytes
            msg = jsonapi.loads(data)
            peer = frames[0].bytes
            prefix = msg['prefix']
            bus = msg['bus']

            subscriptions = self._peer_subscriptions[bus]
            if prefix is None:
                remove = []
                for topic, subscribers in subscriptions.iteritems():
                    subscribers.discard(peer)
                    if not subscribers:
                        remove.append(topic)
                for topic in remove:
                    del subscriptions[topic]
            else:
                for prefix in prefix if isinstance(prefix, list) else [prefix]:
                    subscribers = subscriptions[prefix]
                    subscribers.discard(peer)
                    if not subscribers:
                        del subscriptions[prefix]
            return True

    def _peer_publish(self, frames, user_id):
        """Publish the incoming message to all the subscribers subscribed to the specified topic.
        :param frames list of frames
        :type frames list
        :param user_id user id of the publishing agent. This is required for protected topics check.
        :type user_id  UTF-8 encoded User-Id property
        :returns: Count of subscribers.
        :rtype: int

        :Return Values:
        Number of subscribers to whom the message was sent
        """
        if len(frames) > 8:
            topic = frames[7].bytes
            data = frames[8].bytes
            try:
                msg = jsonapi.loads(data)
                headers = msg['headers']
                message = msg['message']
                bus = ''
                peer = frames[0].bytes
                bus = msg['bus']
                pub_msg = jsonapi.dumps(
                     dict(sender=peer, bus=bus, headers=headers, message=message)
                )
                #self._logger.debug("PLATFORM PUBSUB: Publish msg: {}".format(pub_msg))
                frames[8] = zmq.Frame(str(pub_msg))
            except ValueError:
                self._logger.debug("JSON decode error. Invalid character")
                return 0
            return self._distribute(frames, peer, topic, headers, message, bus, user_id)

    def _peer_list(self, frames):
        """Returns a list of subscriptions for a specific bus. If bus is None, then it returns list of subscriptions
        for all the buses.
        :param frames list of frames
        :type frames list
        :returns: list of tuples of bus, topic and flag to indicate if peer is a subscriber or not
        :rtype: list

        :Return Values:
        List of tuples [(bus, topic, flag to indicate if peer is a subscriber or not)].
        """
        results = []
        if len(frames) > 7:
            data = frames[7].bytes
            msg = jsonapi.loads(data)
            peer = frames[0].bytes
            prefix = msg['prefix']
            bus = msg['bus']
            subscribed = msg['subscribed']
            reverse = msg['reverse']

            if bus is None:
                buses = self._peer_subscriptions.iteritems()
            else:
                buses = [(bus, self._peer_subscriptions[bus])]
            if reverse:
                test = prefix.startswith
            else:
                test = lambda t: t.startswith(prefix)
            for bus, subscriptions in buses:
                for topic, subscribers in subscriptions.iteritems():
                    if test(topic):
                        member = peer in subscribers
                        if not subscribed or member:
                            results.append((bus, topic, member))
        return results

    def _distribute(self, frames, peer, topic, headers, message=None, bus='', user_id=b''):
        """
        Distributes the message to all the subscribers subscribed to the same bus and topic. Check if the topic
        is protected before distributing the message. For protected topics, only authorized publishers can publish
        the message for the topic.
        :param frames list of frames
        :type frames list
        :param peer identity of the publishing agent
        :type peer str
        :param topic topic of the message
        :type topic  str
        :headers message header containing timestamp and version information
        :type headers dict
        :param message actual message
        :type message None or any
        :param bus message bus
        :type bus str
        :param user_id user id of the publishing agent. This is required for protected topics check.
        :type user_id  UTF-8 encoded User-Id property
        :returns: Count of subscribers.
        :rtype: int

        :Return Values:
        Number of subscribers to whom the message was sent
        """
        #Check if peer is authorized to publish the topic
        errmsg = self._check_if_protected_topic(user_id, topic)
        #Send error message as peer is not authorized to publish to the topic
        if errmsg is not None:
            publisher, receiver, proto, user_id, msg_id, subsystem = frames[0:6]
            try:
                frames = [publisher, b'', proto, user_id, msg_id,
                      b'error', zmq.Frame(bytes(jsonrpc.UNAUTHORIZED)), zmq.Frame(str(errmsg)), b'', subsystem]
            except ValueError:
                self._logger.debug("Value error")
            self._send(frames, publisher)
            return 0

        subscriptions = self._peer_subscriptions[bus]
        subscribers = set()

        publisher = frames[0]
        frames[3] = bytes(user_id)
        for prefix, subscription in subscriptions.iteritems():
            if subscription and topic.startswith(prefix):
                subscribers |= subscription
        if subscribers:
            for subscriber in subscribers:
                frames[0] = zmq.Frame(subscriber)
                try:
                    #Send the message to the subscriber
                    for sub in self._send(frames, publisher):
                        # Drop the subscriber if unreachable
                        self.peer_drop(sub)
                except ZMQError:
                    raise
        return len(subscribers)

    def _send(self, frames, publisher):
        """
        Sends the message to the recipient. If the recipient is unreachable, it is dropped from list of peers (and
        associated subscriptions are removed. Any EAGAIN errors are reported back to the publisher.
        :param frames list of frames
        :type frames list
        :param publisher
        :type bytes
        :returns: List of dropped recipients, if any
        :rtype: list

        :Return Values:
        List of dropped recipients, if any
        """
        drop = []
        subscriber = frames[0]
        # Expecting outgoing frames:
        #   [RECIPIENT, SENDER, PROTO, USER_ID, MSG_ID, SUBSYS, ...]

        try:
            # Try sending the message to its recipient
            self._vip_sock.send_multipart(frames, flags=NOBLOCK, copy=False)
        except ZMQError as exc:
            try:
                errnum, errmsg = error = _ROUTE_ERRORS[exc.errno]
            except KeyError:
                error = None
            if exc.errno == EHOSTUNREACH:
                self._logger.debug("Host unreachable {}".format(subscriber.bytes))
                drop.append(bytes(subscriber))
            elif exc.errno == EAGAIN:
                self._logger.debug("EAGAIN error {}".format(subscriber.bytes))
                # Only send EAGAIN errors
                proto, user_id, msg_id, subsystem = frames[2:6]
                frames = [publisher, b'', proto, user_id, msg_id,
                          b'error', errnum, errmsg, subscriber, subsystem]
                try:
                    self._vip_sock.send_multipart(frames, flags=NOBLOCK, copy=False)
                except ZMQError as exc:
                    #raise
                    pass
        return drop

    def _update_caps_users(self, frames):
        """
        Stores the user capabilities sent by the Auth Service
        :param frames list of frames
        :type frames list
        """
        if len(frames) > 7:
            data = frames[7].bytes
            try:
                msg = jsonapi.loads(data)
                self._user_capabilities = msg['capabilities']
            except ValueError:
                pass

    def _update_protected_topics(self, frames):
        """
         Update the protected topics and capabilities as per message received from AuthService.
        :peer frames list of frames
        :type frames list
        """

        if len(frames) > 7:
            data = frames[7].bytes
            try:
                msg = jsonapi.loads(data)
                self._load_protected_topics(msg)
            except ValueError:
                pass

    def _load_protected_topics(self, topics_data):
        try:
            write_protect = topics_data['write-protect']
        except KeyError:
            write_protect = []

        topics = ProtectedPubSubTopics()
        try:
            for entry in write_protect:
                topics.add(entry['topic'], entry['capabilities'])
        except KeyError:
            self._logger.exception('invalid format for protected topics ')
        else:
            self._protected_topics = topics
            self._logger.info('protected-topics loaded')

    def handle_subsystem(self, frames, user_id):
        """
         Handler for incoming pubsub frames. It checks operation frame and directs it for appropriate action handler.
        :param frames list of frames
        :type frames list
        :param user_id user id of the publishing agent. This is required for protected topics check.
        :type user_id  UTF-8 encoded User-Id property
        :returns: response frame to be sent back to the sender
        :rtype: list

        :Return Values:
        response frame to be sent back to the sender
        """
        response = []
        result = None
        sender, recipient, proto, usr_id, msg_id, subsystem = frames[:6]

        if subsystem.bytes == b'pubsub':
            try:
                op = bytes(frames[6])
            except IndexError:
                return False

            if op == b'subscribe':
                result = self._peer_subscribe(frames)
            elif op == b'publish':
                try:
                    result = self._peer_publish(frames, user_id)
                except IndexError:
                    #send response back -- Todo
                    return
            elif op == b'unsubscribe':
                result = self._peer_unsubscribe(frames)
            elif op == b'list':
                result = self._peer_list(frames)
            elif op == b'synchronize':
                self._peer_sync(frames)
            elif op == b'auth_update':
                self._update_caps_users(frames)
            elif op == b'protected_update':
                self._update_protected_topics(frames)
            else:
                self._logger.error("Unknown pubsub request {}".format(bytes(op)))
                pass

        if result is not None:
            #Form response frame
            response = [sender, recipient, proto, user_id, msg_id, subsystem]
            response.append(zmq.Frame(b'request_response'))
            response.append(zmq.Frame(bytes(result)))

        return response

    def _check_if_protected_topic(self, peer, topic):
        """
         Checks if the peer is authorized to publish the topic.
        :peer frames list of frames
        :type frames list
        :topic str
        :str user_id  UTF-8 encoded User-Id property
        :returns: None if authorization check is successful or error message
        :rtype: None or str

        :Return Values:
        None or error message
        """
        msg = None
        required_caps = self._protected_topics.get(topic)

        if required_caps:
            user = peer
            try:
                caps = self._user_capabilities[user]
            except KeyError:
                return
            if not set(required_caps) <= set(caps):
                msg = ('to publish to topic "{}" requires capabilities {},'
                       ' but capability list {} was'
                       ' provided').format(topic, required_caps, caps)
        return msg

class ProtectedPubSubTopics(object):
    '''Simple class to contain protected pubsub topics'''
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

        prefix = self._isprefix(topic)
        if prefix is not None:
            return self._dict[prefix]
        for regex, capabilities in self._re_list:
            if regex.match(topic):
                return capabilities
        return None

    def _isprefix(self, topic):
        for prefix in self._dict:
            if topic[:len(prefix)] == prefix:
                return prefix
        return None
