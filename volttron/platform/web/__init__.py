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
