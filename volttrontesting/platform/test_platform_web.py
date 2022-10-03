import random

import requests

from volttron.platform.agent.known_identities import PLATFORM_WEB
from volttron.platform.vip.agent import Agent
from volttrontesting.utils.platformwrapper import start_wrapper_platform
from volttron.utils import get_hostname
from volttrontesting.fixtures.volttron_platform_fixtures import *


def _build_web_agent(vhome):
    """
    Builds a full web enabled agent with a webroot, jsonrpc endpoint..etc.

    :param vhome:
    :return: The directory of the agent to be installed.
    """
    agent_dir = os.path.join(vhome, "Agent{}".format(random.randint(1, 100)))

    package = "webagent"
    os.makedirs(agent_dir)
    package_dir = os.path.join(agent_dir, package)
    os.makedirs(package_dir)
    web_dir = os.path.join(package_dir, 'webroot', 'web')
    os.makedirs(web_dir)

    # Create index.html inside the webroot directory.
    with open(os.path.join(web_dir, 'index.html'), 'w') as f:
        f.write("""
    <html>
        <head>
            <title>Test Page</title>
        </head>
        <body>
            <h1>The body is good</h1>
        </body>
    </html>
    """)

    # Create the setup.py file
    with open(os.path.join(agent_dir, 'setup.py'), 'w') as file:
        file.write('''
from setuptools import setup, find_packages

packages = find_packages('.')

setup(
    include_package_data=True,
    name = '{package}',
    version = '0.1',
    packages = packages,
    zip_safe = False,
    entry_points={{
        'setuptools.installation': [
            'eggsecutable = {package}.agent:main',
        ]
    }}
)
    '''.format(package=package))

    # Crate a manifest file to allow inclusion of other files
    with open(os.path.join(agent_dir, 'MANIFEST.in'), 'w') as file:
        file.write("recursive-include {package}/webroot *".format(
            package=package))

    # Make python package
    with open(os.path.join(package_dir, '__init__.py'), 'w') as f:
        pass

    # Create the agent.py file in the package directory.
    with open(os.path.join(package_dir, 'agent.py'), 'w') as fout:
        fout.write('''
import base64
import logging
import os
import sys

from volttron.platform.vip.agent import Core, Agent
from volttron.platform.agent import utils
from volttron.platform import jsonrpc
from volttron.platform import jsonapi

utils.setup_logging()
_log = logging.getLogger(__name__)

MY_PATH = os.path.dirname(__file__)
WEBROOT = os.path.join(MY_PATH, "webroot")


class WebAgent(Agent):
    def __init__(self, config_path, **kwargs):
        super(WebAgent, self).__init__(enable_web=True, **kwargs)

    @Core.receiver("onstart")
    def starting(self, sender, **kwargs):
        self.vip.web.register_endpoint("/web/text", self.text, "raw")
        self.vip.web.register_endpoint("/web/jsonrpc", self.echoendpoint)
        self.vip.web.register_path("/web", WEBROOT)

    def text(self, env, data):
        ret = "200 OK", "this is some text", [
            ('Content-Type', 'text/plain')]
        _log.debug('returning: {}'.format(ret))
        return ret

    def echoendpoint(self, env, data):
        ret = jsonrpc.json_result('id', jsonapi.loadb(data))
        _log.debug('returning: {}'.format(ret))
        return ret

def main():
    utils.vip_main(WebAgent)

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
    ''')

    return agent_dir


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
def test_can_discover_info(volttron_instance_web):
    """
    Tests whether the web instance returns the key, instance name and
    instance tcp address.
    """

    vi = volttron_instance_web

    with with_os_environ(vi.env):
        url = "{}/discovery/".format(vi.bind_web_address)
        res = requests.get(url)
        assert res.ok

        d = res.json()
        if vi.messagebus == 'zmq' and vi.auth_enabled:
            assert vi.serverkey == d['serverkey']
            assert d['vip-address']

        assert d['instance-name']

        if vi.messagebus == 'rmq':
            rmq_config = vi.rabbitmq_config_obj

            assert vi.certsobj.ca_cert(public_bytes=True).decode('utf-8') == d['rmq-ca-cert']
            assert f"amqps://{get_hostname()}:{rmq_config.rmq_port_ssl}/{rmq_config.virtual_host}" == \
                   d["rmq-address"]


@pytest.mark.web
@pytest.mark.xfail(reason="The web install test has some issues that need to be resolved")
def test_test_web_agent(volttron_instance_web):
    vi = volttron_instance_web

    with with_os_environ(vi.env):
        assert vi.is_running()
        web_agent = _build_web_agent(vi.volttron_home)
        vi.install_agent(agent_dir=web_agent)
        agent_list = vi.list_agents()
        assert len(agent_list) == 1
        gevent.sleep(3)
        base_address = vi.bind_web_address
        index = base_address + "/web/index.html"
        text = base_address + "/web/text"
        rpc = base_address + "/web/jsonrpc"
        resp = requests.get(index)
        assert "<h1>The body is good</h1>" in resp.text
        assert "<html>" in resp.text
        assert "</html>" in resp.text
        assert resp.headers['Content-type'] == 'text/html'

        print(f"URL: {text}")
        resp = requests.get(text)
        assert resp.ok
        print("*" * 50)
        print(resp.headers)
        assert "This is some text" == resp.text
        assert resp.headers['Content-type'] == 'text/plain'

        # now test for json rpc
        payload = {"data": "value", "one": 5, "three": {"two": 1.0}}
        print(f"URL: {rpc}")
        resp = requests.post(rpc, json=payload)
        assert resp.ok
        assert resp.headers['Content-type'] == 'application/json'
        jsonresp = resp.json()['result']

        print(jsonresp)

        for k, v in payload.items():
            assert v == jsonresp[k]


@pytest.mark.web
def test_register_path_route(web_instance):
    vi = web_instance

    with with_os_environ(vi.env):
        assert vi.is_running()
        gevent.sleep(1)

        webdir, index_html = _build_web_dir(vi.volttron_home)
        agent = vi.build_agent(use_ipc=True)
        agent.vip.rpc.call(PLATFORM_WEB,
                           'register_path_route', '', webdir).get(timeout=5)
        response = requests.get(vi.bind_web_address + "/index.html")
        assert index_html == response.text


@pytest.mark.web
@pytest.mark.skipif(True, reason="This works but not in this test.")
def test_register_agent_route(web_instance):
    vi = web_instance
    assert vi.is_running()

    request_data = None
    request_env = None

    class TestWebEnabledAgent(Agent):

        def agent_route_callback(self, env, data):
            print("RETURNING DATA CALLBACK!")
            request_data = data
            request_env = env
            return data

    agent = vi.build_agent(enable_web=True, identity='web.agent',
                           agent_class=TestWebEnabledAgent)
    gevent.sleep(2)
    agent.vip.web.register_endpoint("/foo", agent.agent_route_callback)
    gevent.sleep(2)
    payload = {"data": "value", "one": 5, "three": {"two": 1.0}}
    response = requests.post(vi.bind_web_address + "/foo", json=payload)
    assert response.ok
