import pytest
from  openadr_ven.volttron_openadr_client import OpenADRClientInterface

try:
    import openleadr
except ModuleNotFoundError as e:
    pytest.skip(
        f"openleadr not found! \nPlease install openleadr to run \
    tests: pip install openleadr.\n Original error message: {e}",
        allow_module_level=True,
    )

from pathlib import Path
from mock import MagicMock

from volttrontesting.utils.utils import AgentMock
from volttron.platform.vip.agent import Agent

from openadr_ven.agent import OpenADRVenAgent


@pytest.mark.asyncio
async def test_handle_event_should_return_optIn(mock_openadr_ven):
    # mocking the VIP subsystem
    vipmock = MagicMock()
    pubsub_publishmock = MagicMock()
    pubsub_publishmock.return_value.get.return_value = [42424]
    vipmock.pubsub.publish = pubsub_publishmock
    mock_openadr_ven.vip = vipmock

    expected = await mock_openadr_ven.handle_event(
        {"event_descriptor": {"test_event": True}, "event_signals": [42]}
    )

    assert expected == "optIn"


@pytest.fixture
def mock_openadr_ven():
    config_path = f"{Path(__file__).parent.absolute()}/config_test.json"
    OpenADRVenAgent.__bases__ = (
        AgentMock.imitate(Agent, OpenADRVenAgent(config_path)),
    )

    yield OpenADRVenAgent(config_path, fake_ven_client=FakeOpenADRClient())


class FakeOpenADRClient(OpenADRClientInterface):
    def __init__(self):
        self.ven_name = "fake_ven_name"
    
    async def run(self):
        pass

    
    def get_ven_name(self):
        pass

    
    def add_handler(self, event, function):
        pass

    def add_report(
        self,
        callback,
        report_name,
        resource_id,
        measurement,
    ):
        pass
