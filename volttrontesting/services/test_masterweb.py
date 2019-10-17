"""
This file tests the MasterWebService as it is used in the base platform.  Most
of the tests in here are not integration tests, but unit tests to test the
functionality of the MasterWebService agent.
"""
import mock
from io import BytesIO
import pytest

from volttron.platform import jsonapi
from volttron.platform.agent.known_identities import MASTER_WEB
from volttron.platform.vip.agent import Agent
from volttron.platform.vip.agent.subsystems.web import ResourceType
from volttrontesting.utils.utils import AgentMock
from volttron.platform.web import MasterWebService

# Patch the MasterWebService so the underlying Agent interfaces are mocked
# so we can just test the things that the MasterWebService is responsible for.
MasterWebService.__bases__ = (AgentMock.imitate(Agent, Agent()),)


@pytest.fixture()
def master_web_service():
    serverkey = "serverkey"
    mock_aip = mock.Mock()
    yield MasterWebService(serverkey=serverkey, identity=MASTER_WEB, address="tcp://stuff",
                           bind_web_address="http://v2:8888", aip=mock_aip)


def add_points_of_interest(ws: MasterWebService, endpoints: dict):
    for k, v in endpoints.items():
        if v['type'] == 'agent_route':
            ws.register_agent_route(k, v['fn'])
        elif v['type'] == 'endpoint':
            ws.register_endpoint(k, ResourceType.RAW.value)
        elif v['type'] == 'path':
            ws.register_path_route(k, v['root_dir'])
        else:
            raise ValueError(f"Invalid type specified in endpoints dictionary {k}")


def test_register_route(master_web_service: MasterWebService):
    ws = master_web_service
    fn_mock = mock.Mock()
    fn_mock.__name__ = "test_register_route"
    interest = {'/web': {'type': 'agent_route', 'fn': fn_mock}}
    routes_before = len(ws.peerroutes)
    registered_routes_before = len(ws.registeredroutes)
    add_points_of_interest(ws, interest)
    assert routes_before + 1 == len(ws.peerroutes)
    assert registered_routes_before + 1 == len(ws.registeredroutes)
    ws.unregister_all_agent_routes()
    assert routes_before == len(ws.peerroutes)
    assert registered_routes_before == len(ws.registeredroutes)


def test_register_endpoint(master_web_service: MasterWebService):
    ws = master_web_service
    fn_mock = mock.Mock()
    fn_mock.__name__ = "test_register_endpoint"
    interest = {"/battle/one": {'type': 'endpoint'}}
    add_points_of_interest(ws, interest)

    assert len(ws.endpoints) == 1
    ws.unregister_all_agent_routes()
    assert len(ws.endpoints) == 0


def test_register_path_route(master_web_service: MasterWebService):
    ws = master_web_service
    fn_mock = mock.Mock()
    fn_mock.__name__ = "test_register_path_route"
    interest = {"/foo": {"type": "path", "root_dir": "./foo"}}
    registerd_routes_before = len(ws.registeredroutes)
    add_points_of_interest(ws, interest)
    assert 1 == len(ws.pathroutes)
    assert registerd_routes_before + 1 == len(ws.registeredroutes)
    ws.unregister_all_agent_routes()
    assert 0 == len(ws.pathroutes)
    assert registerd_routes_before == len(ws.registeredroutes)

