import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from volttrontesting.platform.web.conftest import set_caller
from volttrontesting.utils.web_utils import get_test_web_env


def test_register_routes(web_service, tmp_path, monkeypatch):
    # A path route serves <root><request path>, so the junk namespace maps
    # to <root>/junk.
    html_root = tmp_path / "html"
    os.makedirs(html_root / "junk")
    attempt_to_get_file = tmp_path / "index.html"
    should_get_index_file = html_root / "junk" / "index.html"
    file_contents_bad = "HOLY COW!"
    file_contents_good = "Woot there it is!"
    attempt_to_get_file.write_text(file_contents_bad)
    should_get_index_file.write_text(file_contents_good)
    monkeypatch.chdir(tmp_path)

    pws = web_service
    set_caller(pws, "foo")
    routes_before = len(pws.registeredroutes)

    pws.register_path_route("^/junk/.*", str(html_root))
    with pytest.raises(PermissionError):
        pws.register_path_route("/flubber", ".")
    # Test to make sure the route is resolved to a full directory so easier
    # to detect chroot for html paths.
    added = pws.registeredroutes[routes_before - 1:-1]
    assert len(pws.registeredroutes) == routes_before + 1
    assert [x[2] for x in added] == [str(html_root.resolve())]
    for x in added:
        # x is a tuple regex, 'path', directory
        assert Path(x[2]).is_absolute()

    start_response = MagicMock()
    data = pws.app_routing(get_test_web_env("/junk/index.html"), start_response)
    data = "".join([x.decode("utf-8") for x in data])
    assert "200 OK" in start_response.call_args[0]
    assert data == file_contents_good

    # Test relative route to the index.html file above the html_root, but using a
    # rooted path to do so.
    start_response.reset_mock()
    data = pws.app_routing(get_test_web_env("/junk/../../index.html"), start_response)
    data = "".join([x.decode("utf-8") for x in data])
    assert "403 Forbidden" in start_response.call_args[0]
    assert "403 Forbidden" in data

    # Test relative route to the index.html file above the html_root.
    start_response.reset_mock()
    data = pws.app_routing(get_test_web_env("../index.html"), start_response)
    data = "".join([x.decode("utf-8") for x in data])
    assert "200 OK" not in start_response.call_args[0]
    assert data != file_contents_bad
