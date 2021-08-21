import sqlite3

from gevent import subprocess
import pytest
import os

from setuptools import glob

from volttron.platform.dbutils.sqlitefuncts import SqlLiteFuncts


TOPICS_TABLE = "topics"
DATA_TABLE = "data"
META_TABLE = "meta"
AGG_TOPICS_TABLE = "aggregate_topics"
AGG_META_TABLE = "aggregate_meta"
TABLE_PREFIX = ""
CONNECT_PARAMS = {"database": "data/historian.sqlite"}


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_setup_historian_tables(sqlitefuncts_db_not_initialized):
    expected_tables = {"data", "topics"}

    sqlitefuncts_db_not_initialized.setup_historian_tables()

    actual_tables = get_tables()

    assert actual_tables == expected_tables


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_setup_aggregate_historian_tables(get_sqlitefuncts):
    sqlitefuncts, historain_version = get_sqlitefuncts

    if historain_version == "<4.0.0":
        expected_tables = {
            "data",
            "aggregate_meta",
            "meta",
            "aggregate_topics",
            "topics"
        }
    else:
        expected_tables = {
            "data",
            "aggregate_meta",
            "aggregate_topics",
            "topics"
        }

    sqlitefuncts.setup_aggregate_historian_tables()

    actual_tables = get_tables()
    assert actual_tables == expected_tables


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
@pytest.mark.parametrize(
    "topic_ids, id_name_map, expected_values",
    [
        ([42], {42: "topic42"}, {"topic42": []}),
        ([43], {43: "topic43"}, {"topic43": [("2020-06-01T12:30:59.000000", [2, 3])]}),
    ],
)
def test_query(get_sqlitefuncts, topic_ids, id_name_map, expected_values):
    sqlitefuncts, historain_version = get_sqlitefuncts

    query = """INSERT OR REPLACE INTO data VALUES('2020-06-01 12:30:59',43,'[2,3]')"""
    query_db(query)

    actual_results = sqlitefuncts.query(topic_ids, id_name_map)

    assert actual_results == expected_values


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
@pytest.mark.parametrize(
    "history_limit_timestamp, storage_limit_gb, expected_data",
    [
        ("2020-06-01 12:30:59", None, []),
        (None, 10, ["2000-06-01 12:30:59|43|[2,3]", "2000-06-01 12:30:58|42|[2,3]"]),
        ("2020-06-01 12:30:59", 10, []),
    ],
)
def test_manage_db_size(get_sqlitefuncts, history_limit_timestamp, storage_limit_gb, expected_data):
    sqlitefuncts, historain_version = get_sqlitefuncts
    query = (
        "INSERT OR REPLACE INTO data VALUES('2000-06-01 12:30:59',43,'[2,3]'); "
        "INSERT OR REPLACE INTO data VALUES('2000-06-01 12:30:58',42,'[2,3]')"
    )

    query_db(query)
    data_before_resize = [
        "2000-06-01 12:30:59|43|[2,3]",
        "2000-06-01 12:30:58|42|[2,3]",
    ]
    assert get_all_data(DATA_TABLE) == data_before_resize

    sqlitefuncts.manage_db_size(history_limit_timestamp, storage_limit_gb)

    assert get_all_data(DATA_TABLE) == expected_data


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_insert_meta(get_sqlitefuncts):
    sqlitefuncts, historain_version = get_sqlitefuncts
    if historain_version != "<4.0.0":
        pytest.skip("insert_meta() is called by historian only for schema <4.0.0")

    assert get_all_data(META_TABLE) == []

    topic_id = "44"
    metadata = "foobar44"
    expected_data = ['44|"foobar44"']

    res = sqlitefuncts.insert_meta(topic_id, metadata)
    sqlitefuncts.commit()

    assert res is True
    assert get_all_data(META_TABLE) == expected_data


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_insert_data(get_sqlitefuncts):
    sqlitefuncts, historain_version = get_sqlitefuncts
    assert get_all_data(DATA_TABLE) == []

    ts = "2001-09-11 08:46:00"
    topic_id = "11"
    data = "1wtc"
    expected_data = ['2001-09-11 08:46:00|11|"1wtc"']

    res = sqlitefuncts.insert_data(ts, topic_id, data)
    sqlitefuncts.commit()

    assert res is True
    assert get_all_data(DATA_TABLE) == expected_data


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_insert_topic(get_sqlitefuncts):
    sqlitefuncts, historain_version = get_sqlitefuncts
    assert get_all_data(TOPICS_TABLE) == []

    topic = "football"
    if historain_version == "<4.0.0":
        expected_data = ["1|football"]
    else:
        expected_data = ["1|football|"]

    res = sqlitefuncts.insert_topic(topic)
    sqlitefuncts.commit()

    assert res == 1
    assert get_all_data(TOPICS_TABLE) == expected_data


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_update_topic(get_sqlitefuncts):
    sqlitefuncts, historain_version = get_sqlitefuncts
    query = "INSERT INTO topics (topic_name) values ('football')"
    query_db(query)

    if historain_version == "<4.0.0":
        expected_data = ["1|football"]
    else:
        expected_data = ["1|football|"]
    assert get_all_data(TOPICS_TABLE) == expected_data

    res = sqlitefuncts.update_topic("basketball", 1)
    sqlitefuncts.commit()

    assert res is True
    if historain_version == "<4.0.0":
        expected_data = ["1|basketball"]
    else:
        expected_data = ["1|basketball|"]
    assert get_all_data("topics") == expected_data


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_get_aggregation_list(get_sqlitefuncts):
    sqlitefuncts, historain_version = get_sqlitefuncts
    assert sqlitefuncts.get_aggregation_list() == [
        "AVG",
        "MIN",
        "MAX",
        "COUNT",
        "SUM",
        "TOTAL"
    ]


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_insert_agg_topic(get_sqlitefuncts):
    sqlitefuncts, historain_version = get_sqlitefuncts
    assert get_all_data(AGG_TOPICS_TABLE) == []

    topic = "agg_topics"
    agg_type = "AVG"
    agg_time_period = "2019"
    expected_data = ["1|agg_topics|AVG|2019"]

    sqlitefuncts.insert_agg_topic(topic, agg_type, agg_time_period)
    sqlitefuncts.commit()

    assert get_all_data(AGG_TOPICS_TABLE) == expected_data


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_update_agg_topic(get_sqlitefuncts):
    sqlitefuncts, historain_version = get_sqlitefuncts
    query = "INSERT INTO aggregate_topics " \
            "(agg_topic_name, agg_type, agg_time_period) values ('cars', 'SUM', '2100ZULU')"
    query_db(query)

    assert get_all_data(AGG_TOPICS_TABLE) == ["1|cars|SUM|2100ZULU"]

    new_agg_topic_name = "boats"
    expected_data = ["1|cars|SUM|2100ZULU"]

    res = sqlitefuncts.update_agg_topic(1, new_agg_topic_name)

    assert res is True
    assert get_all_data(AGG_TOPICS_TABLE) == expected_data


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_insert_agg_meta(get_sqlitefuncts):
    sqlitefuncts, historain_version = get_sqlitefuncts
    assert get_all_data(AGG_META_TABLE) == []

    topic_id = 42
    metadata = "meaning of life"
    expected_data = ['42|"meaning of life"']
    res = sqlitefuncts.insert_agg_meta(topic_id, metadata)
    sqlitefuncts.commit()

    assert res is True
    assert get_all_data(AGG_META_TABLE) == expected_data


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_get_topic_map(get_sqlitefuncts):
    sqlitefuncts, historain_version = get_sqlitefuncts
    query = "INSERT INTO topics (topic_name) values ('football');INSERT INTO topics (topic_name) values ('netball');"
    query_db(query)
    expected_topic_map = (
        {"football": 1, "netball": 2},
        {"football": "football", "netball": "netball"},
    )

    if historain_version == "<4.0.0":
        expected_data = ["1|football", "2|netball"]
    else:
        # topics table contains metadata column
        expected_data = ["1|football|", "2|netball|"]
    assert get_all_data(TOPICS_TABLE) == expected_data

    actual_topic_map = sqlitefuncts.get_topic_map()

    assert actual_topic_map == expected_topic_map


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_get_agg_topics(get_sqlitefuncts):
    sqlitefuncts, historain_version = get_sqlitefuncts
    query = (
        "INSERT INTO aggregate_topics (agg_topic_name, agg_type, agg_time_period ) "
        "values('topic_name', 'AVG', '2001');"
    )
    query_db(query)
    sqlitefuncts.insert_agg_meta(1, {"configured_topics": "great books"})
    sqlitefuncts.commit()
    expected_topics = [("topic_name", "AVG", "2001", "great books")]

    actual_topics = sqlitefuncts.get_agg_topics()

    assert actual_topics == expected_topics


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_agg_topics_should_return_empty_on_nonexistent_table(sqlitefuncts_db_not_initialized):
    init_historian_tables(sqlitefuncts_db_not_initialized)

    actual_topic_map = sqlitefuncts_db_not_initialized.get_agg_topics()

    assert actual_topic_map == []


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_get_agg_topic_map(get_sqlitefuncts):
    sqlitefuncts, historain_version = get_sqlitefuncts
    query = (
        "INSERT INTO aggregate_topics (agg_topic_name, agg_type, agg_time_period ) "
        "values('topic_name', 'AVG', '2001');"
    )
    query_db(query)
    expected_acutal_topic_map = {("topic_name", "AVG", "2001"): 1}

    actual_topic_map = sqlitefuncts.get_agg_topic_map()

    assert actual_topic_map == expected_acutal_topic_map


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_agg_topic_map_should_return_empty_on_nonexistent_table(sqlitefuncts_db_not_initialized):
    init_historian_tables(sqlitefuncts_db_not_initialized)

    actual_topic_map = sqlitefuncts_db_not_initialized.get_agg_topic_map()

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
def test_query_topics_by_pattern(get_sqlitefuncts, topic_1, topic_2, topic_3, topic_pattern, expected_topics):
    sqlitefuncts, historain_version = get_sqlitefuncts
    query = (
        f"INSERT INTO topics (topic_name) values ({topic_1});"
        f"INSERT INTO topics (topic_name) values ({topic_2});"
        f"INSERT INTO topics (topic_name) values ({topic_3});"
    )
    query_db(query)

    actual_topics = sqlitefuncts.query_topics_by_pattern(topic_pattern)

    assert actual_topics == expected_topics


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_create_aggregate_store(get_sqlitefuncts):
    sqlitefuncts, historain_version = get_sqlitefuncts
    agg_type = "AVG"
    agg_time_period = "1984"
    expected_new_agg_table = "AVG_1984"
    expected_indexes = ["0|idx_AVG_1984|0|c|0", "1|sqlite_autoindex_AVG_1984_1|1|u|0"]

    result = sqlitefuncts.create_aggregate_store(agg_type, agg_time_period)

    assert result is True
    assert expected_new_agg_table in get_tables()

    actual_indexes = get_indexes(expected_new_agg_table)
    assert actual_indexes == expected_indexes


