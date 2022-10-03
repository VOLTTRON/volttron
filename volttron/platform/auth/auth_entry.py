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
import re
from typing import Optional
import uuid

from volttron.platform.vip.socket import BASE64_ENCODED_CURVE_KEY_LEN
from volttron.platform.auth.auth_utils import isregex
from volttron.platform.auth.auth_exception import AuthException

_log = logging.getLogger(__name__)


class String(str):
    def __new__(cls, value):
        obj = super(String, cls).__new__(cls, value)
        if isregex(obj):
            obj.regex = regex = re.compile("^" + obj[1:-1] + "$")
            obj.match = lambda val: bool(regex.match(val))
        return obj

    def match(self, value):
        return value == self


class List(list):
    def match(self, value):
        for elem in self:
            if elem.match(value):
                return True
        return False


class AuthEntryInvalid(AuthException):
    """Exception for invalid AuthEntry objects"""
    pass


class AuthEntry(object):
    """
    An authentication entry contains fields for authenticating and
    granting permissions to an agent that connects to the platform.

    :param str domain: Name assigned to locally bound address
    :param str address: Remote address of the agent
    :param str mechanism: Authentication mechanism, valid options are
        'NULL' (no authentication), 'PLAIN' (username/password),
        'CURVE' (CurveMQ public/private keys)
    :param str credentials: Value depends on `mechanism` parameter:
        `None` if mechanism is 'NULL'; password if mechanism is
        'PLAIN'; encoded public key if mechanism is 'CURVE' (see
        :py:meth:`volttron.platform.vip.socket.encode_key` for method
        to encode public key)
    :param str user_id: Name to associate with agent (Note: this does
        not have to match the agent's VIP identity)
    :param str identity: This does match the agent's VIP identity
    :param list capabilities: Authorized capabilities for this agent
    :param list roles: Authorized roles for this agent. (Role names map
        to a set of capabilities)
    :param list groups: Authorized groups for this agent. (Group names
        map to a set of roles)
    :param list rpc_method_authorizations: Authorized
        capabilities for this agent's rpc methods
    :param str comments: Comments to associate with entry
    :param bool enabled: Entry will only be used if this value is True
    :param kwargs: These extra arguments will be ignored
    """

    def __init__(
            self,
            domain=None,
            address=None,
            mechanism="CURVE",
            credentials=None,
            user_id=None,
            identity=None,
            groups=None,
            roles=None,
            capabilities: Optional[dict] = None,
            rpc_method_authorizations=None,
            comments=None,
            enabled=True,
            **kwargs,
    ):
        """Initialize AuthEntry."""
        self.domain = AuthEntry._build_field(domain)
        self.address = AuthEntry._build_field(address)
        self.mechanism = mechanism
        self.credentials = AuthEntry._build_field(credentials)
        self.groups = AuthEntry._build_field(groups) or []
        self.roles = AuthEntry._build_field(roles) or []
        self.capabilities = (
            AuthEntry.build_capabilities_field(capabilities) or {}
        )
        self.rpc_method_authorizations = (
            AuthEntry.build_rpc_authorizations_field(rpc_method_authorizations)
            or {}
        )
        self.comments = AuthEntry._build_field(comments)
        if user_id is None:
            user_id = str(uuid.uuid4())
        self.user_id = user_id
        self.identity = identity
        self.enabled = enabled
        if kwargs:
            _log.debug(
                "auth record has unrecognized keys: %r" % (list(kwargs.keys()),)
            )
        self._check_validity()

    def __lt__(self, other):
        """Entries with non-regex credentials will be less than regex
        credentials. When sorted, the non-regex credentials will be
        checked first."""
        try:
            self.credentials.regex
        except AttributeError:
            return True
        return False

    @staticmethod
    def _build_field(value):
        if not value:
            return None
        if isinstance(value, str):
            return String(value)
        return List(String(elem) for elem in value)

    @staticmethod
    def build_capabilities_field(value: Optional[dict]):
        # _log.debug("_build_capabilities {}".format(value))

        if not value:
            return None

        if isinstance(value, list):
            result = dict()
            for elem in value:
                # update if it is not there or if existing entry doesn't
                # have args.
                # i.e. capability with args can override capability str
                temp = result.update(AuthEntry._get_capability(elem))
                if temp and result[next(iter(temp))] is None:
                    result.update(temp)
            _log.debug("Returning field _build_capabilities {}".format(result))
            return result
        else:
            return AuthEntry._get_capability(value)

    @staticmethod
    def _get_capability(value):
        err_message = (
            "Invalid capability value: {} of type {}. Capability "
            "entries can only be a string or "
            "dictionary or list containing string/dictionary. "
            "dictionaries should be of the format {"
            "'capability_name':None} or "
            "{'capability_name':{'arg1':'value',...}"
        )
        if isinstance(value, str):
            return {value: None}
        elif isinstance(value, dict):
            return value
        else:
            raise AuthEntryInvalid(err_message.format(value, type(value)))

    def add_capabilities(self, capabilities):
        temp = AuthEntry.build_capabilities_field(capabilities)
        if temp:
            self.capabilities.update(temp)

    @staticmethod
    def build_rpc_authorizations_field(value):
        """Returns auth entry's rpc method authorizations value if valid."""
        if not value:
            return None
        return AuthEntry._get_rpc_method_authorizations(value)

    @staticmethod
    def _get_rpc_method_authorizations(value):
        """Returns auth entry's rpc method authorizations value if valid."""
        err_message = (
            "Invalid rpc method authorization value: {} "
            "of type {}. Authorized rpc method entries can "
            "only be a dictionary. Dictionaries should be of "
            "the format: "
            "{'method1:[list of capabilities], 'method2: [], ...}"
        )
        if isinstance(value, dict):
            return value
        else:
            raise AuthEntryInvalid(err_message.format(value, type(value)))

    def match(self, domain, address, mechanism, credentials):
        return (
            (self.domain is None or self.domain.match(domain))
            and (self.address is None or self.address.match(address))
            and self.mechanism == mechanism
            and (
                self.mechanism == "NULL"
                or (
                    len(self.credentials) > 0
                    and self.credentials.match(credentials[0])
                )
            )
        )

    def __str__(self):
        return (
            "domain={0.domain!r}, address={0.address!r}, "
            "mechanism={0.mechanism!r}, credentials={0.credentials!r}, "
            "user_id={0.user_id!r}, "
            "capabilities={0.capabilities!r}".format(self)
        )

    def __repr__(self):
        cls = self.__class__
        return "%s.%s(%s)" % (cls.__module__, cls.__name__, self)

    @staticmethod
    def valid_credentials(cred, mechanism="CURVE"):
        """Raises AuthEntryInvalid if credentials are invalid."""
        AuthEntry.valid_mechanism(mechanism)
        if mechanism == "NULL":
            return
        if cred is None:
            raise AuthEntryInvalid(
                "credentials parameter is required for mechanism {}".format(
                    mechanism
                )
            )
        if isregex(cred):
            return
        if mechanism == "CURVE" and len(cred) != BASE64_ENCODED_CURVE_KEY_LEN:
            raise AuthEntryInvalid("Invalid CURVE public key {}")

    @staticmethod
    def valid_mechanism(mechanism):
        """Raises AuthEntryInvalid if mechanism is invalid."""
        if mechanism not in ("NULL", "PLAIN", "CURVE"):
            raise AuthEntryInvalid(
                'mechanism must be either "NULL", "PLAIN" or "CURVE"'
            )

    def _check_validity(self):
        """Raises AuthEntryInvalid if entry is invalid."""
        AuthEntry.valid_credentials(self.credentials, self.mechanism)


