# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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
import urllib.parse
import uuid
import os

import gevent

from volttron import platform
from volttron.platform import get_home
from volttron.platform.agent.utils import get_aware_utc_now
from volttron.platform.vip.agent import Agent
from volttron.platform import build_vip_address_string

__version__ = '1.0.3'
__author__ = 'Craig Allwardt <craig.allwardt@pnnl.gov>'


DEFAULT_TIMEOUT = 30


class Connection(object):
    """ A class that manages a connection to a peer and/or server.

    """
    def __init__(self, address, peer=None, publickey=None,
                 secretkey=None, serverkey=None, volttron_home=None,
                 instance_name=None, message_bus=None, **kwargs):

        self._log = logging.getLogger(__name__)
        self._log.debug("Connection: {}, {}, {}, {}, {}, {}"
                   .format(address, peer, publickey, secretkey, serverkey, message_bus))
        self._address = address
        self._peer = peer
        self._serverkey = None
        if peer is None:
            self._log.warning('Peer is non so must be passed in call method.')
        self.volttron_home = volttron_home

        if self.volttron_home is None:
            self.volttron_home = os.path.abspath(platform.get_home())

        if address.startswith('ipc'):
            full_address = address
        else:
            parsed = urllib.parse.urlparse(address)
            if parsed.scheme == 'tcp':
                qs = urllib.parse.parse_qs(parsed.query)
                self._log.debug('QS IS: {}'.format(qs))
                if 'serverkey' in qs:
                    self._serverkey = qs.get('serverkey')
                else:
                    self._serverkey = serverkey

                # Handle case when the address has all the information in it.
                if 'serverkey' in qs and 'publickey' in qs and \
                                'secretkey' in qs:
                    full_address = address
                else:
                    full_address = build_vip_address_string(
                        vip_root=address, serverkey=serverkey,
                        publickey=publickey, secretkey=secretkey
                    )
            elif parsed.scheme == 'ipc':
                full_address = address
            else:
                raise AttributeError(
                    'Invalid address type specified. ipc or tcp accepted.')

        self._server = Agent(address=full_address,
                             volttron_home=self.volttron_home,
                             enable_store=False,
                             reconnect_interval=1000,
                             instance_name=instance_name,
                             message_bus=message_bus,
                             **kwargs)
        # TODO the following should work as well, but doesn't.  Not sure why!
        # self._server = Agent(address=address, serverkey=serverkey,
        #                      secretkey=secretkey, publickey=publickey,
        #                      enable_store=False,
        #                      volttron_home=self.volttron_home, **kwargs)
        self._greenlet = None
        self._connected_since = None
        self._last_publish = None
        self._last_publish_failed = False
        self._last_rpc_call = None

        # Make the actual attempt to connect to the server.
        self.is_connected()

    @property
    def serverkey(self):
        return self._serverkey

    @property
    def last_publish_failed(self):
        return self._last_publish_failed

    @property
    def connected_since(self):
        return self._connected_since

    @property
    def last_publish(self):
        return self._last_publish

    @property
    def last_rpc_call(self):
        return self._last_rpc_call

    @property
    def address(self):
        return self._address

    @property
    def peer(self):
        return self._peer

    @property
    def server(self):
        if self._greenlet is None:
            event = gevent.event.Event()
            self._greenlet = gevent.spawn(self._server.core.run, event)

            try:
                with gevent.Timeout(DEFAULT_TIMEOUT):
                    event.wait()
            except gevent.Timeout:
                self.kill()
                self._greenlet = None
                raise

            self._connected_since = get_aware_utc_now()
            if self.peer:
                if self.peer not in self._server.vip.peerlist().get(timeout=2):
                    self._log.warning('peer {} not found connected to router.'.format(self.peer))
        return self._server

    def peers(self, timeout=DEFAULT_TIMEOUT):
        return self.server.vip.peerlist().get(timeout=timeout)

    def is_connected(self, timeout=DEFAULT_TIMEOUT):
        return self.server.core.connected and self.is_peer_connected(timeout)

    def is_peer_connected(self, timeout=DEFAULT_TIMEOUT):
        self._log.debug('Checking for peer {}'.format(self.peer))
        return self.peer in self.peers()

    def publish(self, topic, headers=None, message=None, timeout=DEFAULT_TIMEOUT):
        if timeout is None:
            raise ValueError('timeout cannot be None')

        timeout = int(timeout)

        self.server.vip.pubsub.publish(
            'pubsub', topic=topic, headers=headers, message=message
        ).get(timeout=timeout)

    def subscribe(self, prefix, callback):
        self.server.vip.pubsub.subscribe('pubsub', prefix, callback)

    def call(self, method, *args, **kwargs):
        timeout = kwargs.pop('timeout', DEFAULT_TIMEOUT)
        peer = kwargs.pop('peer', None)

        if peer is not None:
            return self.server.vip.rpc.call(
                peer, method, *args, **kwargs).get(timeout=timeout)

        if self.peer is not None:
            return self.server.vip.rpc.call(
                self.peer, method, *args, **kwargs).get(timeout=timeout)

        raise ValueError("peer not specified on class or as method argument.")

    def notify(self, method, *args, **kwargs):
        peer = kwargs.pop('peer')

        if peer is not None:
            return self.server.vip.rpc.notify(
                peer, method, *args, **kwargs)

        if self.peer is not None:
            return self.server.vip.rpc.notify(
                self.peer, method, *args, **kwargs)

        raise ValueError("peer not specified on class or as method argument.")

    def kill(self, *args, **kwargs):
        if self._greenlet is not None:
            self._greenlet.kill(*args, **kwargs)
            del(self._greenlet)
            self._greenlet = None
