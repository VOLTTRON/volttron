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

import gevent
from gevent.fileobject import FileObject
import zmq
from zmq import SNDMORE, EHOSTUNREACH, ZMQError, EAGAIN, NOBLOCK
from zmq import green
# Create a context common to the green and non-green zmq modules.
green.Context._instance = green.Context.shadow(zmq.Context.instance().underlying)
from zmq.utils import jsonapi
from ..agent import utils
from .agent.subsystems.pubsub import ProtectedPubSubTopics
from .. import jsonrpc

# Optimizing by pre-creating frames
_ROUTE_ERRORS = {
    errnum: (zmq.Frame(str(errnum).encode('ascii')),
             zmq.Frame(os.strerror(errnum).encode('ascii')))
    for errnum in [zmq.EHOSTUNREACH, zmq.EAGAIN]
}

class PubSubService(object):
    def __init__(self, protected_topics_file, socket, *args, **kwargs):
        self._protected_topics_file = os.path.abspath(protected_topics_file)
        self._logger = logging.getLogger(__name__)
        # if self._logger.level == logging.NOTSET:
        #     self._logger.setLevel(logging.WARNING)
        self._peer_subscriptions = {}
        self._vip_sock = socket
        self.add_bus('')
        self._user_capabilities = {}
        self._protected_topics = ProtectedPubSubTopics()
        self._read_protected_topics_file()
        self._read_protected_greenlet = gevent.spawn(utils.watch_file, self._protected_topics_file,
                                                    self._read_protected_topics_file)
    def _read_protected_topics_file(self):
        self._logger.info('loading protected-topics file %s',
                  self._protected_topics_file)
        try:
            utils.create_file_if_missing(self._protected_topics_file)
            with open(self._protected_topics_file) as fil:
                # Use gevent FileObject to avoid blocking the thread
                data = FileObject(fil, close=False).read()
                topics_data = jsonapi.loads(data) if data else {}
        except Exception:
            self._logger.exception('error loading %s', self._protected_topics_file)
        else:
            write_protect = topics_data.get('write-protect', [])
            topics = ProtectedPubSubTopics()
            try:
                for entry in write_protect:
                    topics.add(entry['topic'], entry['capabilities'])
            except KeyError:
                self._logger.exception('invalid format for protected topics '
                               'file {}'.format(self._protected_topics_file))
            else:
                self._protected_topics = topics
                self._logger.info('protected-topics file %s loaded',
                          self._protected_topics_file)
        #self._logger.debug("PUBSUBSERVICE: protect file contents {0}, {1}".format(self._protected_topics._dict, self._protected_topics._re_list))

    def _add_peer_subscription(self, peer, bus, prefix):
        try:
            subscriptions = self._peer_subscriptions[bus]
        except KeyError:
            self._peer_subscriptions.setdefault(bus, {})
            subscriptions = self._peer_subscriptions[bus]
        try:
            subscribers = subscriptions[prefix]
        except KeyError:
            subscriptions[prefix] = subscribers = set()
        subscribers.add(peer)
        #self._logger.debug("Added peer in subscription list {0} {1}".format(peer, self._peer_subscriptions))

    def add_bus(self, name):
        self._peer_subscriptions.setdefault(name, {})

    def peer_add(self, peer, **kwargs):
        self._logger.debug("PUBSUBSERVICE: PEER ADD {}".format(peer))
        #gevent.spawn(self._sync(peer, {}))

    def peer_drop(self, peer, **kwargs):
        self._logger.debug("PUBSUBSERVICE: PEER DROP {}".format(peer))
        self._sync(peer, {})

    def _sync(self, peer, items):
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
        self._logger.debug("PubSubService: In peer sync")
        if len(frames) > 8:
            conn = frames[7].bytes
            #self._logger.debug("PubSubService: peer_sync: {0}".format(conn))
            if conn == b'connected':
                data = frames[8].bytes
                json0 = data.find('{')
                msg = jsonapi.loads(data[json0:])
                peer = msg['identity']
                items = msg['subscriptions']
                #peer = bytes(self.rpc().context.vip_message.peer)
                assert isinstance(items, dict)
                self._sync(peer, items)
            #self._logger.debug("PubSubService: peer_subscriptions: {0}".format(self._peer_subscriptions))

    def _peer_subscribe(self, frames):
        #self._logger.debug("Peer subscriptions before subscribe: {}".format(self._peer_subscriptions))
        if len(frames) > 7:
            data = frames[7].bytes
            json0 = data.find('{')
            msg = jsonapi.loads(data[json0:])
            peer = msg['identity']
            prefix = msg['prefix']
            bus = msg['bus']
        #self._logger.debug("Subscription: peer: {0}, prefix: {1}, bus: {2}".format(peer, prefix, bus))
        #peer = bytes(self.vip.rpc.context.vip_message.peer)
        for prefix in prefix if isinstance(prefix, list) else [prefix]:
            self._add_peer_subscription(peer, bus, prefix)
        self._logger.debug("Peer subscriptions after subscribe: {}".format(self._peer_subscriptions))

    def _peer_unsubscribe(self, frames):
