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

import logging

_log = logging.getLogger(__name__)


class ServicePeerNotifier(object):
    """
    This class is responsible for routing the base_router's connections and disconnections
    from the zmq thread through to the registered callback functions.
    """
    def __init__(self):
        self._registered_added = set()
        self._registered_dropped = set()

    def register_peer_callback(self, added_callback, dropped_callback):
        """
        Register functions for adding callbacks for connected and disconnected peers
        to the message bus.

        The signature of the callback should be:

        .. code-block :: python

            def added_callback(peer):
                # the peer is a string identity connected.
                pass

        :param added_callback:
        :param dropped_callback:
        """
        assert added_callback is not None
        assert dropped_callback is not None

        self._registered_added.add(added_callback)
        self._registered_dropped.add(dropped_callback)

    def peer_added(self, peer):
        """
        Handles calling registered methods
        :param peer:
        :return:
        """
        for fn in self._registered_added:
            fn(peer)

    def peer_dropped(self, peer):
        """
        Handles calling of registered methods when a peer drops a connection to the platform.
        :param peer:
        :return:
        """
        for fn in self._registered_dropped:
            fn(peer)
