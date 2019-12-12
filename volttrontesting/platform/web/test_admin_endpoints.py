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


import pytest
from volttron.platform.web.admin_endpoints import AdminEndpoints
from volttron.utils import get_random_key
from volttron.utils.rmq_mgmt import RabbitMQMgmt
from mock import patch
from urllib.parse import urlencode
from volttrontesting.utils.web_utils import get_test_web_env
from volttrontesting.fixtures.volttron_platform_fixtures import get_test_volttron_home

from volttron.platform import jsonapi
import os

___WEB_USER_FILE_NAME__ = 'web-users.json'


@pytest.mark.web
def test_admin_unauthorized():
    config_params = {"web_secret_key": get_random_key()}
    with get_test_volttron_home(messagebus='zmq', config_params=config_params) as vhome:
        myuser = 'testing'
        mypass = 'funky'
        adminep = AdminEndpoints()
        adminep.add_user(myuser, mypass)

        # User hasn't logged in so this should be not authorized.
        env = get_test_web_env('/admin/api/boo')
        response = adminep.admin(env, {})
        assert '401 Unauthorized' == response.status
        assert b'Unauthorized User' in response.response[0]


@pytest.mark.web
def test_set_master_password_setup():
    with get_test_volttron_home(messagebus='zmq'):
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
        assert 3 == len(response.headers)
        assert response.headers.has_key('Location')
        assert '/admin/login.html' == response.headers.get('Location')
        assert 302 == response.status_code

        # TODO: Test and make sure that bart/wowsa is in web-users.json


@pytest.mark.web
def test_admin_login_page():
    with get_test_volttron_home(messagebus='zmq') as vhome:
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
        assert 'text/html' == response.headers.get('Content-Type')
        # assert ('Content-Type', 'text/html') in response.headers
        assert '200 OK' == response.status


@pytest.mark.web
def test_persistent_users():
    with get_test_volttron_home(messagebus='zmq') as vhome:
        username_test = "mytest"
        username_test_passwd = "value-plus"
        adminep = AdminEndpoints()
        oid = id(adminep)
        adminep.add_user(username_test, username_test_passwd, ['admin'])

        another_ep = AdminEndpoints()
        assert oid != id(another_ep)
        assert len(another_ep._userdict) == 1
        assert username_test == list(another_ep._userdict)[0]


@pytest.mark.web
def test_add_user():
    with get_test_volttron_home(messagebus='zmq') as vhome:
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


@pytest.mark.web
def test_construction():

    # within rabbitmq mgmt this is used
    with patch("volttron.platform.agent.utils.get_platform_instance_name",
               return_value="volttron"):
        mgmt = RabbitMQMgmt()
        assert mgmt is not None

