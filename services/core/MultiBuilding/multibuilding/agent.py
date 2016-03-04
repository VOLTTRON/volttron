# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2015, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
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
# nor any of their employees, nor any jurisdiction or organization
# that has cooperated in the development of these materials, makes
# any warranty, express or implied, or assumes any legal liability
# or responsibility for the accuracy, completeness, or usefulness or
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does
# not necessarily constitute or imply its endorsement, recommendation,
# r favoring by the United States Government or any agency thereof,
# or Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

#}}}

'''VOLTTRON platform™ service for multi-building messaging.'''

import errno
from errno import EAGAIN, EINTR
import logging
import sys
import uuid

import zmq
from zmq import NOBLOCK, ZMQError
import zmq.utils
from zmq.utils import z85

from volttron.platform.agent import BaseAgent, PublishMixin, periodic
from volttron.platform.agent import utils, matching
from volttron.platform import messaging


_log = logging.getLogger(__name__)
__version__ ='0.1'

def MultiBuildingAgent(config_path=None, **kwargs):
    '''Return agent object providing multi-building messaging.

    The configuration file, if given by config_path, may contain the
    declarations below. An initial configuration may be passed in as a
    dictionary via the config keyword argument.

      building-publish-address:
          A ØMQ address used to publish to the building's message bus.
          Defaults to 'tcp://0.0.0.0:9161'.

      building-subscribe-address:
          A ØMQ address used to subscribe to the building's message bus.
          Defaults to 'tcp://0.0.0.0:9160'.

      public-key, secret-key:
          Curve keypair (create with zmq.curve_keypair()) to use for
          authentication and encryption. If not provided, all
          communications will be unencrypted.

      cleanup-period:
          Frequency, in seconds, to check for and close stale
          connections. Defaults to 600 seconds (10 minutes).

      hosts:
          A mapping (dictionary) of building names to publish/subscribe
          addresses. Each entry is of the form:

              <BUILDING>: {'pub': <PUB_ADDRESS>, 'sub': <SUB_ADDRESS>,
                           'public-key': <PUBKEY>, 'allow': <PUB_OR_SUB>}

          where <BUILDING>, <PUB_ADDRESS, <SUB_ADDRESS>, <PUBKEY>, and
          <PUB_OR_SUB> are all strings specifying the building name as
          'CAMPUS/BUILDING', the publish and subscribe addresses as
          ØMQ addresses, the curve public key, and either 'pub' or 'sub'
          to allow publish only or both publish and subscribe.

      uuid:
          A UUID to use in the Cookie header. If not given, one will
          be automatically generated.
    '''

    config = kwargs.pop('config', {})
    if config_path:
        config.update(utils.load_config(config_path))
    cleanup_period = config.get('cleanup-period', 600)
    assert cleanup_period >= 1

    class Proxy(PublishMixin, BaseAgent):
        '''Proxy messages between internal bus and other buildings.

        This class could be combined with the Agent class below rather
        than using it as a base class. Keeping the implementations
        separate, however, provides for a cleaner implementation and
        allows one to more easily track the agent logic.
        '''

        def __init__(self, **kwargs):
            '''Create and register the external sockets.'''
            super(Proxy, self).__init__(**kwargs)
            # Use separate context for these sockets to avoid
            # authentication conflicts with other sockets.
            ctx = zmq.Context()
            self.zap_sock = ctx.socket(zmq.REP)
            self.zap_sock.bind('inproc://zeromq.zap.01')
            self.reactor.register(self.zap_sock, self.handle_authentication)
            self.outgoing = messaging.Socket(zmq.XPUB, context=ctx)
            self._config_socket(self.outgoing)
            self.outgoing.zap_domain = 'building.outgoing'
            self.incoming = messaging.Socket(zmq.PULL, context=ctx)
            self._config_socket(self.incoming)
            self.incoming.zap_domain = 'building.incoming'
            key = config.get('secret-key')
            if key:
                self.outgoing.curve_secretkey = key
                self.outgoing.curve_server = 1
                self.incoming.curve_secretkey = key
                self.incoming.curve_server = 1
            self.hosts = config.get('hosts', {})
            self.allow_sub = set(key for host in self.hosts.itervalues()
                    for key, allow in [(host.get('public-key'), host.get('allow', 'sub'))]
                        if key and allow in ['pub', 'sub'])
            self.allow_pub = set(key for host in self.hosts.itervalues()
                    for key, allow in [(host.get('public-key'), host.get('allow', 'sub'))]
                        if key and allow == 'pub')

        def _config_socket(self, sock):
            sock.reconnect_ivl = 1000
            sock.reconnect_ivl_max = 180000
            sock.sndtimeo = 10000
            sock.rcvtimeo = 10000
            sock.linger = 10000

        def setup(self):
            '''Bind the external ports.'''
            super(Proxy, self).setup()
            self.reactor.register(self.outgoing, self.handle_subscribe)
            self.outgoing.bind(config.get(
                    'building-subscribe-address', 'tcp://0.0.0.0:9160'))
            pub_addr = config.get('building-publish-address',
                                  'tcp://0.0.0.0:9161')
            if pub_addr:
                self.reactor.register(self.incoming, self.handle_incoming)
                self.incoming.bind(pub_addr)

        def handle_incoming(self, sock):
            '''Receive incoming messages and publish to internal bus.'''
            try:
                topic, headers, message = self.incoming.recv_message(NOBLOCK)
            except ZMQError as e:
                if e.errno == EINTR:
                    return
                raise
            self.publish(topic, headers, *message)

        def handle_subscribe(self, sock):
            '''Manage external subscription messages.'''
            try:
                message = self.outgoing.recv(NOBLOCK)
            except ZMQError as e:
                if e.errno == EINTR:
                    return
                raise
            if message:
                add = bool(ord(message[0]))
                topic = message[1:]
                if add:
                    self.subscribe(topic, self.on_outgoing)
                else:
                    self.unsubscribe(topic)

        def handle_authentication(self, sock):
            '''Restrict connections to approved clients.'''
            allow = False
            auth = sock.recv_multipart()
            version, sequence, domain, address, identity, mechanism = auth[:6]
            assert version == '1.0'
            if mechanism == 'CURVE':
                creds = z85.encode(auth[6])
                if domain == 'building.outgoing':
                    allow = creds in self.allow_sub
                elif domain == 'building.incoming':
                    allow = creds in self.allow_pub
            elif mechanism == 'NULL':
                allow, creds = True, ''
            else:
                creds = ''
            _log.info('{} {} at {} via {} {}'.format(
                    'allow' if allow else 'deny', address, domain,
                    mechanism, creds))
            if allow:
                reply = [version, sequence, "200", "OK", "", ""]
            else:
                reply = [version, sequence, "400", "Forbidden", "", ""]
            sock.send_multipart(reply)

        def on_outgoing(self, topic, headers, message, match):
            '''Forward messages to external subscribers.'''
            while True:
                try:
                    self.outgoing.send_message(
                            topic, headers, *message, flags=NOBLOCK)
                except ZMQError as e:
                    if e.errno == EINTR:
                        continue
                    if e.errno != EAGAIN:
                        raise
                break


    class Agent(Proxy):
        '''Provide inter-building publish/subscribe service.

        Provides three topics for inter-building messaging:

          building/recv/<CAMPUS>/<BUILDING>/<TOPIC>:
              Agents can subscribe to to this topic to receive messages
              sent to <TOPIC> ant the building specified by
              <CAMPUS>/<BUILDING>.

          building/send/<CAMPUS>/<BUILDING>/<TOPIC>:
              Agents can send messages to this topic to have them
              forwarded to <TOPIC> at the building specified by
              <CAMPUS>/<BUILDING>.
            
          building/error/<CAMPUS>/<BUILDING>/<TOPIC>
              Errors encountered during sending/receiving to/from the
              above two topics will be sent over this topic.
        '''

        def __init__(self, **kwargs):
            super(Agent, self).__init__(**kwargs)
            self.uuid = config.get('uuid') or str(uuid.uuid4())
            self.subs = {}
            self.rsubs = {}
            self.pubs = {}
            self.sequence = 0

        def setup(self):
            '''Request list of current subscriptions.'''
            super(Agent, self).setup()
            # Check and connect existing subscriptions
            self.publish('subscriptions/list/building/recv/',
                         {'Cookie': 'init ' + self.uuid})

        @matching.match_regex('subscriptions/add/building/recv/([^/]+/[^/]+)/(.*)')
        def on_subscribe(self, full_topic, headers, message, match):
            '''Handle new external building subscription requests.'''
            building, topic = match.groups()
            self.add_subscription(building, topic, cookie=headers.get('Cookie'))

        def add_subscription(self, building, topic, cookie=None):
            '''Add external building subscription.'''
            sock = self.subs.get(building)
            if not sock:
                host = self.hosts.get(building)
                address = host.get('sub') if host else None
                # Handle missing address
                if not address:
                    headers = {'Cookie': cookie} if cookie else {}
                    self.publish_error(building, topic, headers, errno.ENOENT,
                                       'building subscription address not found')
                    return
                sock = messaging.Socket(zmq.SUB)
                key = host.get('public-key')
                if key:
                    sock.curve_serverkey = key
                    sock.curve_secretkey = config.get('secret-key')
                    sock.curve_publickey = config.get('public-key')
                self._config_socket(sock)
                sock.connect(address)
                self.subs[building] = sock
                self.rsubs[sock] = building
                self.reactor.register(sock, self.handle_republish)
            sock.subscribe = topic.encode('utf-8')

        def handle_republish(self, sock):
            '''Publish incoming messages on internal bus.'''
            building = self.rsubs[sock]
            try:
                orig_topic, headers, message = sock.recv_message(flags=NOBLOCK)
            except ZMQError as e:
                if e.errno == EINTR:
                    return
                self.reactor.unregister(sock)
                self.subs.pop(building, None)
                self.rsubs.pop(sock, None)
                sock.close()
                return
            topic = 'building/recv/{}/{}'.format(building, orig_topic)
            self.publish(topic, headers, *message)

        def publish_error(self, building, topic, headers, errnum, message):
            '''Publish errors to error topic.'''
            topic = 'building/error/{}/{}'.format(building, topic)
            self.publish(topic, headers, str(errnum), message)

        @matching.match_regex('subscriptions/remove/building/recv/([^/]+/[^/]+)/(.*)')
        def on_unsubscribe(self, full_topic, headers, message, match):
            '''Handle external building unsubscribe requests.'''
            building, topic = match.groups()
            sock = self.subs.get(building)
            if sock:
                sock.unsubscribe = topic

        @matching.match_regex('building/send/([^/]+/[^/]+)/(.*)')
        def on_send(self, full_topic, headers, message, match):
            '''Handle external building publish requests.'''
            building, topic = match.groups()
            sock, seq = self.pubs.get(building, (None, None))
            if not sock:
                host = self.hosts.get(building)
                address = host.get('pub') if host else None
                # Handle missing address
                if not address:
                    cookie = headers.get('Cookie')
                    headers = {'Cookie': cookie} if cookie else {}
                    self.publish_error(building, topic, headers, errno.ENOENT,
                                       'building publish address not found')
                    return
                sock = messaging.Socket(zmq.PUSH)
                key = host.get('public-key')
                if key:
                    sock.curve_serverkey = key
                    sock.curve_secretkey = config.get('secret-key')
                    sock.curve_publickey = config.get('public-key')
                self._config_socket(sock)
                sock.connect(address)
            if seq != self.sequence:
                self.pubs[building] = sock, self.sequence
            while True:
                try:
                    sock.send_message(topic, headers, *message, flags=NOBLOCK)
                except ZMQError as e:
                    if e.errno == EINTR:
                        continue
                    self.pubs.pop(building, None)
                    sock.close()
                    self.publish_error(building, topic, headers,
                                       errno.ECONNABORTED,
                                       'message not sent; socket closed')
                break
                

        @periodic(cleanup_period)
        def on_cleanup(self):
            '''Periodically request subscription list for cleaning.'''
            self.publish('subscriptions/list/building/recv/',
                         {'Cookie': 'clean ' + self.uuid})
            for building, (sock, seq) in self.pubs.items():
                if seq != self.sequence:
                    del self.pubs[building]
            self.sequence += 1

        @matching.match_exact('subscriptions/list/building/recv/')
        def on_subscription_list(self, topic, headers, message, match):
            '''Handle closing unused sockets.'''
            if headers.get('Cookie') != 'clean ' + self.uuid:
                return
            topics = set()
            for prefix in message:
                try:
                    campus, building = prefix[33:].split('/', 2)[:2]
                except ValueError:
                    continue
                topics.add('/'.join([campus, building]))
            for building, sock in self.subs.values():
                if building not in topics:
                    self.subs.pop(building, None)
                    self.rsubs.pop(sock, None)
                    try:
                        self.reactor.unregister(sock)
                    except KeyError:
                        pass
                    sock.close()

        @matching.match_exact('subscriptions/list/building/recv/')
        def on_subscription_init(self, topic, headers, message, match):
            '''Handle existing subscriptions to external buildings on start.'''
            if headers.get('Cookie') != 'init ' + self.uuid:
                return
            for prefix in message:
                try:
                    ## len('building/recv/') == 14
                    campus, building, topic = prefix[14:].split('/', 2)
                except ValueError:
                    continue
                building = '/'.join([campus, building])
                self.add_subscription(building, topic)

    # Rename agent to match factory function.
    Agent.__name__ = 'MultiBuildingAgent'
    return Agent(**kwargs)



def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    utils.setup_logging()
    try:
        utils.default_main(MultiBuildingAgent,
            description='VOLTTRON platform™ multi-building message routing agent',
            argv=argv)
    except Exception:
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