@pytest.mark.sqlitefuncts
@pytest.mark.dbutils
def test_collect_aggregate(get_sqlitefuncts):
    sqlitefuncts, historain_version = get_sqlitefuncts
    query = (
        "INSERT OR REPLACE INTO data values('2020-06-01 12:30:59', 42, '2');"
        "INSERT OR REPLACE INTO data values('2020-06-01 12:31:59', 43, '8');"
    )
    query_db(query)

    topic_ids = [42, 43]
    agg_type = "avg"
    expected_aggregate = (5.0, 2)

    actual_aggregate = sqlitefuncts.collect_aggregate(topic_ids, agg_type)

    assert actual_aggregate == expected_aggregate


def get_indexes(table):
    res = query_db(f"""PRAGMA index_list({table})""")
    return res.splitlines()


def get_tables():
    result = query_db(""".tables""")
    res = set(result.replace("\n", "").split())
    return res


def get_all_data(table):
    q = f"""SELECT * FROM {table}"""
    res = query_db(q)
    return res.splitlines()


def query_db(query):
    output = subprocess.run(
        ["sqlite3", "data/historian.sqlite", query], text=True, capture_output=True
    )
    # check_returncode() will raise a CalledProcessError if the query fails
    # see https://docs.python.org/3/library/subprocess.html#subprocess.CompletedProcess.returncode
    output.check_returncode()

    return output.stdout


