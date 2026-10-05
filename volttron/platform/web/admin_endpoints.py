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

import hmac
import logging
import os
import re
import secrets
import stat
from urllib.parse import parse_qs

from volttron.platform.agent.known_identities import PLATFORM_WEB, AUTH
from volttron.platform.jsonrpc import RemoteError

try:
    from jinja2 import FileSystemLoader, select_autoescape, TemplateNotFound
except ImportError:
    logging.getLogger().warning("Missing jinja2 library in admin_endpoints.py")

try:
    from passlib.hash import argon2
except ImportError:
    logging.getLogger().warning("Missing passlib library in admin_endpoints.py")

from watchdog_gevent import Observer
from volttron.platform.agent.web import Response

from volttron.platform import get_home
from volttron.platform import jsonapi
from volttron.utils import VolttronHomeFileReloader


_log = logging.getLogger(__name__)

SETUP_TOKEN_FILE = 'web-setup-token'


def template_env(env):
    return env['JINJA2_TEMPLATE_ENV']


class AdminEndpoints:

    def __init__(self, rmq_mgmt=None, ssl_public_key: bytes = None, rpc_caller=None):

        self._rpc_caller = rpc_caller
        self._rmq_mgmt = rmq_mgmt

        self._pending_auths = None
        self._denied_auths = None
        self._approved_auths = None

        if ssl_public_key is None:
            self._insecure_mode = True
        else:
            self._insecure_mode = False

        # must have a none value for when we don't have an ssl context available.
        if ssl_public_key is not None:
            if isinstance(ssl_public_key, bytes):
                self._ssl_public_key = ssl_public_key.decode('utf-8')
            elif isinstance(ssl_public_key, str):
                self._ssl_public_key = ssl_public_key

            else:
                raise ValueError("Invalid type for ssl_public_key")
        else:
            self._ssl_public_key = None

        self._userdict = {}
        self.reload_userdict()

        self._observer = Observer()
        self._observer.schedule(
            VolttronHomeFileReloader("web-users.json", self.reload_userdict),
            get_home()
        )
        self._observer.start()

    def reload_userdict(self):
        webuserpath = os.path.join(get_home(), 'web-users.json')
        if os.path.exists(webuserpath):
            with open(webuserpath) as fp:
                try:
                    self._userdict = jsonapi.loads(fp.read())
                except json.decoder.JSONDecodeError:
                    self._userdict = {}
                    # Keep same behavior as with PersistentDict
                    raise ValueError("File not in a supported format")

    def get_routes(self):
        """
        Returns a list of tuples with the routes for the administration endpoints
        available in it.

        :return:
        """
        return [
            (re.compile('^/admin.*'), 'callable', self.admin)
        ]

    @staticmethod
    def _setup_token_path() -> str:
        return os.path.join(get_home(), SETUP_TOKEN_FILE)

    def _ensure_setup_token(self) -> bool:
        """Create the one-time setup token file when it does not exist yet.

        Returns False when the file cannot be created, so setup is refused
        instead of left open without a token.
        """
        token_path = self._setup_token_path()
        if os.path.lexists(token_path):
            return True
        try:
            fd = os.open(token_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        except FileExistsError:
            return True
        except OSError as exc:
            _log.error("Web setup refused: cannot create the setup token file %s: %s", token_path, exc)
            return False
        try:
            with os.fdopen(fd, 'w') as fp:
                fp.write(secrets.token_urlsafe(32))
        except OSError as exc:
            _log.error("Web setup refused: cannot write the setup token file %s: %s", token_path, exc)
            try:
                os.remove(token_path)
            except OSError as remove_exc:
                _log.error("Cannot remove the incomplete setup token file %s: %s", token_path, remove_exc)
            return False
        _log.warning("No web users exist. Create the first administrator with the setup token in %s",
                     token_path)
        return True

    def _read_setup_token(self) -> str:
        """Read the setup token, refusing any file the platform user does not solely own.

        O_NONBLOCK keeps a FIFO planted at the path from blocking the server.
        Raises OSError or ValueError when the file must not be trusted.
        """
        fd = os.open(self._setup_token_path(), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as fp:
            st = os.fstat(fp.fileno())
            if not stat.S_ISREG(st.st_mode):
                raise ValueError("not a regular file")
            if st.st_uid != os.geteuid():
                raise ValueError("not owned by the platform user")
            if stat.S_IMODE(st.st_mode) != 0o600:
                raise ValueError(f"mode is {stat.S_IMODE(st.st_mode):o}, not 600")
            return fp.read().decode('ascii').strip()

    @staticmethod
    def _setup_page(env, status='200 OK'):
        template = template_env(env).get_template('first.html')
        return Response(template.render(), status=status, content_type="text/html")

    @staticmethod
    def _setup_unavailable():
        return Response('Service temporarily unavailable', status='503 Service Unavailable',
                        content_type='text/plain')

    def _create_first_admin(self, env, data):
        form = parse_qs(data)

        def field(name: str) -> str:
            # A repeated field is treated as absent rather than guessed at.
            values = form.get(name, [])
            return values[0] if len(values) == 1 else ''

        submitted_token = field('setup_token')
        username = field('username')
        pass1 = field('password1')
        pass2 = field('password2')
        remote = env.get('REMOTE_ADDR', 'unknown')
        token_path = self._setup_token_path()

        try:
            stored_token = self._read_setup_token()
        except FileNotFoundError:
            stored_token = ''
        except (OSError, ValueError) as exc:
            _log.error("Web setup refused: the setup token file %s is unusable: %s", token_path, exc)
            return self._setup_unavailable()

        # compare_digest('', '') is True, so both sides must be non-empty.
        if not (submitted_token and stored_token
                and hmac.compare_digest(submitted_token.encode('utf-8'), stored_token.encode('utf-8'))):
            _log.warning("Web setup refused: missing or wrong setup token from %s", remote)
            return self._setup_page(env, '403 Forbidden')

        if not username.strip() or not pass1:
            _log.warning("Web setup refused: blank username or password from %s", remote)
            return self._setup_page(env, '403 Forbidden')

        if pass1 != pass2:
            return self._setup_page(env)

        # Only one request can win this removal, so it precedes any write; nothing
        # between it and add_user yields to another greenlet.
        try:
            os.remove(token_path)
        except FileNotFoundError:
            _log.warning("Web setup refused: the setup token was already used, request from %s", remote)
            return self._setup_page(env, '403 Forbidden')
        except OSError as exc:
            _log.error("Web setup refused: cannot remove the setup token file %s: %s", token_path, exc)
            return self._setup_unavailable()

        # Another request or process may have written a user since this one
        # entered setup; writing now would replace that file.
        self.reload_userdict()
        if self._userdict:
            _log.warning("Web setup refused: a web user already exists, request from %s", remote)
            return self._setup_page(env, '403 Forbidden')

        _log.debug("Setting administrator password")
        self.add_user(username, pass1, groups=['admin', 'vui'], overwrite=False)
        return Response('', status='302', headers={'Location': '/admin/login.html'})

    def admin(self, env, data):
        if len(self._userdict) == 0:
            if not self._ensure_setup_token():
                return self._setup_unavailable()
            if env.get('REQUEST_METHOD') == 'POST':
                return self._create_first_admin(env, data)
            return self._setup_page(env)

        if 'login.html' in env.get('PATH_INFO') or '/admin/' == env.get('PATH_INFO'):
            template = template_env(env).get_template('login.html')
            _log.debug("Login.html: {}".format(env.get('PATH_INFO')))
            return Response(template.render(), content_type='text/html')

        return self.verify_and_dispatch(env, data)

    def verify_and_dispatch(self, env, data):
        """ Verify that the user is an admin and dispatch

        :param env: web environment
        :param data: data associated with a web form or json/xml request data
        :return: Response object.
        """
        from volttron.platform.web import get_bearer, NotAuthorized
        try:
            claims = self._rpc_caller(PLATFORM_WEB, 'get_user_claims', get_bearer(env)).get()
        except NotAuthorized:
            _log.error("Unauthorized user attempted to connect to {}".format(env.get('PATH_INFO')))
            return Response('<h1>Unauthorized User</h1>', status="401 Unauthorized")
        except RemoteError as e:
            if "ExpiredSignatureError" in e.exc_info["exc_type"]:
                _log.warning("Access token has expired! Please re-login to renew.")
                template = template_env(env).get_template('login.html')
                _log.debug("Login.html: {}".format(env.get('PATH_INFO')))
                return Response(template.render(), content_type='text/html')
            else:
                _log.error(e)

        # Make sure we have only admins for viewing this.
        if 'admin' not in claims.get('groups'):
            return Response('<h1>Unauthorized User</h1>', status="401 Unauthorized")

        path_info = env.get('PATH_INFO')
        if path_info.startswith('/admin/api/'):
            return self.__api_endpoint(path_info[len('/admin/api/'):], data)

        if path_info.endswith('html'):
            page = path_info.split('/')[-1]
            try:
                template = template_env(env).get_template(page)
            except TemplateNotFound:
                return Response("<h1>404 Not Found</h1>", status="404 Not Found")

            if page == 'pending_auth_reqs.html':
                try:
                    self._pending_auths = self._rpc_caller.call(AUTH, 'get_pending_authorizations').get(timeout=2)
                    self._denied_auths = self._rpc_caller.call(AUTH, 'get_denied_authorizations').get(timeout=2)
                    self._approved_auths = self._rpc_caller.call(AUTH, 'get_approved_authorizations').get(timeout=2)
                    # RMQ CSR Mapping
                    self._pending_auths = [{"user_id" if k == "identity" else "address" if "remote_ip_address" else k:v for k,v in output.items()} for output in self._pending_auths]
                    self._denied_auths = [{"user_id" if k == "identity" else "address" if "remote_ip_address" else k:v for k,v in output.items()} for output in self._denied_auths]
                    self._approved_auths = [{"user_id" if k == "identity" else "address" if "remote_ip_address" else k:v for k,v in output.items()} for output in self._approved_auths]
                except TimeoutError:
                    self._pending_auths = []
                    self._denied_auths = []
                    self._approved_auths = []
                except Exception as err:
                    _log.error(f"Error message is: {err}")
                # # When messagebus is rmq, include pending csrs in the output pending_auth_reqs.html page
                # if self._rmq_mgmt is not None:
                #     html = template.render(csrs=self._rpc_caller.call(AUTH, 'get_pending_csrs').get(timeout=4),
                #                            auths=self._pending_auths,
                #                            denied_auths=self._denied_auths,
                #                            approved_auths=self._approved_auths)
                # else:
                html = template.render(auths=self._pending_auths,
                                        denied_auths=self._denied_auths,
                                        approved_auths=self._approved_auths)
            else:
                # A template with no params.
                html = template.render()

            return Response(html)

        template = template_env(env).get_template('index.html')
        resp = template.render()
        return Response(resp)

    def __api_endpoint(self, endpoint, data):
        _log.debug("Doing admin endpoint {}".format(endpoint))
        if endpoint == 'certs':
            response = self.__cert_list_api()
        elif endpoint == 'pending_csrs':
            response = self.__pending_csrs_api()
        elif endpoint.startswith('approve_csr/'):
            response = self.__approve_csr_api(endpoint.split('/')[1])
        elif endpoint.startswith('deny_csr/'):
            response = self.__deny_csr_api(endpoint.split('/')[1])
        elif endpoint.startswith('delete_csr/'):
            response = self.__delete_csr_api(endpoint.split('/')[1])
        elif endpoint.startswith('approve_credential/'):
            response = self.__approve_credential_api(endpoint.split('/')[1])
        elif endpoint.startswith('deny_credential/'):
            response = self.__deny_credential_api(endpoint.split('/')[1])
        elif endpoint.startswith('delete_credential/'):
            response = self.__delete_credential_api(endpoint.split('/')[1])
        else:
            response = Response('{"status": "Unknown endpoint {}"}'.format(endpoint),
                                content_type="application/json")
        return response

    def __approve_csr_api(self, common_name):
        try:
            _log.debug("Creating cert and permissions for user: {}".format(common_name))
            self._rpc_caller.call(AUTH, 'approve_authorization', common_name).wait(timeout=4)
            data = dict(status=self._rpc_caller.call(AUTH, "get_authorization_status", common_name).get(timeout=2),
                        cert=self._rpc_caller.call(AUTH, "get_authorization", common_name).get(timeout=2))
        except ValueError as e:
            data = dict(status="ERROR", message=str(e))

        except TimeoutError as e:
            data = dict(status="ERROR", message=str(e))

        return Response(jsonapi.dumps(data), content_type="application/json")

    def __deny_csr_api(self, common_name):
        try:
            self._rpc_caller.call(AUTH, 'deny_authorization', common_name).wait(timeout=2)
            data = dict(status="DENIED",
                        message="The administrator has denied the request")
        except ValueError as e:
            data = dict(status="ERROR", message=str(e))

        except TimeoutError as e:
            data = dict(status="ERROR", message=str(e))

        return Response(jsonapi.dumps(data), content_type="application/json")

    def __delete_csr_api(self, common_name):
        try:
            self._rpc_caller.call(AUTH, 'delete_authorization', common_name).wait(timeout=2)
            data = dict(status="DELETED",
                        message="The administrator has denied the request")
        except ValueError as e:
            data = dict(status="ERROR", message=str(e))

        except TimeoutError as e:
            data = dict(status="ERROR", message=str(e))

        return Response(jsonapi.dumps(data), content_type="application/json")

    def __pending_csrs_api(self):
        try:
            data = self._rpc_caller.call(AUTH, 'get_pending_authorizations').get(timeout=4)

        except TimeoutError as e:
            data = dict(status="ERROR", message=str(e))

        return Response(jsonapi.dumps(data), content_type="application/json")

    def __cert_list_api(self):

        try:
            data = [dict(common_name=x.common_name) for x in
                    self._rpc_caller.call(AUTH, "get_approved_authorizations").get(timeout=2)]

        except TimeoutError as e:
            data = dict(status="ERROR", message=str(e))

        return Response(jsonapi.dumps(data), content_type="application/json")

    def __approve_credential_api(self, user_id):
        try:
            _log.debug("Creating credential and permissions for user: {}".format(user_id))
            self._rpc_caller.call(AUTH, 'approve_authorization', user_id).wait(timeout=4)
            data = dict(status='APPROVED',
                        message="The administrator has approved the request")
        except ValueError as e:
            data = dict(status="ERROR", message=str(e))

        except TimeoutError as e:
            data = dict(status="ERROR", message=str(e))

        return Response(jsonapi.dumps(data), content_type="application/json")

    def __deny_credential_api(self, user_id):
        try:
            self._rpc_caller.call(AUTH, 'deny_authorization', user_id).wait(timeout=2)
            data = dict(status="DENIED",
                        message="The administrator has denied the request")
        except ValueError as e:
            data = dict(status="ERROR", message=str(e))

        except TimeoutError as e:
            data = dict(status="ERROR", message=str(e))

        return Response(jsonapi.dumps(data), content_type="application/json")

    def __delete_credential_api(self, user_id):
        try:
            self._rpc_caller.call(AUTH, 'delete_authorization', user_id).wait(timeout=2)
            data = dict(status="DELETED",
                        message="The administrator has denied the request")
        except ValueError as e:
            data = dict(status="ERROR", message=str(e))

        except TimeoutError as e:
            data = dict(status="ERROR", message=str(e))

        return Response(jsonapi.dumps(data), content_type="application/json")

    def add_user(self, username, unencrypted_pw, groups=None, overwrite=False):
        if self._userdict.get(username) and not overwrite:
            raise ValueError(f"The user {username} is already present and overwrite not set to True")
        if groups is None:
            groups = []
        hashed_pass = argon2.hash(unencrypted_pw)
        self._userdict[username] = dict(
            hashed_password=hashed_pass,
            groups=groups
        )

        with open(os.path.join(get_home(), 'web-users.json'), 'w') as fp:
            fp.write(jsonapi.dumps(self._userdict, indent=2))
