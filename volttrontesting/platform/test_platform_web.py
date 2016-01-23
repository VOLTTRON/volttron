import logging

import gevent
from zmq.utils import jsonapi as json
import pytest
import requests

logging.basicConfig(level=logging.DEBUG)
from volttrontesting.utils.build_agent import build_agent, build_agent_with_key

WEB = "http://localhost:8080"


def web_path(path):
    return '{}/{}'.format(WEB, path)


@pytest.mark.web
def test_can_discover_key(volttron_instance1_encrypt):

    vi = volttron_instance1_encrypt
    assert vi.is_running()
    # must sleep because the web server takes a bit to get going.
    gevent.sleep(1)
    url = web_path('discovery/')
    print('requesting url: {}'.format(url))
    res = requests.get(web_path(url))
    print(res.text)
    d = res.json()

    assert vi.publickey == d['serverkey']