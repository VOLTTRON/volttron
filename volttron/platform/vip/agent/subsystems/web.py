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
# }}}

from collections import defaultdict
import logging
import weakref

from volttron.platform.agent.known_identities import MASTER_WEB
from volttron.platform.vip.agent.subsystems.base import SubsystemBase

__docformat__ = 'reStructuredText'

_log = logging.getLogger(__name__)


class WebSubSystem(SubsystemBase):
    """
    The web subsystem handles the agent side of routing web data from the
    :class:`volttron.platform.web.MasterWebService`.

    """

    def __init__(self, owner, core, rpc):
        self._owner = weakref.ref(owner)
        self._rpc = weakref.ref(rpc)
        self._core = weakref.ref(core)
        self._endpoints = {}
        self._ws_endpoint = {}

        rpc.export(self._opened, 'client.opened')
        rpc.export(self._closed, 'client.closed')
        rpc.export(self._message, 'client.message')
        rpc.export(self._route_callback, 'route.callback')

        def onstop(sender, **kwargs):
            rpc.call(MASTER_WEB, 'unregister_all_agent_routes')

        core.onstop.connect(onstop, self)

    def register_endpoint(self, endpoint, callback, res_type="jsonrpc"):
        """
        The :meth:`register_endpoint` method registers an endpoint with the
        :class:`volttron.platform.web.MasterWebService` on the VOLTTRON
        instance.

        Each endpoint can map to at most one callback function.  The callback
        function must support the following interface

        .. code-block:: python

            def callback(self, env, data):
                print('The environmental variables {}'.format(env))
                print('The data sent {}'.format(data))

        .. versionadded:: VOLTTRON 4.0.1

        :param endpoint:
            Http endpoint matching the PATH_INFO environmental variable
        :param callback: Agent method to be called with the env and data.
        :type endpoint: str
        :type callback: function
        """
        _log.info('Registering route endpoint: {}'.format(endpoint))
        self._endpoints[endpoint] = callback
        self._rpc().call(MASTER_WEB, 'register_endpoint', endpoint, res_type)

    def register_path(self, prefix, static_path):
        """
        The :meth:`register_path` method registers a prefix that can be used
        for routing static files.

        .. versionadded:: VOLTTRON 4.0.1

        :param prefix:
        :param static_path:
            An existing path available to the
            :class:`volttron.platform.web.MasterWebService`
        :type prefix: str
        :type static_path: str
        """
        _log.info('Registering path prefix: {}, path: {}'.format(
            prefix, static_path
        ))
        self._rpc().call(MASTER_WEB, 'register_path_route', prefix,
                         static_path)

    def register_websocket(self, endpoint, opened=None, closed=None,
                           received=None):
        """
        The :meth:`register_websocket` method registers a websocket endpoint
        that can be connected to through the
        :class:`volttron.platform.web.MasterWebService`.

        The parameters opened and closed can be specified as callback events
        with the following signature:

        .. code-block:: python

            def ws_opened(self, endpoint):
                print('ws_opened endpoint {}'.format(endpoint))

            def ws_closed(self, endpoint):
                print('ws_closed endpoint {}'.format(endpoint))

        The received event is triggered when the websocket is writtent to fro
        the client.  The received event must have a signature such as the
        following interface:

        .. code-block:: python

            def ws_received(self, endpoint, message):
                print('ws_received endpoint {} message: {}'.format(endpoint,
                                                                   message))

        .. versionadded:: VOLTTRON 4.0.1

        :param endpoint: The endpoint of the websocket event occurred on.
        :param opened:
            An event triggered when a client is connected to the endpoint.
        :param closed:
            An event triggered when a client is closed or disconnected from
            the endpoint.
        :param received:
            An event triggered when data comes in on the endpoint's websocket.
        :type endpoint: str
        :type opened: function
        :type closed: function
        :type received: function
        """
        self._ws_endpoint[endpoint] = (opened, closed, received)
        self._rpc().call(MASTER_WEB, 'register_websocket', endpoint).get(
            timeout=5)

    def unregister_websocket(self, endpoint):
        self._rpc().call(MASTER_WEB, 'unregister_websocket', endpoint).get(
            timeout=5
        )

    def send(self, endpoint, message=''):
        """
        The :meth:`send` method publishes data to the registered websocket
        clients that are subscribed to the passed endpoint.

        .. versionadded:: VOLTTRON 4.0.1

        :param endpoint: The endpoint to be used to send the message.
        :param message:
            The message to be sent through to the client.  This parameter must
            be serializable.
        :type endpoint: str
        :type message: str
        """
        _log.debug('SENDING DATA TO CALLBACK {} {}'.format(endpoint, message))
        self._rpc().call(MASTER_WEB, 'websocket_send', endpoint, message).get(
            timeout=5)

    def _route_callback(self, env, data):
        _log.debug('Routing callback env: {} data: {}'.format(env, data))
        fn = self._endpoints.get(env['PATH_INFO'])
        if fn:
            _log.debug("Calling function: {}".format(fn.__name__))
            return fn(env, data)

        return None

    def _opened(self, fromip, endpoint):
        _log.debug('Client opened callback ip: {} endpoint: {}'.format(
            fromip, endpoint))
        callbacks = self._ws_endpoint.get(endpoint)
        if callbacks is None:
            _log.error('Websocket endpoint {} is not available'.format(
                endpoint))
        else:
            if callbacks[0]:
                return callbacks[0](fromip, endpoint)

        return False

    def _closed(self, endpoint):
        _log.debug('Client closed callback endpoint: {}'.format(endpoint))

        callbacks = self._ws_endpoint.get(endpoint)
        if callbacks is None:
            _log.error('Websocket endpoint {} is not available'.format(
                endpoint))
        else:
            if callbacks[1]:
                callbacks[1](endpoint)

    def _message(self, endpoint, message):
        print('Client received message callback')

        callbacks = self._ws_endpoint.get(endpoint)
        if callbacks is None:
            _log.error('Websocket endpoint {} is not available'.format(
                endpoint))
        else:
            if callbacks[2]:
                callbacks[2](endpoint, message)
