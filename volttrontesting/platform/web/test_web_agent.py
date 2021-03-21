import os
from pathlib import Path
import shutil
from unittest.mock import MagicMock

import pytest

from volttron.platform.vip.agent import Agent
from volttron.platform.web import PlatformWebService
from volttrontesting.utils.utils import AgentMock
from volttrontesting.utils.web_utils import get_test_web_env


@pytest.fixture()
def mock_platformweb_service() -> PlatformWebService:
    PlatformWebService.__bases__ = (AgentMock.imitate(Agent, Agent()),)
    platformweb = PlatformWebService(serverkey=MagicMock(),
                                     identity=MagicMock(),
                                     address=MagicMock(),
                                     bind_web_address=MagicMock())
    # rpc_caller = platformweb.vip.rpc
    # platformweb._admin_endpoints = AdminEndpoints(rpc_caller=rpc_caller)

    # Internally the register uses this value to determine the caller's identity
    # to allow the platform web service to map calls back to the proper agent
    platformweb.vip.rpc.context.vip_message.peer.return_value = "foo"

    yield platformweb


def test_register_routes(mock_platformweb_service):
    html_root = "/tmp/junk/html"
    attempt_to_get_file = "/tmp/junk/index.html"
    should_get_index_file = os.path.join(html_root, "index.html")
    file_contents_bad = "HOLY COW!"
    file_contents_good = "Woot there it is!"
    try:

        os.makedirs(html_root, exist_ok=True)
        with open(attempt_to_get_file, "w") as should_not_get:
            should_not_get.write(file_contents_bad)
        with open(should_get_index_file, "w") as should_get:
            should_get.write(file_contents_good)

        pws = mock_platformweb_service

        pws.register_path_route(f"/.*", html_root)

        start_response = MagicMock()
        data = pws.app_routing(get_test_web_env("/index.html"), start_response)
        data = "".join([x.decode("utf-8") for x in data])
        assert "200 OK" in start_response.call_args[0]
        assert data == file_contents_good

        # Test relative route to the index.html file above the html_root, but using a
        # rooted path to do so.
        start_response.reset_mock()
        data = pws.app_routing(get_test_web_env("/../index.html"), start_response)
        data = "".join([x.decode("utf-8") for x in data])
        assert "404 Not Found" in start_response.call_args[0]
        assert data != file_contents_bad

        # Test relative route to the index.html file above the html_root.
        start_response.reset_mock()
        data = pws.app_routing(get_test_web_env("../index.html"), start_response)
        data = "".join([x.decode("utf-8") for x in data])
        assert "200 OK" not in start_response.call_args[0]
        assert data != file_contents_bad


    finally:
        shutil.rmtree(str(Path(html_root).parent), ignore_errors=True)
