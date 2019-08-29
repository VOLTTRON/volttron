import docker

client = docker.from_env()

container = client.containers.run('postgres', detach=True, auto_remove=True,
                                  ports={5432:5432}, environment={'POSTGRES_PASSWORD': 'test'})

print(container.id)