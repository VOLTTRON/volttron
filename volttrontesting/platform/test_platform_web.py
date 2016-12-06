import logging

import gevent
from volttrontesting.utils.platformwrapper import start_wrapper_platform
from zmq.utils import jsonapi as json
import pytest
import requests
import os

logging.basicConfig(level=logging.DEBUG)
from volttrontesting.utils.build_agent import build_agent, build_agent_with_key


@pytest.fixture(scope="module")
def volttron_instance_web_enabled(request, get_volttron_instances):
    instance = get_volttron_instances(1, should_start=False)

    start_wrapper_platform(instance, with_http=True)

    return instance


def _build_web_dir(vhome):
    """ Creates a web directory that can be served.

    The web directory will contain an index.html file that should be
    able to be retrieved.


    @param:str:
        The path to vhome or where it should be

    @return:tuple:
        The path to the web directory and the content of index.html.

    """
    webdir = os.path.join(vhome, "webdir")
    os.makedirs(webdir)
    html = """
        <html>
            <head>
                <title>Test Page</title>
            </head>
            <body>
                <h1>The body is good</h1>
            </body>
        </html>
        """
    with open(os.path.join(webdir, 'index.html'), 'w') as f:
        f.write(html)

    return webdir, html

@pytest.mark.web
def test_can_discover_key(volttron_instance_web_enabled):

    vi = volttron_instance_web_enabled

    # must sleep because the web server takes a bit to get going.
    gevent.sleep(1)
    url = "{}/discovery/".format(vi.bind_web_address)
    res = requests.get(url)
    assert res.ok

    d = res.json()
    assert vi.serverkey == d['serverkey']
    assert d['vip-address']


@pytest.mark.web
def test_register_path_route(volttron_instance_web_enabled):
    vi = volttron_instance_web_enabled
    assert vi.is_running()
    gevent.sleep(1)

    webdir, index_html = _build_web_dir(vi.volttron_home)
    agent = vi.build_agent(use_ipc=True)
    agent.vip.rpc.call('master.web',
                       'register_path_route', '', webdir).get(timeout=5)
    response = requests.get(vi.bind_web_address+"/index.html")
    assert index_html == response.text

@pytest.mark.web
def test_register_agent_route(volttron_instance_web_enabled):
    vi = volttron_instance_web_enabled
    assert vi.is_running()

    request_data = None
    request_env = None

    def agent_route_callback(env, data):
        request_data = data
        request_env = env
        return data

    agent = vi.build_agent(enable_web=True, identity='web.agent')
    agent.vip.web.register_endpoint("/foo", agent_route_callback)

    payload = {"data": "value", "one": 5, "three": {"two": 1.0}}
    response = requests.post(vi.bind_web_address+"/foo", json=payload)
    assert response.ok
