# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

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
#}}}


"""Module for storing local public and secret keys and remote public keys"""


from volttron.platform import jsonapi
import logging
import os
import urllib.parse

from zmq import curve_keypair

from .agent.utils import create_file_if_missing
from .vip.socket import encode_key
from volttron.platform import get_home

_log = logging.getLogger(__name__)


class BaseJSONStore(object):
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
        url = urllib.parse.urlparse(addr)
        if url.netloc:
            return url.netloc
        return url.path
