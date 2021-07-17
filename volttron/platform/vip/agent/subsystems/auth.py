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
import os
import gevent
import grequests

from urllib.parse import urlparse
import weakref

from .base import SubsystemBase

from volttron.platform import jsonapi
from volttron.platform.agent.known_identities import AUTH, PLATFORM_WEB, CONTROL, KEY_DISCOVERY, CONFIGURATION_STORE, \
    CONTROL_CONNECTION, PLATFORM_HEALTH
from volttron.platform.keystore import KnownHostsStore
from volttron.platform.agent.utils import get_platform_instance_name, get_fq_identity, get_messagebus
from volttron.platform.certs import Certs
from volttron.platform.jsonrpc import RemoteError
from volttron.utils.rmq_config_params import RMQConfig
from volttron.platform.keystore import KeyStore
from volttron.platform.vip.agent.subsystems.health import BAD_STATUS, Status
from volttron.platform import get_home

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
        self.remote_certs_dir = None

        def onsetup(sender, **kwargs):
            rpc.export(self._update_capabilities, 'auth.update')
            rpc.export(self.get_rpc_authorizations, "auth.get_rpc_authorizations")
            rpc.export(self.get_all_rpc_authorizations, "auth.get_all_rpc_authorizations")
            rpc.export(self.set_rpc_authorizations, "auth.set_rpc_authorizations")
            rpc.export(self.set_multiple_rpc_authorizations, "auth.set_multiple_rpc_authorizations")
            rpc.allow("auth.set_rpc_authorizations", 'modify_rpc_method_allowance')
            rpc.allow("auth.set_multiple_rpc_authorizations", 'modify_rpc_method_allowance')

            # Do not update platform agents on start-up, which can cause trouble.
            ignored_ids = [AUTH, PLATFORM_WEB, CONTROL, KEY_DISCOVERY, CONFIGURATION_STORE,
                           CONTROL_CONNECTION, PLATFORM_HEALTH, 'pubsub']
            if core.identity not in ignored_ids:
                gevent.spawn_later(1, self.update_rpc_method_capabilities)
        core.onsetup.connect(onsetup, self)

    def connect_remote_platform(self, address, serverkey=None, agent_class=None):
        """
        Agent atempts to connect to a remote platform to exchange data.

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
        from volttron.platform.vip.agent import Agent

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
            from volttron.platform.web import DiscoveryInfo
            from volttron.platform.web import DiscoveryError
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

                        #Check if we already have the cert, if so use it instead of requesting cert again
                        remote_certs_dir = self.get_remote_certs_dir()
                        remote_cert_name = "{}.{}".format(info.instance_name, fqid_local)
                        certfile = os.path.join(remote_certs_dir, remote_cert_name + ".crt")
                        if os.path.exists(certfile):
                            response = certfile
                        else:
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
                                info.rmq_address,
                                ssl_auth=True,
                                cert_dir=self.get_remote_certs_dir())

                            value = build_agent(identity=fqid_local,
                                                address=remote_rmq_address,
                                                instance_name=info.instance_name,
                                                publickey=self._core().publickey,
                                                secretkey=self._core().secretkey,
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
        remote_certs_dir = self.get_remote_certs_dir()
        if status == 'SUCCESSFUL' or status == 'APPROVED':
            certs.save_agent_remote_info(remote_certs_dir,
                                         fully_qualified_local_identity,
                                         remote_cert_name, cert.encode("utf-8"),
                                         remote_ca_name,
                                         discovery_info.rmq_ca_cert.encode("utf-8"))
            os.environ['REQUESTS_CA_BUNDLE'] = os.path.join(remote_certs_dir, "requests_ca_bundle")
            _log.debug("Set os.environ requests ca bundle to {}".format(os.environ['REQUESTS_CA_BUNDLE']))
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

        certfile = os.path.join(remote_certs_dir, remote_cert_name + ".crt")
        if os.path.exists(certfile):
            return certfile
        else:
            return status, message

    def get_remote_certs_dir(self):
        if not self.remote_certs_dir:
            install_dir = os.path.join(get_home(), "agents", self._core().agent_uuid)
            files = os.listdir(install_dir)
            for f in files:
                agent_dir = os.path.join(install_dir, f)
                if os.path.isdir(agent_dir):
                    break  # found
            sub_dirs = os.listdir(agent_dir)
            for d in sub_dirs:
                d_path = os.path.join(agent_dir, d)
                if os.path.isdir(d_path) and d.endswith("agent-data"):
                    self.remote_certs_dir = d_path
        return self.remote_certs_dir

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

    def get_rpc_exports(self):
        """Returns a list of agent's RPC exported methods
        :returns: agent's list of RPC exported methods
        :rtype: list
        """
        rpc_exports = list(self._rpc()._exports)
        return rpc_exports

    def get_all_rpc_authorizations(self):
        """Returns a dict of methods with authorized capabilities for the provided method
        These dynamic changes are recorded and handled by the auth file. This method's primary purpose is
        to collect the initial condition of all method's allowed capabilites.

        :returns: dict of rpc methods with list of capabilities that will be able to access the method, exclusively
        :rtype: dict
        """
        rpc_methods = self.get_rpc_exports()
        rpc_method_authorizations = {}
        for method in rpc_methods:
            if len(method.split(".")) > 1:
                pass
            else:
                rpc_method_authorizations[method] = self.get_rpc_authorizations(method)
        _log.debug(f"get_all_rpc_authorizations finished correctly!")
        return rpc_method_authorizations.copy()

    def get_rpc_authorizations(self, method_str):
        """Returns a list of authorized capabilities for the provided method
        This list will only include authorized capabilities included in the RPC.allow() decorator.
        Any capabilities added dynamically later or by calling RPC.allow() in-line will not be included.
        These dynamic changes are recorded and handled by the auth file. This method's primary purpose is
        to collect the initial condition of the method's allowed capabilites.

        :param method_str: name of method to get list of allowed capabilities
        :type method_str: str
        :returns: list of capabilities that will be able to access the method, exclusively
        :rtype: list
        """
        # Prevent getting of subsystem methods, noted with a '.' in the RPC export name.
        if len(method_str.split(".")) > 1:
            _log.error(f"Illegal operation. Attempt to get authorization on subsystem method: {method_str}")
            return []
        try:
            method = getattr(self._owner, method_str)
        except AttributeError as err:
            _log.warning(f"{err}")
            return []
        try:
            authorized_capabilities = list(method._annotations['rpc.allow_capabilities'])
        except KeyError:
            authorized_capabilities = []
        except Exception as e:
            _log.error(e)
            authorized_capabilities = []
        return authorized_capabilities.copy()

    def set_multiple_rpc_authorizations(self, rpc_authorizations):
        """Sets authorized capabilites for multiple RPC exported methods.

        :param rpc_authorizations: dictionary of {method: [authorized capabilities]}
        :type rpc_authorizations: dict
        """
        for method in rpc_authorizations:
            self.set_rpc_authorizations(method, rpc_authorizations[method])

    def set_rpc_authorizations(self, method_str, capabilities):
        """Sets authorized capabilites for an RPC exported method.

        :param method_str: name of method to modify
        :type method_str: str
        :param capabilities: list of capabilities that will be able to access the method, exclusively
        :type capabilities: list
        """
        # Prevent setting on subsystem methods, noted with a '.' in the RPC export name.
        if len(method_str.split(".")) > 1:
            _log.error(f"Illegal operation. Attempt to set authorization on subsystem method: {method_str}")
            return
        try:
            method = getattr(self._owner, method_str)
        except AttributeError as err:
            _log.warning(f"{err}")
            return
        _log.debug(f"Setting authorized capabilities: {capabilities} for method: {method_str}")
        self._rpc().allow(method, capabilities)
        _log.debug(f"Authorized capabilities: {capabilities} for method: {method_str} set")

    def update_rpc_method_capabilities(self):
        """
        Updates the rpc_method_authorizations field in the auth entry
        for this agent by sending rpc_method_authorizations to AuthService on startup.
        If there are any modifications to the agent from the auth entry, it will update
        the agent's rpc_method_authorizations.
        :return: None
        """
        rpc_method_authorizations = {}
        rpc_methods = self.get_rpc_exports()
        for method in rpc_methods:
            if len(method.split(".")) > 1:
                pass
            else:
                rpc_method_authorizations[method] = self.get_rpc_authorizations(method)
        updated_rpc_method_authorizations = self._rpc().call(AUTH, 'update_auth_entry_rpc_method_authorizations',
                         self._core().identity, rpc_method_authorizations).get(timeout=4)
        if updated_rpc_method_authorizations is None:
            _log.error(f"Auth entry not found for {self._core().identity}: rpc_method_authorizations not updated.")
            return
        if rpc_method_authorizations != updated_rpc_method_authorizations:
            for method in updated_rpc_method_authorizations:
                self.set_rpc_authorizations(method, updated_rpc_method_authorizations[method])
