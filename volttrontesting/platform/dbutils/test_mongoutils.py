import os
from time import time

from gevent import sleep
import pytest

try:
    import pymongo
except ImportError:
    pytest.skip("pymongo not available", allow_module_level=True)

import volttron.platform.dbutils.mongoutils as mongoutils
from volttrontesting.fixtures.docker_wrapper import create_container
from volttrontesting.utils.utils import get_rand_port


IMAGES = ["mongo:latest"]
if "CI" in os.environ:
    IMAGES.extend(
        ["mongo:5.0", "mongo:4.0"]
    )

TEST_DATABASE = "test_historian"
ROOT_USERNAME = "mongoadmin"
ROOT_PASSWORD = "12345"
ENV_MONGODB = {
    "MONGO_INITDB_ROOT_USERNAME": ROOT_USERNAME,
    "MONGO_INITDB_ROOT_PASSWORD": ROOT_PASSWORD,
    "MONGO_INITDB_DATABASE": TEST_DATABASE,
}
ALLOW_CONNECTION_TIME = 10


@pytest.mark.mongoutils
@pytest.mark.parametrize(
    "query, expected_topic_id_map, expected_topic_name_map",
    [
        (
            '\'db.topics.insertOne({topic_name:"foobar", _id:"42"})\'',
            {"foobar": "42"},
            {"foobar": "foobar"},
        ),
        (
            '\'db.topics.insertOne({topic_name:"ROMA", _id:"17"})\'',
            {"roma": "17"},
            {"roma": "ROMA"},
        ),
    ],
)
def test_get_topic_map(
    get_container_func,
    ports_config,
    query,
    expected_topic_id_map,
    expected_topic_name_map,
):
    get_container, image = get_container_func
    with get_container(
        image, ports=ports_config["ports"], env=ENV_MONGODB
    ) as container:
        wait_for_connection(container)
        query_database(container, query)

        actual_topic_id_map, actual_topic_name_map = mongoutils.get_topic_map(
            mongo_client(ports_config["port_on_host"]), "topics"
        )

        assert actual_topic_id_map == expected_topic_id_map
        assert actual_topic_name_map == expected_topic_name_map


@pytest.mark.mongoutils
@pytest.mark.parametrize(
    "query, agg_topics_collection, expected_agg_topic_map",
    [
        (
            '\'db.aggregate_topics.insertOne({agg_topic_name:"foobar", agg_type:"AVG", agg_time_period:"2001", _id:"42"})\'',
            "aggregate_topics",
            {("foobar", "AVG", "2001"): "42"},
        ),
        (
            '\'db.aggregate_topics.insertOne({agg_topic_name:"ROmA", agg_type:"AVG", agg_time_period:"2001", _id:"42"})\'',
            "aggregate_topics",
            {("roma", "AVG", "2001"): "42"},
        ),
    ],
)
def test_get_agg_topic_map(
    get_container_func,
    ports_config,
    query,
    agg_topics_collection,
    expected_agg_topic_map,
):
    get_container, image = get_container_func
    with get_container(
        image, ports=ports_config["ports"], env=ENV_MONGODB
    ) as container:
        wait_for_connection(container)
        query_database(container, query)

        actual_agg_topic_map = mongoutils.get_agg_topic_map(
            mongo_client(ports_config["port_on_host"]), agg_topics_collection
        )

        assert actual_agg_topic_map == expected_agg_topic_map


@pytest.mark.mongoutils
@pytest.mark.parametrize(
    "query_agg_topics, query_agg_meta, expected_agg_topics",
    [
        (
            '\'db.aggregate_topics.insertOne({agg_topic_name:"foobar", agg_type:"AVG", agg_time_period:"2001", _id:"42"})\'',
            '\'db.aggregate_meta.insertOne({agg_topic_id:"42", meta:{configured_topics: "topic1"}})\'',
            [("foobar", "AVG", "2001", "topic1")],
        ),
        (
            '\'db.aggregate_topics.insertOne({agg_topic_name:"FOO", agg_type:"AVG", agg_time_period:"2001", _id:"42"})\'',
            '\'db.aggregate_meta.insertOne({agg_topic_id:"42", meta:{configured_topics: "topic1"}})\'',
            [("foo", "AVG", "2001", "topic1")],
        ),
    ],
)
def test_get_agg_topics(
    get_container_func,
    ports_config,
    query_agg_topics,
    query_agg_meta,
    expected_agg_topics,
):
    get_container, image = get_container_func
    with get_container(
        image, ports=ports_config["ports"], env=ENV_MONGODB
    ) as container:
        wait_for_connection(container)
        query_database(container, query_agg_topics)
        query_database(container, query_agg_meta)

        actual_agg_topics = mongoutils.get_agg_topics(
            mongo_client(ports_config["port_on_host"]),
            "aggregate_topics",
            "aggregate_meta",
        )

        assert actual_agg_topics == expected_agg_topics


def mongo_client(port):
    connection_params = {
        "host": "localhost",
        "port": port,
        "database": TEST_DATABASE,
        "user": ROOT_USERNAME,
        "passwd": ROOT_PASSWORD,
        "authSource": "admin",
    }

    return mongoutils.get_mongo_client(connection_params)


@pytest.fixture(params=IMAGES)
def get_container_func(request):
    return create_container, request.param


@pytest.fixture()
def ports_config():
    port_on_host = get_rand_port(ip="27017")
    return {"port_on_host": port_on_host, "ports": {"27017/tcp": port_on_host}}


def wait_for_connection(container):
    command = f'mongo --username="{ROOT_USERNAME}" --password="{ROOT_PASSWORD}" --authenticationDatabase admin {TEST_DATABASE} --eval "db.getName()"'
    query_database(container, None, command=command)


def query_database(container, query, command=None):
    if command is None:
        cmd = (
            f'mongo --username "{ROOT_USERNAME}" --password "{ROOT_PASSWORD}" '
            f"--authenticationDatabase admin {TEST_DATABASE} --eval={query}"
        )
    else:
        cmd = command

    start_time = time()
    while time() - start_time < ALLOW_CONNECTION_TIME:
        r = container.exec_run(cmd=cmd, tty=True)
        if r[0] != 0:
            continue
        else:
            sleep(0.5)
            return

    return RuntimeError(r)
