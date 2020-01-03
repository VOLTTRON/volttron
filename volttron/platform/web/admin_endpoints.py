# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
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

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateNotFound
except ImportError:
    logging.getLogger().warning("Missing jinja2 libaray in admin_endpoints.py")

try:
    from passlib.hash import argon2
except ImportError:
    logging.getLogger().warning("Missing passlib libaray in admin_endpoints.py")

from watchdog_gevent import Observer
from volttron.platform.agent.web import Response

from ...platform import get_home
from ...platform import jsonapi
from ...platform.certs import Certs
from ...utils import VolttronHomeFileReloader
from ...utils.persistance import PersistentDict


_log = logging.getLogger(__name__)


def template_env(env):
    return env['JINJA2_TEMPLATE_ENV']


class AdminEndpoints(object):

    def __init__(self, rmq_mgmt=None, ssl_public_key: bytes = None):

        self._rmq_mgmt = rmq_mgmt
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
        self._userdict = None
        self.reload_userdict()

        self._observer = Observer()
        self._observer.schedule(
            VolttronHomeFileReloader("web-users.json", self.reload_userdict),
            get_home()
        )
        self._observer.start()
        if ssl_public_key is not None:
            self._certs = Certs()

    def reload_userdict(self):
        webuserpath = os.path.join(get_home(), 'web-users.json')
        self._userdict = PersistentDict(webuserpath, format="json")

    def get_routes(self):
        """
        Returns a list of tuples with the routes for the adminstration endpoints
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
                    _log.debug("Setting master password")
                    self.add_user(username, pass1, groups=['admin'])
                    return Response('', status='302', headers={'Location': '/admin/login.html'})

            template = template_env(env).get_template('first.html')
            return Response(template.render(), content_type="text/html")

        if 'login.html' in env.get('PATH_INFO') or '/admin/' == env.get('PATH_INFO'):
            template = template_env(env).get_template('login.html')
            return Response(template.render(), content_type='text/html')

        return self.verify_and_dispatch(env, data)

    def verify_and_dispatch(self, env, data):
        """ Verify that the user is an admin and dispatch

        :param env: web environment
        :param data: data associated with a web form or json/xml request data
        :return: Response object.
        """
        from volttron.platform.web import get_user_claims, NotAuthorized
        try:
            claims = get_user_claims(env)
        except NotAuthorized:
            _log.error("Unauthorized user attempted to connect to {}".format(env.get('PATH_INFO')))
            return Response('<h1>Unauthorized User</h1>', status="401 Unauthorized")

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

            if page == 'list_certs.html':
                html = template.render(certs=self._certs.get_all_cert_subjects())
            elif page == 'pending_csrs.html':
                html = template.render(csrs=self._certs.get_pending_csr_requests())
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
        else:
            response = Response('{"status": "Unknown endpoint {}"}'.format(endpoint),
                                content_type="application/json")
        return response

    def __approve_csr_api(self, common_name):
        try:
            _log.debug("Creating cert and permissions for user: {}".format(common_name))
            self._certs.approve_csr(common_name)
            permissions = self._rmq_mgmt.get_default_permissions(common_name)
            self._rmq_mgmt.create_user_with_permissions(common_name,
                                                        permissions,
                                                        True)
            data = dict(status=self._certs.get_csr_status(common_name),
                        cert=self._certs.get_cert_from_csr(common_name))
        except ValueError as e:
            data = dict(status="ERROR", message=e.message)

        return Response(jsonapi.dumps(data), content_type="application/json")

    def __deny_csr_api(self, common_name):
        try:
            self._certs.deny_csr(common_name)
            data = dict(status="DENIED",
                        message="The administrator has denied the request")
        except ValueError as e:
            data = dict(status="ERROR", message=e.message)

        return Response(jsonapi.dumps(data), content_type="application/json")

    def __delete_csr_api(self, common_name):
        try:
            self._certs.delete_csr(common_name)
            data = dict(status="DELETED",
                        message="The administrator has denied the request")
        except ValueError as e:
            data = dict(status="ERROR", message=e.message)

        return Response(jsonapi.dumps(data), content_type="application/json")

    def __pending_csrs_api(self):
        csrs = [c for c in self._certs.get_pending_csr_requests()]
        return Response(jsonapi.dumps(csrs), content_type="application/json")

    def __cert_list_api(self):

        subjects = [dict(common_name=x.common_name)
                    for x in self._certs.get_all_cert_subjects()]
        return Response(jsonapi.dumps(subjects), content_type="application/json")

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
