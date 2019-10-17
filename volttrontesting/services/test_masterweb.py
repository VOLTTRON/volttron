"""
This file tests the MasterWebService as it is used in the base platform.  Most
of the tests in here are not integration tests, but unit tests to test the
functionality of the MasterWebService agent.
"""
import mock
import pytest

from volttron.platform.agent.known_identities import MASTER_WEB
from volttron.platform.vip.agent import Agent
from volttron.platform.vip.agent.subsystems.web import ResourceType
from volttrontesting.utils.utils import AgentMock
from volttron.platform.web import MasterWebService


MasterWebService.__bases__ = (AgentMock.imitate(Agent, Agent()),)


@pytest.fixture()
def master_web_service():
    serverkey = "serverkey"
    mock_aip = mock.Mock()
    yield MasterWebService(serverkey=serverkey, identity=MASTER_WEB, address="tcp://stuff",
                           bind_web_address="http://v2:8888", aip=mock_aip)


def test_register_route(master_web_service: MasterWebService):
    ws = master_web_service
    fn_mock = mock.Mock()
    fn_mock.__name__ = "test_register_route"
    ws.register_agent_route("/web/", fn_mock)
    assert len(ws.peerroutes) == 1
    assert len(ws.registeredroutes) == 1
    ws.unregister_all_agent_routes()
    assert len(ws.peerroutes) == 0
    assert len(ws.registeredroutes) == 0


def test_register_endpoint(master_web_service: MasterWebService):
    ws = master_web_service
    fn_mock = mock.Mock()
    fn_mock.__name__ = "test_register_endpoint"
    ws.register_endpoint("/battle/one", ResourceType.RAW.value)

    assert len(ws.endpoints) == 1
    ws.unregister_all_agent_routes()
    assert len(ws.endpoints) == 0


def test_register_path_route(master_web_service: MasterWebService):
    ws = master_web_service
    fn_mock = mock.Mock()
    fn_mock.__name__ = "test_register_path_route"
    ws.register_path_route("/foo/", "./foo")

    assert len(ws.pathroutes) == 1
    assert len(ws.registeredroutes) == 1
    ws.unregister_all_agent_routes()
    assert len(ws.pathroutes) == 0
    assert len(ws.registeredroutes) == 0
