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
import gevent

import weakref

from volttron.platform.agent.known_identities import (
    AUTH,
    PLATFORM_WEB,
    CONTROL,
    KEY_DISCOVERY,
    CONFIGURATION_STORE,
    CONTROL_CONNECTION,
    PLATFORM_HEALTH,
)

from volttron.platform.jsonrpc import RemoteError, MethodNotFound

from .base import SubsystemBase

"""
The auth subsystem allows an agent to quickly query authorization state
(e.g., which capabilities each user has been granted).
"""

__docformat__ = "reStructuredText"
__version__ = "1.1"

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
            rpc.export(self._update_capabilities, "auth.update")
            rpc.export(
                self.get_rpc_authorizations, "auth.get_rpc_authorizations"
            )
            rpc.export(
                self.get_all_rpc_authorizations,
                "auth.get_all_rpc_authorizations",
            )
            rpc.export(
                self.set_rpc_authorizations, "auth.set_rpc_authorizations"
            )
            rpc.export(
                self.set_multiple_rpc_authorizations,
                "auth.set_multiple_rpc_authorizations",
            )
            rpc.allow(
                "auth.set_rpc_authorizations", "modify_rpc_method_allowance"
            )
            rpc.allow(
                "auth.set_multiple_rpc_authorizations",
                "modify_rpc_method_allowance",
            )

            # Do not update platform agents on start-up, which can cause
            # trouble.
            ignored_ids = [
                AUTH,
                PLATFORM_WEB,
                CONTROL,
                KEY_DISCOVERY,
                CONFIGURATION_STORE,
                CONTROL_CONNECTION,
                PLATFORM_HEALTH,
                "pubsub",
            ]
            if core.identity not in ignored_ids:
                gevent.spawn_later(1, self.update_rpc_method_capabilities)

        core.onsetup.connect(onsetup, self)

    def _fetch_capabilities(self):
        while self._dirty:
            self._dirty = False
            try:
                self._user_to_capabilities = (
                    self._rpc()
                    .call(AUTH, "get_user_to_capabilities")
                    .get(timeout=10)
                )
                _log.debug("self. user to cap %s", self._user_to_capabilities)
            except RemoteError:
                self._dirty = True

    def get_capabilities(self, user_id):
        """
        Gets capabilities for a given user.

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
        """
        Returns a list of agent's RPC exported methods

        :returns: agent's list of RPC exported methods
        :rtype: list
        """
        rpc_exports = self._rpc().get_exports()
        return rpc_exports

    def get_all_rpc_authorizations(self):
        """
        Returns a dict of methods with authorized capabilities for the
        provided method
        These dynamic changes are recorded and handled by the auth file.
        This method's primary purpose is
        to collect the initial condition of all method's allowed capabilites.

        :returns: dict of rpc methods with list of capabilities that will be
        able to access the method, exclusively
        :rtype: dict
        """
        rpc_methods = self.get_rpc_exports()
        rpc_method_authorizations = {}
        for method in rpc_methods:
            if len(method.split(".")) > 1:
                pass
            else:
                rpc_method_authorizations[method] = self.get_rpc_authorizations(
                    method
                )
        return rpc_method_authorizations.copy()

    def get_rpc_authorizations(self, method_str):
        """
        Returns a list of authorized capabilities for the provided method
        This list will only include authorized capabilities included in the
        RPC.allow() decorator.
        Any capabilities added dynamically later or by calling RPC.allow()
        in-line will not be included.
        These dynamic changes are recorded and handled by the auth file.
        This method's primary purpose is
        to collect the initial condition of the method's allowed capabilites.

        :param method_str: name of method to get list of allowed capabilities
        :type method_str: str
        :returns: list of capabilities that will be able to access the
        method, exclusively
        :rtype: list
        """
        # Prevent getting of subsystem methods, noted with a '.' in the RPC
        # export name.
        if len(method_str.split(".")) > 1:
            _log.error(
                "Illegal operation. Attempt to get authorization on "
                "subsystem method: %s",
                method_str,
            )
            return []
        try:
            method = getattr(self._owner, method_str)
        except AttributeError as err:
            _log.warning(f"{err}")
            return []
        try:
            authorized_capabilities = list(
                method._annotations["rpc.allow_capabilities"]
            )
        except KeyError:
            authorized_capabilities = []
        return authorized_capabilities.copy()

    def set_multiple_rpc_authorizations(self, rpc_authorizations):
        """
        Sets authorized capabilities for multiple RPC exported methods.

        :param rpc_authorizations: dictionary of {method: [authorized
        capabilities]}
        :type rpc_authorizations: dict
        """
        for method in rpc_authorizations:
            self.set_rpc_authorizations(method, rpc_authorizations[method])

    def set_rpc_authorizations(self, method_str, capabilities):
        """
        Sets authorized capabilities for an RPC exported method.

        :param method_str: name of method to modify
        :type method_str: str
        :param capabilities: list of capabilities that will be able to
        access the method, exclusively
        :type capabilities: list
        """
        # Prevent setting on subsystem methods, noted with a '.' in the RPC
        # export name.
        if len(method_str.split(".")) > 1:
            _log.error(
                "Illegal operation. Attempt to set authorization on "
                "subsystem method: %s",
                method_str,
            )
            return
        try:
            method = getattr(self._owner, method_str)
        except AttributeError as err:
            _log.warning(f"{err}")
            return
        _log.debug(
            f"Setting authorized capabilities: {capabilities} for method: "
            f"{method_str}"
        )
        self._rpc().allow(method, capabilities)
        _log.debug(
            f"Authorized capabilities: {capabilities} for meth"
            f"od: "
            f"{method_str} set"
        )

    def update_rpc_method_capabilities(self):
        """
        Updates the rpc_method_authorizations field in the auth entry
        for this agent by sending rpc_method_authorizations to AuthService
        on startup.
        If there are any modifications to the agent from the auth entry,
        it will update
        the agent's rpc_method_authorizations.

        :return: None
        """
        rpc_method_authorizations = {}
        rpc_methods = self.get_rpc_exports()
        for method in rpc_methods:
            if len(method.split(".")) > 1:
                pass
            else:
                rpc_method_authorizations[method] = self.get_rpc_authorizations(
                    method
                )
        try:
            from volttron.platform.agent.utils import load_platform_config
            local_instance_name = load_platform_config().get("instance-name")
            # if using ipc connection or if agent's connecting to same instance as the local instance update rpc auth
            # if not agent is connecting to remote platform
            if self._core().address.startswith("ipc") or local_instance_name == self._core().instance_name:
                updated_rpc_authorizations = (
                    self._rpc()
                    .call(
                        AUTH,
                        "update_id_rpc_authorizations",
                        self._core().identity,
                        rpc_method_authorizations,
                    )
                    .get(timeout=4)
                )
            else:
                _log.info(
                    f"Skipping updating rpc auth capabilities for agent "
                    f"{self._core().identity} connecting to remote address: {self._core().address} ")
                updated_rpc_authorizations = None
        except gevent.timeout.Timeout:
            updated_rpc_authorizations = None
            _log.warning(f"update_id_rpc_authorization rpc call timed out for {self._core().identity}   {rpc_method_authorizations}")
        except MethodNotFound:
            _log.warning("update_id_rpc_authorization method is missing from "
                         "AuthService! The VOLTTRON Instance you are "
                         "attempting to connect to is to old to support "
                         "dynamic RPC authorizations.")
            return
        except Exception as e:
            updated_rpc_authorizations = None
            _log.exception(f"Exception when calling rpc method update_id_rpc_authorizations for identity: "
                           f"{self._core().identity}  Exception:{e}")
        if updated_rpc_authorizations is None:
            _log.warning(
                f"Auth entry not found for {self._core().identity}: "
                f"rpc_method_authorizations not updated. If this agent "
                f"does have an auth entry, verify that the 'identity' field "
                f"has been included in the auth entry. This should be set to "
                f"the identity of the agent"
            )
            return
        if rpc_method_authorizations != updated_rpc_authorizations:
            for method in updated_rpc_authorizations:
                self.set_rpc_authorizations(
                    method, updated_rpc_authorizations[method]
                )
