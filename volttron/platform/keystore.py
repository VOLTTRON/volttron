# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

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
#}}}


"""Module for storing local public and secret keys and remote public keys"""


from volttron.platform import jsonapi
import logging
import os
import stat
import urllib.parse

from zmq import curve_keypair

from .agent.utils import create_file_if_missing
from .vip.socket import encode_key
from volttron.platform import get_home

_log = logging.getLogger(__name__)


KEYSTORES_DIRNAME = "keystores"
_PRIVATE_DIR_MODE = 0o700


def _make_private_dir(path):
    """Creates path owner-only whatever the umask. An existing directory is
    left as it is; tighten_keystore_dirs repairs those."""
    try:
        os.mkdir(path, _PRIVATE_DIR_MODE)
    except FileExistsError:
        return
    os.chmod(path, _PRIVATE_DIR_MODE)


def create_keystore_dir(directory):
    """Creates VOLTTRON_HOME/keystores and keystores/<id> owner-only.
    Agent isolation mode runs with umask 007, which would leave them
    group-writable, and the platform refuses reserved keys stored there."""
    root = os.path.dirname(directory)
    os.makedirs(os.path.dirname(root), exist_ok=True)
    _make_private_dir(root)
    _make_private_dir(directory)


def tighten_keystore_dirs():
    """Makes keystores/ and keystores/<id> owner-only when this user owns
    them, for homes made by releases that created them group-writable.
    Directories owned by anyone else, and symlinks, are left alone."""
    root = os.path.join(get_home(), KEYSTORES_DIRNAME)
    try:
        children = [os.path.join(root, name) for name in os.listdir(root)]
    except FileNotFoundError:
        return
    for path in [root] + children:
        try:
            info = os.lstat(path)
        except FileNotFoundError:
            continue
        except OSError as err:
            _log.warning("cannot check key directory %s: %s", path, err)
            continue
        if not stat.S_ISDIR(info.st_mode):
            continue
        if info.st_uid != os.getuid():
            _log.warning("not tightening key directory %s: it is owned by "
                         "another user", path)
            continue
        if stat.S_IMODE(info.st_mode) == _PRIVATE_DIR_MODE:
            continue
        os.chmod(path, _PRIVATE_DIR_MODE)
        _log.info("tightened %s from mode %o to %o", path,
                  stat.S_IMODE(info.st_mode), _PRIVATE_DIR_MODE)


class HomeOwnedByAnotherUser(Exception):
    """VOLTTRON_HOME is writable by group or others and is owned by someone
    other than the user running the platform, so the platform cannot fix it."""


def tighten_volttron_home():
    """Removes group and other write from VOLTTRON_HOME when this user owns
    it. Every read and execute bit stays, because agent users reach their
    folders through the home's execute bit. The platform's key lives in the
    home and is refused while the home is writable by anyone else. A home
    owned by another user raises HomeOwnedByAnotherUser. A symlink or a
    non-directory is left alone."""
    home = get_home()
    info = os.lstat(home)
    if not stat.S_ISDIR(info.st_mode):
        return
    loose = info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
    if not loose:
        return
    if info.st_uid != os.getuid():
        raise HomeOwnedByAnotherUser(
            "VOLTTRON_HOME {0} is writable by its group or others and is "
            "owned by another user. Ask its owner to run: chmod go-w {0}"
            .format(home))
    before = stat.S_IMODE(info.st_mode)
    after = before & ~loose
    os.chmod(home, after)
    _log.warning("removed group and other write access from %s: mode %o "
                 "changed to %o", home, before, after)


