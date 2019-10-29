# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
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



import logging
import logging.config
import os
import re

import zmq
from zmq import SNDMORE, EHOSTUNREACH, ZMQError, EAGAIN, NOBLOCK
from zmq import green
from collections import defaultdict

# Create a context common to the green and non-green zmq modules.
from volttron.platform.agent.utils import get_platform_instance_name
from volttron.utils.frame_serialization import serialize_frames

green.Context._instance = green.Context.shadow(zmq.Context.instance().underlying)
from volttron.platform import get_home
from .agent.subsystems.pubsub import ProtectedPubSubTopics
from volttron.platform.jsonrpc import (INVALID_REQUEST, UNAUTHORIZED)
from volttron.platform import jsonapi

# Optimizing by pre-creating frames
_ROUTE_ERRORS = {
    errnum: (zmq.Frame(str(errnum).encode('ascii')),
             zmq.Frame(os.strerror(errnum).encode('ascii')))
    for errnum in [zmq.EHOSTUNREACH, zmq.EAGAIN]
}

_log = logging.getLogger(__name__)

class PubSubService(object):
    def __init__(self, socket, protected_topics, routing_service, *args, **kwargs):
        self._logger = logging.getLogger(__name__)

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
        self._rabbitmq_agent = None

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
        # To do
        temp = {}

    def add_rabbitmq_agent(self, agent):
        self._rabbitmq_agent = agent

    def external_platform_add(self, instance_name):
        self._logger.debug("PUBSUBSERVICE send subs external {}".format(instance_name))
        if self._ext_router is not None:
            self._send_external_subscriptions([instance_name])

    def external_platform_drop(self, instance_name):
        if instance_name in self._ext_subscriptions:
            self._logger.debug("PUBSUBSERVICE dropping external subscriptions for {}".format(instance_name))
            del self._ext_subscriptions[instance_name]

    def _sync(self, peer, items):
        """
        Synchronize the subscriptions with calling agent (peer) when it gets newly connected. OR Unsubscribe from
        stale/forgotten/unsolicited subscriptions when the peer is dropped.
        :param peer
        :type peer str
        :param items subcription items or empty dict
        :type dict
        """
        # self._logger.debug("SYNC before: {0}, {1}".format(peer, items))
        items = {(platform, bus, prefix) for platform, buses in items.items()
                                         for bus, topics in buses.items()
                                         for prefix in topics}
        #self._logger.debug("SYNC after: {}".format(items))
        remove = []
        for platform, bus_subscriptions in self._peer_subscriptions.items():
            for bus, subscriptions in bus_subscriptions.items():
                for prefix, subscribers in subscriptions.items():
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
        if 'all' in self._peer_subscriptions and self._ext_router is not None:
            # self._logger.debug("Syncing ext subscriptions: {}".format(self._peer_subscriptions))
            # Send subscription message to all connected platforms
            external_platforms = self._ext_router.get_connected_platforms()
            self._send_external_subscriptions(external_platforms)

    def _peer_sync(self, frames):
        """
        Synchronizes the subscriptions with the calling agent.
        :param frames list of frames
        :type frames list
        """
        if len(frames) > 8:
            conn = frames[7]
            if conn == 'connected':
                # _log.debug(f"_peer_sync frames: {frames}")
                msg = frames[8]
                peer = frames[0]
                try:
                    items = msg['subscriptions']
                    assert isinstance(items, dict)
                    self._sync(peer, items)
                except KeyError as exc:
                    self._logger.error("Missing key in _peer_sync message {}".format(exc))

    def _peer_subscribe(self, frames):
        """It stores the subscription information sent by the agent. It unpacks the frames to get identity of the
        subscriber, prefix and bus and saves it for future use.
        :param frames list of frames
        :type frames list
        """
        if len(frames) < 8:
            return False
        else:
            # self._logger.debug("Subscribe before: {}".format(self._peer_subscriptions))
            msg = frames[7]
            peer = frames[0]

            try:
                prefix = msg['prefix']
                bus = msg['bus']
            except KeyError as exc:
                self._logger.error("Missing key in _peer_subscribe message {}".format(exc))
                return False

            is_all = msg.get('all_platforms', False)

            if is_all:
                platform = 'all'
            else:
                platform = 'internal'
                if self._rabbitmq_agent:
                    # Subscribe to RMQ bus
                    self._rabbitmq_agent.vip.pubsub.subscribe('pubsub',
                                                              prefix,
                                                              self.publish_callback,
                                                              all_platforms=is_all)

            for prefix in prefix if isinstance(prefix, list) else [prefix]:
                self._add_peer_subscription(peer, bus, prefix, platform)

            # self._logger.debug("Subscribe after: {}".format(self._peer_subscriptions))
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
            msg = frames[7]
            peer = frames[0]
            unsubmsg = dict()
            # Added for backward compatibility
            try:
                sub = msg['internal']
                unsubmsg = msg
            except KeyError:
                try:
                    sub = msg['all']
                    unsubmsg = msg
                except KeyError:
                    unsubmsg['internal'] = msg

            for platform in unsubmsg:
                prefix = unsubmsg[platform]['prefix']
                bus = unsubmsg[platform]['bus']
                subscriptions = self._peer_subscriptions[platform][bus]
                if prefix is None:
                    remove = []
                    for topic, subscribers in subscriptions.items():
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
                    # Send updated subscription list to all connected platforms
                    external_platforms = self._ext_router.get_connected_platforms()
                    self._send_external_subscriptions(external_platforms)
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
            try:
                msg = frames[8]
                headers = msg['headers']
                message = msg['message']
                peer = frames[0]
                bus = msg['bus']
                pub_msg = dict(sender=peer, bus=bus, headers=headers, message=message)
                frames[8] = pub_msg
            except KeyError as exc:
                self._logger.error("Missing key in _peer_publish message {}".format(exc))
                return 0
            except ValueError:
                self._logger.error("JSON decode error. Invalid character")
                return 0
            if self._rabbitmq_agent:
                self._publish_on_rmq_bus(frames)
            return self._distribute(frames, user_id)

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
            msg = jsonapi.loadb(data)
            peer = frames[0].bytes
            try:
                prefix = msg['prefix']
                bus = msg['bus']
                subscribed = msg['subscribed']
                reverse = msg['reverse']
            except KeyError as exc:
                self._logger.error("Missing key in _peer_list message {}".format(exc))
                return results

            is_all = msg.get('all_platforms', False)
            if not is_all:
                platform = 'internal'
            else:
                platform = 'all'

            if bus is None:
                buses = self._peer_subscriptions[platform].items()
            else:
                buses = [(bus, self._peer_subscriptions[platform][bus])]
            if reverse:
                test = prefix.startswith
            else:
                test = lambda t: t.startswith(prefix)
            for bus, subscriptions in buses:
                for topic, subscribers in subscriptions.items():
                    if test(topic):
                        member = peer in subscribers
                        if not subscribed or member:
                            results.append((bus, topic, member))
            results = jsonapi.dumps(results)
        return results

    def _distribute(self, frames, user_id):
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
        publisher, receiver, proto, _, msg_id, subsystem, op, topic, data = frames[0:9]
        # Check if peer is authorized to publish the topic
        errmsg = self._check_if_protected_topic(user_id, topic)

        # Send error message as peer is not authorized to publish to the topic
        if errmsg is not None:
            try:
                frames = [publisher, '', proto, user_id, msg_id,
                          'error', str(UNAUTHORIZED),
                          str(errmsg), '', subsystem]
            except ValueError:
                self._logger.debug("Value error")
            self._send(frames, publisher)
            return 0

        # First: Try to send to internal platform subscribers
        internal_count = self._distribute_internal(frames)
        # Second: Try to send to external platform subscribers
        # external_count=0
        external_count = self._distribute_external(frames)
        return internal_count + external_count

    def _distribute_internal(self, frames):
        """
        Distribute the publish message to local subscribers
        :param frames: list of frames
        :return: Number of local subscribers
        """
        publisher = frames[0]
        topic = frames[7]
        try:
            msg = frames[8]
            bus = msg['bus']
        except KeyError as exc:
            self._logger.error("Missing key in _peer_publish message {}".format(exc))
            return 0
        except ValueError:
            self._logger.error("JSON decode error. Invalid character")
            return 0

        all_subscriptions = dict()
        subscriptions = dict()
        subs = dict()
        # Get subscriptions for all platforms
        try:
            all_subscriptions = self._peer_subscriptions['all'][bus]
        except KeyError:
            pass
        try:
            subscriptions = self._peer_subscriptions['internal'][bus]
        except KeyError:
            pass

        subs.update(all_subscriptions)
        subs.update(subscriptions)
        subscribers = set()
        # Check for local subscribers
        for prefix, subscription in subs.items():
            if subscription and topic.startswith(prefix):
                subscribers |= subscription

        if subscribers:
            # self._logger.debug("PUBSUBSERVICE: found subscribers: {}".format(subscribers))
            for subscriber in subscribers:
                frames[0] = subscriber
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
        topic = topic
        for platform_id, subscriptions in self._ext_subscriptions.items():
            for prefix in subscriptions:
                if topic.startswith(prefix):
                    external_subscribers.add(platform_id)
        # self._logger.debug("PUBSUBSERVICE External subscriptions {0}, {1}".format(topic, external_subscribers))
        if external_subscribers:
            frames[:] = []
            frames[0:7] = '', proto, user_id, msg_id, subsystem, 'external_publish', topic, data
            for platform_id in external_subscribers:
                try:
                    if self._ext_router is not None:
                        self._logger.debug("Sending to: {}".format(platform_id))
                        # Send the message to the external platform
                        success = self._ext_router.send_external(platform_id, frames)
                except ZMQError as exc:
                    try:
                        errnum, errmsg = error = _ROUTE_ERRORS[exc.errno]
                    except KeyError:
                        error = None
                    if exc.errno == EAGAIN:
                        # Only send EAGAIN errors, so that publisher can try sending again later
                        frames = [publisher, '', proto, user_id, msg_id,
                                  'error', errnum, errmsg, platform_id, subsystem]
                        try:
                            self._vip_sock.send_multipart(frames, flags=NOBLOCK, copy=False)
                        except ZMQError as exc:
                            # raise
                            pass
                    # If external platform is unreachable, drop the all subscriptions
                    if exc.errno == EHOSTUNREACH:
                        self._logger.debug("Host not reachable: {}".format(platform_id))
                        # self.external_platform_drop(platform_id)
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
        # _log.debug(f"pubsubservice _send {frames}")

        try:
            # Try sending the message to its recipient
            # Because we are sending directly on the socket we need
            # bytes
            serialized = serialize_frames(frames)
            self._vip_sock.send_multipart(serialized, flags=NOBLOCK, copy=False)
        except ZMQError as exc:
            try:
                errnum, errmsg = error = _ROUTE_ERRORS[exc.errno]
            except KeyError:
                error = None
            if exc.errno == EHOSTUNREACH:
                self._logger.debug("Host unreachable {}".format(subscriber))
                drop.append(subscriber)
            elif exc.errno == EAGAIN:
                self._logger.debug("EAGAIN error {}".format(subscriber))
                # Only send EAGAIN errors
                proto, user_id, msg_id, subsystem = frames[2:6]
                frames = [publisher, b'', proto, user_id, msg_id,
                          b'error', errnum, errmsg, subscriber, subsystem]
                try:
                    self._vip_sock.send_multipart(frames, flags=NOBLOCK, copy=False)
                except ZMQError as exc:
                    # raise
                    pass
        return drop

    def _update_caps_users(self, frames):
        """
        Stores the user capabilities sent by the Auth Service
        :param frames list of frames
        :type frames list
        """
        if len(frames) > 7:
            try:
                msg = frames[7]
                self._user_capabilities = msg['capabilities']
            except KeyError as exc:
                self._logger.error("Missing key in update auth capabilities message {}".format(exc))
            except ValueError:
                pass

    def _update_protected_topics(self, frames):
        """
         Update the protected topics and capabilities as per message received from AuthService.
        :peer frames list of frames
        :type frames list
        """

        if len(frames) > 7:
            # _log.debug(f"Update protected topics frames {frames}")
            try:
                msg = frames[7]
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

    def handle_subsystem(self, frames, user_id=''):
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

        try:
            sender, recipient, proto, usr_id, msg_id, subsystem, op = frames[:7]
        except (ValueError, TypeError):  # TypeError will happen if frames is not subscriptable.
            _log.error(f"Invalid number of frames handle_subsystem {frames}")
            return False

        # subsystem = bytes(subsystem)
        # op = bytes(op)

        if subsystem == 'pubsub':
            if op == 'subscribe':
                result = self._peer_subscribe(frames)
            elif op == 'publish':
                try:
                    result = self._peer_publish(frames, user_id)
                except IndexError:
                    #send response back -- Todo
                    return []
            elif op == 'unsubscribe':
                result = self._peer_unsubscribe(frames)
            elif op == 'list':
                result = self._peer_list(frames)
                # Form response frame
                response = [sender, recipient, proto, user_id, msg_id, subsystem]
                response.append(zmq.Frame('list_response'))
                response.append(zmq.Frame(result))
                result = None
            elif op == 'synchronize':
                self._peer_sync(frames)
            elif op == 'auth_update':
                self._update_caps_users(frames)
            elif op == 'protected_update':
                self._update_protected_topics(frames)
            elif op == 'external_list':
                # self._logger.debug("PUBSUBSERVICE external_list")
                result = self._update_external_subscriptions(frames)
            elif op == 'external_publish':
                self._logger.debug("PUBSUBSERVICE external to local publish")
                self._external_to_local_publish(frames)
            elif op == b'error':
                self._handle_error(frames)
            elif op == 'request_response':
                pass
            else:
                self._logger.error("PUBSUBSERVICE Unknown pubsub request {}".format(op.decode("utf-8")))
                pass

        if result is not None:
            # Form response frame
            response = [sender, recipient, proto, user_id, msg_id, subsystem]
            response.append('request_response')
            response.append(result)

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
        frames = ['', 'VIP1', '', '', 'pubsub', 'external_list', msg]

        if self._ext_router is not None:
            for name in external_platforms:
                self._ext_router.send_external(name, frames)

    def _update_external_subscriptions(self, frames):
        """
        Store external subscriptions
        :param frames: frames containing external subscriptions
        :return:
        """
        results = []

        if len(frames) <= 7:
            return False
        else:
            msg = frames[7]
            try:
                this_platform_instance_name = get_platform_instance_name()
                for instance_name in msg:
                    if instance_name == this_platform_instance_name:
                        _log.error("Invalid configuraiton of external instances!\n"
                                   f"The name {instance_name} is specified as local and "
                                   "external instance name.  Please fix this issue in the "
                                   "external_platform_discovery.json file in the "
                                   "the VOLTTRON_HOME of the external instance.")
                        continue
                    prefixes = msg[instance_name]
                    # Store external subscription list for later use (during publish)
                    self._ext_subscriptions[instance_name] = prefixes
                    self._logger.debug("PUBSUBSERVICE New external list from {0}: List: {1}".
                                       format(instance_name, self._ext_subscriptions))
                    if self._rabbitmq_agent:
                        for prefix in prefixes:
                            self._rabbitmq_agent.vip.pubsub.subscribe('pubsub',
                                                                      prefix,
                                                                      self.publish_callback
                                                                      )
            except KeyError as exc:
                self._logger.error("Unknown external instance name: {}".format(instance_name))
                return False
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
            # Check if peer is authorized to publish the topic
            errmsg = self._check_if_protected_topic(user_id, topic)

            # peer is not authorized to publish to the topic, send error message to the peer
            if errmsg is not None:
                try:
                    frames = [publisher, b'', proto, user_id, msg_id,
                              subsystem, b'error', zmq.Frame(str(UNAUTHORIZED).encode("utf-8")),
                              zmq.Frame(str(errmsg).encode("utf-8"))]
                    self._ext_router.send_external(publisher, frames)
                    return
                except ValueError:
                    self._logger.debug("Value error")

            # Make it an internal publish
            frames[6] = 'publish'
            subscribers_count = 1
            if self._rabbitmq_agent:
                self._publish_on_rmq_bus(frames)
            else:
                subscribers_count = self._distribute_internal(frames)
            # There are no subscribers, send error message back to source platform
            if not subscribers_count:
                try:
                    frames = [publisher, b'', proto, user_id, msg_id,
                              subsystem, zmq.Frame(b'error'), zmq.Frame(str(INVALID_REQUEST).encode("utf-8")),
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
        if len(frames) > 7:
            error_type = frames[7].bytes
            if error_type == INVALID_REQUEST:
                topic = frames[8].bytes
                # Remove subscriber for that topic

    def publish_callback(self, peer, sender, bus, topic, headers, message):
        """
        Callback method to receive PubSub messages from internal RabbitMQ message bus and send it
        to external platform subscribers over ZMQ message bus.
        :param peer: pubsub
        :param sender: publisher
        :param bus: bus
        :param topic: publisher topic
        :param headers: message header
        :param message: message body
        :return:
        """
        # self._logger.debug("PubSubService message: {}".format(message))
        json_msg = jsonapi.dumps(dict(sender=peer, bus=bus, headers=headers, message=message))
        frames = [sender, '', 'VIP1', '', '', 'pubsub', 'publish', topic, json_msg]
        # Send it through ZMQ bus
        self._distribute(frames, '')
        self._logger.debug("Publish callback {}".format(topic))

    def _publish_on_rmq_bus(self, frames: list):
        """
        Publish the message on RabbitMQ message bus.
        :param frames: ZMQ message frames
        :return:
        """
        publisher = frames[0]
        topic = frames[7]

        try:
            msg = frames[8]
            bus = msg['bus']
        except KeyError as exc:
            self._logger.error("Missing key in _peer_publish message {}".format(exc))
        except ValueError:
            self._logger.error("JSON decode error. Invalid character")
        if self._rabbitmq_agent:
            self._rabbitmq_agent.vip.pubsub.publish('pubsub',
                                                    topic,
                                                    msg['headers'],
                                                    msg['message'],
                                                    bus=bus)


class ProtectedPubSubTopics(object):
    '''Simple class to contain protected pubsub topics'''

    def __init__(self):
        self._dict = {}
        self._re_list = []

    def add(self, topic, capabilities):
        if isinstance(capabilities, str):
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

    def get_topic_caps(self):
        return self._dict.copy()

    def _isprefix(self, topic):
        for prefix in self._dict:
            if topic[:len(prefix)] == prefix:
                _log.debug(f"Prefix is {prefix}")
                return prefix
        return None
