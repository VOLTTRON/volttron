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
from dataclasses import dataclass
import os
import random
import uuid
import bisect
from urllib.parse import urlsplit, parse_qs, urlunsplit
import gevent
import gevent.time
from pytest import param
from zmq import green as zmq
from zmq.green import ZMQError, EAGAIN, ENOTSOCK
from zmq.utils.monitor import recv_monitor_message
import volttron.platform
from volttron.platform.auth.auth_utils import dump_user, load_user
from volttron.platform.auth.auth_protocols.auth_protocol import BaseAuthorization, BaseAuthentication
from volttron.platform.keystore import KeyStore, KnownHostsStore
from volttron.platform.parameters import Parameters
from volttron.platform.vip.agent.core import ZMQCore
from volttron.platform.vip.socket import encode_key, BASE64_ENCODED_CURVE_KEY_LEN
from volttron.platform.agent.utils import watch_file

_log = logging.getLogger(__name__)

@dataclass
class ZMQClientParameters(Parameters):
    address: str = None 
    identity: str = None
    publickey: str = None
    secretkey: str = None
    serverkey: str = None
    volttron_home: str = os.path.abspath(volttron.platform.get_home())
    agent_uuid: str = None



# ZMQAuthorization(BaseAuthorization)
# ZMQClientAuthentication(BaseAuthentication) - Client create and verify keys
# ZMQServerAuthentication(object) - Zap loop (Auth File Entries)
# ZMQServerAuthorization - Approve, deny, delete certs
# ZMQParameters(Parameters)
class ZMQClientAuthentication(BaseAuthentication):
    def __init__(self, params=ZMQClientParameters()):
        super(ZMQClientAuthentication).__init__(self, params=params)
        self.address = params.address
        self.identity = params.identity
        self.agent_uuid = params.agent_uuid
        self.publickey = params.publickey
        self.secretkey = params.secretkey
        self.serverkey = params.serverkey
        self.volttron_home = params.volttron_home

# Make Common (set_parameters? - use Parameters class)
    def create_authenticated_address(self):
        """Implements logic for setting encryption keys and putting
        those keys in the parameters of the VIP address
        """
        self._set_server_key()
        self._set_public_and_secret_keys()

        if self.publickey and self.secretkey and self.serverkey:
            self._add_keys_to_addr()
        return self.address
        
    def _add_keys_to_addr(self):
        '''Adds public, secret, and server keys to query in VIP address if
        they are not already present'''

        def add_param(query_str, key, value):
            query_dict = parse_qs(query_str)
            if not value or key in query_dict:
                return ''
            # urlparse automatically adds '?', but we need to add the '&'s
            return '{}{}={}'.format('&' if query_str else '', key, value)

        url = list(urlsplit(self.address))

        if url[0] in ['tcp', 'ipc']:
            url[3] += add_param(url[3], 'publickey', self.publickey)
            url[3] += add_param(url[3], 'secretkey', self.secretkey)
            url[3] += add_param(url[3], 'serverkey', self.serverkey)
            self.address = str(urlunsplit(url))
    
    def _get_keys_from_keystore(self):
        '''Returns agent's public and secret key from keystore'''
        if self.agent_uuid:
            # this is an installed agent, put keystore in its dist-info
            current_directory = os.path.abspath(os.curdir)
            keystore_dir = os.path.join(current_directory,
                                        "{}.dist-info".format(os.path.basename(current_directory)))
        elif self.identity is None:
            raise ValueError("Agent's VIP identity is not set")
        else:
            if not self.volttron_home:
                raise ValueError('VOLTTRON_HOME must be specified.')
            keystore_dir = os.path.join(
                self.volttron_home, 'keystores',
                self.identity)

        keystore_path = os.path.join(keystore_dir, 'keystore.json')
        keystore = KeyStore(keystore_path)
        return keystore.public, keystore.secret
    
    def _set_public_and_secret_keys(self):
        if self.publickey is None or self.secretkey is None:
            self.publickey, self.secretkey, _ = self._get_keys_from_addr()
        if self.publickey is None or self.secretkey is None:
            self.publickey, self.secretkey = self._get_keys_from_keystore()

    def _set_server_key(self):
        if self.serverkey is None:
            self.serverkey = self._get_keys_from_addr()[2]
        known_serverkey = self._get_serverkey_from_known_hosts()

        if (self.serverkey is not None and known_serverkey is not None
                and self.serverkey != known_serverkey):
            raise Exception("Provided server key ({}) for {} does "
                            "not match known serverkey ({}).".format(
                self.serverkey, self.address, known_serverkey))

        # Until we have containers for agents we should not require all
        # platforms that connect to be in the known host file.
        # See issue https://github.com/VOLTTRON/volttron/issues/1117
        if known_serverkey is not None:
            self.serverkey = known_serverkey

    def _get_serverkey_from_known_hosts(self):
        known_hosts_file = os.path.join(self.volttron_home, 'known_hosts')
        known_hosts = KnownHostsStore(known_hosts_file)
        return known_hosts.serverkey(self.address)

    def _get_keys_from_addr(self):
        url = list(urlsplit(self.address))
        query = parse_qs(url[3])
        publickey = query.get('publickey', [None])[0]
        secretkey = query.get('secretkey', [None])[0]
        serverkey = query.get('serverkey', [None])[0]
        return publickey, secretkey, serverkey

