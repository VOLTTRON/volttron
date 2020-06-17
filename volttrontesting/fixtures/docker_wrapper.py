try:
    import docker

    HAS_DOCKER = True
except ImportError:
    HAS_DOCKER = False

import time
import contextlib

# Only allow this function if docker is available from the pip library.
if HAS_DOCKER:

    @contextlib.contextmanager
    def create_container(image_name: str, ports: dict = None, env: dict = None, command: (list, str) = None,
                         startup_time_seconds: int = 30) -> \
            (docker.models.containers.Container, None):
        """ Creates a container instance in a context that will clean up after itself.

        This is a wrapper around the docker api documented at https://docker-py.readthedocs.io/en/stable/containers.html.
        Some things that this will do automatically for the caller is make the container be ephemeral by removing it
        once the context manager is cleaned up.

        This function is being used for long running processes.  Short processes may not work correctly because
        the execution time might be too short for the returning of data from the container.

        Usage:

            with create_container("mysql", {"3306/tcp": 3306}):
                # connect to localhost:3306 with mysql using connector

        :param image_name: The image name (from dockerhub) that is to be instantiated
        :param ports:
            a dictionary following the convention {'portincontainre/protocol': portonhost}

            ::
                # example port exposing mysql's known port.
                {'3306/tcp': 3306}
        :param env:
        :param command: string or list of commands to run during the startup of the container.
        :param startup_time_seconds: Allow this many seconds for the startup of the container before raising a
            runtime exception (Download of image and instantiation could take a while)

        :return:
            A container object (https://docker-py.readthedocs.io/en/stable/containers.html.) or None
        """

        # Create docker client (Uses localhost as agent connection.
        client = docker.from_env()
        if ":" in image_name:
            client.images.pull(image_name)
        else:
            # So all tags aren't pulled. According to docs https://docker-py.readthedocs.io/en/stable/images.html.
            client.images.pull(image_name + ":latest")
        container = client.containers.run(image_name, ports=ports, environment=env, auto_remove=True, detach=True)

        if container is None:
            raise RuntimeError(f"Unable to run image {image_name}")

        error_time = time.time() + startup_time_seconds
        invalid = False
        while container.status != 'running':
            if time.time() > error_time:
                invalid = True
                break
            time.sleep(0.1)
            container.reload()

        if invalid:
            yield None
        else:
            yield container

        container.kill()

