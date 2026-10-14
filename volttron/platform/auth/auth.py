# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
# }}}

import copy
import json
import logging
import os

import gevent
import gevent.core
import gevent.lock
from gevent.fileobject import FileObject
from watchdog.events import FileSystemEventHandler
from watchdog_gevent import Observer

from volttron.platform import get_home
from volttron.platform.agent.known_identities import (CONTROL_CONNECTION, PROCESS_IDENTITIES,
                                                      RESERVED_USER_IDS)
from volttron.platform.agent.utils import (create_file_if_missing, get_messagebus,
                                           get_platform_instance_name, watch_file)
from volttron.platform.auth.auth_entry import AuthEntry
from volttron.platform.auth.auth_file import (AuthFile, AuthFileEntryNotOwned,
                                              AuthFileUnavailable)
from volttron.platform.auth.auth_utils import load_user
from volttron.platform.jsonrpc import RemoteError
from volttron.platform.keystore import KeyStore
from volttron.platform.vip.agent import RPC, Agent, Core
from volttron.platform.vip.agent.errors import Unreachable
from volttron.platform.vip.pubsubservice import (MAX_PLATFORM_MAP_PAIRS,
                                                 ProtectedPubSubTopics)

_log = logging.getLogger(__name__)


def _merge_agent_rpc_methods(authorizations, rpc_methods):
    """Returns the entry's authorizations with each of the agent's methods
    filled in where the entry has none, and the authorizations the agent
    should enforce. A non-empty entry in the file is never replaced."""
    merged = dict(authorizations)
    enforced = {}
    for method, capabilities in rpc_methods.items():
        if not merged.get(method):
            merged[method] = capabilities
        enforced[method] = merged[method]
    return merged, enforced


DISCOVERY_FILE = "external_platform_discovery.json"


def build_platform_map(entries, discovery, own_name, own_key):
    """Maps each user id that connects with a listed platform's key to that
    platform's instance name.

    `entries` are the auth entries the ZAP handler walks, `discovery` the
    parsed discovery file. Returns the map and the causes to warn about. A
    user maps only when every entry that carries it holds, as a plain string,
    the key of one discovery entry and none carries an identity, which
    agents' entries do.
    """
    causes = []
    listed = {}
    for file_key, info in discovery.items():
        name = info.get("instance-name") if isinstance(info, dict) else None
        key = info.get("serverkey") if isinstance(info, dict) else None
        if (not isinstance(name, str) or not name
                or not isinstance(key, str) or not key):
            causes.append("%s entry %r has no text instance-name and "
                          "serverkey and is skipped" % (DISCOVERY_FILE,
                                                        file_key))
            continue
        listed.setdefault(key, []).append((file_key, name))

    name_of_key = {}
    for key, found in listed.items():
        if len(found) > 1:
            causes.append("%s lists one serverkey under %s; none of them "
                          "maps" % (DISCOVERY_FILE,
                                    " and ".join(repr(f) for f, _ in found)))
        elif found[0][1] != own_name and key != own_key:
            name_of_key[key] = found[0][1]

    carried = {}
    for entry in entries:
        carried.setdefault(entry.user_id, []).append(entry)
    platforms = {}
    for user, user_entries in carried.items():
        if not user or user in RESERVED_USER_IDS:
            continue
        if any(entry.identity for entry in user_entries):
            continue
        names = set()
        for entry in user_entries:
            credentials = entry.credentials
            if (not isinstance(credentials, str)
                    or hasattr(credentials, "regex")):
                names = None
                break
            names.add(name_of_key.get(str(credentials)))
        if names and len(names) == 1 and None not in names:
            platforms[user] = sorted(names)
    return platforms, causes


