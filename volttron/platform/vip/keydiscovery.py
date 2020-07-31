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

from __future__ import print_function, absolute_import

import logging
import requests
import random
import os
import grequests
from datetime import datetime, timedelta
from zmq import ZMQError
from volttron.platform import jsonapi
from gevent.lock import Semaphore

from volttron.platform.agent import utils
from .agent import Agent, Core, RPC
from requests.packages.urllib3.connection import (ConnectionError,
                                                  NewConnectionError)
from urllib.parse import urlparse, urljoin
from gevent.fileobject import FileObject
from volttron.utils.persistance import PersistentDict


_log = logging.getLogger(__name__)

__version__ = '0.1'

class DiscoveryError(Exception):
    """ Raised when a different volttron central tries to register.
    """
    pass


class KeyDiscoveryAgent(Agent):
    """
    Class to get server key, instance name and vip address of external/remote platforms
    """

    def __init__(self, address, serverkey, identity, external_address_config,
                 setup_mode, bind_web_address, *args, **kwargs):
        super(KeyDiscoveryAgent, self).__init__(identity, address, **kwargs)
        self._external_address_file = external_address_config
        self._ext_addresses = dict()
        self._grnlets = dict()
        self._vip_socket = None
        self._my_web_address = bind_web_address
        self.r = random.random()
        self._setup_mode = setup_mode
        if self._setup_mode:
            _log.debug("RUNNING IN MULTI-PLATFORM SETUP MODE")

        self._store_path = os.path.join(os.environ['VOLTTRON_HOME'],
                                        'external_platform_discovery.json')
        self._ext_addresses_store = dict()
        self._ext_addresses_store_lock = Semaphore()

    @Core.receiver('onstart')
    def startup(self, sender, **kwargs):
        """
        Try to get platform discovery info of all the remote platforms. If unsuccessful, setup events to try again later
        :param sender: caller
        :param kwargs: optional arguments
        :return:
        """
        self._vip_socket = self.core.socket

        # If in setup mode, read the external_addresses.json to get web addresses to set up authorized connection with
        # external platforms.
        if self._setup_mode:
            if self._my_web_address is None:
                _log.error("Web bind address is needed in multiplatform setup mode")
                return
            with self._ext_addresses_store_lock:
                try:
                    self._ext_addresses_store = PersistentDict(filename=self._store_path, flag='c', format='json')
                except ValueError as exc:
                    _log.error("Error in json format: {0}".format(exc))
                # Delete the existing store.
                if self._ext_addresses_store:
                    self._ext_addresses_store.clear()
                    self._ext_addresses_store.async_sync()
            web_addresses = dict()
            # Read External web addresses file
            try:
                web_addresses = self._read_platform_address_file()
                try:
                    web_addresses.remove(self._my_web_address)
                except ValueError:
                    _log.debug("My web address is not in the external bind web adress list")

                op = 'web-addresses'
                self._send_to_router(op, web_addresses)
            except IOError as exc:
                _log.error("Error in reading file: {}".format(exc))
                return
            sec = random.random() * self.r + 10
            delay = utils.get_aware_utc_now() + timedelta(seconds=sec)
            grnlt = self.core.schedule(delay, self._key_collection, web_addresses)
        else:
            # Use the existing store for platform discovery information
            with self._ext_addresses_store_lock:
                try:
                    self._ext_addresses_store = PersistentDict(filename=self._store_path, flag='c', format='json')
                except ValueError as exc:
                    _log.error("Error in json file format: {0}".format(exc))
                for name, discovery_info in self._ext_addresses_store.items():
                    op = 'normalmode_platform_connection'
                    self._send_to_router(op, discovery_info)

    def _key_collection(self, web_addresses):
        """
        Collect platform discovery information (server key, instance name, vip-address) for all platforms.
        :param web_addresses: List of web addresses to get discovery info
        :return:
        """
        for web_address in web_addresses:
            if web_address not in self._my_web_address:
                self._collect_key(web_address)

    def _collect_key(self, web_address):
        """
        Try to get (server key, instance name, vip-address) of remote instance and send it to RoutingService
        to connect to the remote instance. If unsuccessful, try again later.
        :param name: instance name
        :param web_address: web address of remote instance
        :return:
        """
        platform_info = dict()

        try:
            platform_info = self._get_platform_discovery(web_address)
            with self._ext_addresses_store_lock:
                _log.debug("Platform discovery info: {}".format(platform_info))
                name = platform_info['instance-name']
                self._ext_addresses_store[name] = platform_info
                self._ext_addresses_store.async_sync()
        except KeyError as exc:
            _log.error("Discovery info does not contain instance name {}".format(exc))
        except DiscoveryError:
            # If discovery error, try again later
            sec = random.random() * self.r + 30
            delay = utils.get_aware_utc_now() + timedelta(seconds=sec)
            grnlet = self.core.schedule(delay, self._collect_key, web_address)
        except ConnectionError as e:
            _log.error("HTTP connection error {}".format(e))

        #If platform discovery is successful, send the info to RoutingService
        #to establish connection with remote platform.
        if platform_info:
            op = 'setupmode_platform_connection'
            connection_settings = dict(platform_info)
            connection_settings['web-address'] = web_address
            self._send_to_router(op, connection_settings)

    def _send_to_router(self, op, platform_info):
        """
        Send the platform discovery stats to the router to establish new connection
        :param platform_info: platform discovery stats
        :return:
        """
        address = jsonapi.dumps(platform_info)

        frames = [op, address]
        try:
            self._vip_socket.send_vip('', 'routing_table', frames, copy=False)
        except ZMQError as ex:
            # Try sending later
            _log.error("ZMQ error while sending external platform info to router: {}".format(ex))

    def _read_platform_address_file(self):
        """
        Read the external addresses file
        :return:
        """

        try:
            with open(self._external_address_file) as fil:
                # Use gevent FileObject to avoid blocking the thread
                data = FileObject(fil, close=False).read()
                web_addresses = jsonapi.loads(data) if data else {}
                return web_addresses
        except IOError as e:
            _log.error("Error opening file {}".format(self._external_address_file))
            raise
        except Exception:
            _log.exception('error loading %s', self._external_address_file)
            raise

    def _get_platform_discovery(self, web_address):
        """
        Use http discovery call to get serverkey, instance name and vip-address of remote instance
        :param web_address: web address of remote instance
        :return:
        """

        r = {}
        try:
            parsed = urlparse(web_address)

            assert parsed.scheme
            assert not parsed.path

            real_url = urljoin(web_address, "/discovery/")
            req = grequests.get(real_url)
            responses = grequests.map([req])
            responses[0].raise_for_status()
            r = responses[0].json()
            return r
        except requests.exceptions.HTTPError:
            raise DiscoveryError(
                    "Invalid discovery response from {}".format(real_url)
                )
        except requests.exceptions.Timeout:
            raise DiscoveryError(
                    "Timeout error from {}".format(real_url)
                )
        except AttributeError as e:
            raise DiscoveryError(
                "Invalid web_address passed {}"
                    .format(web_address)
            )
        except (ConnectionError, NewConnectionError) as e:
            raise DiscoveryError(
                "Connection to {} not available".format(real_url)
            )
        except Exception as e:
            raise DiscoveryError(
                "Unknown Exception: {}".format(e)
            )

