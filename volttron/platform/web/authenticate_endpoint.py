import logging
import os
import re
import time
from urllib.parse import parse_qs
from datetime import datetime, timedelta
import json

import jwt
from jinja2 import Environment, FileSystemLoader, select_autoescape
from passlib.hash import argon2
from watchdog_gevent import Observer

from volttron.platform import get_home
from volttron.platform.agent.web import Response
from volttron.utils import VolttronHomeFileReloader
from volttron.utils.persistance import PersistentDict
from .token_revocation import (RevokedSessions, REVOKED_SESSIONS_FILE, SESSION_CLAIM, new_session_id,
                               session_id)

_log = logging.getLogger(__name__)


def printable_text(text):
    # Imported lazily: volttron.platform.web imports this module.
    from volttron.platform.web import printable_text as _printable_text
    return _printable_text(text)


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


MAX_USERNAME_LENGTH = 256
MAX_PASSWORD_LENGTH = 1024


class AuthenticateEndpoints:

    def __init__(self, tls_private_key=None, tls_public_key=None, web_secret_key=None, revoked_sessions=None,
                 on_revoke=None):
        """
        :param revoked_sessions: the RevokedSessions deny-list to record revocations in. The web service shares
            its own so that every token check sees them; by default a list persisted in VOLTTRON_HOME is used.
        :param on_revoke: optional callable(session_id) run after a session is revoked, e.g. to close websockets.
        """

        self.refresh_token_timeout = 240  # minutes before token expires. TODO: Should this be a setting somewhere?
        self.access_token_timeout = 15  # minutes before token expires. TODO: Should this be a setting somewhere?
        self._tls_private_key = tls_private_key
        self._tls_public_key = tls_public_key
        self._web_secret_key = web_secret_key
        if self._tls_private_key is None and self._web_secret_key is None:
            raise ValueError("Must have either ssl_private_key or web_secret_key specified!")
        if self._tls_private_key is not None and self._web_secret_key is not None:
            raise ValueError("Must use either ssl_private_key or web_secret_key not both!")
        if revoked_sessions is None:
            revoked_sessions = RevokedSessions(os.path.join(get_home(), REVOKED_SESSIONS_FILE))
        self._revoked_sessions = revoked_sessions
        self._on_revoke = on_revoke
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

    @property
    def revoked_sessions(self):
        return self._revoked_sessions

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

        _log.debug("Username is: {}".format(printable_text(username)))

        error = ""
        if username is None:
            error += "Invalid username passed"
        if not password:
            error += "Invalid password passed"

        if error:
            _log.error("Invalid parameters passed: {}".format(printable_text(error)))
            return Response(error, status='401')

        user = self.__get_user(username, password)
        if user is None:
            _log.error("No matching user for passed username: {}".format(printable_text(username)))
            return Response('', status='401')
        access_token, refresh_token = self._get_tokens(user)
        response = Response(json.dumps({"refresh_token": refresh_token, "access_token": access_token}),
                            content_type="application/json")
        return response

    def _get_tokens(self, claims):
        # One session id per login; renewed access tokens inherit it from the refresh token, so revoking the
        # session revokes every token minted for it.
        if session_id(claims) is None:
            claims[SESSION_CLAIM] = new_session_id()
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
        return access_token, refresh_token

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
        # The body is optional; a JSON body arrives already parsed only when the
        # request declared a JSON content type.
        if isinstance(data, str) and data.strip():
            try:
                data = json.loads(data)
            except ValueError:
                data = None
        elif not data:
            data = {}
        if not isinstance(data, dict):
            _log.error("Invalid request body sent to {}".format(printable_text(env.get('PATH_INFO'))))
            return Response('Unauthorized User', status="401 Unauthorized")
        current_access_token = data.get('current_access_token')
        from volttron.platform.web import get_bearer, get_user_claim_from_bearer, NotAuthorized
        try:
            # ValueError: an Authorization header that is not "<type> <token>".
            current_refresh_token = get_bearer(env)
        except (NotAuthorized, ValueError):
            _log.error("Unauthorized user attempted to connect to {}".format(printable_text(env.get('PATH_INFO'))))
            return Response('Unauthorized User', status="401 Unauthorized")
        try:
            claims = get_user_claim_from_bearer(current_refresh_token, web_secret_key=self._web_secret_key,
                                                tls_public_key=self._tls_public_key)
        except jwt.ExpiredSignatureError:
            _log.error("User attempted to connect to {} with an expired signature".format(
                printable_text(env.get('PATH_INFO'))))
            return Response('Unauthorized User', status="401 Unauthorized")

        except jwt.PyJWTError:
            _log.error("Invalid refresh token presented to {}".format(printable_text(env.get('PATH_INFO'))))
            return Response('Unauthorized User', status="401 Unauthorized")

        if claims.get('grant_type') != 'refresh_token' or not claims.get('groups'):
            return Response('Invalid refresh token.', status="401 Unauthorized")
        if not self._revoked_sessions.allows(claims):
            _log.warning("Refresh attempted with a revoked or unrevocable token at {}".format(
                printable_text(env.get('PATH_INFO'))))
            return Response('Unauthorized User', status="401 Unauthorized")
        # TODO: Consider blacklisting and reissuing refresh tokens also when used.
        new_access_token, _ = self._get_tokens(claims)
        if current_access_token:
            pass  # TODO: keep current subscriptions? blacklist old token?
        return Response(json.dumps({"access_token": new_access_token}), content_type="application/json")

    def revoke_auth_token(self, env, data):
        """
        Revokes the login session of the presented token (logout).  Request should contain:
            • Authorization: BEARER <jwt_access_token or jwt_refresh_token>

        Every token minted for that login - the access token, the refresh token and any access token renewed
        from it - is refused from then on, and websockets opened with them are closed. The token is read from
        the Authorization header only, never the cookie, so a request made by another site cannot log the
        user out.

        :return: 204 when the session is revoked (also when it already was); 401 when no valid token of this
            server is presented.
        """
        from volttron.platform.web import get_authorization_bearer, get_user_claim_from_bearer
        path = printable_text(env.get('PATH_INFO'))
        bearer = get_authorization_bearer(env)
        if not bearer:
            _log.error("Revocation request to {} without a bearer Authorization header".format(path))
            return Response('Unauthorized User', status="401 Unauthorized")
        try:
            claims = get_user_claim_from_bearer(bearer, web_secret_key=self._web_secret_key,
                                                tls_public_key=self._tls_public_key)
        except jwt.PyJWTError as err:
            _log.error("Revocation request to {} with a token that does not validate: {}".format(
                path, type(err).__name__))
            return Response('Unauthorized User', status="401 Unauthorized")
        sid = session_id(claims)
        if claims.get('grant_type') not in ('access_token', 'refresh_token') or sid is None:
            _log.error("Revocation request to {} with a token that is not a session token".format(path))
            return Response('Unauthorized User', status="401 Unauthorized")
        self._revoked_sessions.revoke(sid, self._session_end(claims))
        _log.info("Web session revoked.")
        if self._on_revoke is not None:
            try:
                self._on_revoke(sid)
            except Exception as err:
                # The deny-list is already written; a cleanup failure must not look like a failed logout.
                _log.error("Post-revocation cleanup failed: %s", type(err).__name__)
        return Response('', status='204 No Content', content_type='text/plain')

    def _session_end(self, claims):
        """Latest moment any token of the session can still be valid.

        The refresh token lives refresh_token_timeout past the login that minted it, and an access token renewed
        just before that lives access_token_timeout longer. The ``iat`` of any token of the session is at or
        after the login, so this is an upper bound whichever token was presented.
        """
        now = time.time()
        issued = claims.get('iat')
        if not isinstance(issued, (int, float)) or isinstance(issued, bool):
            issued = now
        return max(issued, now) + (self.refresh_token_timeout + self.access_token_timeout) * 60

    def authenticate_web_user(self, username, password):
        """Check a login against the user store without minting a token.

        Returns exactly {'user': ..., 'groups': [...]} for a valid pair and {}
        for anything else, including input that is not a string or is over
        the length bounds, so no hash runs on an oversized value.
        """
        if not (isinstance(username, str) and isinstance(password, str)):
            return {}
        if not username or not password:
            return {}
        if len(username) > MAX_USERNAME_LENGTH or len(password) > MAX_PASSWORD_LENGTH:
            return {}
        if not self._userdict:
            return {}
        record = self.__get_user(username, password)
        if record is None:
            return {}
        groups = record.get('groups', [])
        if not isinstance(groups, (list, tuple)) or not all(isinstance(g, str) for g in groups):
            return {}
        return {'user': username, 'groups': list(groups)}

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

