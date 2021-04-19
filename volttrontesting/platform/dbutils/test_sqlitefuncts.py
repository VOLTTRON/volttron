import shutil
import os
import docker
import pytest

from volttron.platform.dbutils.sqlitefuncts import SqlLiteFuncts

TOPICS_TABLE = "topics"
DATA_TABLE = "data"
META_TABLE = "meta"
METAMETA_TABLE = "metameta"
AGG_TOPICS_TABLE = "aggregate_topics"
AGG_META_TABLE = "aggregate_meta"
TABLE_PREFIX = ""
IMAGE = "nouchka/sqlite3:latest"
DATABASE = "historian.sqlite"
DATABASE_PATH = os.path.join(os.getcwd(), "data")
CONTAINER_VOLUME_PATH = '/root/db'


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_setup_historian_tables(sqlite_container, sqlitefuncts):
    expected_tables = {"data", "meta", "topics"}
    actual_tables = get_tables(sqlite_container)
    assert set(expected_tables).issubset(actual_tables)


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_record_table_definitions(sqlite_container, sqlitefuncts):
    expected_tables = {"data", "meta", "metameta", "topics"}
    actual_tables = get_tables(sqlite_container)
    assert set(expected_tables).issubset(actual_tables)


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_setup_aggregate_historian_tables(sqlite_container, sqlitefuncts):
    expected_tables = {
        "data",
        "aggregate_meta",
        "meta",
        "aggregate_topics",
        "topics",
        "metameta",
    }
    actual_tables = get_tables(sqlite_container)
    assert expected_tables.issubset(actual_tables)


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
@pytest.mark.parametrize(
    "topic_ids, id_name_map, expected_values",
    [
        ([42], {42: "topic42"}, {"topic42": []}),
        ([43], {43: "topic43"}, {"topic43": [("2020-06-01T12:30:59.000000", [2, 3])]}),
    ],
)
def test_query(sqlite_container, sqlitefuncts, topic_ids, id_name_map, expected_values):
    query = """INSERT OR REPLACE INTO data VALUES('2020-06-01 12:30:59',43,'[2,3]')"""
    query_db(query, sqlite_container)

    actual_results = sqlitefuncts.query(topic_ids, id_name_map)

    assert actual_results == expected_values


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
@pytest.mark.parametrize(
    "history_limit_timestamp, storage_limit_gb, expected_data",
    [
        ("2020-06-01 12:30:59", None, []),
        (None, 10, ["2000-06-01", "12:30:59|43|[2,3]", "2000-06-01", "12:30:58|42|[2,3]"]),
        ("2020-06-01 12:30:59", 10, []),
    ],
)
def test_manage_db_size(sqlite_container, sqlitefuncts, history_limit_timestamp, storage_limit_gb, expected_data):
    query = (
        "INSERT OR REPLACE INTO data VALUES('2000-06-01 12:30:59',43,'[2,3]'); "
        "INSERT OR REPLACE INTO data VALUES('2000-06-01 12:30:58',42,'[2,3]')"
    )

    query_db(query, sqlite_container)
    data_before_resize = [
        "2000-06-01", "12:30:59|43|[2,3]",
        "2000-06-01", "12:30:58|42|[2,3]",
    ]
    assert get_all_data(DATA_TABLE, sqlite_container) == data_before_resize

    sqlitefuncts.manage_db_size(history_limit_timestamp, storage_limit_gb)

    assert get_all_data(DATA_TABLE, sqlite_container) == expected_data


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_insert_meta(sqlitefuncts, sqlite_container):
    assert get_all_data(META_TABLE, sqlite_container) == []

    topic_id = "44"
    metadata = "foobar44"
    expected_data = ['44|"foobar44"']

    res = sqlitefuncts.insert_meta(topic_id, metadata)
    sqlitefuncts.commit()

    assert res is True
    assert get_all_data(META_TABLE, sqlite_container) == expected_data


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_insert_data(sqlitefuncts, sqlite_container):
    assert get_all_data(DATA_TABLE, sqlite_container) == []

    time_stamp = "2001-09-11 08:46:00"
    topic_id = "11"
    data = "1wtc"
    expected_data = ['2001-09-11', '08:46:00|11|"1wtc"']

    res = sqlitefuncts.insert_data(time_stamp, topic_id, data)
    sqlitefuncts.commit()

    assert res is True
    assert get_all_data(DATA_TABLE, sqlite_container) == expected_data


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_insert_topic(sqlitefuncts, sqlite_container):
    assert get_all_data(TOPICS_TABLE, sqlite_container) == []

    topic = "football"
    expected_data = ["1|football"]

    res = sqlitefuncts.insert_topic(topic)
    sqlitefuncts.commit()

    assert res == 1
    assert get_all_data(TOPICS_TABLE, sqlite_container) == expected_data


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_update_topic(sqlitefuncts, sqlite_container):
    query = "INSERT INTO topics (topic_name) values ('football')"
    query_db(query, sqlite_container)

    assert get_all_data(TOPICS_TABLE, sqlite_container) == ["1|football"]

    res = sqlitefuncts.update_topic("basketball", 1)
    sqlitefuncts.commit()

    assert res is True
    assert get_all_data("topics", sqlite_container) == ["1|basketball"]


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_get_aggregation_list(sqlitefuncts):
    assert sqlitefuncts.get_aggregation_list() == [
        "AVG",
        "MIN",
        "MAX",
        "COUNT",
        "SUM",
        "TOTAL",
        "GROUP_CONCAT",
    ]


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_insert_agg_topic(sqlitefuncts, sqlite_container):
    assert get_all_data(AGG_TOPICS_TABLE, sqlite_container) == []

    topic = "agg_topics"
    agg_type = "AVG"
    agg_time_period = "2019"
    expected_data = ["1|agg_topics|AVG|2019"]

    sqlitefuncts.insert_agg_topic(topic, agg_type, agg_time_period)
    sqlitefuncts.commit()

    assert get_all_data(AGG_TOPICS_TABLE, sqlite_container) == expected_data


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_update_agg_topic(sqlitefuncts, sqlite_container):
    query = "INSERT INTO aggregate_topics (agg_topic_name, agg_type, agg_time_period) values ('cars', 'SUM', '2100ZULU')"
    query_db(query, sqlite_container)

    assert get_all_data(AGG_TOPICS_TABLE, sqlite_container) == ["1|cars|SUM|2100ZULU"]

    new_agg_topic_name = "boats"
    expected_data = ["1|cars|SUM|2100ZULU"]

    res = sqlitefuncts.update_agg_topic(1, new_agg_topic_name)

    assert res is True
    assert get_all_data(AGG_TOPICS_TABLE, sqlite_container) == expected_data


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_insert_agg_meta(sqlitefuncts, sqlite_container):
    assert get_all_data(AGG_META_TABLE, sqlite_container) == []

    topic_id = 42
    metadata = "meaning of life"
    expected_data = ['42|"meaning of life"']
    res = sqlitefuncts.insert_agg_meta(topic_id, metadata)
    sqlitefuncts.commit()

    assert res is True
    actual_data = [(" ".join(get_all_data(AGG_META_TABLE, sqlite_container)))]

    assert actual_data == expected_data


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_get_topic_map(sqlitefuncts, sqlite_container):
    query = "INSERT INTO topics (topic_name) values ('football');INSERT INTO topics (topic_name) values ('netball');"
    query_db(query, sqlite_container)
    expected_topic_map = (
        {"football": 1, "netball": 2},
        {"football": "football", "netball": "netball"},
    )

    assert get_all_data(TOPICS_TABLE, sqlite_container) == ["1|football", "2|netball"]

    actual_topic_map = sqlitefuncts.get_topic_map()

    assert actual_topic_map == expected_topic_map


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_get_agg_topics(sqlitefuncts, sqlite_container):
    query = (
        "INSERT INTO aggregate_topics (agg_topic_name, agg_type, agg_time_period ) "
        "values('topic_name', 'AVG', '2001');"
    )
    query_db(query, sqlite_container)
    sqlitefuncts.insert_agg_meta(1, {"configured_topics": "great books"})
    sqlitefuncts.commit()
    expected_topics = [("topic_name", "AVG", "2001", "great books")]

    actual_topics = sqlitefuncts.get_agg_topics()

    assert actual_topics == expected_topics


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_agg_topics_should_return_empty_on_nonexistent_table(sqlitefuncts):
    actual_topic_map = sqlitefuncts.get_agg_topics()
    assert actual_topic_map == []


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_get_agg_topic_map(sqlitefuncts, sqlite_container):
    query = (
        "INSERT INTO aggregate_topics (agg_topic_name, agg_type, agg_time_period ) "
        "values('topic_name', 'AVG', '2001');"
    )
    query_db(query, sqlite_container)
    expected_acutal_topic_map = {("topic_name", "AVG", "2001"): 1}

    actual_topic_map = sqlitefuncts.get_agg_topic_map()

    assert actual_topic_map == expected_acutal_topic_map


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_agg_topic_map_should_return_empty_on_nonexistent_table(sqlitefuncts):
    actual_topic_map = sqlitefuncts.get_agg_topic_map()
    assert actual_topic_map == {}


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
@pytest.mark.parametrize(
    "topic_1, topic_2, topic_3, topic_pattern, expected_topics",
    [
        ("'football'", "'foobar'", "'xzxzxccx'", "foo", {"football": 1, "foobar": 2}),
        ("'football'", "'foobar'", "'xzxzxccx'", "ba", {"football": 1, "foobar": 2}),
        ("'football'", "'foobar'", "'xzxzxccx'", "ccx", {"xzxzxccx": 3}),
        ("'fotball'", "'foobar'", "'xzxzxccx'", "foo", {"foobar": 2}),
        ("'football'", "'foooobar'", "'xzxzxccx'", "foooo", {"foooobar": 2}),
        (
                "'FOOtball'",
                "'ABCFOOoXYZ'",
                "'XXXfOoOo'",
                "foo",
                {"FOOtball": 1, "ABCFOOoXYZ": 2, "XXXfOoOo": 3},
        ),
    ],
)
def test_query_topics_by_pattern(
        sqlitefuncts, sqlite_container, topic_1, topic_2, topic_3, topic_pattern, expected_topics
):
    query = (
        f"INSERT INTO topics (topic_name) values ({topic_1});"
        f"INSERT INTO topics (topic_name) values ({topic_2});"
        f"INSERT INTO topics (topic_name) values ({topic_3});"
    )
    query_db(query, sqlite_container)

    actual_topics = sqlitefuncts.query_topics_by_pattern(topic_pattern)

    assert actual_topics == expected_topics


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_create_aggregate_store(sqlitefuncts, sqlite_container):
    agg_type = "AVG"
    agg_time_period = "1984"
    expected_new_agg_table = "AVG_1984"
    expected_indexes = ["0|idx_AVG_1984|0|c|0", "1|sqlite_autoindex_AVG_1984_1|1|u|0"]

    result = sqlitefuncts.create_aggregate_store(agg_type, agg_time_period)

    assert result is True
    assert expected_new_agg_table in get_tables(sqlite_container)

    actual_indexes = get_indexes(expected_new_agg_table, sqlite_container)
    assert actual_indexes == expected_indexes


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_collect_aggregate(sqlitefuncts, sqlite_container):
    query = (
        "INSERT OR REPLACE INTO data values('2020-06-01 12:30:59', 42, '2');"
        "INSERT OR REPLACE INTO data values('2020-06-01 12:31:59', 43, '8');"
    )
    query_db(query, sqlite_container)

    topic_ids = [42, 43]
    agg_type = "avg"
    expected_aggregate = (5.0, 2)

    actual_aggregate = sqlitefuncts.collect_aggregate(topic_ids, agg_type)

    assert actual_aggregate == expected_aggregate