#        peer = bytes(self.rpc().context.vip_message.peer)
        if len(frames) > 7:
            data = frames[7].bytes
            json0 = data.find('{')
            msg = jsonapi.loads(data[json0:])
            peer = msg['identity']
            prefix = msg['prefix']
            bus = msg['bus']
            #self._logger.debug("UnSubscription: peer: {0}, prefix: {1}, bus: {2}".format(peer, prefix, bus))
            #self._logger.debug("Peer subscriptions: {}".format(self._peer_subscriptions))
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
                    #self._logger.debug("subscriptions: {}".format(subscriptions))
                    subscribers = subscriptions[prefix]
                    subscribers.discard(peer)
                    if not subscribers:
                        del subscriptions[prefix]
            #self._logger.debug("Peer subscriptions: {}".format(self._peer_subscriptions))

    def _peer_publish(self, frames, user_id):
        # for f in frames:
        #     self._logger.debug("PUBSUBSERIVE: publish frames {}".format(bytes(f)))
        self._logger.debug("PUBSUBSERVICE PUBLISH peer subscriptions {}".format(self._peer_subscriptions))
        if len(frames) > 7:
            topic = frames[7].bytes
            data = frames[8].bytes
            try:
                msg = jsonapi.loads(data)
                headers = msg['headers']
                message = msg['message']
                bus = ''
                peer = msg['identity']
                bus = msg['bus']
            except ValueError:
                self._logger.debug("JSON decode error. Invalid character")
                return 0
            return self.router_distribute(frames, peer, topic, headers, message, bus, user_id)

    def _peer_list(self, frames):
        results = []
        if len(frames) > 7:
            data = frames[7].bytes
            json0 = data.find('{')
            msg = jsonapi.loads(data[json0:])
            peer = msg['identity']
            prefix = msg['prefix']
            bus = msg['bus']
            subscribed = msg['subscribed']
            reverse = msg['reverse']
            #self._logger.debug("List request: peer: {0}, prefix: {1}, bus: {2}".format(peer, prefix, bus))

            #peer = bytes(self.rpc().context.vip_message.peer)
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
        self._logger.debug("Peer list: {}".format(results))
        return results

    def router_distribute(self, frames, peer, topic, headers, message=None, bus='', user_id=b''):
        #self._logger.debug("PUBSUBSERVICE checking protected topic for USER_ID: {}".format(user_id))
        errmsg = self._check_if_protected_topic(user_id, topic)
        #Send error message back as unauthorized publish for the topic
        if errmsg is not None:
            #self._logger.debug("PUBSUBSERVICE Protected topic error message: {}".format(errmsg))
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
        # for f in frames:
        #     self._logger.debug("PUBSUBSERVICE: sending frames: {}".format(f.bytes))
        publisher = frames[0]
        frames[3] = bytes(user_id)
        for prefix, subscription in subscriptions.iteritems():
            if subscription and topic.startswith(prefix):
                subscribers |= subscription
        if subscribers:
            for subscriber in subscribers:
                #self._logger.debug("Sending to subscriber: {}".format(subscriber))
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

    def update_caps_users(self, frames):
        if len(frames) > 7:
            data = frames[7].bytes
            #self._logger.debug("PUBSUBSERVICE: user capabilities from auth: {}".format(data))
            try:
                json0 = data.find('{')
                msg = jsonapi.loads(data[json0:])
                self._user_capabilities = msg['capabilities']
            except ValueError:
                pass
            #self._logger.debug("PUBSUBSERVICE: user capabilities from auth after update: {}".format(self._user_capabilities))

    def handle_subsystem(self, frames, user_id):
        response = []

        sender, recipient, proto, usr_id, msg_id, subsystem = frames[:6]
        #subsystem = bytes(frames[5])

        if subsystem.bytes == b'pubsub':
            try:
                op = bytes(frames[6])
            except IndexError:
                return False

            if op == b'subscribe':
                #self._logger.debug("subscribe something")
                self._peer_subscribe(frames)
                #self._peer_subscribe(frames)
            elif op == b'publish':
                #print("publish something")
                try:
                    result = self._peer_publish(frames, user_id)
                    #Form a response frame
                    response = [sender, recipient, proto, user_id, msg_id, subsystem]
                    response.append(zmq.Frame(b'publish_response'))
                    response.append(zmq.Frame(bytes(result)))
                except IndexError:
                    #send response back -- Todo
                    return
            elif op == b'unsubscribe':
                #print("unsubscribe something")
                result = self._peer_unsubscribe(frames)

            elif op == b'list':
                #print("listing all subscriptions")
                result = self._peer_list(frames)
                # Form a response frame
                response = [sender, recipient, proto, user_id, msg_id, subsystem]
                response.append(zmq.Frame(b'list_response'))
                response.append(zmq.Frame(bytes(result)))

            elif op == b'synchronize':
                #print("synchronize all subscriptions")
                self._peer_sync(frames)

            elif op == b'auth_update':
                #print("update protected topics")
                self.update_caps_users(frames)
            else:
                pass
        return response

    def _check_if_protected_topic(self, peer, topic):
        msg = None
        required_caps = self._protected_topics.get(topic)
        #self._logger.debug("PUBSUBSERVCE: REQUIRED CAP {}".format(required_caps))
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
                #raise jsonrpc.exception_from_json(jsonrpc.UNAUTHORIZED, msg)
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
        for prefix in self._dict.keys():
            if topic[:len(prefix)] == prefix:
                return prefix
        return None
