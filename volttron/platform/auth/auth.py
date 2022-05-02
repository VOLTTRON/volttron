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
import copy

import gevent
import gevent.core
from gevent.fileobject import FileObject

from volttron.platform.agent.known_identities import (
    CONTROL_CONNECTION,
    PROCESS_IDENTITIES,
)

from volttron.platform.auth.auth_utils import load_user
from volttron.platform.auth.auth_entry import AuthEntry
from volttron.platform.auth.auth_file import AuthFile

from volttron.platform.jsonrpc import RemoteError
from volttron.platform.vip.agent.errors import Unreachable
from volttron.platform.vip.pubsubservice import ProtectedPubSubTopics
from volttron.platform.agent.utils import (
    create_file_if_missing,
    watch_file,
    get_messagebus,
)
from volttron.platform.vip.agent import Agent, Core, RPC


_log = logging.getLogger(__name__)

# ZMQAuthService(AuthService)
# self.authentication_server = ZMQServerAuthentication(self.vip, self.core, self.aip)
# self.authorization_server = ZMQAuthorization(self.auth_file)
# RMQAuthService(AuthService)
# self.authentication_server = ZMQServerAuthentication(self.vip, self.core, self.aip)
# self.authorization_server = ZMQAuthorization(self.auth_file)

class AuthService(Agent):
    def __init__(
            self,
            auth_file,
            protected_topics_file,
            setup_mode,
            aip,
            *args,
            **kwargs
    ):
        """Initializes AuthService, and prepares AuthFile."""
        self.allow_any = kwargs.pop("allow_any", False)
        self.is_zap_required = kwargs.pop('zap_required', True)
        self.auth_protocol = kwargs.pop('auth_protocol', None)
        super(AuthService, self).__init__(*args, **kwargs)

        # This agent is started before the router so we need
        # to keep it from blocking.
        self.core.delay_running_event_set = False
        self.auth_file_path = os.path.abspath(auth_file)
        self.auth_file = AuthFile(self.auth_file_path)
        self.export_auth_file()
        self.can_update = False
        self.needs_rpc_update = False
        self.aip = aip
        self.zap_socket = None
        self._zap_greenlet = None
        self.auth_entries = []
        self._is_connected = False
        self._protected_topics_file = protected_topics_file
        self._protected_topics_file_path = os.path.abspath(
            protected_topics_file
        )
        self._protected_topics = {}
        self._protected_topics_for_rmq = ProtectedPubSubTopics()
        self._setup_mode = setup_mode
        self._auth_pending = []
        self._auth_denied = []
        self._auth_approved = []
        self.authentication_server = None
        self.authorization_server = None

    def export_auth_file(self):
        """
        Export all relevant AuthFile methods to external agents
        through AuthService
        :params: None
        :return: None
        """

        def auth_file_read():
            """
            Returns AuthFile data object
            :params: None
            :return: auth_data
            """
            return self.auth_file.auth_data

        def auth_file_add(entry):
            """
            Wrapper function to add entry to AuthFile
            :params: entry
            :return: None
            """ 
            self.auth_file.add(AuthEntry(**entry))

        def auth_file_update_by_index(auth_entry, index, is_allow=True):
            """
            Wrapper function to update entry in AuthFile
            :params: auth_entry, index, is_allow
            :return: None
            """
            self.auth_file.update_by_index(
                AuthEntry(**auth_entry), index, is_allow
            )

        self.vip.rpc.export(auth_file_read, "auth_file.read")
        self.vip.rpc.export(
            self.auth_file.find_by_credentials, "auth_file.find_by_credentials"
        )
        self.vip.rpc.export(auth_file_add, "auth_file.add")
        self.vip.rpc.export(
            auth_file_update_by_index, "auth_file.update_by_index"
        )
        self.vip.rpc.export(
            self.auth_file.remove_by_credentials,
            "auth_file.remove_by_credentials",
        )
        self.vip.rpc.export(
            self.auth_file.remove_by_index, "auth_file.remove_by_index"
        )
        self.vip.rpc.export(
            self.auth_file.remove_by_indices, "auth_file.remove_by_indices"
        )
        self.vip.rpc.export(self.auth_file.set_groups, "auth_file.set_groups")
        self.vip.rpc.export(self.auth_file.set_roles, "auth_file.set_roles")

    @Core.receiver("onsetup")
    def setup_authentication_server(self, sender, **kwargs):
        if self.allow_any:
            _log.warning("insecure permissive authentication enabled")
        self.read_auth_file()
        if get_messagebus() == "zmq":
            from volttron.platform.auth.auth_protocols.auth_zmq import ZMQAuthorization, ZMQServerAuthentication
            self.authentication_server = ZMQServerAuthentication(auth_service=self
                    # auth_vip=self.vip,
                    # auth_core=self.core,
                    # aip=self.aip,
                    # allow_any=self.allow_any,
                    # is_connected=self._is_connected,
                    # setup_mode=self._setup_mode,
                    # auth_file=self.auth_file,
                    # auth_entries=self.auth_entries,
                    # auth_pending=self._auth_pending,
                    # auth_approved=self._auth_approved,
                    # auth_denied=self._auth_denied
            )
            self.authorization_server = ZMQAuthorization(auth_service=self
                    # auth_core=self.core,
                    # is_connected=self._is_connected,
                    # auth_file=self.auth_file,
                    # auth_pending=self._auth_pending,
                    # auth_approved=self._auth_approved,
                    # auth_denied=self._auth_denied
            )
        else:
            from volttron.platform.auth.auth_protocols.auth_rmq import RMQAuthorization, RMQServerAuthentication
            self.authentication_server = RMQServerAuthentication(self.vip, self.core)
            self.authorization_server = RMQAuthorization(self.auth_file)
        self._read_protected_topics_file()
        self.core.spawn(watch_file, self.auth_file_path, self.read_auth_file)
        self.core.spawn(
            watch_file,
            self._protected_topics_file_path,
            self._read_protected_topics_file,
        )
        self.authentication_server.setup_authentication()

    @Core.receiver("onstart")
    def start_authentication_server(self, sender, **kwargs):
        self.authentication_server.handle_authentication(self._protected_topics)

    @Core.receiver("onstop")
    def stop_authentication_server(self, sender, **kwargs):
        self.authentication_server.stop_authentication()

    @Core.receiver("onfinish")
    def unbind_authentication_server(self, sender, **kwargs):
        self.authentication_server.unbind_authentication()

    # def _update_entries(self, entries=None, pending=None, approved=None, denied=None):
    #     if entries:
    #         self.auth_entries=self.authentication_server.auth_entries=self.authorization_server.auth_entries=entries
    #     if pending:
    #         self._auth_pending=self.authentication_server._auth_pending=self.authorization_server._auth_pending=pending
    #     if approved:
    #         self._auth_approved=self.authentication_server._auth_approved=self.authorization_server._auth_approved=approved
    #     if denied:
    #         self._auth_denied=self.authentication_server._auth_denied=self.authorization_server._auth_denied=denied

    @RPC.export
    def update_id_rpc_authorizations(self, identity, rpc_methods):
        """
        Update RPC methods for an auth entry. This is called by the subsystem
        on agent start-up to ensure that the agent's current rpc allowances are
        recorded with it's auth entry.
        :param identity: The agent's identity in the auth entry
        :param rpc_methods: The rpc methods to update in the format
            {rpc_method_name: [allowed_rpc_capability_1, ...]}
        :return: updated_rpc_methods or None
        """
        entries = self.auth_file.read_allow_entries()
        for entry in entries:
            if entry.identity == identity:
                updated_rpc_methods = {}
                # Only update auth_file if changed
                is_updated = False
                for method in rpc_methods:
                    updated_rpc_methods[method] = rpc_methods[method]
                    # Check if the rpc method exists in the auth file entry
                    if method not in entry.rpc_method_authorizations:
                        # Create it and set it to have the provided
                        # rpc capabilities
                        entry.rpc_method_authorizations[method] = rpc_methods[
                            method
                        ]
                        is_updated = True
                    # Check if the rpc method does not have any
                    # rpc capabilities
                    if not entry.rpc_method_authorizations[method]:
                        # Set it to have the provided rpc capabilities
                        entry.rpc_method_authorizations[method] = rpc_methods[
                            method
                        ]
                        is_updated = True
                    # Check if the rpc method's capabilities match
                    # what have been provided
                    if (
                            entry.rpc_method_authorizations[method]
                            != rpc_methods[method]
                    ):
                        # Update rpc_methods based on auth entries
                        updated_rpc_methods[
                            method
                        ] = entry.rpc_method_authorizations[method]
                # Update auth file if changed and return rpc_methods
                if is_updated:
                    self.auth_file.update_by_index(entry, entries.index(entry))
                return updated_rpc_methods
        return None

    def get_entry_authorizations(self, identity):
        """
        Gets all rpc_method_authorizations for an agent using RPC.
        :param identity: Agent identity in the auth file
        :return: rpc_method_authorizations
        """
        rpc_method_authorizations = {}
        try:
            rpc_method_authorizations = self.vip.rpc.call(
                identity, "auth.get_all_rpc_authorizations"
            ).get()
            _log.debug(f"RPC Methods are: {rpc_method_authorizations}")
        except Unreachable:
            _log.warning(
                f"{identity} "
                f"is unreachable while attempting to get rpc methods"
            )

        return rpc_method_authorizations

    def update_rpc_authorizations(self, entries):
        """
        Update allowed capabilities for an rpc method if it
        doesn't match what is in the auth file.
        :param entries: Entries read in from the auth file
        :return: None
        """
        for entry in entries:
            # Skip if core agent
            if (
                    entry.identity is not None
                    and entry.identity not in PROCESS_IDENTITIES
                    and entry.identity != CONTROL_CONNECTION
            ):
                # Collect all modified methods
                modified_methods = {}
                for method in entry.rpc_method_authorizations:
                    # Check if the rpc method does not have
                    # any rpc capabilities
                    if not entry.rpc_method_authorizations[method]:
                        # Do not need to update agent capabilities
                        # if no capabilities in auth file
                        continue
                    modified_methods[method] = entry.rpc_method_authorizations[
                        method
                    ]
                if modified_methods:
                    method_error = True
                    try:
                        self.vip.rpc.call(
                            entry.identity,
                            "auth.set_multiple_rpc_authorizations",
                            rpc_authorizations=modified_methods,
                        ).wait(timeout=4)
                        method_error = False
                    except gevent.Timeout:
                        _log.error(
                            f"{entry.identity} "
                            f"has timed out while attempting "
                            f"to update rpc_method_authorizations"
                        )
                        method_error = False
                    except RemoteError:
                        method_error = True

                    # One or more methods are invalid, need to iterate
                    if method_error:
                        for method in modified_methods:
                            try:
                                self.vip.rpc.call(
                                    entry.identity,
                                    "auth.set_rpc_authorizations",
                                    method_str=method,
                                    capabilities=
                                    entry.rpc_method_authorizations[
                                        method
                                    ],
                                )
                            except gevent.Timeout:
                                _log.error(
                                    f"{entry.identity} "
                                    f"has timed out while attempting "
                                    f"to update "
                                    f"rpc_method_authorizations"
                                )
                            except RemoteError:
                                _log.error(f"Method {method} does not exist.")

    @RPC.export
    def add_rpc_authorizations(self, identity, method, authorizations):
        """
        Adds authorizations to method in auth entry in auth file.

        :param identity: Agent identity in the auth file
        :param method: RPC exported method in the auth entry
        :param authorizations: Allowed capabilities to access the RPC exported
        method
        :return: None
        """
        if identity in PROCESS_IDENTITIES or identity == CONTROL_CONNECTION:
            _log.error(f"{identity} cannot be modified using this command!")
            return
        entries = copy.deepcopy(self.auth_file.read_allow_entries())
        for entry in entries:
            if entry.identity == identity:
                if method not in entry.rpc_method_authorizations:
                    entry.rpc_method_authorizations[method] = authorizations
                elif not entry.rpc_method_authorizations[method]:
                    entry.rpc_method_authorizations[method] = authorizations
                else:
                    entry.rpc_method_authorizations[method].extend(
                        [
                            rpc_auth
                            for rpc_auth in authorizations
                            if rpc_auth in authorizations
                            and rpc_auth
                            not in entry.rpc_method_authorizations[method]
                        ]
                    )
                self.auth_file.update_by_index(entry, entries.index(entry))
                return
        _log.error("Agent identity not found in auth file!")
        return

    @RPC.export
    def delete_rpc_authorizations(
            self,
            identity,
            method,
            denied_authorizations
    ):
        """
        Removes authorizations to method in auth entry in auth file.

        :param identity: Agent identity in the auth file
        :param method: RPC exported method in the auth entry
        :param denied_authorizations: Capabilities that can no longer access
        the RPC exported method
        :return: None
        """
        if identity in PROCESS_IDENTITIES or identity == CONTROL_CONNECTION:
            _log.error(f"{identity} cannot be modified using this command!")
            return
        entries = copy.deepcopy(self.auth_file.read_allow_entries())
        for entry in entries:
            if entry.identity == identity:
                if method not in entry.rpc_method_authorizations:
                    _log.error(
                        f"{entry.identity} does not have a method called "
                        f"{method}"
                    )
                elif not entry.rpc_method_authorizations[method]:
                    _log.error(
                        f"{entry.identity}.{method} does not have any "
                        f"authorized capabilities."
                    )
                else:
                    any_match = False
                    for rpc_auth in denied_authorizations:
                        if (
                                rpc_auth
                                not in entry.rpc_method_authorizations[method]
                        ):
                            _log.error(
                                f"{rpc_auth} is not an authorized capability "
                                f"for {method}"
                            )
                        else:
                            any_match = True
                    if any_match:
                        entry.rpc_method_authorizations[method] = [
                            rpc_auth
                            for rpc_auth in entry.rpc_method_authorizations[
                                method
                            ]
                            if rpc_auth not in denied_authorizations
                        ]
                        if not entry.rpc_method_authorizations[method]:
                            entry.rpc_method_authorizations[method] = [""]
                        self.auth_file.update_by_index(
                            entry, entries.index(entry)
                        )
                    else:
                        _log.error(
                            f"No matching authorized capabilities provided "
                            f"for {method}"
                        )
                return
        _log.error("Agent identity not found in auth file!")
        return

    def _update_auth_lists(self, entries, is_allow=True):
        auth_list = []
        for entry in entries:
            auth_list.append(
                {
                    "domain": entry.domain,
                    "address": entry.address,
                    "mechanism": entry.mechanism,
                    "credentials": entry.credentials,
                    "user_id": entry.user_id,
                    "retries": 0,
                }
            )
        if is_allow:
            self._auth_approved = [
                entry for entry in auth_list if entry["address"] is not None
            ]
        else:
            self._auth_denied = [
                entry for entry in auth_list if entry["address"] is not None
            ]

    def _get_updated_entries(self, old_entries, new_entries):
        """
        Compare old and new entries rpc_method_authorization data. Return
        which entries have been changed.
        :param old_entries: Old entries currently stored in memory
        :type old_entries: list
        :param new_entries: New entries read in from auth_file.json
        :type new_entries: list
        :return: modified_entries
        """
        modified_entries = []
        for entry in new_entries:
            if (
                    entry.identity is not None
                    and entry.identity not in PROCESS_IDENTITIES
                    and entry.identity != CONTROL_CONNECTION
            ):

                for old_entry in old_entries:
                    if entry.identity == old_entry.identity:
                        if (
                                entry.rpc_method_authorizations
                                != old_entry.rpc_method_authorizations
                        ):
                            modified_entries.append(entry)
                        else:
                            pass
                    else:
                        pass
                if entry.identity not in [
                        old_entry.identity for old_entry in old_entries
                ]:
                    modified_entries.append(entry)
            else:
                pass
        return modified_entries

    def read_auth_file(self):
        _log.info("loading auth file %s", self.auth_file_path)
        # Update from auth file into memory
        if self.auth_file.auth_data:
            old_entries = self.auth_file.read_allow_entries().copy()
            self.auth_file.load()
            entries = self.auth_file.read_allow_entries()
            count = 0
            # Allow for multiple tries to ensure auth file is read
            while not entries and count < 3:
                self.auth_file.load()
                entries = self.auth_file.read_allow_entries()
                count += 1
            modified_entries = self._get_updated_entries(old_entries, entries)
            denied_entries = self.auth_file.read_deny_entries()
        else:
            self.auth_file.load()
            entries = self.auth_file.read_allow_entries()
            denied_entries = self.auth_file.read_deny_entries()
        # Populate auth lists with current entries
        self._update_auth_lists(entries)
        self._update_auth_lists(denied_entries, is_allow=False)
        entries = [entry for entry in entries if entry.enabled]
        # sort the entries so the regex credentials follow the concrete creds
        entries.sort()
        self.auth_entries = entries
        if self._is_connected:
            try:
                _log.debug("Sending auth updates to peers")
                # Give it few seconds for platform to startup or for the
                # router to detect agent install/remove action
                gevent.sleep(2)
                self._send_update(modified_entries)
            except BaseException as err:
                _log.error(
                    "Exception sending auth updates to peer. %r",
                    err
                )
                raise err
        _log.info("auth file %s loaded", self.auth_file_path)

    def get_protected_topics(self):
        protected = self._protected_topics
        return protected

    def _read_protected_topics_file(self):
        # Read protected topics file and send to router
        try:
            create_file_if_missing(self._protected_topics_file)
            with open(self._protected_topics_file) as fil:
                # Use gevent FileObject to avoid blocking the thread
                data = FileObject(fil, close=False).read()
                self._protected_topics = self.authorization_server.load_protected_topics(data)

        except Exception:
            _log.exception("error loading %s", self._protected_topics_file)

    def _send_update(self, modified_entries=None):
        """
        Compare old and new entries rpc_method_authorization data. Return
        which entries have been changed.

        :param modified_entries: Entries that have been modified when compared
        to the auth file.
        :type modified_entries: list
        """
        user_to_caps = self.get_user_to_capabilities()
        i = 0
        peers = None
        # peerlist times out lots of times when running test suite. This
        # happens even with higher timeout in get()
        # but if we retry peerlist succeeds by second attempt most of the
        # time!!!
        while not peers and i < 3:
            try:
                i = i + 1
                peers = self.vip.peerlist().get(timeout=0.5)
            except BaseException as err:
                _log.warning(
                    "Attempt %i to get peerlist failed with " "exception %s",
                    i,
                    err,
                )
                peers = list(self.vip.peerlist.peers_list)
                _log.warning("Get list of peers from subsystem directly")

        if not peers:
            raise BaseException("No peers connected to the platform")

        _log.debug("after getting peerlist to send auth updates")

        for peer in peers:
            if peer not in [self.core.identity, CONTROL_CONNECTION]:
                _log.debug(f"Sending auth update to peers {peer}")
                self.vip.rpc.call(peer, "auth.update", user_to_caps)

        # Update RPC method authorizations on agents
        if modified_entries:
            try:
                gevent.spawn(
                    self.update_rpc_authorizations, modified_entries
                ).join(timeout=15)
            except gevent.Timeout:
                _log.error("Timed out updating methods from auth file!")
        self.authorization_server.update_user_capabilites(self.get_user_to_capabilities())


    @RPC.export
    def get_user_to_capabilities(self):
        """RPC method

        Gets a mapping of all users to their capabiliites.

        :returns: mapping of users to capabilities
        :rtype: dict
        """
        user_to_caps = {}
        for entry in self.auth_entries:
            user_to_caps[entry.user_id] = entry.capabilities
        return user_to_caps

    @RPC.export
    def get_authorizations(self, user_id):
        """RPC method

        Gets capabilities, groups, and roles for a given user.

        :param user_id: user id field from VOLTTRON Interconnect Protocol
        :type user_id: str
        :returns: tuple of capabiliy-list, group-list, role-list
        :rtype: tuple
        """
        use_parts = True
        try:
            domain, address, mechanism, credentials = load_user(user_id)
        except ValueError:
            use_parts = False
        for entry in self.auth_entries:
            if entry.user_id == user_id:
                return [entry.capabilities, entry.groups, entry.roles]
            elif use_parts:
                if entry.match(domain, address, mechanism, [credentials]):
                    return entry.capabilities, entry.groups, entry.roles

    @RPC.export
    @RPC.allow(capabilities="allow_auth_modifications")
    def approve_authorization(self, user_id):
        """RPC method

        Approves a pending CSR or credential, based on provided identity.
        The approved CSR or credential can be deleted or denied later.
        An approved credential is stored in the allow list in auth.json.

        :param user_id: user id field from VOLTTRON Interconnect Protocol or
        common name for CSR
        :type user_id: str
        """
        self.authorization_server.approve_authorization(user_id)

    @RPC.export
    @RPC.allow(capabilities="allow_auth_modifications")
    def deny_authorization(self, user_id):
        """RPC method

        Denies a pending CSR or credential, based on provided identity.
        The denied CSR or credential can be deleted or accepted later.
        A denied credential is stored in the deny list in auth.json.

        :param user_id: user id field from VOLTTRON Interconnect Protocol or
        common name for CSR
        :type user_id: str
        """

        self.authorization_server.deny_authorization(user_id)

    @RPC.export
    @RPC.allow(capabilities="allow_auth_modifications")
    def delete_authorization(self, user_id):
        """RPC method

        Deletes a pending CSR or credential, based on provided identity.
        To approve or deny a deleted pending CSR or credential,
        the request must be resent by the remote platform or agent.

        :param user_id: user id field from VOLTTRON Interconnect Protocol or
        common name for CSR
        :type user_id: str
        """

        self.authorization_server.delete_authorization(user_id)

    @RPC.export
    @RPC.allow(capabilities="allow_auth_modifications")
    def get_authorization(self, common_name):
        """RPC method

        Returns the cert of a pending CSR.
        This method provides RPC access to the Certs class's
        get_cert_from_csr method.
        This method is only applicable for web-enabled, RMQ instances.
        Currently, this method is only used by admin_endpoints.

        :param common_name: Common name for CSR
        :type common_name: str
        :rtype: str
        """
        return self.authorization_server.get_authorization(common_name)

    @RPC.export
    @RPC.allow(capabilities="allow_auth_modifications")
    def get_authorization_status(self, common_name):
        """RPC method

        Returns the status of a pending CSRs.
        This method provides RPC access to the Certs class's get_csr_status
        method.
        This method is only applicable for web-enabled, RMQ instances.
        Currently, this method is only used by admin_endpoints.

        :param common_name: Common name for CSR
        :type common_name: str
        :rtype: str
        """
        return self.authorization_server.get_authorization_status(common_name)

    @RPC.export
    def get_pending_authorizations(self):
        """RPC method

        Returns a list of failed (pending) ZMQ credentials.

        :rtype: list
        """
        return self.authorization_server.get_pending_authorizations()

    @RPC.export
    def get_approved_authorizations(self):
        """RPC method

        Returns a list of approved ZMQ credentials.
        This list is updated whenever the auth file is read.
        It includes all allow entries from the auth file that contain a
        populated address field.

        :rtype: list
        """
        return self.authorization_server.get_approved_authorizations()

    @RPC.export
    def get_denied_authorizations(self):
        """RPC method

        Returns a list of denied ZMQ credentials.
        This list is updated whenever the auth file is read.
        It includes all deny entries from the auth file that contain a
        populated address field.

        :rtype: list
        """
        return self.authorization_server.get_denied_authorizations()

    def _get_authorizations(self, user_id, index):
        """Convenience method for getting authorization component by index"""
        auths = self.get_authorizations(user_id)
        if auths:
            return auths[index]
        return []

    @RPC.export
    def get_capabilities(self, user_id):
        """RPC method

        Gets capabilities for a given user.

        :param user_id: user id field from VOLTTRON Interconnect Protocol
        :type user_id: str
        :returns: list of capabilities
        :rtype: list
        """
        return self._get_authorizations(user_id, 0)

    @RPC.export
    def get_groups(self, user_id):
        """RPC method

        Gets groups for a given user.

        :param user_id: user id field from VOLTTRON Interconnect Protocol
        :type user_id: str
        :returns: list of groups
        :rtype: list
        """
        return self._get_authorizations(user_id, 1)

    @RPC.export
    def get_roles(self, user_id):
        """RPC method

        Gets roles for a given user.

        :param user_id: user id field from VOLTTRON Interconnect Protocol
        :type user_id: str
        :returns: list of roles
        :rtype: list
        """
        return self._get_authorizations(user_id, 2)
