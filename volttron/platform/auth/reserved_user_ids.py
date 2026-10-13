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

"""The keys the platform holds for the user ids it reserves for itself."""

import logging
import os
import stat

from volttron.platform import get_home, jsonapi
from volttron.platform.agent.known_identities import (
    CONTROL_CONNECTION,
    PLATFORM,
    PROCESS_IDENTITIES,
    RESERVED_USER_IDS,
    VOLTTRON_CENTRAL,
)
from volttron.platform.auth.auth_entry import AuthEntryInvalid
from volttron.platform.keystore import KEYSTORES_DIRNAME, KeyStore

_log = logging.getLogger(__name__)

# Platform services, in-process agents included, keep their key in
# VOLTTRON_HOME/keystores/<identity>.
_SERVICE_KEYSTORE_IDENTITIES = frozenset(PROCESS_IDENTITIES) | {CONTROL_CONNECTION}


class ReservedUserIdRefused(AuthEntryInvalid):
    """The entry is valid but its reserved user id lacks the platform's key."""


def _writable_by_others(mode):
    return bool(mode & (stat.S_IWGRP | stat.S_IWOTH))


def _closed_directory(path):
    """True for a real directory this user owns that nobody else can write."""
    info = os.lstat(path)
    return (stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
            and not _writable_by_others(info.st_mode))


def _open_trusted(path):
    """Opens a key file only if the platform's user owns it as a regular file
    that nobody else can write, in a directory nobody else can write. A key
    under keystores/ also needs keystores/ itself closed, or a group member
    could swap the per-identity directories."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
                 | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        directory = os.path.dirname(path)
        parent = os.path.dirname(directory)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or _writable_by_others(info.st_mode)
                or not _closed_directory(directory)
                or (os.path.basename(parent) == KEYSTORES_DIRNAME
                    and not _closed_directory(parent))):
            raise PermissionError(
                "not a regular file and directories owned by this user and "
                "closed to group and other writes")
        return os.fdopen(fd)
    except BaseException:
        os.close(fd)
        raise


def _read_public_key(path):
    """Reads a keystore file without creating or repairing it."""
    try:
        with _open_trusted(path) as keystore:
            key = jsonapi.load(keystore).get("public")
    except FileNotFoundError:
        _log.warning("the platform's key file %s does not exist", path)
        return None
    except (OSError, ValueError, AttributeError) as err:
        _log.warning("cannot trust the platform's key file %s: %s", path, err)
        return None
    return key if isinstance(key, str) and key else None


def _installed_agent_key_path(agent_dir):
    """The keystore of the agent installed in agent_dir, found as the agent
    installer lays it out: <dir>/<name>/<name>.dist-info/keystore.json.
    None unless exactly one package directory has a dist-info."""
    try:
        names = [name for name in os.listdir(agent_dir)
                 if os.path.isdir(os.path.join(
                     agent_dir, name, name + ".dist-info"))]
    except OSError as err:
        _log.warning("cannot list the installed agent folder %s: %s",
                     agent_dir, err)
        return None
    if len(names) != 1:
        _log.warning("expected one package with a dist-info in %s, found %d",
                     agent_dir, len(names))
        return None
    name = names[0]
    return os.path.join(agent_dir, name, name + ".dist-info", "keystore.json")


def _installed_agent_keys(identity):
    """Public keys of installed agents whose identity is `identity`."""
    agents_dir = os.path.join(get_home(), "agents")
    try:
        agent_ids = os.listdir(agents_dir)
    except FileNotFoundError:
        return frozenset()
    keys = set()
    for agent_id in agent_ids:
        agent_dir = os.path.join(agents_dir, agent_id)
        try:
            with open(os.path.join(agent_dir, "IDENTITY")) as fil:
                installed_identity = fil.read().strip()
        except OSError as err:
            _log.warning("cannot read the IDENTITY file of the agent in %s: "
                         "%s", agent_dir, err)
            continue
        if installed_identity != identity:
            continue
        path = _installed_agent_key_path(agent_dir)
        key = _read_public_key(path) if path else None
        if key:
            keys.add(key)
    return frozenset(keys)


def platform_held_keys(user_id):
    """The public keys the platform itself holds for a reserved user id.
    Empty when it holds none, which makes every entry for the id refused."""
    if user_id == PLATFORM:
        key = _read_public_key(KeyStore.get_default_path())
    elif user_id in _SERVICE_KEYSTORE_IDENTITIES:
        key = _read_public_key(KeyStore.get_agent_keystore_path(user_id))
    elif user_id == VOLTTRON_CENTRAL:
        return _installed_agent_keys(user_id)
    else:
        return frozenset()
    return frozenset((key,)) if key else frozenset()


def check_reserved_user_id(entry):
    """Raises AuthEntryInvalid when the entry carries a reserved user id
    without the key the platform holds for it."""
    if entry.user_id not in RESERVED_USER_IDS:
        return
    credentials = entry.credentials
    held = platform_held_keys(entry.user_id)
    if (entry.mechanism == "CURVE" and isinstance(credentials, str)
            and credentials in held):
        return
    if not held:
        reason = "the platform holds no key for it"
    elif entry.mechanism != "CURVE":
        reason = "the entry does not use CURVE credentials"
    else:
        reason = "the entry holds a different key than the platform's"
    raise ReservedUserIdRefused(
        f"user_id {entry.user_id!r} is reserved for a platform service and "
        f"{reason}")
