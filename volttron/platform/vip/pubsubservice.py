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

import logging
import logging.config
import os
import uuid
import re

import gevent
from gevent.fileobject import FileObject
import zmq
from zmq import SNDMORE, EHOSTUNREACH, ZMQError, EAGAIN, NOBLOCK
from zmq import green
from collections import defaultdict

# Create a context common to the green and non-green zmq modules.
green.Context._instance = green.Context.shadow(zmq.Context.instance().underlying)
from .agent.subsystems.pubsub import ProtectedPubSubTopics
from volttron.platform.jsonrpc import (INVALID_REQUEST, UNAUTHORIZED)
from volttron.platform.vip.agent.errors import VIPError
from volttron.platform.agent import json as jsonapi

# Optimizing by pre-creating frames
_ROUTE_ERRORS = {
    errnum: (zmq.Frame(str(errnum).encode('ascii')),
             zmq.Frame(os.strerror(errnum).encode('ascii')))
    for errnum in [zmq.EHOSTUNREACH, zmq.EAGAIN]
}


class PubSubService(object):
    def __init__(self, socket, protected_topics, routing_service, *args, **kwargs):
        self._logger = logging.getLogger(__name__)
        # if self._logger.level == logging.NOTSET:
        #     self._logger.setLevel(logging.WARNING)

        def platform_subscriptions():
            return defaultdict(subscriptions)

        def subscriptions():
            return defaultdict(set)

        self._peer_subscriptions = defaultdict(platform_subscriptions)
        self._vip_sock = socket
        self._user_capabilities = {}
        self._protected_topics = ProtectedPubSubTopics()
        self._load_protected_topics(protected_topics)
        self._ext_subscriptions = defaultdict(set)
        self._ext_router = routing_service
        if self._ext_router is not None:
            self._ext_router.register('on_connect', self.external_platform_add)
            self._ext_router.register('on_disconnect', self.external_platform_drop)

    def _add_peer_subscription(self, peer, bus, prefix, platform='internal'):
        """
        This maintains subscriptions for specified peer (subscriber), bus and prefix.
        :param peer identity of the subscriber
        :type peer str
        :param bus bus.
        :type str
        :param prefix subscription prefix (peer is subscribing to all topics matching the prefix)
        :type str
        """
        self._peer_subscriptions[platform][bus][prefix].add(peer)

    def peer_drop(self, peer, **kwargs):
        """
        Drop/Remove subscriptions related to the peer as it is no longer reachable/available.
        :param peer agent to be dropped
        :type peer str
        :param **kwargs optional arguments
        :type pointer to arguments
        """
        self._sync(peer, {})

    def peer_add(self, peer):
        #To do
        temp = {}

    def external_platform_add(self, instance_name):
        self._logger.debug("PUBSUBSERVICE send subs external {}".format(instance_name))
        if self._ext_router is not None:
            self._send_external_subscriptions([instance_name])

    def external_platform_drop(self, instance_name):
        self._logger.debug("PUBSUBSERVICE dropping external subscriptions for {}".format(instance_name))
        #del self._ext_subscriptions[instance_name]

    def _sync(self, peer, items):
        """
        Synchronize the subscriptions with calling agent (peer) when it gets newly connected. OR Unsubscribe from
        stale/forgotten/unsolicited subscriptions when the peer is dropped.
        :param peer
        :type peer str
        :param items subcription items or empty dict
        :type dict
        """
        #self._logger.debug("SYNC before: {0}, {1}".format(peer, items))
        items = {(platform, bus, prefix) for platform, buses in items.iteritems()
                                            for bus, topics in buses.iteritems()
                                                for prefix in topics}
        #self._logger.debug("SYNC after: {}".format(items))
        remove = []
        for platform, bus_subscriptions in self._peer_subscriptions.iteritems():
            for bus, subscriptions in bus_subscriptions.iteritems():
                for prefix, subscribers in subscriptions.iteritems():
                    item = platform, bus, prefix
                    try:
                        items.remove(item)
                    except KeyError:
                        subscribers.discard(peer)
                        if not subscribers:
                            remove.append(item)
                    else:
                        subscribers.add(peer)
        for platform, bus, prefix in remove:
            subscriptions = self._peer_subscriptions[platform][bus]
            assert not subscriptions.pop(prefix)
        for platform, bus, prefix in items:
            self._add_peer_subscription(peer, bus, prefix, platform)

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
        # for f in frames:
        #     self._logger.debug("sub frames: {}".format(bytes(f)))
        if len(frames) < 8:
            return False
        else:
            data = frames[7].bytes
            msg = jsonapi.loads(data)
            peer = frames[0].bytes
            prefix = msg['prefix']
            bus = msg['bus']
            is_all = msg['all_platforms']
            if is_all:
                platform = 'all'
            else:
                platform = 'internal'

            for prefix in prefix if isinstance(prefix, list) else [prefix]:
                self._add_peer_subscription(peer, bus, prefix, platform)
            #self._logger.debug("PUBSUBERVICE: peer subscriptions{}".format(self._peer_subscriptions['all'][bus][prefix]))

            if is_all and self._ext_router is not None:
                # Send subscription message to all connected platforms
                external_platforms = self._ext_router.get_connected_platforms()
                self._send_external_subscriptions(external_platforms)
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

            for platform in msg:
                prefix = msg[platform]['prefix']
                bus = msg[platform]['bus']

                subscriptions = self._peer_subscriptions[platform][bus]
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

                if platform == 'all' and self._ext_router is not None:
                    # Send subscription message to all connected platforms
                    external_platforms = self._ext_router.get_connected_platforms()
                    self._send_external_subscriptions(external_platforms)
                return True

    def _peer_publish(self, frames):
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
            data = frames[8].bytes
            try:
                msg = jsonapi.loads(data)
                headers = msg['headers']
                message = msg['message']
                peer = frames[0].bytes
                bus = msg['bus']
                pub_msg = jsonapi.dumps(
                    dict(sender=peer, bus=bus, headers=headers, message=message)
                )
                frames[8] = zmq.Frame(str(pub_msg))
            except ValueError:
                self._logger.error("JSON decode error. Invalid character")
                return 0
            return self._distribute(frames)

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
            is_all = msg['all_platforms']
            if not is_all:
                platform = 'internal'
            else:
                platform = 'all'
            if bus is None:
                buses = self._peer_subscriptions[platform].iteritems()
            else:
                buses = [(bus, self._peer_subscriptions[platform][bus])]
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

    def _distribute(self, frames):
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
        :returns: Count of subscribers.
        :rtype: int

        :Return Values:
        Number of subscribers to whom the mess
        """
        publisher, receiver, proto, user_id, msg_id, subsystem, op, topic, data = frames[0:9]
        #Check if peer is authorized to publish the topic
        errmsg = self._check_if_protected_topic(bytes(user_id), bytes(topic))

        #Send error message as peer is not authorized to publish to the topic
        if errmsg is not None:
            try:
                frames = [publisher, b'', proto, user_id, msg_id,
                      b'error', zmq.Frame(bytes(UNAUTHORIZED)), zmq.Frame(str(errmsg)), b'', subsystem]
            except ValueError:
                self._logger.debug("Value error")
            self._send(frames, publisher)
            return 0

        # First: Try to send to internal platform subscribers
        internal_count = self._distribute_internal(frames)
        # Second: Try to send to external platform subscribers
        #external_count=0
        external_count = self._distribute_external(frames)
        return internal_count+external_count

    def _distribute_internal(self, frames):
        """
        Distribute the publish message to local subscribers
        :param frames: list of frames
        :return: Number of local subscribers
        """
        publisher = frames[0].bytes
        topic = frames[7].bytes
        data = frames[8].bytes
        try:
            msg = jsonapi.loads(data)
            bus = msg['bus']
        except ValueError:
            self._logger.error("JSON decode error. Invalid character")
            return 0

        all = 'all'
        # Get subscriptions for all platforms
        if all in self._peer_subscriptions:
            subscriptions = self._peer_subscriptions[all][bus]
        else:
            # Get subscriptions for local platform
            subscriptions = self._peer_subscriptions['internal'][bus]
        subscribers = set()
        # Check for local subscribers
        for prefix, subscription in subscriptions.iteritems():
            if subscription and topic.startswith(prefix):
                subscribers |= subscription
        if subscribers:
            #self._logger.debug("PUBSUBSERVICE: found subscribers: {}".format(subscribers))
            for subscriber in subscribers:
                frames[0] = zmq.Frame(subscriber)
                try:
                    # Send the message to the subscriber
                    for sub in self._send(frames, publisher):
                        # Drop the subscriber if unreachable
                        self.peer_drop(sub)
                except ZMQError:
                    raise
        return len(subscribers)

    def _distribute_external(self, frames):
        """
        Distribute the publish message to external subscribers (platforms)
        :param frames: list of frames
        :return: Number of external subscribers
        """
        publisher, receiver, proto, user_id, msg_id, subsystem, op, topic, data = frames[0:9]
        success = False
        external_subscribers = set()
        for platform_id, subscriptions in self._ext_subscriptions.items():
            for prefix in subscriptions:
                if bytes(topic).startswith(prefix):
                    external_subscribers.add(platform_id)
        ##self._logger.debug("PUBSUBSERVICE External subscriptions {0}".format(external_subscribers))
        if external_subscribers:
            frames[:] = []
            frames[0:7] = b'', proto, user_id, msg_id, subsystem, b'external_publish', topic, data
            for platform_id in external_subscribers:
                #self._logger.debug("PUBSUBSERVICE sending external publish {0}, subscriptions: {1}".format(platform_id, external_subscribers))
                try:
                    if self._ext_router is not None:
                        # Send the message to the external platform
                        success = self._ext_router.send_external(platform_id, frames)
                        #If external platform is unreachable, drop the all subscriptions
                        if not success:
                            self.external_platform_drop(platform_id)
                except ZMQError as exc:
                    try:
                        errnum, errmsg = error = _ROUTE_ERRORS[exc.errno]
                    except KeyError:
                        error = None
                    if exc.errno == EAGAIN:
                        # Only send EAGAIN errors, so that publisher can try sending again later
                        frames = [publisher, b'', proto, user_id, msg_id,
                                  b'error', errnum, errmsg, platform_id, subsystem]
                        try:
                            self._vip_sock.send_multipart(frames, flags=NOBLOCK, copy=False)
                        except ZMQError as exc:
                            # raise
                            pass
                    # If external platform is unreachable, drop the all subscriptions
                    if exc.errno == EHOSTUNREACH:
                        self._logger.debug("Host not reachable: {}".format(platform_id))
                        #self.external_platform_drop(platform_id)
                    else:
                        raise
        return len(external_subscribers)

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
        # for f in frames:
        #     self._logger.debug("PUBSUBSERVICE msg {}".format(bytes(f)))
        if subsystem.bytes == b'pubsub':
            try:
                op = bytes(frames[6])
            except IndexError:
                return False

            if op == b'subscribe':
                result = self._peer_subscribe(frames)
            elif op == b'publish':
                try:
                    result = self._peer_publish(frames)
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
            elif op == b'external_list':
                self._logger.debug("PUBSUBSERVICE external_list")
                result = self._update_external_subscriptions(frames)
            elif op == b'external_publish':
                self._logger.debug("PUBSUBSERVICE external to local publish")
                self._external_to_local_publish(frames)
            elif op == b'error':
                self._handle_error(frames)
            elif op == b'request_response':
                pass
            else:
                self._logger.error("PUBSUBSERVICE Unknown pubsub request {}".format(bytes(op)))
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

    def _get_external_prefix_list(self):
        """
        Get list of subscriptions of 'all' type
        :return:
        """
        prefixes = []

        all = 'all'
        if all in self._peer_subscriptions:
            self._logger.debug("PUBSUBSERVICE get subscriptions: {}".format(self._peer_subscriptions[all]))
            bus_subscriptions = self._peer_subscriptions[all]
            for bus, subscriptions in bus_subscriptions.items():
                for prefix in subscriptions:
                    prefixes.append(prefix)
        return prefixes

    def _send_external_subscriptions(self, external_platforms):
        """
        Send external subscriptions to remote platforms
        :param external_platforms: list of remote platforms
        :return:
        """
        prefixes = self._get_external_prefix_list()
        instance_name = self._ext_router.my_instance_name()
        prefix_msg = dict()
        prefix_msg[instance_name] = prefixes
        msg = jsonapi.dumps(prefix_msg)
        #self._logger.debug("PUBSUBSERVICE My vip id: {}".format(self._ext_router.my_instance_name()))
        frames = [b'', 'VIP1', b'', b'', b'pubsub', b'external_list', msg]

        if self._ext_router is not None:
            for name in external_platforms:
                self._logger.debug("PUBSUBSERVICE Sending to platform: {}".format(name))
                self._ext_router.send_external(name, frames)

    def _update_external_subscriptions(self, frames):
        """
        Store external subscriptions
        :param frames: frames containing external subscriptions
        :return:
        """
        self._logger.debug("PUBSUBSERVICE external_subscriptions from external platforms: {}".format(bytes(frames[0])))
        results = []

        if len(frames) <= 7:
            return False
        else:
            data = frames[7].bytes
            msg = jsonapi.loads(data)
            for instance_name in msg:
                prefixes = msg[instance_name]
                # Store external subscription list for later use (during publish)
                self._ext_subscriptions[instance_name] = prefixes
                self._logger.debug("PUBSUBSERVICE New external list from {0}: List: {1}".format(instance_name, self._ext_subscriptions))
            return True

    def _external_to_local_publish(self, frames):
        """
        Publish external pubsub message to local subscribers
        :param frames: frames containing publish message
        :return: count of local subscribers or error message if no local subscribers found
        """
        results = []
        subscribers_count = 0
        # Check if destination is local VIP -- Todo

        if len(frames) > 8:
            publisher, receiver, proto, user_id, msg_id, subsystem, op, topic, data = frames[0:9]
            data = frames[8].bytes
            msg = jsonapi.loads(data)
            # Check if peer is authorized to publish the topic
            errmsg = self._check_if_protected_topic(bytes(user_id), bytes(topic))

            #peer is not authorized to publish to the topic, send error message to the peer
            if errmsg is not None:
                try:
                    frames = [publisher, b'', proto, user_id, msg_id,
                              subsystem, b'error', zmq.Frame(bytes(UNAUTHORIZED)),
                              zmq.Frame(str(errmsg))]
                    self._ext_router.send_external(publisher, frames)
                    return
                except ValueError:
                    self._logger.debug("Value error")

            # Make it an internal publish
            frames[6] = 'publish'
            subscribers_count = self._distribute_internal(frames)
            self._logger.debug("Number of subscribers {}".format(subscribers_count))
            # There are no subscribers, send error message back to source platform
            if subscribers_count == 0:
                try:
                    errmsg = 'NO SUBSCRIBERS'
                    frames = [publisher, b'', proto, user_id, msg_id,
                              subsystem, zmq.Frame(b'error'), zmq.Frame(bytes(INVALID_REQUEST)),
                              topic]
                    self._ext_router.send_external(publisher, frames)
                except ValueError:
                    self._logger.debug("Value error")
        else:
            self._logger.debug("Incorrect frames {}".format(len(frames)))
        return subscribers_count

    def _handle_error(self, frames):
        """
        Error handler
        :param frames:
        :return:
        """
        self._logger.debug("handle error")
        if len(frames) > 7:
            error_type = frames[7].bytes
            if error_type == INVALID_REQUEST:
                topic = frames[8].bytes
                #Remove subscriber for that topic

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

