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
import os
import re
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
from volttron.utils.persistance import PersistentDict


_log = logging.getLogger(__name__)


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
        self._userdict = PersistentDict(webuserpath, format="json")

    def get_routes(self):
        """
        Returns a list of tuples with the routes for the administration endpoints
        available in it.

        :return:
        """
        return [
            (re.compile('^/admin.*'), 'callable', self.admin)
        ]

    def admin(self, env, data):
        if len(self._userdict) == 0:
            if env.get('REQUEST_METHOD') == 'POST':
                decoded = dict((k, v if len(v) > 1 else v[0])
                               for k, v in parse_qs(data).items())
                username = decoded.get('username')
                pass1 = decoded.get('password1')
                pass2 = decoded.get('password2')

                if pass1 == pass2 and pass1 is not None:
                    _log.debug("Setting administrator password")
                    self.add_user(username, pass1, groups=['admin', 'vui'])
                    return Response('', status='302', headers={'Location': '/admin/login.html'})

            template = template_env(env).get_template('first.html')
            return Response(template.render(), content_type="text/html")

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

        self._userdict.sync()
