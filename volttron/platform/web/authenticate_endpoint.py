import logging
import os
import re
from urllib.parse import parse_qs
from datetime import datetime, timedelta
import json

import jwt
from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateNotFound
from passlib.hash import argon2
from watchdog_gevent import Observer

from volttron.platform import get_home
from volttron.platform.agent.web import Response
from volttron.utils import VolttronHomeFileReloader
from volttron.utils.persistance import PersistentDict

_log = logging.getLogger(__name__)


__PACKAGE_DIR__ = os.path.dirname(os.path.abspath(__file__))
__TEMPLATE_DIR__ = os.path.join(__PACKAGE_DIR__, "templates")
__STATIC_DIR__ = os.path.join(__PACKAGE_DIR__, "static")


# Our admin interface will use Jinja2 templates based upon the above paths
# reference api for using Jinja2 http://jinja.pocoo.org/docs/2.10/api/
# Using the FileSystemLoader instead of the package loader in this case however.
tplenv = Environment(
    loader=FileSystemLoader(__TEMPLATE_DIR__),
    autoescape=select_autoescape(['html', 'xml'])
)


class AuthenticateEndpoints(object):

    def __init__(self, tls_private_key=None, tls_public_key=None, web_secret_key=None):

        self.refresh_token_timeout = 240  # minutes before token expires. TODO: Should this be a setting somewhere?
        self.access_token_timeout = 15  # minutes before token expires. TODO: Should this be a setting somewhere?
        self._tls_private_key = tls_private_key
        self._tls_public_key = tls_public_key
        self._web_secret_key = web_secret_key
        if self._tls_private_key is None and self._web_secret_key is None:
            raise ValueError("Must have either ssl_private_key or web_secret_key specified!")
        if self._tls_private_key is not None and self._web_secret_key is not None:
            raise ValueError("Must use either ssl_private_key or web_secret_key not both!")
        self._userdict = None
        self.reload_userdict()
        self._observer = Observer()
        self._observer.schedule(
            VolttronHomeFileReloader("web-users.json", self.reload_userdict),
            get_home()
        )
        self._observer.start()

    def reload_userdict(self):
        webuserpath = os.path.join(get_home(), 'web-users.json')
        self._userdict = PersistentDict(webuserpath)

    def get_routes(self):
        """
        Returns a list of tuples with the routes for authentication.

        Tuple should have the following:

            - regular expression for calling the endpoint
            - 'callable' keyword specifying that a method is being specified
            - the method that should be used to call when the regular expression matches

        code:

            return [
                (re.compile('^/csr/request_new$'), 'callable', self._csr_request_new)
            ]

        :return:
        """
        return [
            (re.compile('^/authenticate'), 'callable', self.handle_authenticate)
        ]

    def handle_authenticate(self, env, data):
        """
        Callback for /authenticate endpoint.

        Routes request based on HTTP method and returns a text/plain encoded token or error.

        :param env:
        :param data:
        :return: Response
        """
        method = env.get('REQUEST_METHOD')
        if method == 'POST':
            response = self.get_auth_tokens(env, data)
        elif method == 'PUT':
            response = self.renew_auth_token(env, data)
        elif method == 'DELETE':
            response = self.revoke_auth_token(env, data)
        else:
            error = f"/authenticate endpoint accepts only POST, PUT, or DELETE methods. Received: {method}"
            _log.warning(error)
            return Response(error, status='405 Method Not Allowed', content_type='text/plain')
        return response

    def get_auth_tokens(self, env, data):
        """
        Creates an authentication refresh and acccss tokens to be returned to the caller.  The
        response will be a text/plain encoded user.  Data should contain:
        {
            "username": "<username>",
            "password": "<password>"
        }
        :param env:
        :param data:
        :return:
        """

        assert len(self._userdict) > 0, "No users in user dictionary, set the administrator password first!"

        if not isinstance(data, dict):
            _log.debug("data is not a dict, decoding")
            decoded = dict((k, v if len(v) > 1 else v[0])
                           for k, v in parse_qs(data).items())

            username = decoded.get('username')
            password = decoded.get('password')

        else:
            username = data.get('username')
            password = data.get('password')

        _log.debug("Username is: {}".format(username))

        error = ""
        if username is None:
            error += "Invalid username passed"
        if not password:
            error += "Invalid password passed"

        if error:
            _log.error("Invalid parameters passed: {}".format(error))
            return Response(error, status='401')

        user = self.__get_user(username, password)
        if user is None:
            _log.error("No matching user for passed username: {}".format(username))
            return Response('', status='401')
        access_token, refresh_token = self._get_tokens(user)
        response = Response(json.dumps({"refresh_token": refresh_token, "access_token": access_token}),
                            content_type="application/json")
        return response

    def _get_tokens(self, claims):
        now = datetime.utcnow()
        claims['iat'] = now
        claims['nbf'] = now
        claims['exp'] = now + timedelta(minutes=self.access_token_timeout)
        claims['grant_type'] = 'access_token'
        algorithm = 'RS256' if self._tls_private_key is not None else 'HS256'
        encode_key = self._tls_private_key if algorithm == 'RS256' else self._web_secret_key
        access_token = jwt.encode(claims, encode_key, algorithm=algorithm)
        claims['exp'] = now + timedelta(minutes=self.refresh_token_timeout)
        claims['grant_type'] = 'refresh_token'
        refresh_token = jwt.encode(claims, encode_key, algorithm=algorithm)
        return access_token.decode('utf-8'), refresh_token.decode('utf8')

    def renew_auth_token(self, env, data):
        """
        Creates a new authentication access token to be returned to the caller.  The
        response will be a text/plain encoded user.  Request should contain:
            • Content Type: application/json
            • Authorization: BEARER <jwt_refresh_token>
            • Body (optional):
                {
                "current_access_token": "<jwt_access_token>"
                }

        :param env:
        :param data:
        :return:
        """
        current_access_token = data.get('current_access_token')
        from volttron.platform.web import get_bearer, get_user_claim_from_bearer, NotAuthorized
        try:
            current_refresh_token = get_bearer(env)
            claims = get_user_claim_from_bearer(current_refresh_token, web_secret_key=self._web_secret_key,
                                                tls_public_key=self._tls_public_key)
        except NotAuthorized:
            _log.error("Unauthorized user attempted to connect to {}".format(env.get('PATH_INFO')))
            return Response('Unauthorized User', status="401 Unauthorized")

        if claims.get('grant_type') != 'refresh_token' or not claims.get('groups'):
            return Response('Invalid refresh token.', status="401 Unauthorized")
        else:
            # TODO: Consider blacklisting and reissuing refresh tokens also when used.
            new_access_token, _ = self._get_tokens(claims)
            if current_access_token:
                pass  # TODO: keep current subscriptions? blacklist old token?
            return Response(json.dumps({"access_token": new_access_token}), content_type="application/json")

    def revoke_auth_token(self, env, data):
        # TODO: Blacklist old token? Immediately close websockets?
        return Response('DELETE /authenticate is not yet implemented', status='501 Not Implemented',
                        content_type='text/plain')

    def __get_user(self, username, password):
        """
        Retrieve user from the user store based upon username/password

        The hashed_password will not be returned with the value in the user
        object.

        If there is not a username/password that match return None.

        :param username:
        :param password:
        :return:
        """
        user = self._userdict.get(username)
        if user is not None:
            hashed_pass = user.get('hashed_password')
            if hashed_pass and argon2.verify(password, hashed_pass):
                usr_cpy = user.copy()
                del usr_cpy['hashed_password']
                return usr_cpy
        return None

