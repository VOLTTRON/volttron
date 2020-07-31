import pytest
import requests
import gevent
import os


def test_web_service_running(volttron_instance_web):
    instance = volttron_instance_web
    # This allows the requests object to use the root ca to validate the
    # server client connection.
    if instance.ssl_auth:
        os.environ['REQUESTS_CA_BUNDLE'] = instance.certsobj.cert_file(instance.certsobj.root_ca_name)
    resp = requests.get(volttron_instance_web.discovery_address)

    assert resp.ok