import logging

import gevent
from zmq.utils import jsonapi as json
import pytest
import requests

logging.basicConfig(level=logging.DEBUG)
from volttrontesting.utils.build_agent import build_agent, build_agent_with_key


@pytest.mark.web
def test_can_discover_key(volttron_instance1_web):

    vi = volttron_instance1_web
    assert vi.is_running()
    # must sleep because the web server takes a bit to get going.
    gevent.sleep(1)
    url = "http://{}/discovery/".format(vi.bind_web_address)
    res = requests.get(url)
    assert res.ok

    d = res.json()
    assert vi.publickey == d['serverkey']
    assert d['vip-address']
