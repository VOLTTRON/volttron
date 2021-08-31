import os

import gevent
import pytest

from volttrontesting.fixtures.volttron_platform_fixtures import volttron_instance_web


@pytest.fixture(scope="module")
def user_pass():
    yield 'admin', 'admin'


def test_can_authenticate_admin_user(volttron_instance_web, user_pass):
    instance = volttron_instance_web

    webadmin = instance.web_admin_api

    user, password = user_pass

    resp = webadmin.authenticate(user, password)
    assert resp.ok
    assert resp.headers.get('Content-Type') == 'application/json'

    resp = webadmin.authenticate('fake', password)
    assert resp.status_code == 401  # unauthorized
    assert resp.headers.get('Content-Type') == 'text/html'


@pytest.mark.skip(reason="Can't test using platformwrapper. Needs to be unit test")
def test_can_create_admin_user(volttron_instance_web, user_pass):
    instance = volttron_instance_web
    webadmin = instance.web_admin_api
    user, password = user_pass

    resp = webadmin.create_web_admin(user, password)
    assert resp.ok
    # Allow file operation to run
    gevent.sleep(2)

    resp = webadmin.authenticate(user, password)
    assert resp.ok
    assert resp.headers.get('Content-Type') == 'application/json'

    resp = webadmin.authenticate('fake', password)
    assert resp.status_code == 401  # unauthorized
    assert resp.headers.get('Content-Type') == 'text/html'

