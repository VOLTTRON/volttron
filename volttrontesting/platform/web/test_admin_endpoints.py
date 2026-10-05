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


import errno
import os
import re
import stat
from urllib.parse import urlencode

import gevent
import pytest
from mock import patch
from passlib.hash import argon2

from volttron.platform import jsonapi
from volttron.platform.web import admin_endpoints
from volttron.platform.web.admin_endpoints import AdminEndpoints
from volttron.utils import get_random_key
from volttron.utils.rmq_mgmt import RabbitMQMgmt
from volttrontesting.fixtures.volttron_platform_fixtures import \
    get_test_volttron_home, rmq_skipif
from volttrontesting.utils.web_utils import get_test_web_env

___WEB_USER_FILE_NAME__ = 'web-users.json'
SETUP_TOKEN_FILE_NAME = admin_endpoints.SETUP_TOKEN_FILE
SETUP_PAGE = 'first-page'


def _request(adminep, method, form=None):
    env = get_test_web_env('/admin/setpassword', method=method)
    env['JINJA2_TEMPLATE_ENV'].get_template.return_value.render.return_value = SETUP_PAGE
    return adminep.admin(env, urlencode(form or {}))


def _issue_setup_token(adminep, vhome):
    _request(adminep, 'GET')
    with open(os.path.join(vhome, SETUP_TOKEN_FILE_NAME)) as fp:
        return fp.read()


def _stored_users(vhome):
    path = os.path.join(vhome, ___WEB_USER_FILE_NAME__)
    if not os.path.exists(path):
        return {}
    with open(path) as fp:
        return jsonapi.load(fp)


def _admin_form(token, username='bart', password='wowsa'):
    return dict(username=username, password1=password, password2=password, setup_token=token)


@pytest.mark.web
def test_admin_unauthorized():
    config_params = {"web-secret-key": get_random_key()}
    with get_test_volttron_home(messagebus='zmq', config_params=config_params):
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
def test_set_platform_password_setup():
    with get_test_volttron_home(messagebus='zmq') as vhome:
        adminep = AdminEndpoints()
        token = _issue_setup_token(adminep, vhome)

        # Mismatched passwords return the setup page again.
        response = _request(adminep, 'POST', dict(username='bart', password1='goodwin',
                                                  password2='wowsa', setup_token=token))
        assert 'Location' not in response.headers
        assert 200 == response.status_code
        assert 'text/html' == response.headers.get('Content-Type')
        assert SETUP_PAGE.encode() == response.get_data()
        assert {} == _stored_users(vhome)

        response = _request(adminep, 'POST', _admin_form(token))
        assert 3 == len(response.headers)
        assert '/admin/login.html' == response.headers.get('Location')
        assert 302 == response.status_code

        user = _stored_users(vhome).get('bart')
        assert user is not None
        assert argon2.verify("wowsa", user['hashed_password'])


@pytest.mark.web
@pytest.mark.parametrize('form', [
    dict(username='bart', password1='wowsa', password2='wowsa'),
    dict(username='bart', password1='wowsa', password2='wowsa', setup_token=''),
    dict(username='bart', password1='wowsa', password2='wowsa', setup_token='not-the-token'),
])
def test_first_admin_refused_without_the_setup_token(form):
    with get_test_volttron_home(messagebus='zmq') as vhome:
        adminep = AdminEndpoints()
        token = _issue_setup_token(adminep, vhome)

        response = _request(adminep, 'POST', form)

        assert 403 == response.status_code
        assert SETUP_PAGE.encode() == response.get_data()
        assert not os.path.exists(os.path.join(vhome, ___WEB_USER_FILE_NAME__))
        assert {} == adminep._userdict
        with open(os.path.join(vhome, SETUP_TOKEN_FILE_NAME)) as fp:
            assert token == fp.read()


