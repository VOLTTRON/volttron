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

import random
import gevent
from gevent import time
from volttron.platform.vip.agent.core import ZMQCore
from volttron.platform.vip.socket import encode_key, BASE64_ENCODED_CURVE_KEY_LEN

_log = logging.getLogger(__name__)


#ZMQAuthorization(BaseAuthorization)
#ZMQ/ZAPAuthentication(BaseAuthentication)

def setup_zap(self, sender, **kwargs):
    self.zap_socket = ZMQCore.Socket(zmq.Context.instance(), zmq.ROUTER)
    self.zap_socket.bind("inproc://zeromq.zap.01")
    # if self.allow_any:
    #     _log.warning("insecure permissive authentication enabled")
    # if self.core.messagebus == "rmq":
    #     self.vip.peerlist.onadd.connect(self._check_topic_rules)


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
    if self.core.messagebus == "rmq":
        # Check the topic permissions of all the connected agents
        self._check_rmq_topic_permissions()
    else:
        self._send_protected_update_to_pubsub(self._protected_topics)

    while True:
        events = sock.poll(timeout)
        now = time.time()
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
                if self._setup_mode:
                    self._update_auth_entry(
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
                    self._update_auth_pending(
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
    if self.is_zap_required and self._zap_greenlet is not None:
        self._zap_greenlet.kill()

def unbind_zap(self, sender, **kwargs):
    if self.is_zap_required and self.zap_socket is not None:
        self.zap_socket.unbind("inproc://zeromq.zap.01")

def start_zap(self, sender, **kwargs):
    if self.auth_protocol:
        self.init_auth_protocol()