def get_indexes(table, container):
    query = f"""PRAGMA index_list({table})"""
    return query_db(query, container)


def get_tables(container):
    return query_db(".tables", container)


def get_all_data(table, container):
    query = f"""SELECT * FROM {table}"""
    return query_db(query, container)


def query_db(query, container):
    cmd = ["sqlite3", DATABASE, query]
    _, output = container.exec_run(cmd)
    return output.decode().split()


@pytest.fixture()
def volume_container():
    os.makedirs(DATABASE_PATH, exist_ok=True)
    volumes = {DATABASE_PATH: {'bind': CONTAINER_VOLUME_PATH, 'mode': 'rw'}}
    client = docker.from_env()
    container = client.containers.run('alpine',
                                      detach=True,
                                      entrypoint=["tail", "-f", "/dev/null"],
                                      remove=True,
                                      volumes=volumes)
    yield [container.id]
    shutil.rmtree(DATABASE_PATH)
    container.stop()


@pytest.fixture()
def sqlite_container(volume_container):
    client = docker.from_env()
    container = client.containers.run(IMAGE,
                                      detach=True,
                                      entrypoint=["tail", "-f", "/dev/null"],
                                      remove=True,
                                      volumes_from=volume_container)
    yield container
    container.stop()


@pytest.fixture()
def sqlitefuncts(sqlite_container):
    connect_params = {"database": os.path.join(DATABASE_PATH, f"{DATABASE}")}
    table_names = {
        "data_table": DATA_TABLE,
        "topics_table": TOPICS_TABLE,
        "meta_table": META_TABLE,
        "agg_topics_table": AGG_TOPICS_TABLE,
        "agg_meta_table": AGG_META_TABLE,
    }
    sqlitefuncts_client = SqlLiteFuncts(connect_params, table_names)

    sqlitefuncts_client.setup_historian_tables()
    table_defs = {
        "table_prefix": TABLE_PREFIX,
        "data_table": DATA_TABLE,
        "topics_table": TOPICS_TABLE,
        "meta_table": META_TABLE,
    }
    meta_table_name = METAMETA_TABLE
    sqlitefuncts_client.record_table_definitions(table_defs, meta_table_name)
    sqlitefuncts_client.setup_aggregate_historian_tables(meta_table_name)
    yield sqlitefuncts_client
