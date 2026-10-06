"""create_container must cap container memory so a database server cannot size its buffers against the host."""
import logging
import time
from unittest import mock

import pytest

docker = pytest.importorskip("docker")
from docker.errors import APIError, NotFound

from volttrontesting.fixtures.docker_wrapper import create_container

# Tiny pinned image; the wrapper pulls it when absent.
IMAGE = "alpine:3.20"
SLEEP = ["sleep", "60"]
GIB = 1024 ** 3


def _host_config(container) -> dict:
    """Read the limits back through the Docker API, as the daemon enforces them."""
    return docker.from_env(version="auto").api.inspect_container(container.id)["HostConfig"]


def _configured_memory(container) -> int:
    return _host_config(container)["Memory"]


@pytest.mark.unit
def test_default_memory_limit_is_two_gib():
    with create_container(IMAGE, command=SLEEP) as container:
        assert container is not None
        assert _configured_memory(container) == 2 * GIB
        assert _host_config(container)["MemorySwap"] == 2 * GIB


@pytest.mark.unit
def test_caller_memory_limit_is_applied():
    with create_container(IMAGE, command=SLEEP, mem_limit="512m") as container:
        assert container is not None
        assert _configured_memory(container) == 512 * 1024 ** 2
        assert _host_config(container)["MemorySwap"] == 512 * 1024 ** 2


@pytest.mark.unit
def test_body_exception_survives_container_that_stopped_on_its_own():
    with pytest.raises(ValueError, match="test body failed"):
        with create_container(IMAGE, command=["sleep", "1"]) as container:
            assert container is not None
            time.sleep(4)
            raise ValueError("test body failed")


def _mock_container(status="running"):
    container = mock.Mock(id="abc123", status=status)
    container.attrs = {"State": {"ExitCode": 137, "OOMKilled": True}}
    return container


def _patched_client(container, in_docker):
    client = mock.Mock()
    client.containers.run.return_value = container
    client.api.inspect_container.return_value = {"NetworkSettings": {"Networks": {"testnet": {}}}}
    return client, [
        mock.patch("docker.from_env", return_value=client),
        mock.patch("subprocess.run", return_value=mock.Mock(returncode=0)),
        mock.patch("os.path.exists", return_value=in_docker),
        mock.patch.dict("os.environ", {"HOSTNAME": "me"}),
    ]


def _enter(patches):
    for p in patches:
        p.start()


def _exit(patches):
    for p in patches:
        p.stop()


@pytest.mark.unit
@pytest.mark.parametrize("in_docker", [True, False])
def test_run_receives_cap_and_command_on_both_branches(in_docker):
    container = _mock_container()
    client, patches = _patched_client(container, in_docker)
    _enter(patches)
    try:
        with create_container(IMAGE, command=["sleep", "5"], mem_limit="256m"):
            pass
    finally:
        _exit(patches)
    kwargs = client.containers.run.call_args.kwargs
    assert kwargs["mem_limit"] == "256m"
    assert kwargs["memswap_limit"] == "256m"
    assert kwargs["command"] == ["sleep", "5"]
    assert ("network" in kwargs) == in_docker


@pytest.mark.unit
def test_stopped_container_is_logged_with_exit_code_and_oom(caplog):
    container = _mock_container()
    container.kill.side_effect = NotFound("gone")
    _, patches = _patched_client(container, False)
    _enter(patches)
    try:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError, match="body"):
                with create_container(IMAGE):
                    raise ValueError("body")
    finally:
        _exit(patches)
    assert "exit code 137" in caplog.text
    assert "OOM-killed: True" in caplog.text


@pytest.mark.unit
def test_container_gone_during_startup_is_reported():
    container = _mock_container(status="created")
    container.reload.side_effect = NotFound("gone")
    _, patches = _patched_client(container, False)
    _enter(patches)
    try:
        with pytest.raises(RuntimeError, match="exited during startup"):
            with create_container(IMAGE):
                pytest.fail("body must not run")
    finally:
        _exit(patches)


def _conflict(status):
    response = mock.Mock(status_code=status)
    return APIError("kill failed", response=response)


@pytest.mark.unit
@pytest.mark.parametrize("status, expected", [(409, ValueError), (500, APIError)])
def test_kill_conflict_is_tolerated_but_other_api_errors_are_not(status, expected):
    container = _mock_container()
    container.kill.side_effect = _conflict(status)
    _, patches = _patched_client(container, False)
    _enter(patches)
    try:
        with pytest.raises(expected):
            with create_container(IMAGE):
                raise ValueError("body")
    finally:
        _exit(patches)
