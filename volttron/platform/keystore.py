# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

#}}}


"""Module for storing local public and secret keys and remote public keys"""


import json
import logging
import os
import urlparse

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
        create_file_if_missing(filename)
        os.chmod(filename, permissions)

    def store(self, data):
        fd = os.open(self.filename, os.O_CREAT | os.O_WRONLY, self.permissions)
        try:
            os.write(fd, json.dumps(data, indent=4))
        finally:
            os.close(fd)

    def load(self):
        try:
            with open(self.filename, 'r') as json_file:
                return json.load(json_file)
        except IOError:
            return {}
        except ValueError:
            return {}

    def update(self, new_data):
        data = self.load()
        data.update(new_data)
        self.store(data)


class KeyStore(BaseJSONStore):
    """Handle generation, storage, and retrival of CURVE key pairs"""

    def __init__(self, filename=None):
        if filename is None:
            filename = os.path.join(get_home(), 'keystore')
        super(KeyStore, self).__init__(filename)
        if not self.isvalid():
            self.generate()

    def generate(self):
        """Generate new key pair"""
        public, secret = curve_keypair()
        self.store({'public': encode_key(public),
                    'secret': encode_key(secret)})

    def _get_key(self, keyname):
        """Get key and make sure it's type is str (not unicode)

        The json module returns all strings as unicode type, but base64
        decode expects str type as input. The conversion from unicode
        type to str type is safe in this case, because encode_key
        returns str type (ASCII characters only).
        """
        key = self.load().get(keyname, None)
        if key:
            try:
                key = str(key)
            except UnicodeEncodeError:
                _log.warning(
                    'Non-ASCII character found for key {} in {}'
                    .format(keyname, self.filename))
                key = None
        return key

    def public(self):
        """Return encoded public key"""
        return self._get_key('public')

    def secret(self):
        """Return encoded secret key"""
        return self._get_key('secret')

    def isvalid(self):
        """Check if key pair is valid"""
        return self.public() and self.secret()


class KnownHostsStore(BaseJSONStore):
    """Handle storage and retrival of known hosts"""

    def __init__(self, filename=None):
        if filename is None:
            filename = os.path.join(get_home(), 'known_hosts')
        super(KnownHostsStore, self).__init__(filename)

    def add(self, addr, server_key):
        self.update({self._parse_addr(addr): server_key})

    def serverkey(self, addr):
        return self.load().get(self._parse_addr(addr), None)

    @staticmethod
    def _parse_addr(addr):
        url = urlparse.urlparse(addr)
        if url.netloc:
            return url.netloc
        return url.path