class ZMQServerAuthentication(object):
    """
    Implementation of the Zap Loop used by AuthService 
    for handling ZMQ Authentication on the VOLTTRON Server Instance
    """
    def __init__(self, auth_service=None) -> None:
        self.auth_service = auth_service
        self.zap_socket = None
        self._zap_greenlet = None
        self._is_connected = False


    def setup_zap(self, sender, **kwargs):
        self.zap_socket = zmq.Socket(zmq.Context.instance(), zmq.ROUTER)
        self.zap_socket.bind("inproc://zeromq.zap.01")
        if self.auth_service.allow_any:
            _log.warning("insecure permissive authentication enabled")
        self.auth_service.read_auth_file()
        self.auth_service._read_protected_topics_file()
        self.auth_service.core.spawn(watch_file, self.auth_service.auth_file_path, self.auth_service.read_auth_file)
        self.auth_service.core.spawn(
            watch_file,
            self.auth_service._protected_topics_file_path,
            self.auth_service._read_protected_topics_file,
        )
        if self.auth_service.core.messagebus == "rmq":
            self.auth_service.vip.peerlist.onadd.connect(self.auth_service._check_topic_rules)


    def authenticate(self, domain, address, mechanism, credentials):
        for entry in self.auth_service.auth_entries:
            if entry.match(domain, address, mechanism, credentials):
                return entry.user_id or dump_user(
                    domain, address, mechanism, *credentials[:1]
                )
        if mechanism == "NULL" and address.startswith("localhost:"):
            parts = address.split(":")[1:]
            if len(parts) > 2:
                pid = int(parts[2])
                agent_uuid = self.auth_service.aip.agent_uuid_from_pid(pid)
                if agent_uuid:
                    return dump_user(domain, address, "AGENT", agent_uuid)
            uid = int(parts[0])
            if uid == os.getuid():
                return dump_user(domain, address, mechanism, *credentials[:1])
        if self.auth_service.allow_any:
            return dump_user(domain, address, mechanism, *credentials[:1])

    def zap_loop(self, sender, **kwargs):
        """
        The zap loop is the starting of the authentication process for
        the VOLTTRON zmq message bus.  It talks directly with the low
        level socket so all responses must be byte like objects, in
        this case we are going to send zmq frames across the wire.

        :param sender:
        :param kwargs:
        :return:
        """
        self._is_connected = True
        self._zap_greenlet = gevent.getcurrent()
        sock = self.zap_socket
        blocked = {}
        wait_list = []
        timeout = None

        self.auth_service._send_protected_update_to_pubsub(self.auth_service._protected_topics)

        while True:
            events = sock.poll(timeout)
            now = gevent.time.time()
            if events:
                zap = sock.recv_multipart()

                version = zap[2]
                if version != b"1.0":
                    continue
                domain, address, userid, kind = zap[4:8]
                credentials = zap[8:]
                if kind == b"CURVE":
                    credentials[0] = encode_key(credentials[0])
                elif kind not in [b"NULL", b"PLAIN"]:
                    continue
                response = zap[:4]
                domain = domain.decode("utf-8")
                address = address.decode("utf-8")
                kind = kind.decode("utf-8")
                user = self.authenticate(domain, address, kind, credentials)
                _log.info(
                    "AUTH: After authenticate user id: %r, %r", user, userid
                )
                if user:
                    _log.info(
                        "authentication success: userid=%r domain=%r, "
                        "address=%r, "
                        "mechanism=%r, credentials=%r, user=%r",
                        userid,
                        domain,
                        address,
                        kind,
                        credentials[:1],
                        user,
                    )
                    response.extend(
                        [b"200", b"SUCCESS", user.encode("utf-8"), b""]
                    )
                    sock.send_multipart(response)
                else:
                    userid = str(uuid.uuid4())
                    _log.info(
                        "authentication failure: userid=%r, domain=%r, "
                        "address=%r, "
                        "mechanism=%r, credentials=%r",
                        userid,
                        domain,
                        address,
                        kind,
                        credentials,
                    )
                    # If in setup mode, add/update auth entry
                    if self.auth_service._setup_mode:
                        self.auth_service._update_auth_entry(
                            domain, address, kind, credentials[0], userid
                        )
                        _log.info(
                            "new authentication entry added in setup mode: "
                            "domain=%r, address=%r, "
                            "mechanism=%r, credentials=%r, user_id=%r",
                            domain,
                            address,
                            kind,
                            credentials[:1],
                            userid,
                        )
                        response.extend([b"200", b"SUCCESS", b"", b""])
                        _log.debug("AUTH response: {}".format(response))
                        sock.send_multipart(response)
                    else:
                        if type(userid) == bytes:
                            userid = userid.decode("utf-8")
                        self.auth_service._update_auth_pending(
                            domain, address, kind, credentials[0], userid
                        )

                    try:
                        expire, delay = blocked[address]
                    except KeyError:
                        delay = random.random()
                    else:
                        if now >= expire:
                            delay = random.random()
                        else:
                            delay *= 2
                            if delay > 100:
                                delay = 100
                    expire = now + delay
                    bisect.bisect(wait_list, (expire, address, response))
                    blocked[address] = expire, delay
            while wait_list:
                expire, address, response = wait_list[0]
                if now < expire:
                    break
                wait_list.pop(0)
                response.extend([b"400", b"FAIL", b"", b""])
                sock.send_multipart(response)
                try:
                    if now >= blocked[address][0]:
                        blocked.pop(address)
                except KeyError:
                    pass
            timeout = (wait_list[0][0] - now) if wait_list else None


    def stop_zap(self, sender, **kwargs):
        if self._zap_greenlet is not None:
            self._zap_greenlet.kill()

    def unbind_zap(self, sender, **kwargs):
        if self.zap_socket is not None:
            self.zap_socket.unbind("inproc://zeromq.zap.01")