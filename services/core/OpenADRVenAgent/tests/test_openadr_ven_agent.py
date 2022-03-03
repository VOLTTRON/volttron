try:
    import openleadr
except ModuleNotFoundError as e:
    print("Please install openleadr to run tests: pip install openleadr")
    print(f"Original error message: {e}")

import pytest

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

    expected = await mock_openadr_ven.handle_event({"event_signals": [42]})

    assert expected == 'optIn'


@pytest.fixture
def mock_openadr_ven():
    config_path = str(Path('config_test.json').absolute())
    OpenADRVenAgent.__bases__ = (AgentMock.imitate(Agent, OpenADRVenAgent(config_path)),)

    yield OpenADRVenAgent(config_path, fake_ven_client=FakeOpenADRClient())


class FakeOpenADRClient:
    def __init__(self):
        self.ven_name = 'fake_ven_name'
