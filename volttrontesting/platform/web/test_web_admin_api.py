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

import os
from types import SimpleNamespace

import pytest
from mock import patch

from volttron.platform import jsonapi
from volttron.platform.web.admin_endpoints import SETUP_TOKEN_FILE
from volttrontesting.utils import platformwrapper
from volttrontesting.utils.platformwrapper import WebAdminApi

pytestmark = pytest.mark.web

WEB_ADDRESS = 'http://127.0.0.1:8443'


class FakeRequests:
    """Stands in for grequests: records each request and replays scripted results."""

    def __init__(self, vhome, get_status=200, post_status=302, get_error=None, post_error=None,
                 write_token=True):
        self.vhome = vhome
        self.calls = []
        self._results = {'get': (get_status, get_error), 'post': (post_status, post_error)}
        self._write_token = write_token

    def _send(self, method, url, kwargs):
        self.calls.append((method, url, kwargs))
        status, error = self._results[method]
        if method == 'get' and self._write_token and error is None:
            with open(os.path.join(self.vhome, SETUP_TOKEN_FILE), 'w') as fp:
                fp.write('the-token')
        response = None if error else SimpleNamespace(status_code=status, text='body', ok=status < 400)
        return SimpleNamespace(response=response, exception=error)

    def get(self, url, **kwargs):
        return SimpleNamespace(send=lambda: self._send('get', url, kwargs))

    def post(self, url, **kwargs):
        return SimpleNamespace(send=lambda: self._send('post', url, kwargs))


def _api(vhome):
    api = WebAdminApi.__new__(WebAdminApi)
    api._wrapper = SimpleNamespace(volttron_home=vhome, ssl_auth=False)
    api.bind_web_address = WEB_ADDRESS
    api.certsobj = None
    return api


def _create(vhome, fake):
    with patch.object(platformwrapper, 'grequests', fake):
        return _api(vhome).create_web_admin('admin', 'admin')


def test_create_web_admin_submits_the_setup_token_without_following_redirects(tmp_path):
    fake = FakeRequests(str(tmp_path))

    response = _create(str(tmp_path), fake)

    assert 302 == response.status_code
    assert ['get', 'post'] == [c[0] for c in fake.calls]
    assert WEB_ADDRESS + '/admin/' == fake.calls[0][1]
    method, url, kwargs = fake.calls[1]
    assert WEB_ADDRESS + '/admin/setpassword' == url
    assert dict(username='admin', password1='admin', password2='admin',
                setup_token='the-token') == kwargs['data']
    assert kwargs['allow_redirects'] is False


def test_create_web_admin_skips_when_users_exist(tmp_path):
    with open(tmp_path / 'web-users.json', 'w') as fp:
        jsonapi.dump({'admin': {'groups': ['admin']}}, fp)
    fake = FakeRequests(str(tmp_path))

    assert _create(str(tmp_path), fake) is None
    assert [] == fake.calls


def test_create_web_admin_raises_with_the_cause_when_the_page_is_unreachable(tmp_path):
    fake = FakeRequests(str(tmp_path), get_error=ConnectionError('refused by test'))

    with pytest.raises(RuntimeError, match='refused by test'):
        _create(str(tmp_path), fake)
    assert ['get'] == [c[0] for c in fake.calls]


def test_create_web_admin_raises_when_the_setup_page_fails(tmp_path):
    fake = FakeRequests(str(tmp_path), get_status=503, write_token=False)

    with pytest.raises(RuntimeError, match='503'):
        _create(str(tmp_path), fake)
    assert ['get'] == [c[0] for c in fake.calls]


def test_create_web_admin_raises_when_no_setup_token_was_written(tmp_path):
    fake = FakeRequests(str(tmp_path), write_token=False)

    with pytest.raises(RuntimeError, match=SETUP_TOKEN_FILE):
        _create(str(tmp_path), fake)
    assert ['get'] == [c[0] for c in fake.calls]


@pytest.mark.parametrize('post_status, post_error, expected', [
    (403, None, '403'),
    (200, None, '200'),
    (None, ConnectionError('reset by test'), 'reset by test'),
])
def test_create_web_admin_raises_when_creation_is_not_confirmed(tmp_path, post_status, post_error, expected):
    fake = FakeRequests(str(tmp_path), post_status=post_status, post_error=post_error)

    with pytest.raises(RuntimeError, match=expected):
        _create(str(tmp_path), fake)
