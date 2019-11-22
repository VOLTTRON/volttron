from io import BytesIO

import gevent
from mock import patch, Mock
import pytest
from volttron.platform.web.admin_endpoints import AdminEndpoints
from volttron.utils.rmq_mgmt import RabbitMQMgmt
from mock import patch
from urllib.parse import urlencode
from volttron.utils.rmq_config_params import RMQConfig
from volttrontesting.utils.web_utils import get_test_web_env
from volttrontesting.utils.platformwrapper import create_volttron_home
from volttron.platform.agent.utils import get_platform_instance_name
from volttron.platform import jsonapi
import contextlib
import os
import shutil


___WEB_USER_FILE_NAME__ = 'web-users.json'


@contextlib.contextmanager
def get_test_volttron_home():
    volttron_home = create_volttron_home()
    original_home = os.environ.get('VOLTTRON_HOME')
    os.environ['VOLTTRON_HOME'] = volttron_home
    yield volttron_home
    if original_home is None:
        os.environ.unsetenv('VOLTTRON_HOME')
    else:
        os.environ['VOLTTRON_HOME'] = original_home
    shutil.rmtree(volttron_home, ignore_errors=True)


def test_set_master_password_setup():
    with get_test_volttron_home():
        # Note these passwords are not right so we expect to be redirected back to the
        # first.html
        params = urlencode(dict(username='bart', password1='goodwin', password2='wowsa'))
        env = get_test_web_env("/admin/setpassword", method='POST')  # , input_data=input)
        jinja_mock = env['JINJA2_TEMPLATE_ENV']
        adminep = AdminEndpoints()
        response = adminep.admin(env, params)

        # TODO: Assert some things about response.
        assert 1 == jinja_mock.get_template.call_count
        assert ('first.html',) == jinja_mock.get_template.call_args[0]
        assert 1 == jinja_mock.get_template.return_value.render.call_count
        jinja_mock.reset_mock()

        # Now we have the correct password1 and password2 set we expect to redirected to
        # /admin/login.html
        params = urlencode(dict(username='bart', password1='wowsa', password2='wowsa'))
        env = get_test_web_env("/admin/setpassword", method='POST')  # , input_data=input)

        # expect Location and Content-Type headers to be set
        response = adminep.admin(env, params)
        assert 2 == len(response.headers)
        assert ('Location', '/admin/login.html') in response.headers
        assert ('Content-Type', 'text/html') in response.headers
        assert '302' == response.status


def test_admin_login_page():
    with get_test_volttron_home() as vhome:
        username_test = "mytest"
        username_test_passwd = "value-plus"
        adminep = AdminEndpoints()
        adminep.add_user(username_test, username_test_passwd, ['admin'])
        myenv = get_test_web_env(path='login.html')
        response = adminep.admin(myenv, {})
        jinja_mock = myenv['JINJA2_TEMPLATE_ENV']
        assert 1 == jinja_mock.get_template.call_count
        assert ('login.html',) == jinja_mock.get_template.call_args[0]
        assert 1 == jinja_mock.get_template.return_value.render.call_count
        assert ('Content-Type', 'text/html') in response.headers
        assert '200 OK' == response.status


def test_persistent_users():
    with get_test_volttron_home() as vhome:
        username_test = "mytest"
        username_test_passwd = "value-plus"
        adminep = AdminEndpoints()
        oid = id(adminep)
        adminep.add_user(username_test, username_test_passwd, ['admin'])

        another_ep = AdminEndpoints()
        assert oid != id(another_ep)
        assert len(another_ep._userdict) == 1
        assert username_test == list(another_ep._userdict)[0]


def test_add_user():
    with get_test_volttron_home() as vhome:
        webuserpath = os.path.join(vhome, ___WEB_USER_FILE_NAME__)
        assert not os.path.exists(webuserpath)

        username_test = "test"
        username_test_passwd = "passwd"
        adminep = AdminEndpoints()
        adminep.add_user(username_test, username_test_passwd, ['admin'])

        # since add_user is async with persistance we use sleep to allow the write
        # gevent.sleep(0.01)
        assert os.path.exists(webuserpath)

        with open(webuserpath) as fp:
            users = jsonapi.load(fp)

        assert len(users) == 1
        assert users.get(username_test) is not None
        user = users.get(username_test)
        objid = id(user)
        assert ['admin'] == user['groups']
        assert user['hashed_password'] is not None
        original_hashed_passwordd = user['hashed_password']

        # raise ValueError if not overwrite == True
        with pytest.raises(ValueError,
                           match=f"The user {username_test} is already present and overwrite not set to True"):
            adminep.add_user(username_test, username_test_passwd, ['admin'])

        # make sure the overwrite works because we are changing the group
        adminep.add_user(username_test, username_test_passwd, ['read_only', 'jr-devs'], overwrite=True)
        assert os.path.exists(webuserpath)

        with open(webuserpath) as fp:
            users = jsonapi.load(fp)

        assert len(users) == 1
        assert users.get(username_test) is not None
        user = users.get(username_test)
        assert objid != id(user)
        assert ['read_only', 'jr-devs'] == user['groups']
        assert user['hashed_password'] is not None
        assert original_hashed_passwordd != user['hashed_password']


def test_construction():

    # within rabbitmq mgmt this is used
    with patch("volttron.platform.agent.utils.get_platform_instance_name",
               return_value="volttron"):
        mgmt = RabbitMQMgmt()
        assert mgmt is not None

