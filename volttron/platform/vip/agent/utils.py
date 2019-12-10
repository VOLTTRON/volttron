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

from __future__ import absolute_import, print_function

import logging
import os

import gevent

from volttron.platform import get_address
from volttron.platform.agent import utils
from volttron.platform.keystore import KeyStore, KnownHostsStore
from volttron.platform.vip.agent import Agent
from volttron.platform.vip.agent.connection import Connection

utils.setup_logging()
_log = logging.getLogger(__name__)

host_store = KnownHostsStore()


def get_known_host_serverkey(vip_address):
    return host_store.serverkey(vip_address)


def get_server_keys():
    try:
        # attempt to read server's keys. Should be used only by multiplatform connection and tests
        # If agents such as forwarder attempt this in secure mode this will throw access violation exception
        ks = KeyStore()
    except IOError as e:
        raise RuntimeError("Exception accessing server keystore. Agents must use agent's public and private key"
                           "to build dynamic agents when running in secure mode. Exception:{}".format(e))

    return ks.public, ks.secret


def build_connection(identity, peer='', address=get_address(),
                     publickey=None, secretkey=None, message_bus=None, **kwargs):
    if publickey is None or secretkey is None:
        publickey, secretkey = get_server_keys(publickey, secretkey)

    cn = Connection(address=address, identity=identity, peer=peer,
                    publickey=publickey, secretkey=secretkey, message_bus=message_bus, **kwargs)
    return cn


def build_agent(address=get_address(), identity=None, publickey=None,
                secretkey=None, timeout=10, serverkey=None,
                agent_class=Agent, volttron_central_address=None,
                volttron_central_instance_name=None, **kwargs):
    """ Builds a dynamic agent connected to the specifiedd address.

    All key parameters should have been encoded with
    :py:meth:`volttron.platform.vip.socket.encode_key`

    :param str address: VIP address to connect to
    :param str identity: Agent's identity
    :param str publickey: Agent's Base64-encoded CURVE public key
    :param str secretkey: Agent's Base64-encoded CURVE secret key
    :param str serverkey: Server's Base64-encoded CURVE public key
    :param class agent_class: Class to use for creating the instance
    :param int timeout: Seconds to wait for agent to start
    :param kwargs: Any Agent specific parameters
    :return: an agent based upon agent_class that has been started
    :rtype: agent_class
    """
    # if not serverkey:
    #     serverkey = get_known_host_serverkey(address)

    # This is a fix allows the connect to message bus to be different than
    # the one that is currently running.
    if publickey is None or secretkey is None:
        publickey, secretkey = get_server_keys()
    try:
        message_bus = kwargs.pop('message_bus')
    except KeyError:
        message_bus = os.environ.get('MESSAGEBUS', 'zmq')

    try:
        enable_store = kwargs.pop('enable_store')
    except KeyError:
        enable_store = False

    agent = agent_class(address=address, identity=identity, publickey=publickey,
                        secretkey=secretkey, serverkey=serverkey, volttron_central_address=volttron_central_address,
                        volttron_central_instance_name=volttron_central_instance_name,
                        message_bus=message_bus, enable_store=enable_store, **kwargs)
    event = gevent.event.Event()
    gevent.spawn(agent.core.run, event)
    with gevent.Timeout(timeout):
        event.wait()
    return agent
