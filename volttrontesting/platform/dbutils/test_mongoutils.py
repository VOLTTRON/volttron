from time import time

import pytest


import volttron.platform.dbutils.mongoutils as mongoutils
from volttrontesting.fixtures.docker_wrapper import create_container
from volttrontesting.utils.utils import get_rand_port


IMAGES = ["mongo:3-xenial"]  # To test more images, add them here
TEST_DATABASE = "test_historian"
ROOT_USERNAME = "mongoadmin"
ROOT_PASSWORD = "12345"
ENV_MONGODB = {
    "MONGO_INITDB_ROOT_USERNAME": ROOT_USERNAME,
    "MONGO_INITDB_ROOT_PASSWORD": ROOT_PASSWORD,
    "MONGO_INITDB_DATABASE": TEST_DATABASE,
}
ALLOW_CONNECTION_TIME = 10


test_data_get_topic_map = [
    (
        "'db.topics.insertOne({topic_name:\"foobar\"})'",
        ({"foobar": "foobar"}),
        {"foobar"},
    )
]


@pytest.mark.mongoutils
@pytest.mark.parametrize(
    "query, expected_topic_name_map, expected_topic_id_keys", test_data_get_topic_map
)
def test_get_topic_map(
    get_container_func,
    ports_config,
    query,
    expected_topic_name_map,
    expected_topic_id_keys,
):
    get_container, image = get_container_func
    with get_container(
        image, ports=ports_config["ports"], env=ENV_MONGODB
    ) as container:
        wait_for_connection(container)
        seed_database(container, query)

        actual_topic_map = mongoutils.get_topic_map(
            mongo_client(ports_config["port_on_host"]), "topics"
        )

        assert actual_topic_map[1] == expected_topic_name_map
        assert actual_topic_map[0].keys() == expected_topic_id_keys


test_data_get_agg_topic_map = [
    (
        '\'db.aggregate_topics.insertOne({agg_topic_name:"foobar", agg_type:"AVG", agg_time_period:"2001", _id:"42"})\'',
        "aggregate_topics",
        {("foobar", "AVG", "2001")},
    )
]


@pytest.mark.mongoutils
@pytest.mark.parametrize(
    "query, agg_topics_collection, expected_topic_id_map_keys",
    test_data_get_agg_topic_map,
)
def test_get_agg_topic_map(
    get_container_func,
    ports_config,
    query,
    agg_topics_collection,
    expected_topic_id_map_keys,
):
    get_container, image = get_container_func
    with get_container(
        image, ports=ports_config["ports"], env=ENV_MONGODB
    ) as container:
        wait_for_connection(container)
        seed_database(container, query)

        actual_agg_topic_map = mongoutils.get_agg_topic_map(
            mongo_client(ports_config["port_on_host"]), agg_topics_collection
        )

        assert actual_agg_topic_map.keys() == expected_topic_id_map_keys


test_data_get_agg_topics = [
    (
        '\'db.aggregate_topics.insertOne({agg_topic_name:"foobar", agg_type:"AVG", agg_time_period:"2001", _id:"42"})\'',
        '\'db.aggregate_meta.insertOne({agg_topic_id:"42", meta:{configured_topics: "topic1"}})\'',
        "aggregate_topics",
        "aggregate_meta",
        [("foobar", "AVG", "2001", "topic1")],
    )
]


@pytest.mark.mongoutils
@pytest.mark.parametrize(
    "query_agg_topics, query_agg_meta, agg_topics_collection, agg_meta_collection, expected_agg_topics",
    test_data_get_agg_topics,
)
def test_get_agg_topics(
    get_container_func,
    ports_config,
    query_agg_topics,
    query_agg_meta,
    agg_topics_collection,
    agg_meta_collection,
    expected_agg_topics,
):
    get_container, image = get_container_func
    with get_container(
        image, ports=ports_config["ports"], env=ENV_MONGODB
    ) as container:
        wait_for_connection(container)
        seed_database(container, query_agg_topics)
        seed_database(container, query_agg_meta)

        actual_agg_topics = mongoutils.get_agg_topics(
            mongo_client(ports_config["port_on_host"]),
            agg_topics_collection,
            agg_meta_collection,
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
    start_time = time()
    # exit codes for MongoDb can be referenced at https://docs.mongodb.com/manual/reference/exit-codes/
    while time() - start_time < ALLOW_CONNECTION_TIME:
        command = f'mongo --username="{ROOT_USERNAME}" --password="{ROOT_PASSWORD}" --authenticationDatabase admin {TEST_DATABASE} --eval "db.getName()"'
        r = container.exec_run(command, tty=True)
        if r[0] == 0:
            return
        else:
            continue

    return RuntimeError(r)


def seed_database(container, query):
    command = (
        f'mongo --username "{ROOT_USERNAME}" --password "{ROOT_PASSWORD}" '
        f"--authenticationDatabase admin {TEST_DATABASE} --eval={query}"
    )
    container.exec_run(cmd=command, tty=True)