@pytest.fixture()
def sqlitefuncts_db_not_initialized():
    global CONNECT_PARAMS
    table_names = {
        "data_table": DATA_TABLE,
        "topics_table": TOPICS_TABLE,
        "meta_table": META_TABLE,
        "agg_topics_table": AGG_TOPICS_TABLE,
        "agg_meta_table": AGG_META_TABLE,
    }
    client = SqlLiteFuncts(CONNECT_PARAMS, table_names)
    yield client

    # Teardown
    if os.path.isdir("./data"):
        files = glob.glob("./data/*", recursive=True)
        for f in files:
            os.remove(f)
        os.rmdir("./data/")


@pytest.fixture(params=[
    "<4.0.0",
    ">=4.0.0"
])
def get_sqlitefuncts(request, sqlitefuncts_db_not_initialized):
    init_database(sqlitefuncts_db_not_initialized, request.param)
    yield sqlitefuncts_db_not_initialized, request.param


def init_database(sqlitefuncts_client, historian_version):
    global CONNECT_PARAMS
    if historian_version == "<4.0.0":
        if 'detect_types' not in CONNECT_PARAMS:
            CONNECT_PARAMS['detect_types'] = sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        if 'timeout' not in CONNECT_PARAMS.keys():
            CONNECT_PARAMS['timeout'] = 10
        connection = sqlite3.connect(**CONNECT_PARAMS)
        c = connection.cursor()
        c.execute(
            '''CREATE TABLE ''' + DATA_TABLE +
            ''' (ts timestamp NOT NULL,
                 topic_id INTEGER NOT NULL,
                 value_string TEXT NOT NULL,
                 UNIQUE(topic_id, ts))''')
        c.execute(
            '''CREATE TABLE ''' + TOPICS_TABLE +
            ''' (topic_id INTEGER PRIMARY KEY,
                 topic_name TEXT NOT NULL,
                 UNIQUE(topic_name))''')
        c.execute(
            '''CREATE TABLE ''' + META_TABLE +
            ''' (topic_id INTEGER PRIMARY KEY,
                 metadata TEXT NOT NULL,
                 UNIQUE(topic_id))''')
        connection.commit()
        sqlitefuncts_client.setup_aggregate_historian_tables()
    else:
        sqlitefuncts_client.setup_historian_tables()
        sqlitefuncts_client.setup_aggregate_historian_tables()


def init_historian_tables(sqlitefuncts_client):
    sqlitefuncts_client.setup_historian_tables()
