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
import os
import grequests

from urllib.parse import urlparse
import weakref

from .base import SubsystemBase

from volttron.platform import jsonapi
from volttron.platform.agent.known_identities import AUTH
from volttron.platform.keystore import KnownHostsStore
from volttron.platform.agent.utils import get_platform_instance_name, get_fq_identity, get_messagebus
from volttron.platform.certs import Certs
from volttron.platform.jsonrpc import RemoteError
from volttron.utils.rmq_config_params import RMQConfig
from volttron.platform.keystore import KeyStore
from volttron.platform.vip.agent.subsystems.health import BAD_STATUS, Status

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

    def connect_remote_platform(self, address, serverkey=None, agent_class=None):
        """
        Atempts to connect to a remote platform to exchange data.

        address must start with http, https, tcp, ampq, or ampqs or a ValueError will be
        raised

        If this function is successful it will return an instance of the `agent_class`
        parameter if not then this function will return None.

        If the address parameter begins with http or https
        TODO: use the known host functionality here
        the agent will attempt to use Discovery to find the values associated with it.

        Discovery should return either an rmq-address or a vip-address or both.  In
        that situation the connection will be made using zmq.  In the event that
        fails then rmq will be tried.  If both fail then None is returned from this
        function.

        """
        from volttron.platform.vip.agent.utils import build_agent
        from volttron.platform.web import DiscoveryInfo
        from volttron.platform.vip.agent import Agent
        from volttron.platform.web import DiscoveryError

        if agent_class is None:
            agent_class = Agent

        parsed_address = urlparse(address)
        _log.debug("Begining auth.connect_remote_platform: {}".format(address))

        value = None
        if parsed_address.scheme == 'tcp':
            # ZMQ connection
            hosts = KnownHostsStore()
            temp_serverkey = hosts.serverkey(address)
            if not temp_serverkey:
                _log.info("Destination serverkey not found in known hosts file, using config")
                destination_serverkey = serverkey
            elif not serverkey:
                destination_serverkey = temp_serverkey
            else:
                if temp_serverkey != serverkey:
                    raise ValueError("server_key passed and known hosts serverkey do not match!")
                destination_serverkey = serverkey

            publickey, secretkey = self._core().publickey, self._core().secretkey
            _log.debug("Connecting using: {}".format(get_fq_identity(self._core().identity)))

            value = build_agent(agent_class=agent_class,
                                identity=get_fq_identity(self._core().identity),
                                serverkey=destination_serverkey,
                                publickey=publickey,
                                secretkey=secretkey,
                                message_bus='zmq',
                                address=address)
        elif parsed_address.scheme in ('https', 'http'):
            try:
                # TODO: Use known host instead of looking up for discovery info if possible.

                # We need to discover which type of bus is at the other end.
                info = DiscoveryInfo.request_discovery_info(address)

                remote_identity = "{}.{}.{}".format(info.instance_name,
                                                    get_platform_instance_name(),
                                                    self._core().identity)
                # if the current message bus is zmq then we need
                # to connect a zmq on the remote, whether that be the
                # rmq router or proxy.  Also note that we are using the fully qualified
                # version of the identity because there will be conflicts if
                # volttron central has more than one platform.agent connecting
                if get_messagebus() == 'zmq':
                    if not info.vip_address or not info.serverkey:
                        err = "Discovery from {} did not return serverkey and/or vip_address".format(address)
                        raise ValueError(err)

                    _log.debug("Connecting using: {}".format(get_fq_identity(self._core().identity)))

                    # use fully qualified identity
                    value = build_agent(identity=get_fq_identity(self._core().identity),
                                        address=info.vip_address,
                                        serverkey=info.serverkey,
                                        secretkey=self._core().secretkey,
                                        publickey=self._core().publickey,
                                        agent_class=agent_class)

                else:  # we are on rmq messagebus

                    # This is if both remote and local are rmq message buses.
                    if info.messagebus_type == 'rmq':
                        _log.debug("Both remote and local are rmq messagebus.")
                        fqid_local = get_fq_identity(self._core().identity)
                        # Discovery info for external platform
                        response = self.request_cert(address, fqid_local, info)

                        if response is None:
                            _log.error("there was no response from the server")
                            value = None
                        elif isinstance(response, tuple):
                            if response[0] == 'PENDING':
                                _log.info("Waiting for administrator to accept a CSR request.")
                            value = None
                        # elif isinstance(response, dict):
                        #     response
                        elif os.path.exists(response):
                            # info = DiscoveryInfo.request_discovery_info(address)
                            # From the remote platforms perspective the remote user name is
                            #   remoteinstance.localinstance.identity, this is what we must
                            #   pass to the build_remote_connection_params for a successful

                            remote_rmq_user = get_fq_identity(fqid_local, info.instance_name)
                            _log.debug("REMOTE RMQ USER IS: {}".format(remote_rmq_user))
                            remote_rmq_address = self._core().rmq_mgmt.build_remote_connection_param(
                                remote_rmq_user,
                                info.rmq_address)
                            _log.debug("Building dynamic agent using remote_rmq_address: {}".format(
                                remote_rmq_address))

                            value = build_agent(identity=fqid_local,
                                                address=remote_rmq_address,
                                                instance_name=info.instance_name,
                                                message_bus='rmq',
                                                enable_store=False,
                                                agent_class=agent_class)
                        else:
                            raise ValueError("Unknown path through discovery process!")

                    else:
                        # TODO: cache the connection so we don't always have to ping
                        #       the server to connect.

                        # This branch happens when the message bus is not the same note
                        # this writes to the agent-data directory of this agent if the agent
                        # is installed.
                        if get_messagebus() == 'rmq':
                            if not os.path.exists("keystore.json"):
                                with open("keystore.json", 'w') as fp:
                                    fp.write(jsonapi.dumps(KeyStore.generate_keypair_dict()))

                            with open("keystore.json") as fp:
                                keypair = jsonapi.loads(fp.read())

                        value = build_agent(agent_class=agent_class,
                                            identity=remote_identity,
                                            serverkey=info.serverkey,
                                            publickey=keypair.get('publickey'),
                                            secretkey=keypair.get('secretekey'),
                                            message_bus='zmq',
                                            address=info.vip_address)
            except DiscoveryError:
                _log.error("Couldn't connect to {} or incorrect response returned response was {}".format(address, value))

        else:
            raise ValueError("Invalid configuration found the address: {} has an invalid scheme".format(address))

        return value

    def request_cert(self, csr_server, fully_qualified_local_identity, discovery_info):
        """ Get a signed csr from the csr_server endpoint

        This method will create a csr request that is going to be sent to the
        signing server.

        :param csr_server: the http(s) location of the server to connect to.
        :return:
        """

        if get_messagebus() != 'rmq':
            raise ValueError("Only can create csr for rabbitmq based platform in ssl mode.")

        # from volttron.platform.web import DiscoveryInfo
        config = RMQConfig()

        if not config.is_ssl:
            raise ValueError("Only can create csr for rabbitmq based platform in ssl mode.")

        # info = discovery_info
        # if info is None:
        #     info = DiscoveryInfo.request_discovery_info(csr_server)

        certs = Certs()
        csr_request = certs.create_csr(fully_qualified_local_identity, discovery_info.instance_name)
        # The csr request requires the fully qualified identity that is
        # going to be connected to the external instance.
        #
        # The remote instance id is the instance name of the remote platform
        # concatenated with the identity of the local fully quallified identity.
        remote_cert_name = "{}.{}".format(discovery_info.instance_name, fully_qualified_local_identity)
        remote_ca_name = discovery_info.instance_name + "_ca"

        # if certs.cert_exists(remote_cert_name, True):
        #     return certs.cert(remote_cert_name, True)

        json_request = dict(
            csr=csr_request.decode("utf-8"),
            identity=remote_cert_name,  # get_platform_instance_name()+"."+self._core().identity,
            hostname=config.hostname
        )
        request = grequests.post(csr_server + "/csr/request_new",
                                 json=jsonapi.dumps(json_request),
                                 verify=False)
        response = grequests.map([request])

        if response and isinstance(response, list):
            response[0].raise_for_status()
        response = response[0]
        # response = requests.post(csr_server + "/csr/request_new",
        #                          json=jsonapi.dumps(json_request),
        #                          verify=False)

        _log.debug("The response: {}".format(response))

        j = response.json()
        status = j.get('status')
        cert = j.get('cert')
        message = j.get('message', '')

        if status == 'SUCCESSFUL' or status == 'APPROVED':
            certs.save_remote_info(fully_qualified_local_identity,
                                   remote_cert_name, cert.encode("utf-8"),
                                   remote_ca_name,
                                   discovery_info.rmq_ca_cert.encode("utf-8"))

        elif status == 'PENDING':
            _log.debug("Pending CSR request for {}".format(remote_cert_name))
        elif status == 'DENIED':
            _log.error("Denied from remote machine.  Shutting down agent.")
            status = Status.build(BAD_STATUS,
                                  context="Administrator denied remote connection.  Shutting down")
            self._owner.vip.health.set_status(status.status, status.context)
            self._owner.vip.health.send_alert(self._core().identity+"_DENIED", status)
            self._core().stop()
            return None
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
                _log.debug("self. user to cap {}".format(self._user_to_capabilities))
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
        identity = self._rpc().context.vip_message.peer
        if identity == AUTH:
            self._user_to_capabilities = user_to_capabilities
            self._dirty = True