@pytest.mark.web
def test_first_admin_created_with_the_setup_token_which_is_then_removed():
    with get_test_volttron_home(messagebus='zmq') as vhome:
        adminep = AdminEndpoints()
        token = _issue_setup_token(adminep, vhome)
        assert len(token) >= 43

        with patch.object(admin_endpoints.hmac, 'compare_digest',
                          wraps=admin_endpoints.hmac.compare_digest) as compare:
            response = _request(adminep, 'POST', _admin_form(token))

        assert 302 == response.status_code
        assert '/admin/login.html' == response.headers.get('Location')
        assert 1 == compare.call_count
        users = _stored_users(vhome)
        assert ['bart'] == list(users)
        assert ['admin', 'vui'] == users['bart']['groups']
        assert argon2.verify('wowsa', users['bart']['hashed_password'])
        assert not os.path.lexists(os.path.join(vhome, SETUP_TOKEN_FILE_NAME))


@pytest.mark.web
def test_setup_token_is_single_use():
    with get_test_volttron_home(messagebus='zmq') as vhome:
        adminep = AdminEndpoints()
        token = _issue_setup_token(adminep, vhome)
        assert 302 == _request(adminep, 'POST', _admin_form(token)).status_code

        # A fresh endpoint with no users loaded still enters the setup branch.
        replay = AdminEndpoints()
        replay._userdict = {}
        response = _request(replay, 'POST', _admin_form(token, password='other'))

        assert 403 == response.status_code
        users = _stored_users(vhome)
        assert ['bart'] == list(users)
        assert argon2.verify('wowsa', users['bart']['hashed_password'])


@pytest.mark.web
def test_setup_token_file_is_owner_only_and_token_is_not_logged(caplog):
    caplog.set_level('DEBUG')
    with get_test_volttron_home(messagebus='zmq') as vhome:
        adminep = AdminEndpoints()
        token = _issue_setup_token(adminep, vhome)
        token_path = os.path.join(vhome, SETUP_TOKEN_FILE_NAME)

        st = os.lstat(token_path)
        assert stat.S_ISREG(st.st_mode)
        assert 0o600 == stat.S_IMODE(st.st_mode)
        assert os.geteuid() == st.st_uid

        _request(adminep, 'POST', _admin_form('not-the-token'))
        _request(adminep, 'POST', _admin_form(token))

        assert any(token_path in r.getMessage() for r in caplog.records
                   if r.levelname == 'WARNING')
        assert not any(token in r.getMessage() for r in caplog.records)


