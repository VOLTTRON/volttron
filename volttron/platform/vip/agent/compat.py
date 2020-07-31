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



from contextlib import closing

from zmq import green as zmq
from volttron.platform import jsonapi

from . import Core, ZMQCore, RPC, PeerList, PubSub
from .subsystems.pubsub import encode_peer
from volttron.platform.messaging.headers import Headers


class CompatPubSub(object):
    '''VOLTTRON 2.x compatible agent pub/sub message exchange bus.

    Accept multi-part messages from sockets connected to in_addr, which
    is a PULL socket, and forward them to sockets connected to out_addr,
    which is a XPUB socket. When subscriptions are added or removed, a
    message of the form 'subscriptions/<OP>/<TOPIC>' is broadcast to the
    PUB socket where <OP> is either 'add' or 'remove' and <TOPIC> is the
    topic being subscribed or unsubscribed. When a message is received
    of the form 'subscriptions/list/<PREFIX>', a multipart message will
    be broadcast with the first two received frames (topic and headers)
    sent unchanged and with the remainder of the message containing
    currently subscribed topics which start with <PREFIX>, each frame
    containing exactly one topic.
    '''

    PEER = b'pubsub'
    PUBLISH_ADDRESS = 'inproc://vip/compat/agent/publish'
    SUBSCRIBE_ADDRESS = 'inproc://vip/compat/agent/subscribe'

    def __init__(self, identity=None, address=None, context=None, peer=PEER,
                 publish_address=PUBLISH_ADDRESS,
                 subscribe_address=SUBSCRIBE_ADDRESS,
                 message_bus='zmq'):
        self.core = ZMQCore(
            self, identity=identity, address=address, context=context)
        self.rpc = RPC(self.core, self)
        self.peerlist = PeerList(self.core)
        self.pubsub = PubSub(self.core, self.rpc, self.peerlist, self)
        self.peer = peer
        self.publish_address = publish_address
        self.subscribe_address = subscribe_address
        self.in_sock = None
        self.out_sock = None

    @Core.receiver('onsetup')
    def setup(self, sender, **kwargs):
        self.in_sock = zmq.Socket(self.core.context, zmq.PULL)
        self.out_sock = zmq.Socket(self.core.context, zmq.XPUB)

    @Core.receiver('onstart')
    def in_loop(self, sender, **kwargs):   # pylint: disable=unused-argument
        peer = self.peer
        with closing(self.in_sock) as sock:
            sock.bind(self.publish_address)
            while True:
                message = sock.recv_multipart()
                #log.debug('incoming message: {!r}'.format(message))
                topic = message[0]
                if (topic.startswith('subscriptions/list') and
                        topic[18:19] in ['/', '']):
                    if len(message) > 2:
                        del message[2:]
                    elif len(message) == 1:
                        message.append('')
                    prefix = topic[19:].decode('utf-8')
                    topics = self.pubsub.list(
                        peer, prefix, subscribed=False).get()
                    message.extend(topic.encode('utf-8')
                                   for _, topic, _ in topics)
                    self.out_sock.send_multipart(message)
                else:
                    message = [part.decode('utf-8') for part in message]
                    try:
                        topic, headers = message[:2]
                    except (ValueError, TypeError):
                        continue
                    headers = jsonapi.loads(headers)
                    message = message[2:]
                    self.pubsub.publish(peer, topic, headers, message).get()

    @Core.receiver('onstart')
    def out_loop(self, sender, **kwargs):   # pylint: disable=unused-argument
        peer = self.peer
        with closing(self.out_sock) as sock:
            sock.bind(self.subscribe_address)
            while True:
                message = sock.recv()
                if message:
                    add = bool(ord(message[0]))
                    topic = message[1:].decode('utf-8')
                    if add:
                        self.pubsub.subscribe(peer, topic, self.forward).get()
                    else:
                        self.pubsub.unsubscribe(peer, topic, self.forward).get()
                    #log.debug('incoming subscription: {} {!r}'.format(
                    #    ('add' if add else 'remove'), topic))
                    sock.send('subscriptions/{}{}{}'.format(
                        ('add' if add else 'remove'),
                        ('' if topic[:1] == '/' else '/'), topic))

    def forward(self, peer, sender, bus, topic, headers, message):
        headers = Headers(headers)
        headers['VIP.peer'] = encode_peer(peer)
        headers['VIP.sender'] = encode_peer(sender)
        headers['VIP.bus'] = bus
        parts = [topic]
        if message is not None:
            if 'Content-Type' in headers:
                if isinstance(message, list):
                    parts.extend(message)
                else:
                    parts.append(message)
            else:
                parts.append(jsonapi.dumps(message))
                headers['Content-Type'] = 'application/json'
        parts.insert(1, jsonapi.dumps(headers.dict))
        self.out_sock.send_multipart(parts)


def unpack_legacy_message(headers, message):
    '''Unpack legacy pubsub messages for VIP agents.

    Loads JSON-formatted message parts and removes single-frame messages
    from their containing list. Does not alter headers.
    '''
    if not isinstance(headers, Headers):
        headers = Headers(headers)
    try:
        content_type = headers['Content-Type']
    except KeyError:
        return headers, message
    if isinstance(content_type, str):
        if content_type.lower() == 'application/json':
            if isinstance(message, list) and len(message) == 1:
                return jsonapi.loads(message[0])
            if isinstance(message, str):
                return jsonapi.loads(message)
        if isinstance(message, list) and len(message) == 1:
            return message[0]
    if isinstance(content_type, list) and isinstance(message, list):
        parts = [(jsonapi.loads(msg)
                  if str(ctype).lower() == 'application/json' else msg)
                 for ctype, msg in zip(content_type, message)]
        parts.extend(message[len(parts):])
        if len(parts) == len(content_type) == 1:
            return parts[0]
        return parts
    return message
