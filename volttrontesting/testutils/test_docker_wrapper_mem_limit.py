"""create_container must cap container memory so a database server cannot size its buffers against the host."""
import pytest

docker = pytest.importorskip("docker")

from volttrontesting.fixtures.docker_wrapper import create_container

# Tiny pinned image; the wrapper pulls it when absent.
IMAGE = "alpine:3.20"
SLEEP = ["sleep", "60"]
GIB = 1024 ** 3


def _configured_memory(container) -> int:
    """Read the limit back through the Docker API, as the daemon enforces it."""
    return docker.from_env(version="auto").api.inspect_container(container.id)["HostConfig"]["Memory"]


@pytest.mark.unit
def test_default_memory_limit_is_two_gib():
    with create_container(IMAGE, command=SLEEP) as container:
        assert container is not None
        assert _configured_memory(container) == 2 * GIB


@pytest.mark.unit
def test_caller_memory_limit_is_applied():
    with create_container(IMAGE, command=SLEEP, mem_limit="512m") as container:
        assert container is not None
        assert _configured_memory(container) == 512 * 1024 ** 2