class _DiscoveryFileHandler(FileSystemEventHandler):
    """Calls `callback` for every event that creates, finishes writing,
    moves into or out of place, or deletes the discovery file. Key discovery
    replaces the file by rename, which a watch on close events alone misses."""

    def __init__(self, path, callback):
        super().__init__()
        self._path = os.path.abspath(path)
        self._callback = callback

    def _named(self, *paths):
        return any(path and os.path.abspath(os.fsdecode(path)) == self._path
                   for path in paths)

    def on_created(self, event):
        if self._named(event.src_path):
            self._callback()

    def on_closed(self, event):
        if self._named(event.src_path):
            self._callback()

    def on_moved(self, event):
        if self._named(event.src_path, event.dest_path):
            self._callback()

    def on_deleted(self, event):
        if self._named(event.src_path):
            self._callback()


def watch_discovery_file(path, callback):
    """Runs `callback` on the watcher's native thread whenever the file at
    `path` appears, changes, moves or goes."""
    observer = Observer()
    observer.schedule(_DiscoveryFileHandler(path, callback),
                      os.path.dirname(os.path.abspath(path)))
    observer.start()
    _log.debug("Added file watch for %s", path)
    return observer


class AuthService(Agent):

    def __init__(self, auth_file, protected_topics_file, setup_mode, aip,
                 *args, **kwargs):
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
        # The "before" side of read_auth_file's rpc authorization diff. Kept
        # apart from auth_file.auth_data, which every write through
        # auth_file refreshes before the file watcher runs.
        self._last_loaded_allow_entries = copy.deepcopy(
            self.auth_file.read_allow_entries())
        self.can_update = False
        self.needs_rpc_update = False
        self.aip = aip
        self.zap_socket = None
        self._zap_greenlet = None
        self.auth_entries = []
        self._is_connected = False
        self._platform_map_warned = set()
        self._platform_map_errored = set()
        self._reload_lock = gevent.lock.Semaphore()
        self._protected_topics_lock = gevent.lock.Semaphore()
        self._protected_topics_file = protected_topics_file
        self._protected_topics_file_path = os.path.abspath(
            protected_topics_file)
        self._protected_topics = {}
        self._protected_topics_for_rmq = ProtectedPubSubTopics()
        self._setup_mode = setup_mode
        self._auth_pending = []
        self._auth_denied = []
        self._auth_approved = []
        self.authentication_server = None
        self.authorization_server = None

    @RPC.export("auth_file.read")
    @RPC.allow(capabilities="allow_auth_modifications")
    def _auth_file_read(self):
        """Returns the auth file data as last loaded or written."""
        return self.auth_file.auth_data

    @RPC.export("auth_file.find_by_credentials")
    @RPC.allow(capabilities="allow_auth_modifications")
    def _auth_file_find_by_credentials(self, credentials, is_allow=True):
        return self.auth_file.find_by_credentials(credentials, is_allow)

    @RPC.export("auth_file.add")
    @RPC.allow(capabilities="allow_auth_modifications")
    def _auth_file_add(self, entry):
        """Adds an entry, given as a dict of AuthEntry fields."""
        self.auth_file.add(AuthEntry(**entry))

    @RPC.export("auth_file.update_by_index")
    @RPC.allow(capabilities="allow_auth_modifications")
    def _auth_file_update_by_index(self, auth_entry, index, is_allow=True):
        """Replaces the entry at index with a dict of AuthEntry fields."""
        self.auth_file.update_by_index(AuthEntry(**auth_entry), index,
                                       is_allow)

    @RPC.export("auth_file.remove_by_credentials")
    @RPC.allow(capabilities="allow_auth_modifications")
    def _auth_file_remove_by_credentials(self, credentials, is_allow=True):
        self.auth_file.remove_by_credentials(credentials, is_allow)

    @RPC.export("auth_file.remove_by_index")
    @RPC.allow(capabilities="allow_auth_modifications")
    def _auth_file_remove_by_index(self, index, is_allow=True):
        self.auth_file.remove_by_index(index, is_allow)

    @RPC.export("auth_file.remove_by_indices")
    @RPC.allow(capabilities="allow_auth_modifications")
    def _auth_file_remove_by_indices(self, indices, is_allow=True):
        self.auth_file.remove_by_indices(indices, is_allow)

    @RPC.export("auth_file.set_groups")
    @RPC.allow(capabilities="allow_auth_modifications")
    def _auth_file_set_groups(self, groups):
        self.auth_file.set_groups(groups)

    @RPC.export("auth_file.set_roles")
    @RPC.allow(capabilities="allow_auth_modifications")
    def _auth_file_set_roles(self, roles):
        self.auth_file.set_roles(roles)

    @Core.receiver("onsetup")
    def setup_authentication_server(self, sender, **kwargs):
        if self.allow_any:
            _log.warning("insecure permissive authentication enabled")
        self.read_auth_file()
        if get_messagebus() == "zmq":
            from volttron.platform.auth.auth_protocols.auth_zmq import ZMQAuthorization, ZMQServerAuthentication
            self.authentication_server = ZMQServerAuthentication(
                auth_service=self)
            self.authorization_server = ZMQAuthorization(auth_service=self)
        else:
            from volttron.platform.auth.auth_protocols.auth_rmq import RMQAuthorization, RMQServerAuthentication
            self.authentication_server = RMQServerAuthentication(
                auth_service=self)
            self.authorization_server = RMQAuthorization(auth_service=self)
        self._read_protected_topics_file()
        self.core.spawn(watch_file, self.auth_file_path,
                        self._hand_reload_to_hub)
        self.core.spawn(
            watch_file,
            self._protected_topics_file_path,
            self._hand_protected_topics_to_hub,
        )
        self.core.spawn(watch_discovery_file,
                        os.path.join(get_home(), DISCOVERY_FILE),
                        self._hand_discovery_to_hub)
        self.authentication_server.setup_authentication()

    @Core.receiver("onstart")
    def start_authentication_server(self, sender, **kwargs):
        self.authentication_server.handle_authentication(
            self._protected_topics)

    @Core.receiver("onstop")
    def stop_authentication_server(self, sender, **kwargs):
        self.authentication_server.stop_authentication()

    @Core.receiver("onfinish")
    def unbind_authentication_server(self, sender, **kwargs):
        self.authentication_server.unbind_authentication()

    @RPC.export("update_id_rpc_authorizations")
    def _update_caller_rpc_authorizations(self, identity, rpc_methods):
        """
        RPC entry point of update_id_rpc_authorizations. The caller's
        authenticated user must be the user_id of the entry with the
        identity; otherwise nothing is changed and None is returned.
        """
        user_id = str(self.vip.rpc.context.vip_message.user)
        if get_messagebus() == "rmq":
            # RMQ user names are <instance name>.<user>, as in the RPC
            # subsystem's capability check.
            user_id = user_id[user_id.index(".") + 1:]
        return self.update_id_rpc_authorizations(identity, rpc_methods,
                                                 user_id=user_id)

    def update_id_rpc_authorizations(self, identity, rpc_methods,
                                     user_id=None):
        """
        Update RPC methods for an auth entry. This is called by the subsystem
        on agent start-up to ensure that the agent's current rpc allowances are
        recorded with it's auth entry.
        :param identity: The agent's identity in the auth entry
        :param rpc_methods: The rpc methods to update in the format
            {rpc_method_name: [allowed_rpc_capability_1, ...]}
        :param user_id: when given, the entry must belong to this user, or
            the call is refused
        :return: updated_rpc_methods or None
        """
        enforced = {}

        def fill_missing(authorizations):
            merged, enforced_now = _merge_agent_rpc_methods(authorizations,
                                                            rpc_methods)
            enforced.update(enforced_now)
            return merged if merged != authorizations else None

        try:
            found = self.auth_file.modify_rpc_method_authorizations(
                identity, fill_missing, user_id=user_id)
        except AuthFileEntryNotOwned:
            return self._refuse_rpc_authorizations(identity, user_id)
        except AuthFileUnavailable as err:
            # The agent waits only a few seconds for this answer, then keeps
            # its own defaults, so answer from the last load instead.
            _log.error("auth file not updated for %s: %s", identity, err)
            return self._cached_rpc_authorizations(identity, rpc_methods,
                                                   user_id)
        return enforced if found else None

    def _cached_rpc_authorizations(self, identity, rpc_methods, user_id):
        for entry in self.auth_file.read_allow_entries():
            if entry.identity == identity:
                if user_id is not None and entry.user_id != user_id:
                    return self._refuse_rpc_authorizations(identity, user_id)
                return _merge_agent_rpc_methods(
                    entry.rpc_method_authorizations, rpc_methods)[1]
        return None

    @staticmethod
    def _refuse_rpc_authorizations(identity, user_id):
        _log.warning("rpc method authorizations for identity %r not "
                     "recorded: the caller %r is not that entry's user",
                     identity, user_id)
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
                identity, "auth.get_all_rpc_authorizations").get()
            _log.debug(f"RPC Methods are: {rpc_method_authorizations}")
        except Unreachable:
            _log.warning(f"{identity} "
                         f"is unreachable while attempting to get rpc methods")

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
            if (entry.identity is not None
                    and entry.identity not in PROCESS_IDENTITIES
                    and entry.identity != CONTROL_CONNECTION):
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
                        method]
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
                        _log.error(f"{entry.identity} "
                                   f"has timed out while attempting "
                                   f"to update rpc_method_authorizations")
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
                                    capabilities=entry.
                                    rpc_method_authorizations[method],
                                )
                            except gevent.Timeout:
                                _log.error(f"{entry.identity} "
                                           f"has timed out while attempting "
                                           f"to update "
                                           f"rpc_method_authorizations")
                            except RemoteError:
                                _log.error(f"Method {method} does not exist.")

    @RPC.export
    @RPC.allow(capabilities="modify_rpc_method_allowance")
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

        def add_capabilities(rpc_method_authorizations):
            if not rpc_method_authorizations.get(method):
                rpc_method_authorizations[method] = authorizations
            else:
                rpc_method_authorizations[method].extend([
                    rpc_auth for rpc_auth in authorizations
                    if rpc_auth not in rpc_method_authorizations[method]
                ])
            return rpc_method_authorizations

        if not self.auth_file.modify_rpc_method_authorizations(
                identity, add_capabilities):
            _log.error("Agent identity not found in auth file!")

    @RPC.export
    @RPC.allow(capabilities="modify_rpc_method_allowance")
    def delete_rpc_authorizations(self, identity, method,
                                  denied_authorizations):
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

        def remove_capabilities(rpc_method_authorizations):
            if method not in rpc_method_authorizations:
                _log.error(f"{identity} does not have a method called "
                           f"{method}")
                return None
            if not rpc_method_authorizations[method]:
                _log.error(f"{identity}.{method} does not have any "
                           f"authorized capabilities.")
                return None
            any_match = False
            for rpc_auth in denied_authorizations:
                if rpc_auth not in rpc_method_authorizations[method]:
                    _log.error(f"{rpc_auth} is not an authorized capability "
                               f"for {method}")
                else:
                    any_match = True
            if not any_match:
                _log.error(f"No matching authorized capabilities provided "
                           f"for {method}")
                return None
            rpc_method_authorizations[method] = [
                rpc_auth for rpc_auth in rpc_method_authorizations[method]
                if rpc_auth not in denied_authorizations
            ] or [""]
            return rpc_method_authorizations

        if not self.auth_file.modify_rpc_method_authorizations(
                identity, remove_capabilities):
            _log.error("Agent identity not found in auth file!")

    def _update_auth_lists(self, entries, is_allow=True):
        auth_list = []
        for entry in entries:
            auth_list.append({
                "domain": entry.domain,
                "address": entry.address,
                "mechanism": entry.mechanism,
                "credentials": entry.credentials,
                "user_id": entry.user_id,
                "retries": 0,
            })
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
            if (entry.identity is not None
                    and entry.identity not in PROCESS_IDENTITIES
                    and entry.identity != CONTROL_CONNECTION):

                for old_entry in old_entries:
                    if entry.identity == old_entry.identity:
                        if (entry.rpc_method_authorizations
                                != old_entry.rpc_method_authorizations):
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

    def _hand_reload_to_hub(self):
        """The file watcher's callback. It runs on the watcher's native
        thread, which must not use the VIP socket, so it only hands the
        reload to the hub."""
        self.core.send(self._reload_on_hub)

    def _reload_on_hub(self):
        # One reload at a time, as the watcher's thread gave before.
        with self._reload_lock:
            self.read_auth_file()

    def _hand_protected_topics_to_hub(self):
        """The protected topics file watcher's callback. Reading the file
        sends the topics to the router on the VIP socket, which the watcher's
        native thread must not use."""
        self.core.send(self._read_protected_topics_on_hub)

    def _read_protected_topics_on_hub(self):
        with self._protected_topics_lock:
            self._read_protected_topics_file()

    def _hand_discovery_to_hub(self):
        """The discovery file watcher's callback, on the watcher's native
        thread. The map is rebuilt and pushed on the hub."""
        self.core.send(self._push_map_on_hub)

    def _push_map_on_hub(self):
        if not self._is_connected:
            # The push at the start of the ZAP loop builds the map from the
            # file as it is by then.
            _log.debug("discovery file changed before the router could be "
                       "updated; the start push carries the map")
            return
        self.push_router_update("discovery file change")

    def read_auth_file(self):
        """Reloads auth.json and pushes changed entries to peers.

        An exception that escapes would end a file watch for good, so
        failures are logged here instead of raised.
        """
        try:
            self._load_and_push_auth_file()
        except (KeyboardInterrupt, SystemExit, gevent.GreenletExit):
            raise
        except BaseException:
            # _send_update raises a bare BaseException when no peer answers.
            _log.exception("error loading auth file %s; the next change to "
                           "it retries the load and push",
                           self.auth_file_path)

    def _load_and_push_auth_file(self):
        _log.debug("loading auth file %s", self.auth_file_path)
        # The snapshot is copied from freshly parsed data inside AuthFile:
        # update_id_rpc_authorizations edits auth_data's rpc dicts in place.
        if self.auth_file.auth_data:
            loaded_entries = self.auth_file.load_allow_snapshot()
            entries = self.auth_file.read_allow_entries()
            count = 0
            # Allow for multiple tries to ensure auth file is read
            while not entries and count < 3:
                loaded_entries = self.auth_file.load_allow_snapshot()
                entries = self.auth_file.read_allow_entries()
                count += 1
        else:
            loaded_entries = self.auth_file.load_allow_snapshot()
            entries = self.auth_file.read_allow_entries()
        modified_entries = self._get_updated_entries(
            self._last_loaded_allow_entries, entries)
        denied_entries = self.auth_file.read_deny_entries()
        # Populate auth lists with current entries
        self._update_auth_lists(entries)
        self._update_auth_lists(denied_entries, is_allow=False)
        entries = [entry for entry in entries if entry.enabled]
        # sort the entries so the regex credentials follow the concrete creds
        entries.sort()
        self.auth_entries = entries
        if self._is_connected:
            _log.debug("Sending auth updates to peers")
            # Give it few seconds for platform to startup or for the
            # router to detect agent install/remove action
            gevent.sleep(2)
            self._send_update(modified_entries)
        # Not reached when the push raises, so the next file event diffs
        # against the old snapshot and pushes the same change again.
        self._last_loaded_allow_entries = loaded_entries
        _log.debug("auth file %s loaded", self.auth_file_path)

    def platform_map(self):
        """The map of user ids to platform names for the router, built from
        the entries the ZAP handler walks and the discovery file. Anything
        that stops it being built gives an empty map, which refuses all
        external publishes and lists."""
        platforms, causes, errors = {}, [], []
        path = os.path.join(get_home(), DISCOVERY_FILE)
        try:
            if self._setup_mode:
                causes.append(
                    "setup mode: no platform is mapped, so pub/sub from other "
                    "platforms resumes after a restart in normal mode")
            else:
                with open(path) as discovery_file:
                    discovery = json.load(discovery_file)
                if not isinstance(discovery, dict):
                    raise ValueError("it is not a JSON object")
                platforms, causes = build_platform_map(
                    self.auth_entries, discovery,
                    get_platform_instance_name(), KeyStore().public)
                if (sum(len(names) for names in platforms.values())
                        > MAX_PLATFORM_MAP_PAIRS):
                    platforms = {}
                    errors.append(
                        "the platform map has more than %d user and "
                        "platform pairs, so no platform is mapped and "
                        "pub/sub from other platforms is refused"
                        % MAX_PLATFORM_MAP_PAIRS)
        except Exception as err:
            # Whatever stops the map being built (a missing file, bad JSON,
            # no instance name, an unreadable keystore) must leave it empty
            # and still be sent, because an old map would stay in force.
            causes.append("%s cannot be used (%s), so no platform is mapped "
                          "and pub/sub from other platforms is refused"
                          % (DISCOVERY_FILE, err))
        for cause in causes:
            if cause not in self._platform_map_warned:
                _log.warning(cause)
        self._platform_map_warned = set(causes)
        for error in errors:
            if error not in self._platform_map_errored:
                _log.error(error)
        self._platform_map_errored = set(errors)
        return platforms

    def push_router_update(self, trigger):
        """Sends the router the capabilities and the platform map. A failure
        is logged with its trigger, and the router keeps its previous map."""
        try:
            self.authorization_server.update_user_capabilites(
                self.get_user_to_capabilities())
        except Exception:
            # The push is the last step of a refresh and of the ZAP loop's
            # start, and neither may stop because the router did not take it.
            _log.exception(
                "auth update to the router failed (%s); the router keeps its "
                "previous capabilities and platform map until a later push "
                "succeeds", trigger)

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
                self._protected_topics = self.authorization_server.load_protected_topics(
                    data)

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
        # The map goes first and does not wait on the peer loop below, which
        # raises when no peer is connected.
        self.push_router_update("auth file reload")
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
                    "Attempt %i to get peerlist failed with "
                    "exception %s",
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
                gevent.spawn(self.update_rpc_authorizations,
                             modified_entries).join(timeout=15)
            except gevent.Timeout:
                _log.error("Timed out updating methods from auth file!")

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
    @RPC.allow(capabilities="allow_auth_modifications")
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
    @RPC.allow(capabilities="allow_auth_modifications")
    def get_pending_authorizations(self):
        """RPC method

        Returns a list of failed (pending) ZMQ credentials.

        :rtype: list
        """
        return self.authorization_server.get_pending_authorizations()

    @RPC.export
    @RPC.allow(capabilities="allow_auth_modifications")
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
    @RPC.allow(capabilities="allow_auth_modifications")
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
    @RPC.allow(capabilities="allow_auth_modifications")
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
    @RPC.allow(capabilities="allow_auth_modifications")
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
    @RPC.allow(capabilities="allow_auth_modifications")
    def get_roles(self, user_id):
        """RPC method

        Gets roles for a given user.

        :param user_id: user id field from VOLTTRON Interconnect Protocol
        :type user_id: str
        :returns: list of roles
        :rtype: list
        """
        return self._get_authorizations(user_id, 2)
