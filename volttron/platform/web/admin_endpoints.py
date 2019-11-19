import Cookie
import logging
import os
import re
import urlparse

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateNotFound
except ImportError:
    logging.getLogger().warning("Missing jinja2 libaray in admin_endpoints.py")

try:
    from passlib.hash import argon2
except ImportError:
    logging.getLogger().warning("Missing passlib libaray in admin_endpoints.py")

from watchdog_gevent import Observer

from volttron.platform import get_home
from volttron.platform.agent import json
from volttron.platform.agent.web import Response
from volttron.utils import FileReloader
from volttron.utils.persistance import PersistentDict
from volttron.platform.certs import Certs

_log = logging.getLogger(__name__)


def template_env(env):
    return env['JINJA2_TEMPLATE_ENV']


class AdminEndpoints(object):

    def __init__(self, rmq_mgmt, ssl_public_key):

        self._rmq_mgmt = rmq_mgmt
        self._ssl_public_key = ssl_public_key
        self._userdict = None
        self.reload_userdict()
        self._observer = Observer()
        self._observer.schedule(
            FileReloader("web-users.json", self.reload_userdict),
            get_home()
        )
        self._observer.start()
        self._certs = Certs()

    def reload_userdict(self):
        webuserpath = os.path.join(get_home(), 'web-users.json')
        self._userdict = PersistentDict(webuserpath)

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
                               for k, v in urlparse.parse_qs(data).iteritems())
                username = decoded.get('username')
                pass1 = decoded.get('password1')
                pass2 = decoded.get('password2')
                if pass1 == pass2 and pass1 is not None:
                    _log.debug("Setting master password")
                    self.add_user(username, pass1, groups=['admin'])
                    return Response('', status='302', headers={'Location': '/admin/login.html'})

            template = template_env(env).get_template('first.html')
            return Response(template.render())

        if 'login.html' in env.get('PATH_INFO') or '/admin/' == env.get('PATH_INFO'):
            template = template_env(env).get_template('login.html')
            return Response(template.render())

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

        return Response(json.dumps(data), content_type="application/json")

    def __deny_csr_api(self, common_name):
        try:
            self._certs.deny_csr(common_name)
            data = dict(status="DENIED",
                        message="The administrator has denied the request")
        except ValueError as e:
            data = dict(status="ERROR", message=e.message)

        return Response(json.dumps(data), content_type="application/json")

    def __delete_csr_api(self, common_name):
        try:
            self._certs.delete_csr(common_name)
            data = dict(status="DELETED",
                        message="The administrator has denied the request")
        except ValueError as e:
            data = dict(status="ERROR", message=e.message)

        return Response(json.dumps(data), content_type="application/json")

    def __pending_csrs_api(self):
        csrs = [c for c in self._certs.get_pending_csr_requests()]
        return Response(json.dumps(csrs), content_type="application/json")

    def __cert_list_api(self):

        subjects = [dict(common_name=x.common_name)
                    for x in self._certs.get_all_cert_subjects()]
        return Response(json.dumps(subjects), content_type="application/json")

    def add_user(self, username, unencrypted_pw, groups=[], overwrite=False):
        if self._userdict.get(username):
            raise ValueError("Already exists!")
        if groups is None:
            groups = []
        hashed_pass = argon2.hash(unencrypted_pw)
        self._userdict[username] = dict(
            hashed_password=hashed_pass,
            groups=groups
        )
        self._userdict.async_sync()
