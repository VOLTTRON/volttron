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
# }}}

import logging

import gevent

from volttron.platform.control import Agent
from volttron.platform.web import build_vip_address_string

_log = logging.getLogger(__name__)

__version__ = '1.0.0'
__author__ = 'Craig Allwardt <craig.allwardt@pnnl.gov>'


class Connection(object):
    """ A class that manages a connection to a peer and/or server.

    """
    def __init__(self, address, peer=None, publickey=None,
                 secretkey=None, serverkey=None):
        _log.debug("Connection: {}, {}, {}, {}, {}"
                   .format(address, peer, publickey, secretkey, serverkey))
        self.address = address
        self.peer = peer
        if peer is None:
            _log.warn('Peer is non so must be passed in call method.')
        full_address = build_vip_address_string(
            vip_root=address, serverkey=serverkey, publickey=publickey,
            secretkey=secretkey
        )
        self._server = Agent(address=full_address)
        self._greenlet = None

    @property
    def server(self):
        _log.debug('Spawning greenlet')
        if self._greenlet is None:
            event = gevent.event.Event()
            self._greenlet = gevent.spawn(self._server.core.run, event)
            event.wait()

            _log.debug('Connection peerlist: {}'.format(
                self._server.vip.peerlist().get(timeout=4)
            ))
        return self._server

    def publish(self, topic, header=None, message=None, timeout=None):
        if timeout:
            try:
                timeout = int(timeout)
                self.server.vip.pubsub.publish(
                    'pubsub', topic=topic, header=header, message=message
                ).get(timeout=timeout)
            except ValueError:
                _log.debug('Invalid integer passed for timeout.')
        else:
            self.server.vip.pubsub.publish(
                'pubsub', topic=topic, header=header, message=message
            )

    def call(self, method, *args, **kwargs):
        timeout = kwargs.pop('timeout', 30)
        peer = kwargs.pop('peer')

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
