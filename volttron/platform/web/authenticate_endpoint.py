import logging
import os
import re
import urlparse

from passlib.hash import argon2
import jwt
from jinja2 import Environment, FileSystemLoader, select_autoescape

from volttron.platform import get_home
from volttron.platform.agent import json
from volttron.platform.agent.web import Response
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
        webuserpath = os.path.join(get_home(), 'web-users.json')
        self._ssl_private_key = ssl_private_key
        self._userdict = PersistentDict(webuserpath)

    def get_routes(self):
        """
        Returns a list of tuples with the routes for authentication.

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

        user = self.__get_user(data.get('username'), data.get('password'))
        if user is None:
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

