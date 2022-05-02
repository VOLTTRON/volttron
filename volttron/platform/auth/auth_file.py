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
import re
import shutil
import uuid

import gevent
import gevent.core
from gevent.fileobject import FileObject

from volttron.platform import jsonapi, get_home
from volttron.platform.agent.known_identities import (
    VOLTTRON_CENTRAL_PLATFORM,
    CONTROL)
from volttron.platform.agent.utils import (
    strip_comments,
    create_file_if_missing,
)

from volttron.platform.auth.auth_utils import isregex
from volttron.platform.auth.auth_exception import AuthException
from volttron.platform.auth.auth_entry import AuthEntry, AuthEntryInvalid

_log = logging.getLogger(__name__)

class AuthFile(object):
    def __init__(self, auth_file=None):
        self.auth_data = {}
        if auth_file is None:
            auth_file_dir = get_home()
            auth_file = os.path.join(auth_file_dir, "auth.json")
        self.auth_file = auth_file
        self._check_for_upgrade()
        self.load()

    @property
    def version(self):
        return {"major": 1, "minor": 3}

    def _check_for_upgrade(self):
        auth_data = self._read()
        if auth_data["version"] != self.version:
            if auth_data["version"]["major"] <= self.version["major"]:
                self._upgrade(
                    auth_data["allow_list"],
                    auth_data["deny_list"],
                    auth_data["groups"],
                    auth_data["roles"],
                    auth_data["version"],
                )
            else:
                _log.error(
                    "This version of VOLTTRON cannot parse %r. "
                    "Please upgrade VOLTTRON or move or delete "
                    "this file.",
                    self.auth_file
                )

    def _read(self):
        auth_data = {}
        try:
            create_file_if_missing(self.auth_file)
            with open(self.auth_file) as fil:
                # Use gevent FileObject to avoid blocking the thread
                before_strip_comments = FileObject(fil, close=False).read()
                if isinstance(before_strip_comments, bytes):
                    before_strip_comments = before_strip_comments.decode(
                        "utf-8"
                    )
                data = strip_comments(before_strip_comments)
                if data:
                    auth_data = jsonapi.loads(data)
        except Exception:
            _log.exception("error loading %s", self.auth_file)
        auth_output_data = {}
        auth_output_data["allow_list"] = auth_data.get("allow", [])
        auth_output_data["deny_list"] = auth_data.get("deny", [])
        auth_output_data["groups"] = auth_data.get("groups", {})
        auth_output_data["roles"] = auth_data.get("roles", {})
        auth_output_data["version"] = auth_data.get(
            "version", {"major": 0, "minor": 0}
        )
        return auth_output_data

    def load(self):
        """Reads in auth_file.json and stores it in auth_data."""
        self.auth_data = self._read()

    def read(self):
        """Gets the allowed entries, groups, and roles from the auth
        file.

        :returns: tuple of allow-entries-list, groups-dict, roles-dict
        :rtype: tuple
        """
        allow_entries, deny_entries = self._get_entries(
            self.auth_data["allow_list"], self.auth_data["deny_list"]
        )
        self._use_groups_and_roles(
            allow_entries, self.auth_data["groups"], self.auth_data["roles"]
        )
        return (
            allow_entries,
            deny_entries,
            self.auth_data["groups"],
            self.auth_data["roles"],
        )

    def _upgrade(self, allow_list, deny_list, groups, roles, version):
        backup = self.auth_file + "." + str(uuid.uuid4()) + ".bak"
        shutil.copy(self.auth_file, backup)
        _log.info("Created backup of %s at %s", self.auth_file, backup)

        def warn_invalid(entry, msg=""):
            """Warns if entry is invalid."""
            _log.warning(
                "invalid entry %r in auth file %s (%s)",
                entry,
                self.auth_file,
                msg
            )

        def upgrade_0_to_1(allow_list):
            new_allow_list = []
            for entry in allow_list:
                try:
                    credentials = entry["credentials"]
                except KeyError:
                    warn_invalid(entry)
                    continue
                if isregex(credentials):
                    msg = "Cannot upgrade entries with regex credentials"
                    warn_invalid(entry, msg)
                    continue
                if credentials == "NULL":
                    mechanism = "NULL"
                    credentials = None
                else:
                    match = re.match(r"^(PLAIN|CURVE):(.*)", credentials)
                    if match is None:
                        msg = "Expected NULL, PLAIN, or CURVE credentials"
                        warn_invalid(entry, msg)
                        continue
                    try:
                        mechanism = match.group(1)
                        credentials = match.group(2)
                    except IndexError:
                        warn_invalid(entry, "Unexpected credential format")
                        continue
                new_allow_list.append(
                    {
                        "domain": entry.get("domain"),
                        "address": entry.get("address"),
                        "mechanism": mechanism,
                        "credentials": credentials,
                        "user_id": entry.get("user_id"),
                        "groups": entry.get("groups", []),
                        "roles": entry.get("roles", []),
                        "capabilities": entry.get("capabilities", []),
                        "comments": entry.get("comments"),
                        "enabled": entry.get("enabled", True),
                    }
                )
            return new_allow_list

        def upgrade_1_0_to_1_1(allow_list):
            new_allow_list = []
            user_id_set = set()
            for entry in allow_list:
                user_id = entry.get("user_id")
                if user_id:
                    if user_id in user_id_set:
                        new_user_id = str(uuid.uuid4())
                        msg = (
                            "user_id {} is already present in "
                            "authentication entry. Changed to user_id to "
                            "{}"
                        ).format(user_id, new_user_id)
                        _log.warning(msg)
                        user_id_ = new_user_id
                else:
                    user_id = str(uuid.uuid4())
                user_id_set.add(user_id)
                entry["user_id"] = user_id
                new_allow_list.append(entry)
            return new_allow_list

        def upgrade_1_1_to_1_2(allow_list):
            new_allow_list = []
            for entry in allow_list:
                user_id = entry.get("user_id")
                if user_id in [CONTROL, VOLTTRON_CENTRAL_PLATFORM]:
                    user_id = "/.*/"
                capabilities = entry.get("capabilities")
                entry["capabilities"] = (
                    AuthEntry.build_capabilities_field(capabilities) or {}
                )
                entry["capabilities"]["edit_config_store"] = {
                    "identity": user_id
                }
                new_allow_list.append(entry)
            return new_allow_list

        def upgrade_1_2_to_1_3(allow_list):
            """Adds rpc_method_authorizations section to auth entries."""
            new_allow_list = []
            for entry in allow_list:
                rpc_method_authorizations = entry.get(
                    "rpc_method_authorizations"
                )
                entry["rpc_method_authorizations"] = (
                    AuthEntry.build_rpc_authorizations_field(
                        rpc_method_authorizations
                    )
                    or {}
                )
                new_allow_list.append(entry)
            return new_allow_list

        if version["major"] == 0:
            allow_list = upgrade_0_to_1(allow_list)
            version["major"] = 1
            version["minor"] = 0
        if version["major"] == 1 and version["minor"] == 0:
            allow_list = upgrade_1_0_to_1_1(allow_list)
            version["minor"] = 1
        if version["major"] == 1 and version["minor"] == 1:
            allow_list = upgrade_1_1_to_1_2(allow_list)
            version["minor"] = 2
        if version["major"] == 1 and version["minor"] == 2:
            allow_list = upgrade_1_2_to_1_3(allow_list)

        allow_entries, deny_entries = self._get_entries(allow_list, deny_list)
        self._write(allow_entries, deny_entries, groups, roles)

    def read_allow_entries(self):
        """
        Gets the allowed entries from the auth file.

        :returns: list of allow-entries
        :rtype: list
        """
        return self.read()[0]

    def read_deny_entries(self):
        """
        Gets the denied entries from the auth file.

        :returns: list of deny-entries
        :rtype: list
        """
        return self.read()[1]

    def find_by_credentials(self, credentials, is_allow=True):
        """
        Find all entries that have the given credentials.

        :param str credentials: The credentials to search for
        :return: list of entries
        :rtype: list
        """

        if is_allow:
            return [
                entry
                for entry in self.read_allow_entries()
                if str(entry.credentials) == credentials
            ]
        else:
            return [
                entry
                for entry in self.read_deny_entries()
                if str(entry.credentials) == credentials
            ]

    def _get_entries(self, allow_list, deny_list):
        allow_entries = []
        for file_entry in allow_list:
            try:
                entry = AuthEntry(**file_entry)
            except TypeError:
                _log.warning(
                    "invalid entry %r in auth file %s",
                    file_entry,
                    self.auth_file,
                )
            except AuthEntryInvalid as err:
                _log.warning(
                    "invalid entry %r in auth file %s (%s)",
                    file_entry,
                    self.auth_file,
                    str(err),
                )
            else:
                allow_entries.append(entry)

        deny_entries = []
        for file_entry in deny_list:
            try:
                entry = AuthEntry(**file_entry)
            except TypeError:
                _log.warning(
                    "invalid entry %r in auth file %s",
                    file_entry,
                    self.auth_file,
                )
            except AuthEntryInvalid as err:
                _log.warning(
                    "invalid entry %r in auth file %s (%s)",
                    file_entry,
                    self.auth_file,
                    str(err),
                )
            else:
                deny_entries.append(entry)
        return allow_entries, deny_entries

    def _use_groups_and_roles(self, entries, groups, roles):
        """Add capabilities to each entry based on groups and roles."""
        for entry in entries:
            entry_roles = entry.roles
            # Each group is a list of roles
            for group in entry.groups:
                entry_roles += groups.get(group, [])
            capabilities = []
            # Each role is a list of capabilities
            for role in entry_roles:
                capabilities += roles.get(role, [])
            entry.add_capabilities(list(set(capabilities)))

    def _check_if_exists(self, entry, is_allow=True):
        """Raises AuthFileEntryAlreadyExists if entry is already in file."""
        if is_allow:
            for index, prev_entry in enumerate(self.read_allow_entries()):
                if entry.user_id == prev_entry.user_id:
                    raise AuthFileUserIdAlreadyExists(entry.user_id, [index])

                # Compare AuthEntry objects component-wise, rather than
                # using match, because match will evaluate regex.
                if (
                        prev_entry.domain == entry.domain
                        and prev_entry.address == entry.address
                        and prev_entry.mechanism == entry.mechanism
                        and prev_entry.credentials == entry.credentials
                ):
                    raise AuthFileEntryAlreadyExists([index])
        else:
            for index, prev_entry in enumerate(self.read_deny_entries()):
                if entry.user_id == prev_entry.user_id:
                    raise AuthFileUserIdAlreadyExists(entry.user_id, [index])

                # Compare AuthEntry objects component-wise, rather than
                # using match, because match will evaluate regex.
                if (
                        prev_entry.domain == entry.domain
                        and prev_entry.address == entry.address
                        and prev_entry.mechanism == entry.mechanism
                        and prev_entry.credentials == entry.credentials
                ):
                    raise AuthFileEntryAlreadyExists([index])

    def _update_by_indices(self, auth_entry, indices, is_allow=True):
        """Updates all entries at given indices with auth_entry."""
        for index in indices:
            self.update_by_index(auth_entry, index, is_allow)

    def add(self, auth_entry, overwrite=False, no_error=False, is_allow=True):
        """
        Adds an AuthEntry to the auth file.

        :param auth_entry: authentication entry
        :param overwrite: set to true to overwrite matching entries
        :param no_error:
            set to True to not throw an AuthFileEntryAlreadyExists when
            attempting to add an exiting entry.

        :type auth_entry: AuthEntry
        :type overwrite: bool
        :type no_error: bool

        .. warning:: If overwrite is set to False and if auth_entry matches an
                     existing entry then this method will raise
                     AuthFileEntryAlreadyExists unless no_error is set to true
        """
        try:
            self._check_if_exists(auth_entry, is_allow)
        except AuthFileEntryAlreadyExists as err:
            if overwrite:
                _log.debug("Updating existing auth entry with %s ", auth_entry)
                self._update_by_indices(auth_entry, err.indices, is_allow)
            else:
                if not no_error:
                    raise err
        else:
            allow_entries, deny_entries, groups, roles = self.read()
            if is_allow:
                allow_entries.append(auth_entry)
            else:
                deny_entries.append(auth_entry)
            self._write(allow_entries, deny_entries, groups, roles)
            _log.debug("Added auth entry {} ".format(auth_entry))
        gevent.sleep(1)

    def approve_deny_credential(self, user_id, is_approved=True):
        """
        Approves a denied credential or denies an approved credential.

        :param user_id: entry with this user_id will be
            approved or denied appropriately
        :param is_approved: Determines if the entry should be
            approved from denied, or denied from approved. If True,
            it will attempt to move the selected denied entry to
            the approved entries.

        :type user_id: str
        :type is_approved: bool
        """
        allow_entries, deny_entries, groups, roles = self.read()
        if is_approved:
            for entry in deny_entries:
                if entry.user_id == user_id:
                    try:
                        # If it does not already exist in allow_entries, add it
                        self._check_if_exists(entry)
                        allow_entries.append(entry)
                    except AuthFileEntryAlreadyExists:
                        _log.warning(
                            f"Entry for {user_id} already exists! Removing "
                            f"from denied credentials"
                        )
                else:
                    pass
            # Remove entry from denied entries
            deny_entries = [
                entry for entry in deny_entries if entry.user_id != user_id
            ]
        else:
            for entry in allow_entries:
                if entry.user_id == user_id:
                    try:
                        # If it does not already exist in deny_entries, add it
                        self._check_if_exists(entry, is_allow=False)
                        deny_entries.append(entry)
                    except AuthFileEntryAlreadyExists:
                        _log.warning(
                            f"Entry for {user_id} already exists! Removing "
                            f"from allowed credentials"
                        )
                else:
                    pass
            # Remove entry from allowed entries
            allow_entries = [
                entry for entry in allow_entries if entry.user_id != user_id
            ]

        self._write(allow_entries, deny_entries, groups, roles)
        gevent.sleep(1)

    def remove_by_credentials(self, credentials, is_allow=True):
        """
        Removes entry from auth file by credential.

        :param credentials: entries with these credentials will be removed
        :type credentials: str
        """
        allow_entries, deny_entries, groups, roles = self.read()
        if is_allow:
            entries = allow_entries
        else:
            entries = deny_entries
        entries = [
            entry for entry in entries if entry.credentials != credentials
        ]
        if is_allow:
            self._write(entries, deny_entries, groups, roles)
        else:
            self._write(allow_entries, entries, groups, roles)

    def remove_by_index(self, index, is_allow=True):
        """
        Removes entry from auth file by index.

        :param index: index of entry to remove
        :type index: int

        .. warning:: Calling with out-of-range index will raise
                     AuthFileIndexError
        """
        self.remove_by_indices([index], is_allow)

    def remove_by_indices(self, indices, is_allow=True):
        """
        Removes entry from auth file by indices.

        :param indices: list of indicies of entries to remove
        :type indices: list

        .. warning:: Calling with out-of-range index will raise
                     AuthFileIndexError
        """
        indices = list(set(indices))
        indices.sort(reverse=True)
        allow_entries, deny_entries, groups, roles = self.read()
        if is_allow:
            entries = allow_entries
        else:
            entries = deny_entries
        for index in indices:
            try:
                del entries[index]
            except IndexError:
                raise AuthFileIndexError(index)
        if is_allow:
            self._write(entries, deny_entries, groups, roles)
        else:
            self._write(allow_entries, entries, groups, roles)

    def _set_groups_or_roles(self, groups_or_roles, is_group=True):
        param_name = "groups" if is_group else "roles"
        if not isinstance(groups_or_roles, dict):
            raise ValueError("{} parameter must be dict".format(param_name))
        for key, value in groups_or_roles.items():
            if not isinstance(value, list):
                raise ValueError(
                    "each value of the {} dict must be "
                    "a list".format(param_name)
                )
        allow_entries, deny_entries, groups, roles = self.read()
        if is_group:
            groups = groups_or_roles
        else:
            roles = groups_or_roles
        self._write(allow_entries, deny_entries, groups, roles)

    def set_groups(self, groups):
        """
        Define the mapping of group names to role lists.

        :param groups: dict where the keys are group names and the
                       values are lists of capability names
        :type groups: dict

        .. warning:: Calling with invalid groups will raise ValueError
        """
        self._set_groups_or_roles(groups, is_group=True)

    def set_roles(self, roles):
        """
        Define the mapping of role names to capability lists.

        :param roles: dict where the keys are role names and the
                      values are lists of group names
        :type groups: dict

        .. warning:: Calling with invalid roles will raise ValueError
        """
        self._set_groups_or_roles(roles, is_group=False)

    def update_by_index(self, auth_entry, index, is_allow=True):
        """
        Updates entry with given auth entry at given index.

        :param auth_entry: new authorization entry
        :param index: index of entry to update
        :type auth_entry: AuthEntry
        :type index: int

        .. warning:: Calling with out-of-range index will raise
                     AuthFileIndexError
        """
        allow_entries, deny_entries, groups, roles = self.read()
        if is_allow:
            entries = allow_entries
        else:
            entries = deny_entries
        try:
            entries[index] = auth_entry
        except IndexError:
            raise AuthFileIndexError(index)
        if is_allow:
            self._write(entries, deny_entries, groups, roles)
        else:
            self._write(allow_entries, entries, groups, roles)

    def _write(self, allow_entries, deny_entries, groups, roles):
        auth = {
            "allow": [vars(x) for x in allow_entries],
            "deny": [vars(x) for x in deny_entries],
            "groups": groups,
            "roles": roles,
            "version": self.version,
        }

        with open(self.auth_file, "w") as file_pointer:
            jsonapi.dump(auth, file_pointer, indent=2)


class AuthFileIndexError(AuthException, IndexError):

    """
    Exception for invalid indices provided to AuthFile.
    """

    def __init__(self, indices, message=None):
        if not isinstance(indices, list):
            indices = [indices]
        if message is None:
            message = "Invalid {}: {}".format(
                "indicies" if len(indices) > 1 else "index", indices
            )
        super(AuthFileIndexError, self).__init__(message)
        self.indices = indices


class AuthFileEntryAlreadyExists(AuthFileIndexError):

    """
    Exception if adding an entry that already exists.
    """

    def __init__(self, indicies, message=None):
        if message is None:
            message = (
                "entry matches domain, address and credentials at " "index {}"
            ).format(indicies)
        super(AuthFileEntryAlreadyExists, self).__init__(indicies, message)


class AuthFileUserIdAlreadyExists(AuthFileEntryAlreadyExists):

    """
    Exception if adding an entry that has a taken user_id.
    """

    def __init__(self, user_id, indicies, message=None):
        if message is None:
            message = ("user_id {} is already in use at " "index {}").format(
                user_id, indicies
            )
        super(AuthFileUserIdAlreadyExists, self).__init__(indicies, message)
