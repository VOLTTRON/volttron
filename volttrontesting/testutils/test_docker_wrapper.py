import pytest


try:
    SKIP_DOCKER = False
    from volttrontesting.fixtures.docker_wrapper import create_container
except ImportError:
    SKIP_DOCKER = True

SKIP_REASON = "No docker available in api (install pip install docker) for availability"


@pytest.mark.skipif(SKIP_DOCKER, reason=SKIP_REASON)
def test_docker_wrapper():
    with create_container("mysql", ports={"3306/tcp": 3306}, env={"MYSQL_ROOT_PASSWORD": "12345"}) as container:
        print(f"\nStatus: {container.status}")
        print(f"\nLogs: {container.logs()}")
        assert container.status == 'running'


@pytest.mark.skipif(SKIP_DOCKER, reason=SKIP_REASON)
def test_docker_run_crate_latest():
    with create_container("crate", ports={"4200/tcp": 4200}) as container:
        assert container.status == 'running'


@pytest.mark.skipif(SKIP_DOCKER, reason=SKIP_REASON)
def test_docker_wrapper_should_throw_runtime_error_on_false_image_when_pull():
    with pytest.raises(RuntimeError) as execinfo:
        with create_container("not_a_real_image", ports={"4200/tcp": 4200}) as container:
            container.logs()

    assert "404 Client Error: Not Found" in str(execinfo.value)


@pytest.mark.skipif(SKIP_DOCKER, reason=SKIP_REASON)
def test_docker_wrapper_should_throw_runtime_error_when_ports_clash():
    port = 4200
    with pytest.raises(RuntimeError) as execinfo:
        with create_container("crate", ports={"4200/tcp": port}):
            with create_container("crate", ports={"4200/tcp": port}) as container2:
                assert container2.status == 'running'

    assert "500 Server Error: Internal Server Error" in str(execinfo.value)

