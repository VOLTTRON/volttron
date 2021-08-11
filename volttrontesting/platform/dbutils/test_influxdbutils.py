from time import time

from gevent import sleep, os
import pytest

try:
    from influxdb import InfluxDBClient
except ImportError:
    pytest.skip(
        "Required imports for testing are not installed; thus, not running tests. "
        "If on Ubuntu or Debian OS, install imports with: services/core/InfluxdbHistorian/scripts/install-influx.sh "
        "Otherwise, see https://docs.influxdata.com/influxdb/v1.4/introduction/installation/.",
        allow_module_level=True,
    )

import volttron.platform.dbutils.influxdbutils as influxdbutils
from volttrontesting.fixtures.docker_wrapper import create_container
from volttrontesting.utils.utils import get_rand_port

IMAGES = ["influxdb:1.7"]

if "CI" not in os.environ:
    IMAGES.extend(["influxdb:1.8.1", "influxdb:1.7.10"])

TEST_DATABASE = "test_historian"
ENV_INFLUXDB = {"INFLUXDB_DB": TEST_DATABASE}
ALLOW_CONNECTION_TIME = 10


@pytest.mark.dbutils
@pytest.mark.influxdbutils
def test_get_all_topics(get_container_func, ports_config):
    get_container, image = get_container_func
    with get_container(
        image, ports=ports_config["ports"], env=ENV_INFLUXDB
    ) as container:
        wait_for_connection(container)
        points = [
            {
                "measurement": "meta",
                "tags": {"topic_id": "sometopic_id"},
                "time": 1465839830100400200,
                "fields": {
                    "topic": "some_topic_name",
                    "meta_dict": str({"metadata1": "foobar"}),
                },
            }
        ]
        add_data_to_measurement(ports_config, points)
        expected_topics = ["some_topic_name"]

        actual_topics = influxdbutils.get_all_topics(influxdb_client(ports_config))

        assert actual_topics == expected_topics


@pytest.mark.dbutils
@pytest.mark.influxdbutils
@pytest.mark.parametrize(
    "topic_id", [("a^p"), ("a[p-z]"), ("\\w+\\b"), ("fgfd$"), ("\\/foobar\\/")]
)
def test_get_topic_values_raises_value_error_on_regex(
    get_container_func, ports_config, topic_id
):
    with pytest.raises(ValueError):
        influxdbutils.get_topic_values(
            None, topic_id, None, None, None, None, None, None, None, None
        )


@pytest.mark.dbutils
@pytest.mark.influxdbutils
@pytest.mark.parametrize(
    "points, topic_id, start, end, agg_type, agg_period, skip, count, order,use_calendar_time_periods, expected_topic_values",
    [
        (
            [
                {
                    "measurement": "power_kw",
                    "tags": {
                        "device": "device1",
                        "building": "building1",
                        "campus": "campusa",
                    },
                    "fields": {"value": "somevalue"},
                    "time": 1465839830100400200,
                }
            ],
            "CampusA/Building1/Device1/Power_KW".lower(),
            None,
            None,
            None,
            None,
            0,
            1000,
            "FIRST_TO_LAST",
            False,
            [("2016-06-13T17:43:50.100400+00:00", "somevalue")],
        )
    ],
)
def test_get_topic_values(
    get_container_func,
    ports_config,
    points,
    topic_id,
    start,
    end,
    agg_type,
    agg_period,
    skip,
    count,
    order,
    use_calendar_time_periods,
    expected_topic_values,
):
    get_container, image = get_container_func
    with get_container(
        image, ports=ports_config["ports"], env=ENV_INFLUXDB
    ) as container:
        wait_for_connection(container)
        add_data_to_measurement(ports_config, points)

        actual_topic_values = influxdbutils.get_topic_values(
            influxdb_client(ports_config),
            topic_id,
            start,
            end,
            agg_type,
            agg_period,
            skip,
            count,
            order,
            use_calendar_time_periods,
        )

        assert actual_topic_values == expected_topic_values


@pytest.mark.dbutils
@pytest.mark.influxdbutils
@pytest.mark.parametrize(
    "points, topic_id, expected_meta",
    [
        (
            [
                {
                    "measurement": "meta",
                    "tags": {"topic_id": "sometopic_id"},
                    "time": 1465839830100400200,
                    "fields": {
                        "topic": "some_topic_name",
                        "meta_dict": str({"metadata1": "foobar", "metadata2": 42}),
                        "last_updated": "1465839830100400200",
                    },
                }
            ],
            "sometopic_id",
            {"metadata1": "foobar", "metadata2": 42},
        )
    ],
)
def test_get_topic_meta(
    get_container_func, ports_config, points, topic_id, expected_meta
):
    get_container, image = get_container_func
    with get_container(
        image, ports=ports_config["ports"], env=ENV_INFLUXDB
    ) as container:
        wait_for_connection(container)
        add_data_to_measurement(ports_config, points)

        actual_meta = influxdbutils.get_topic_meta(
            influxdb_client(ports_config), topic_id
        )

        assert actual_meta == expected_meta