@pytest.mark.web
def test_empty_setup_token_file_never_matches():
    with get_test_volttron_home(messagebus='zmq') as vhome:
        token_path = os.path.join(vhome, SETUP_TOKEN_FILE_NAME)
        fd = os.open(token_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        adminep = AdminEndpoints()

        response = _request(adminep, 'POST', _admin_form(''))

        assert 403 == response.status_code
        assert {} == _stored_users(vhome)


@pytest.mark.web
@pytest.mark.parametrize('username, password', [('', 'wowsa'), ('   ', 'wowsa'), ('bart', ''), (None, 'wowsa')])
def test_first_admin_refused_with_blank_username_or_password(username, password):
    with get_test_volttron_home(messagebus='zmq') as vhome:
        adminep = AdminEndpoints()
        token = _issue_setup_token(adminep, vhome)
        form = _admin_form(token, username=username, password=password)
        if username is None:
            del form['username']

        response = _request(adminep, 'POST', form)

        assert 403 == response.status_code
        assert {} == _stored_users(vhome)
        assert {} == adminep._userdict
        assert os.path.exists(os.path.join(vhome, SETUP_TOKEN_FILE_NAME))


@pytest.mark.web
@pytest.mark.parametrize('method', ['GET', 'POST'])
def test_setup_refused_when_the_token_file_cannot_be_written(method):
    with get_test_volttron_home(messagebus='zmq') as vhome:
        os.chmod(vhome, 0o500)
        try:
            adminep = AdminEndpoints()
            response = _request(adminep, method, _admin_form(''))
        finally:
            os.chmod(vhome, 0o700)

        assert 503 == response.status_code
        assert {} == _stored_users(vhome)
        assert not os.path.lexists(os.path.join(vhome, SETUP_TOKEN_FILE_NAME))


def _write_owner_only(path, content):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as fp:
        fp.write(content)


@pytest.mark.web
def test_symlinked_setup_token_file_is_refused():
    with get_test_volttron_home(messagebus='zmq') as vhome:
        target = os.path.join(vhome, 'elsewhere')
        _write_owner_only(target, 'known-token')
        os.symlink(target, os.path.join(vhome, SETUP_TOKEN_FILE_NAME))
        adminep = AdminEndpoints()

        response = _request(adminep, 'POST', _admin_form('known-token'))

        assert 503 == response.status_code
        assert {} == _stored_users(vhome)


@pytest.mark.web
def test_dangling_setup_token_symlink_target_is_not_created():
    with get_test_volttron_home(messagebus='zmq') as vhome:
        target = os.path.join(vhome, 'elsewhere')
        os.symlink(target, os.path.join(vhome, SETUP_TOKEN_FILE_NAME))
        adminep = AdminEndpoints()

        _request(adminep, 'GET')
        response = _request(adminep, 'POST', _admin_form(''))

        assert not os.path.lexists(target)
        assert response.status_code in (403, 503)
        assert {} == _stored_users(vhome)


@pytest.mark.web
@pytest.mark.parametrize('mode', [0o400, 0o640, 0o644, 0o660, 0o606])
def test_setup_token_file_must_be_mode_0600(mode):
    with get_test_volttron_home(messagebus='zmq') as vhome:
        adminep = AdminEndpoints()
        token = _issue_setup_token(adminep, vhome)
        os.chmod(os.path.join(vhome, SETUP_TOKEN_FILE_NAME), mode)

        response = _request(adminep, 'POST', _admin_form(token))

        assert 503 == response.status_code
        assert {} == _stored_users(vhome)


@pytest.mark.web
def test_setup_token_file_owned_by_another_user_is_refused():
    with get_test_volttron_home(messagebus='zmq') as vhome:
        adminep = AdminEndpoints()
        token = _issue_setup_token(adminep, vhome)

        with patch.object(admin_endpoints.os, 'geteuid', return_value=os.geteuid() + 1):
            response = _request(adminep, 'POST', _admin_form(token))

        assert 503 == response.status_code
        assert {} == _stored_users(vhome)


@pytest.mark.web
@pytest.mark.parametrize('kind', ['fifo', 'directory'])
def test_setup_token_path_that_is_not_a_regular_file_is_refused(kind):
    with get_test_volttron_home(messagebus='zmq') as vhome:
        token_path = os.path.join(vhome, SETUP_TOKEN_FILE_NAME)
        if kind == 'fifo':
            os.mkfifo(token_path, 0o600)
        else:
            os.mkdir(token_path, 0o700)
        adminep = AdminEndpoints()

        response = _request(adminep, 'POST', _admin_form('anything'))

        assert 503 == response.status_code
        assert {} == _stored_users(vhome)


@pytest.mark.web
def test_first_admin_not_created_when_a_user_is_written_during_setup():
    with get_test_volttron_home(messagebus='zmq') as vhome:
        adminep = AdminEndpoints()
        token = _issue_setup_token(adminep, vhome)
        real_read = AdminEndpoints._read_setup_token

        def read_after_another_user_is_written(self):
            AdminEndpoints().add_user('other', 'other-pw', ['admin'])
            return real_read(self)

        with patch.object(AdminEndpoints, '_read_setup_token', read_after_another_user_is_written):
            response = _request(adminep, 'POST', _admin_form(token))

        assert 403 == response.status_code
        users = _stored_users(vhome)
        assert ['other'] == list(users)
        assert argon2.verify('other-pw', users['other']['hashed_password'])


@pytest.mark.web
def test_setup_token_used_by_another_request_is_refused():
    with get_test_volttron_home(messagebus='zmq') as vhome:
        adminep = AdminEndpoints()
        token = _issue_setup_token(adminep, vhome)
        real_read = AdminEndpoints._read_setup_token

        def read_then_lose_the_token(self):
            value = real_read(self)
            os.remove(os.path.join(vhome, SETUP_TOKEN_FILE_NAME))
            return value

        with patch.object(AdminEndpoints, '_read_setup_token', read_then_lose_the_token):
            response = _request(adminep, 'POST', _admin_form(token))

        assert 403 == response.status_code
        assert {} == _stored_users(vhome)
        assert {} == adminep._userdict


@pytest.mark.web
def test_concurrent_first_admin_posts_create_one_admin():
    with get_test_volttron_home(messagebus='zmq') as vhome:
        adminep = AdminEndpoints()
        token = _issue_setup_token(adminep, vhome)
        real_read = AdminEndpoints._read_setup_token

        # Both requests pass the token check before either one consumes it.
        def read_then_yield(self):
            value = real_read(self)
            gevent.sleep(0.01)
            return value

        with patch.object(AdminEndpoints, '_read_setup_token', read_then_yield):
            jobs = {name: gevent.spawn(_request, adminep, 'POST',
                                       _admin_form(token, username=name, password=name + '-pw'))
                    for name in ('alice', 'bob')}
            gevent.joinall(list(jobs.values()), timeout=10, raise_error=True)

        statuses = {name: job.value.status_code for name, job in jobs.items()}
        assert [302, 403] == sorted(statuses.values())
        winner = next(name for name, code in statuses.items() if code == 302)
        users = _stored_users(vhome)
        assert [winner] == list(users)
        assert ['admin', 'vui'] == users[winner]['groups']
        assert argon2.verify(winner + '-pw', users[winner]['hashed_password'])


@pytest.mark.web
def test_unreadable_users_file_is_reported_as_unsupported_format():
    with get_test_volttron_home(messagebus='zmq') as vhome:
        with open(os.path.join(vhome, ___WEB_USER_FILE_NAME__), 'w') as fp:
            fp.write('{not json')

        with pytest.raises(ValueError, match="File not in a supported format"):
            AdminEndpoints()


@pytest.mark.web
def test_setup_token_created_when_endpoints_start_without_users(caplog):
    caplog.set_level('DEBUG')
    with get_test_volttron_home(messagebus='zmq') as vhome:
        token_path = os.path.join(vhome, SETUP_TOKEN_FILE_NAME)
        AdminEndpoints()

        st = os.lstat(token_path)
        assert stat.S_ISREG(st.st_mode)
        assert 0o600 == stat.S_IMODE(st.st_mode)
        assert any(token_path in r.getMessage() for r in caplog.records if r.levelname == 'WARNING')


@pytest.mark.web
def test_existing_setup_token_is_reused_and_announced_at_each_start(caplog):
    caplog.set_level('DEBUG')
    with get_test_volttron_home(messagebus='zmq') as vhome:
        token_path = os.path.join(vhome, SETUP_TOKEN_FILE_NAME)
        AdminEndpoints()
        with open(token_path) as fp:
            first = fp.read()
        caplog.clear()

        AdminEndpoints()

        with open(token_path) as fp:
            assert first == fp.read()
        assert any(token_path in r.getMessage() for r in caplog.records if r.levelname == 'WARNING')
        assert not any(first in r.getMessage() for r in caplog.records)


@pytest.mark.web
def test_no_setup_token_created_when_users_exist():
    with get_test_volttron_home(messagebus='zmq') as vhome:
        token_path = os.path.join(vhome, SETUP_TOKEN_FILE_NAME)
        AdminEndpoints().add_user('bart', 'wowsa', ['admin'])
        if os.path.lexists(token_path):
            os.remove(token_path)

        AdminEndpoints()

        assert not os.path.lexists(token_path)


@pytest.mark.web
def test_setup_token_file_is_0600_under_a_restrictive_umask():
    with get_test_volttron_home(messagebus='zmq') as vhome:
        previous = os.umask(0o277)
        try:
            adminep = AdminEndpoints()
        finally:
            os.umask(previous)
        token_path = os.path.join(vhome, SETUP_TOKEN_FILE_NAME)
        assert 0o600 == stat.S_IMODE(os.lstat(token_path).st_mode)
        with open(token_path) as fp:
            token = fp.read()

        assert 302 == _request(adminep, 'POST', _admin_form(token)).status_code


@pytest.mark.web
def test_setup_page_template_posts_the_fields_the_handler_reads():
    from volttron.platform.web.platform_web_service import tplenv
    with get_test_volttron_home(messagebus='zmq') as vhome:
        adminep = AdminEndpoints()
        env = get_test_web_env('/admin/', method='GET', JINJA2_TEMPLATE_ENV=tplenv)
        page = adminep.admin(env, '').get_data(as_text=True)

        assert SETUP_TOKEN_FILE_NAME in page
        names = re.findall(r'<input[^>]*\bname="([^"]+)"', page)
        assert sorted(names) == ['password1', 'password2', 'setup_token', 'username']

        with open(os.path.join(vhome, SETUP_TOKEN_FILE_NAME)) as fp:
            token = fp.read()
        values = dict(username='bart', password1='wowsa', password2='wowsa', setup_token=token)
        env = get_test_web_env('/admin/setpassword', method='POST', JINJA2_TEMPLATE_ENV=tplenv)
        response = adminep.admin(env, urlencode({name: values[name] for name in names}))

        assert 302 == response.status_code
        assert ['bart'] == list(_stored_users(vhome))


@pytest.mark.web
@pytest.mark.parametrize('error, leaves_empty_file', [(errno.ENOSPC, True), (errno.EACCES, False)])
def test_setup_stays_recoverable_when_saving_the_first_admin_fails(caplog, error, leaves_empty_file):
    with get_test_volttron_home(messagebus='zmq') as vhome:
        adminep = AdminEndpoints()
        token = _issue_setup_token(adminep, vhome)
        users_path = os.path.join(vhome, ___WEB_USER_FILE_NAME__)
        real_open = open

        def failing_open(path, mode='r', *args, **kwargs):
            if path == users_path and 'w' in mode:
                if leaves_empty_file:
                    real_open(path, 'w').close()
                raise OSError(error, os.strerror(error))
            return real_open(path, mode, *args, **kwargs)

        with patch('volttron.platform.web.admin_endpoints.open', failing_open, create=True):
            response = _request(adminep, 'POST', _admin_form(token))

        assert 503 == response.status_code
        assert {} == adminep._userdict
        assert not os.path.exists(users_path)
        assert any(r.levelname == 'ERROR' and os.strerror(error) in r.getMessage()
                   for r in caplog.records)
        with open(os.path.join(vhome, SETUP_TOKEN_FILE_NAME)) as fp:
            new_token = fp.read()

        assert 302 == _request(adminep, 'POST', _admin_form(new_token)).status_code
        users = _stored_users(vhome)
        assert ['bart'] == list(users)
        assert argon2.verify('wowsa', users['bart']['hashed_password'])


@pytest.mark.web
def test_admin_login_page():
    with get_test_volttron_home(messagebus='zmq'):
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
    with get_test_volttron_home(messagebus='zmq'):
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
@rmq_skipif
def test_construction():

    # within rabbitmq mgmt this is used
    with patch("volttron.platform.agent.utils.get_platform_instance_name",
               return_value="volttron"):
        mgmt = RabbitMQMgmt()
        assert mgmt is not None
