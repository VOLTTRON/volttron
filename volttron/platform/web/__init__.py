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

from http.cookies import SimpleCookie
import logging

from datetime import datetime
from volttron.platform import check_pyjwt

check_pyjwt()
import jwt

from . discovery import DiscoveryInfo, DiscoveryError

# Used outside so we make it available through this file.
from . platform_web_service import PlatformWebService

_log = logging.getLogger(__name__)


class NotAuthorized(Exception):
    pass


def get_bearer(env):

    # Test if HTTP_AUTHORIZATION header is passed
    http_auth = env.get('HTTP_AUTHORIZATION')
    if http_auth:
        auth_type, bearer = http_auth.split(' ')
        if auth_type.upper() != 'BEARER':
            raise NotAuthorized("Invalid HTTP_AUTHORIZATION header passed, must be Bearer")
        else:
            return bearer
    else:
        cookiestr = env.get('HTTP_COOKIE')
        if not cookiestr:
            raise NotAuthorized()
        cookie = SimpleCookie(cookiestr)
        if 'Bearer' in cookie:
            bearer = cookie.get('Bearer').value
            return bearer
        else:
            return None


def get_authorization_bearer(env):
    """Return the token from an ``Authorization: Bearer`` header, or None.

    Unlike get_bearer this never reads the cookie, which a browser attaches
    to requests that another site makes.
    """
    parts = (env.get('HTTP_AUTHORIZATION') or '').split(' ')
    if len(parts) != 2 or parts[0].upper() != 'BEARER' or not parts[1]:
        return None
    return parts[1]


def get_claim_groups(claims):
    """Return the ``groups`` claim when it is a list of str, else None."""
    if not isinstance(claims, dict):
        return None
    groups = claims.get('groups')
    if not isinstance(groups, list) or not all(isinstance(g, str) for g in groups):
        return None
    return groups


def get_media_type(env):
    """Return the request's media type, lower-cased, without parameters."""
    return (env.get('CONTENT_TYPE') or '').split(';')[0].strip().lower()


def printable_text(text, limit=200):
    """Reduce request-supplied text to one printable log line of at most limit chars."""
    return ''.join(c for c in str(text) if c.isprintable())[:limit]


def describe_call_error(error):
    """Name an RPC failure for a log line: the remote exception type for a
    RemoteError, else the local type. Never the message, which can carry data."""
    exc_info = getattr(error, 'exc_info', None)
    if isinstance(exc_info, dict) and isinstance(exc_info.get('exc_type'), str):
        # The remote side chooses this text: keep it to one printable line.
        return printable_text(exc_info['exc_type'], 100)
    return type(error).__name__


def get_user_claim_from_bearer(bearer, web_secret_key=None, tls_public_key=None):
    if web_secret_key is None and tls_public_key is None:
        raise ValueError("web_secret_key or tls_public_key must be set")
    if web_secret_key is not None and tls_public_key is not None:
        raise ValueError("web_secret_key or tls_public_key must be set not both")

    if web_secret_key is not None:
        algorithm = 'HS256'
        pubkey = web_secret_key
    else:
        algorithm = 'RS256'
        pubkey = tls_public_key
        # if isinstance(tls_public_key, str):
        #     pubkey = CertWrapper.load_cert(tls_public_key)

    claims = jwt.decode(bearer, pubkey, algorithms=[algorithm])
    return claims
