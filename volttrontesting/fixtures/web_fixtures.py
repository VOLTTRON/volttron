from unittest import mock
from unittest.mock import MagicMock

from gevent.event import AsyncResult
import pytest

from volttron.platform.vip.agent import Agent
from volttron.platform.web import PlatformWebService
from volttrontesting.utils.utils import AgentMock


class QueryHelper:
    """
    Query helper allows us to mock out the Query subsystem and return default
    values for calls to it.
    """

    def __init__(self, core):
        pass

    def query(self, name):
        result = AsyncResult()
        result.set_result('my_instance_name')
        return result


@pytest.fixture()
def mock_platform_web_service() -> PlatformWebService:
    PlatformWebService.__bases__ = (AgentMock.imitate(Agent, Agent()),)
    with mock.patch(target='volttron.platform.web.vui_endpoints.Query', new=QueryHelper):
        platform_web = PlatformWebService(serverkey=MagicMock(),
                                          identity=MagicMock(),
                                          address=MagicMock(),
                                          bind_web_address=MagicMock())
        # Internally the register uses this value to determine the caller's identity
        # to allow the platform web service to map calls back to the proper agent
        platform_web.vip.rpc.context.vip_message.peer.return_value = "foo"
        platform_web.core.volttron_home = 'foo_home'
        platform_web.core.instance_name = 'my_instance_name'
        platform_web.get_user_claims = lambda x: {'groups': ['vui']}

        yield platform_web
