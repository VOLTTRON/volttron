#!/usr/bin/env python3

import docker
import os
import re
import shutil
import gevent
import urllib.request
import logging


def expand_all(user_path):
    return os.path.expandvars(os.path.expanduser(user_path))


# This path needs to be the path to the repo where the data is done.
GRIDAPPSD_TEST_REPO = expand_all(os.environ.get("GRIDAPPSD_TEST_REPO", os.path.dirname(__file__)))
GRIDAPPSD_DATA_REPO = expand_all(os.environ.get("GRIDAPPSD_DATA_REPO", "/tmp/gridappsd_temp_data"))

if not os.path.exists(GRIDAPPSD_TEST_REPO):
    raise AttributeError(f"Invalid GRIDAPPSD_TEST_REPO {GRIDAPPSD_TEST_REPO}")

os.makedirs(GRIDAPPSD_DATA_REPO, exist_ok=True)

repo_dir = GRIDAPPSD_TEST_REPO
data_dir = GRIDAPPSD_DATA_REPO

_log = logging.getLogger(__name__)

gridappsd_docker_config = {
    'influxdb': {
        'start': True,
        'image': 'gridappsd/influxdb:develop',
        'pull': True,
        'ports': {'8086/tcp': 8086},
        'environment': {"INFLUXDB_DB": "proven"},
        'links': '',
        'volumes': '',
        'entrypoint': '',
    }
    ,
    'redis': {
        'start': True,
        'image': 'redis:3.2.11-alpine',
        'pull': True,
        'ports': {'6379/tcp': 6379},
        'environment': [],
        'links': '',
        'volumes': '',
        'entrypoint': 'redis-server --appendonly yes',
    },
    'blazegraph': {
        'start': True,
        'image': 'gridappsd/blazegraph:develop',
        'pull': True,
        'ports': {'8080/tcp': 8889},
        'environment': [],
        'links': '',
        'volumes': '',
        'entrypoint': '',
    },
    'mysql': {
        'start': True,
        'image': 'mysql/mysql-server:5.7',
        'pull': True,
        'ports': {'3306/tcp': 3306},
        'environment': {
            "MYSQL_RANDOM_ROOT_PASSWORD": "yes",
            "MYSQL_PORT": '3306'
        },
        'links': '',
        'volumes': {
            data_dir + '/dumps/gridappsd_mysql_dump.sql': {'bind': '/docker-entrypoint-initdb.d/schema.sql',
                                                           'mode': 'ro'}
        },
        'entrypoint': '',
    },
    'proven': {
        'start': True,
        'image': 'gridappsd/proven:develop',
        'pull': True,
        'ports': {'8080/tcp': 18080},
        'environment': {
            "PROVEN_SERVICES_PORT": "18080",
            "PROVEN_SWAGGER_HOST_PORT": "localhost:18080",
            "PROVEN_USE_IDB": "true",
            "PROVEN_IDB_URL": "http://influxdb:8086",
            "PROVEN_IDB_DB": "proven",
            "PROVEN_IDB_RP": "autogen",
            "PROVEN_IDB_USERNAME": "root",
            "PROVEN_IDB_PASSWORD": "root",
            "PROVEN_T3DIR": "/proven"},
        'links': {'influxdb': 'influxdb'},
        'volumes': '',
        'entrypoint': '',
    },
    'gridappsd': {
        'start': True,
        'image': 'gridappsd/gridappsd:develop',
        'pull': True,
        'ports': {'61613/tcp': 61613, '61614/tcp': 61614, '61616/tcp': 61616},
        'environment': {
            "PATH": "/gridappsd/bin:/gridappsd/lib:/gridappsd/services/fncsgossbridge/service:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin",
            "DEBUG": 1,
            "START": 1
        },
        'links': {'mysql': 'mysql', 'influxdb': 'influxdb', 'blazegraph': 'blazegraph', 'proven': 'proven',
                  'redis': 'redis'},
        'volumes': {
            repo_dir + '/conf/entrypoint.sh': {'bind': '/gridappsd/entrypoint.sh', 'mode': 'rw'},
            repo_dir + '/conf/run-gridappsd.sh': {'bind': '/gridappsd/run-gridappsd.sh', 'mode': 'rw'}
        },
        'entrypoint': '',
    }
}


def docker_down(client=None):
    if client is None:
        client = docker.from_env()

    # Stop all containers
    _log.debug("\nStopping all containers")
    for container in client.containers.list():
        container.stop()
        gevent.sleep(5)

    _log.debug("\nRemoving previous data")
    path = '{}/gridappsd'.format(data_dir)
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=False, onerror=None)


def docker_up(docker_config=None):
    global gridappsd_docker_config
    if docker_config is not None:
        gridappsd_docker_config = docker_config

    client = docker.from_env()

    # Start from scratch
    docker_down(client)

    # Downlaod mysql file
    _log.debug("\nDownloading mysql file")
    mysql_dir = '{}/dumps'.format(data_dir)
    mysql_file = '{}/gridappsd_mysql_dump.sql'.format(mysql_dir)
    if not os.path.isdir(mysql_dir):
        os.makedirs(mysql_dir, 0o0775)
    urllib.request.urlretrieve('https://raw.githubusercontent.com/GRIDAPPSD/Bootstrap/master/gridappsd_mysql_dump.sql',
                               filename=mysql_file)

    # Modify the mysql file to allow connections from gridappsd container
    with open(mysql_file, "r") as sources:
        lines = sources.readlines()
    with open(mysql_file, "w") as sources:
        for line in lines:
            sources.write(re.sub(r'localhost', '%', line))

    # Pull the container
    _log.debug ("\n")
    for service, value in gridappsd_docker_config.items():
     if gridappsd_docker_config[service]['pull']:
       _log.debug ("Pulling %s : %s" % ( service, gridappsd_docker_config[service]['image']))
       client.images.pull(gridappsd_docker_config[service]['image'])

    # Start the container
    _log.debug("\n")
    for service, value in gridappsd_docker_config.items():
        if gridappsd_docker_config[service]['start']:
            _log.debug("Starting %s : %s" % (service, gridappsd_docker_config[service]['image']))
            kwargs = {}
            kwargs['image'] = gridappsd_docker_config[service]['image']
            # Only name the containers if remove is on
            kwargs['remove'] = True
            kwargs['name'] = service
            kwargs['detach'] = True
            if gridappsd_docker_config[service]['environment']:
                kwargs['environment'] = gridappsd_docker_config[service]['environment']
            if gridappsd_docker_config[service]['ports']:
                kwargs['ports'] = gridappsd_docker_config[service]['ports']
            if gridappsd_docker_config[service]['volumes']:
                kwargs['volumes'] = gridappsd_docker_config[service]['volumes']
            if gridappsd_docker_config[service]['entrypoint']:
                kwargs['entrypoint'] = gridappsd_docker_config[service]['entrypoint']
            if gridappsd_docker_config[service]['links']:
                kwargs['links'] = gridappsd_docker_config[service]['links']
            # _log.debug (kwargs)
            container = client.containers.run(**kwargs)
            gridappsd_docker_config[service]['containerid'] = container.id

    gevent.sleep(60)

    # List all running containers
    _log.debug("\n\nList all containers")
    for container in client.containers.list():
        _log.debug(container.name)
