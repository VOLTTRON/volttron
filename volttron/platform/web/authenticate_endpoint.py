import logging
import os
import re
from urllib.parse import urlparse

import jwt
from jinja2 import Environment, FileSystemLoader, select_autoescape
from passlib.hash import argon2
#from watchdog_gevent import Observer

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

    def __init__(self, ssl_private_key):

        self._ssl_private_key = ssl_private_key
        self._userdict = None
        self.reload_userdict()
        # TODO Add back reload capability
        # self._observer = Observer()
        # self._observer.schedule(
        #     FileReloader("web-users.json", self.reload_userdict),
        #     get_home()
        # )
        # self._observer.start()

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
            (re.compile('^/authenticate'), 'callable', self.get_auth_token)
        ]

    def get_auth_token(self, env, data):
        """
        Creates an authentication token to be returned to the caller.  The
        response will be a text/plain encoded user

        :param env:
        :param data:
        :return:
        """
        if env.get('REQUEST_METHOD') != 'POST':
            _log.warning("Authentication must use POST request.")
            return Response('', status='401 Unauthorized')

        assert len(self._userdict) > 0, "No users in user dictionary, set the master password first!"

        if not isinstance(data, dict):
            _log.debug("data is not a dict, decoding")
            decoded = dict((k, v if len(v) > 1 else v[0])
                           for k, v in urlparse.parse_qs(data).iteritems())

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

        encoded = jwt.encode(user, self._ssl_private_key, algorithm='RS256').encode('utf-8')

        return Response(encoded, '200 OK', content_type='text/plain')

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

