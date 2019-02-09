import Cookie
import logging
import os
import re
import urlparse

from jinja2 import Environment, FileSystemLoader, select_autoescape
import jwt
from passlib.hash import argon2
from watchdog_gevent import Observer

from volttron.platform import get_home
from volttron.platform.agent.web import Response
from volttron.utils import FileReloader
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


class AdminEndpoints(object):

    def __init__(self, ssl_public_key):

        self._userdict = None #PersistentDict(webuserpath)
        self._ssl_public_key = ssl_public_key
        self._userdict = None
        self.reload_userdict()
        self._observer = Observer()
        self._observer.schedule(
            FileReloader("web-users.json", self.reload_userdict),
            get_home()
        )
        self._observer.start()

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

            template = tplenv.get_template('first.html')
            resp = template.render()
            return Response(template.render())

        if 'login.html' in env.get('PATH_INFO'):
            template = tplenv.get_template('login.html')
            resp = template.render()
            return Response(template.render())

        return self.verify_and_dispatch(env, data)

    def verify_and_dispatch(self, env, data):

        bearer = env.get('HTTP_COOKIE')
        if not bearer:
            template = tplenv.get_template('login.html')
            return Response(template.render(), status='401 Unauthorized')

        cookie = Cookie.SimpleCookie(env.get('HTTP_COOKIE'))
        bearer = cookie.get('Bearer').value.decode('utf-8')

        claims = jwt.decode(bearer, self._ssl_public_key, algorithms='RS256')

        if not isinstance(claims, dict):
            _log.warning("Invalid claimed ")

        template = tplenv.get_template('index.html')
        resp = template.render()
        return Response(resp)

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
