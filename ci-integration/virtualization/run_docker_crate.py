import docker

client = docker.from_env()

container = client.containers.run('crate', detach=True, auto_remove=True,
                                  ports={4200:4200})

print(container.id)