class BaseJSONStore:
    """JSON-file-backed store for dictionaries"""

    def __init__(self, filename, permissions=0o600):
        self.filename = filename
        self.permissions = permissions
        try:
            created = create_file_if_missing(filename, contents='{}')
            if created:
                # remove access to group
                os.chmod(filename, permissions)
        except Exception as e:
            import traceback
            _log.error(traceback.print_exc())
            raise RuntimeError("Failed to access KeyStore: {}".format(filename))

    def store(self, data):
        fd = os.open(self.filename, os.O_CREAT | os.O_WRONLY | os.O_TRUNC,
                     self.permissions)
        try:
            os.write(fd, jsonapi.dumpb(data, indent=4))
        finally:
            os.close(fd)

    def load(self):
        try:
            with open(self.filename, 'r') as json_file:
                return jsonapi.load(json_file)
        except ValueError:
            # If the file is empty jsonapi.load will raise ValueError
            return {}

    def remove(self, key):
        data = self.load()
        try:
            del data[key]
        except KeyError as e:
            msg = 'Key "{}" is not present in {}'.format(key, self.filename)
            raise KeyError(msg)
        else:
            self.store(data)

    def update(self, new_data):
        data = self.load()
        data.update(new_data)
        self.store(data)


class KeyStore(BaseJSONStore):
    """Handle generation, storage, and retrival of CURVE key pairs"""

    def __init__(self, filename=None, encoded_public=None, encoded_secret=None):
        if filename is None:
            filename = self.get_default_path()
        directory = os.path.dirname(filename)
        if os.path.basename(os.path.dirname(directory)) == KEYSTORES_DIRNAME:
            create_keystore_dir(directory)
        super(KeyStore, self).__init__(filename)
        if not self.isvalid():
            if encoded_public and encoded_secret:
                self.store({'public': encoded_public,
                            'secret': encode_key(encoded_secret)})
            else:
                _log.debug("calling generate from keystore")
                self.generate()

    @staticmethod
    def get_default_path():
        return os.path.join(get_home(), 'keystore')

    @staticmethod
    def get_agent_keystore_path(identity=None):
        if identity is None:
            raise AttributeError("invalid identity")
        return os.path.join(get_home(), f"keystores/{identity}/keystore.json")

    @staticmethod
    def generate_keypair_dict():
        """Generate and return new keypair as dictionary"""
        public, secret = curve_keypair()
        encoded_public = encode_key(public)
        encoded_secret = encode_key(secret)
        attempts = 0
        max_attempts = 3

        done = False
        while not done and attempts < max_attempts:
            # Keys that start with '-' are hard to use and cause issues with the platform
            if encoded_secret.startswith('-') or encoded_public.startswith('-'):
                # try generating public and secret key again
                public, secret = curve_keypair()
                encoded_public = encode_key(public)
                encoded_secret = encode_key(secret)
            else:
                done = True

        return {'public': encoded_public,
                'secret': encoded_secret}

    def generate(self):
        """Generate and store new key pair"""
        self.store(self.generate_keypair_dict())

    def _get_key(self, keyname):
        """Get key and make sure it's type is str (not unicode)

        The json module returns all strings as unicode type, but base64
        decode expects byte type as input. The conversion from unicode
        type to str type is safe in this case, because encode_key
        returns str type (ASCII characters only).
        """
        key = self.load().get(keyname, None)
        if key:
            try:
                key.encode('ascii')
            except UnicodeEncodeError:
                _log.warning(
                    'Non-ASCII character found for key {} in {}'
                    .format(keyname, self.filename))
                key = None
        return key

    @property
    def public(self):
        """Return encoded public key"""
        return self._get_key('public')

    @property
    def secret(self):
        """Return encoded secret key"""
        return self._get_key('secret')

    def isvalid(self):
        """Check if key pair is valid"""
        return self.public and self.secret


class KnownHostsStore(BaseJSONStore):
    """Handle storage and retrival of known hosts"""

    def __init__(self, filename=None):
        if filename is None:
            filename = os.path.join(get_home(), 'known_hosts')
        # all agents need read access to known_hosts file
        super(KnownHostsStore, self).__init__(filename, permissions=0o644)


    def add(self, addr, server_key):
        self.update({self._parse_addr(addr): server_key})

    def serverkey(self, addr):
        return self.load().get(self._parse_addr(addr), None)

    @staticmethod
    def _parse_addr(addr):
        if not "://" in addr:  # no schema urlparse parses it wrong and return port number as path
            addr = "//" + addr
        url = urllib.parse.urlparse(addr)
        if url.netloc:
            return url.netloc
        return url.path