@pytest.mark.dbutils
@pytest.mark.influxdbutils
@pytest.mark.parametrize(
    "points, expected_results",
    [
        (
            [
                {
                    "measurement": "meta",
                    "tags": {"topic_id": "sometopic_id"},
                    "fields": {
                        "topic": "actual_topic_name",
                        "meta_dict": str({"metadata1": "foobar"}),
                    },
                }
            ],
            (
                {"sometopic_id": "actual_topic_name"},
                {"sometopic_id": {"metadata1": "foobar"}},
            ),
        ),
        (
            [
                {
                    "measurement": "meta",
                    "tags": {"topic_id": "sometopic_id"},
                    "fields": {
                        "topic": "actual_topic_name1",
                        "meta_dict": str({"metadata1": "foobar"}),
                    },
                },
                {
                    "measurement": "meta",
                    "tags": {"topic_id": "other_id"},
                    "fields": {
                        "topic": "actual_topic_name2",
                        "meta_dict": str({"metadata2": 42}),
                    },
                },
            ],
            (
                {
                    "sometopic_id": "actual_topic_name1",
                    "other_id": "actual_topic_name2",
                },
                {
                    "sometopic_id": {"metadata1": "foobar"},
                    "other_id": {"metadata2": 42},
                },
            ),
        ),
    ],
)
def test_get_all_topic_id_and_meta(
    get_container_func, ports_config, points, expected_results
):
    get_container, image = get_container_func
    with get_container(
        image, ports=ports_config["ports"], env=ENV_INFLUXDB
    ) as container:
        wait_for_connection(container)
        add_data_to_measurement(ports_config, points)

        actual_results = influxdbutils.get_all_topic_id_and_meta(
            influxdb_client(ports_config)
        )

        assert actual_results == expected_results


@pytest.mark.dbutils
@pytest.mark.influxdbutils
@pytest.mark.parametrize(
    "topic_id, topic, meta, updated_time, expected_data",
    [
        (
            "sometopic_id",
            "actual_topic_name",
            {"metadata1": "foobar"},
            "1465839830100400200",
            [
                {
                    "time": "1970-01-01T00:00:00Z",
                    "last_updated": "1465839830100400200",
                    "meta_dict": "{'metadata1': 'foobar'}",
                    "topic": "actual_topic_name",
                    "topic_id": "sometopic_id",
                }
            ],
        )
    ],
)
def test_insert_meta(
    get_container_func, ports_config, topic_id, topic, meta, updated_time, expected_data
):
    get_container, image = get_container_func
    with get_container(
        image, ports=ports_config["ports"], env=ENV_INFLUXDB
    ) as container:
        wait_for_connection(container)
        assert get_data(ports_config, "meta") == []

        influxdbutils.insert_meta(
            influxdb_client(ports_config), topic_id, topic, meta, updated_time
        )
        actual_results = get_data(ports_config, "meta")

        assert actual_results == expected_data


@pytest.mark.dbutils
@pytest.mark.influxdbutils
@pytest.mark.parametrize(
    "measurement, updatedtime, topic_id, source, value, value_string, expected_data",
    [
        (
            "POWER_KW",
            "2017-12-28T20:41:00.004260096Z",
            "CampusA/Building1/Device1/POWER_KW",
            "scrape",
            "123.4",
            "foobar",
            [
                {
                    "time": "2017-12-28T20:41:00.004260Z",
                    "building": "Building1",
                    "campus": "CampusA",
                    "device": "Device1",
                    "source": "scrape",
                    "value": "123.4",
                    "value_string": "foobar",
                }
            ],
        ),
        (
            "OutsideAirTemperature",
            "2017-12-28T20:41:00.004260096Z",
            "CampusA/Building1/LAB/Device/OutsideAirTemperature",
            "scrape",
            "123.4",
            "foobar",
            [
                {
                    "time": "2017-12-28T20:41:00.004260Z",
                    "building": "LAB",
                    "campus": "CampusA/Building1",
                    "device": "Device",
                    "source": "scrape",
                    "value": "123.4",
                    "value_string": "foobar",
                }
            ],
        ),
        (
            "temp",
            "2017-12-28T20:41:00.004260096Z",
            "LAB/Device/temp",
            "scrape",
            "123.4",
            "foobar",
            [
                {
                    "time": "2017-12-28T20:41:00.004260Z",
                    "building": "LAB",
                    "device": "Device",
                    "source": "scrape",
                    "value": "123.4",
                    "value_string": "foobar",
                }
            ],
        ),
    ],
)
def test_insert_data_point(
    get_container_func,
    ports_config,
    measurement,
    updatedtime,
    topic_id,
    source,
    value,
    value_string,
    expected_data,
):
    get_container, image = get_container_func
    with get_container(
        image, ports=ports_config["ports"], env=ENV_INFLUXDB
    ) as container:
        wait_for_connection(container)

        assert get_data(ports_config, measurement) == []

        influxdbutils.insert_data_point(
            influxdb_client(ports_config),
            updatedtime,
            topic_id,
            source,
            value,
            value_string,
        )
        actual_data = get_data(ports_config, measurement)

        assert actual_data == expected_data


