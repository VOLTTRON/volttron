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
import os
import requests
import urlparse
import weakref

from .base import SubsystemBase

import json
from volttron.platform.agent.known_identities import AUTH
from volttron.platform.agent.utils import get_platform_instance_name, get_fq_identity, get_messagebus
from volttron.platform.certs import Certs
from volttron.platform.jsonrpc import RemoteError
from volttron.utils.rmq_config_params import RMQConfig
from volttron.platform.keystore import KeyStore


"""
The auth subsystem allows an agent to quickly query authorization state
(e.g., which capabilities each user has been granted).
"""

__docformat__ = 'reStructuredText'
__version__ = '1.1'

_log = logging.getLogger(__name__)


class Auth(SubsystemBase):
    def __init__(self, owner, core, rpc):
        self._owner = owner
        self._core = weakref.ref(core)
        self._rpc = weakref.ref(rpc)
        self._user_to_capabilities = {}
        self._dirty = True
        self._csr_certs = dict()
        def onsetup(sender, **kwargs):
            rpc.export(self._update_capabilities, 'auth.update')

        core.onsetup.connect(onsetup, self)

    def connect_remote_platform(self, address, server_key=None, remote_bus_type=None, agent_class=None):
        from volttron.platform.vip.agent.utils import build_agent
        from volttron.platform.web import DiscoveryInfo
        from volttron.platform.vip.agent import Agent
        from volttron.platform.web import DiscoveryError

        if agent_class is None:
            agent_class = Agent

        parsed_address = urlparse.urlparse(address)

        value = None
        if parsed_address.scheme in ('https', 'http'):
            try:
                # We need to discover which type of bus is at the other end.
                info = DiscoveryInfo.request_discovery_info(address)

                remote_identity = "{}.{}.{}".format(info.instance_name,
                                                    get_platform_instance_name(),
                                                    self._core().identity)

                if info.messagebus_type == 'rmq' and get_messagebus() == 'zmq':
                    ValueError("ZMQ -> RMQ connection not supported at this time.")

                # If this is present we can assume we are going to connect to rabbit
                if info.messagebus_type == 'rmq':

                    # Discovery info for external platform
                    value = self.request_cert(address)

                    _log.debug("RESPONSE VALUE WAS: {}".format(value))
                    if not isinstance(value, tuple):
                        info = DiscoveryInfo.request_discovery_info(address)
                        remote_rmq_user = remote_identity
                        remote_rmq_address = self._core().rmq_mgmt.build_remote_connection_param(
                            remote_rmq_user,
                            info.rmq_address)
                        
                        value = build_agent(identity=remote_rmq_user,
                                            address=remote_rmq_address,
                                            instance_name=info.instance_name)

                else:
                    # TODO: cache the connection so we don't always have to ping
                    #       the server to connect.

                    # This branch happens when the message bus is not the same note
                    # this writes to the agent-data directory of this agent if the agent
                    # is installed.
                    if get_messagebus() == 'rmq':
                        if not os.path.exists("keystore.json"):
                            with open("keystore.json", 'w') as fp:
                                fp.write(json.dumps(KeyStore.generate_keypair_dict()))

                        with open("keystore.json") as fp:
                            keypair = json.loads(fp.read())

                    value = build_agent(agent_class=agent_class,
                                        identity=remote_identity,
                                        serverkey=info.serverkey,
                                        publickey=keypair.get('publickey'),
                                        secretkey=keypair.get('secretekey'),
                                        message_bus='zmq',
                                        address=info.rmq_address)
            except DiscoveryError:
                value = dict(status='UNKNOWN',
                             message="Couldn't connect to {} or incorrect response returned".format(address))

        return value

    def request_cert(self, csr_server, discovery_info=None):
        """ Get a signed csr from the csr_server endpoint

        This method will create a csr request that is going to be sent to the
        signing server.

        :param csr_server: the http(s) location of the server to connect to.
        :return:
        """
        from volttron.platform.web import DiscoveryInfo
        config = RMQConfig()

        info = discovery_info
        if info is None:
            info = DiscoveryInfo.request_discovery_info(csr_server)

        certs = Certs()
        csr_request = certs.create_csr(self._core().identity, info.instance_name)
        # The csr request requires the fully qualified identity that is
        # going to be connected to the external instance.
        #
        # The remote instance id is the instance name of the remote platform
        # concatenated with the identity of the local fully quallified identity.
        remote_cert_name = "{}.{}".format(info.instance_name,
                                          get_fq_identity(self._core().identity))
        remote_ca_name = info.instance_name+"_ca"

        # if certs.cert_exists(remote_cert_name, True):
        #     return certs.cert(remote_cert_name, True)

        json_request = dict(
            csr=csr_request,
            identity=remote_cert_name, # get_platform_instance_name()+"."+self._core().identity,
            hostname=config.hostname
        )
        response = requests.post(csr_server+"/csr/request_new",
                                 json=json.dumps(json_request),
                                 verify=False)

        _log.debug("The response: {}".format(response))
        # from pprint import pprint
        # pprint(response.json())
        j = response.json()
        status = j.get('status')
        cert = j.get('cert')
        message = j.get('message', '')

        if status == 'SUCCESSFUL' or status == 'APPROVED':
            certs.save_remote_info(get_fq_identity(self._core().identity),
                                   remote_cert_name, cert,
                                   remote_ca_name,
                                   info.rmq_ca_cert)

        elif status == 'PENDING':
            _log.debug("Pending CSR request for {}".format(remote_cert_name))
        elif status == 'DENIAL':
            print("Woops")
        elif status == 'ERROR':
            err = "Error retrieving certificate from {}\n".format(
                config.hostname)
            err += "{}".format(message)
            raise ValueError(err)
        else:  # No resposne
            return None

        certfile = certs.cert_file(remote_cert_name, remote=True)

        if certs.cert_exists(remote_cert_name, remote=True):
            return certfile
        else:
            return status, message

    def _fetch_capabilities(self):
        while self._dirty:
            self._dirty = False
            try:
                self._user_to_capabilities = self._rpc().call(AUTH,
                    'get_user_to_capabilities').get(timeout=10)
            except RemoteError:
                self._dirty = True

    def get_capabilities(self, user_id):
        """Gets capabilities for a given user.

        :param user_id: user id field from VOLTTRON Interconnect Protocol
        :type user_id: str
        :returns: list of capabilities
        :rtype: list
        """
        self._fetch_capabilities()
        return self._user_to_capabilities.get(user_id, [])

    def _update_capabilities(self, user_to_capabilities):
        identity = bytes(self._rpc().context.vip_message.peer)
        if identity == AUTH:
            self._user_to_capabilities = user_to_capabilities
            self._dirty = True