@pytest.mark.dbutils
@pytest.mark.influxdbutils
@pytest.mark.parametrize(
    "pattern, expected_topics",
    [
        ("actual", [{"actual_topic_name": "sometopic_id"}]),
        (
            "topic",
            [
                {"actual_topic_name": "sometopic_id"},
                {"snafu_topic": "ghsfjkhkjf_ID"},
                {"topic_snafu_2": "topic_id_42"},
            ],
        ),
        ("foo", []),
        (
            "^(snafu).*",
            [{"snafu_Topic2": "other_topic_id"}, {"snafu_topic": "ghsfjkhkjf_ID"}],
        ),
        ("(name)$", [{"actual_topic_name": "sometopic_id"}]),
    ],
)
def test_get_topics_by_pattern(
    get_container_func, ports_config, pattern, expected_topics
):
    get_container, image = get_container_func
    with get_container(
        image, ports=ports_config["ports"], env=ENV_INFLUXDB
    ) as container:
        wait_for_connection(container)
        points = [
            {
                "measurement": "meta",
                "tags": {"topic_id": "sometopic_id"},
                "fields": {
                    "topic": "actual_topic_name",
                    "meta_dict": str({"metadata1": "foobar"}),
                },
            },
            {
                "measurement": "meta",
                "tags": {"topic_id": "ghsfjkhkjf_ID"},
                "fields": {
                    "topic": "snafu_topic",
                    "meta_dict": str({"metadata42": "foobar"}),
                },
            },
            {
                "measurement": "meta",
                "tags": {"topic_id": "topic_id_42"},
                "fields": {
                    "topic": "topic_snafu_2",
                    "meta_dict": str({"metadata42": "foobar"}),
                },
            },
            {
                "measurement": "meta",
                "tags": {"topic_id": "other_topic_id"},
                "fields": {
                    "topic": "snafu_Topic2",
                    "meta_dict": str({"metadata42": "foobar"}),
                },
            },
        ]
        add_data_to_measurement(ports_config, points)

        actual_topics = influxdbutils.get_topics_by_pattern(
            influxdb_client(ports_config), pattern
        )

        assert actual_topics == expected_topics


@pytest.fixture(params=IMAGES)
def get_container_func(request):
    return create_container, request.param


@pytest.fixture()
def ports_config():
    port_on_host = get_rand_port(ip="8086")
    return {"port_on_host": port_on_host, "ports": {"8086/tcp": port_on_host}}


def influxdb_client(ports_config):
    connection_params = {
        "host": "localhost",
        "port": ports_config["port_on_host"],
        "database": TEST_DATABASE,
    }
    return influxdbutils.get_client(connection_params)


def wait_for_connection(container):
    sleep(ALLOW_CONNECTION_TIME)
    query_database(container, f"use {TEST_DATABASE}")


def query_database(container, query):
    cmd = f'influx -execute "{query}" -database test_historian'

    start_time = time()
    while time() - start_time < ALLOW_CONNECTION_TIME:
        r = container.exec_run(cmd=cmd, tty=True)
        print(r)
        if r[0] != 0:
            continue
        else:
            return

    return RuntimeError(r)


def add_data_to_measurement(ports_config, points):
    client = InfluxDBClient(
        host="localhost", port=ports_config["port_on_host"], database=TEST_DATABASE
    )
    client.write_points(points)


def get_data(ports_config, measurement):
    client = InfluxDBClient(
        host="localhost", port=ports_config["port_on_host"], database=TEST_DATABASE
    )
    res = client.query(f"""SELECT * from {measurement}""", database=TEST_DATABASE)
    return list(res.get_points())
