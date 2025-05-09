import datetime
import os
import logging

import gevent
import pytest

try:
    import psycopg2
    from psycopg2.sql import SQL, Identifier
except ImportError:
    pytest.skip(
        "Required imports for testing are not installed; thus, not running tests. "
        "Install imports with: python bootstrap.py --postgres",
        allow_module_level=True,
    )
from volttron.platform import jsonapi
from volttron.platform.dbutils.postgresqlfuncts import PostgreSqlFuncts

logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
pytestmark = [pytest.mark.postgresqlfuncts, pytest.mark.dbutils, pytest.mark.unit]

DATA_TABLE = "data"
TOPICS_TABLE = "topics"
META_TABLE = "meta"
AGG_TOPICS_TABLE = "aggregate_topics"
AGG_META_TABLE = "aggregate_meta"
db_connection = None
user = 'postgres'
password = 'postgres'
historian_config = {
    "connection": {
        "type": "postgresql",
        "params": {
            'dbname': 'test_historian',
            'port': os.environ.get("POSTGRES_PORT", 5432),
            'host': 'localhost',
            'user': os.environ.get("POSTGRES_USER", user),
            'password': os.environ.get("POSTGRES_PASSWORD", password)
        }
    }
}
table_names = {
    "data_table": DATA_TABLE,
    "topics_table": TOPICS_TABLE,
    "meta_table": META_TABLE,
    "agg_topics_table": AGG_TOPICS_TABLE,
    "agg_meta_table": AGG_META_TABLE,
}

def test_insert_meta_should_return_true(setup_functs):
    sqlfuncts, historian_version = setup_functs
    if historian_version != "<4.0.0":
        pytest.skip("insert_meta() is called by historian only for schema <4.0.0")
    topic_id = "44"
    metadata = "foobar44"
    expected_data = (44, '"foobar44"')

    res = sqlfuncts.insert_meta(topic_id, metadata)
    #db_connection.commit()
    gevent.sleep(1)
    assert res is True
    assert get_data_in_table("meta")[0] == expected_data
    cleanup_tables(truncate_tables=["meta"], drop_tables=False)

def test_update_meta_should_succeed(setup_functs):
    sqlfuncts, historian_version = setup_functs
    metadata = {"units": "count"}
    metadata_s = jsonapi.dumps(metadata)
    topic = "foobar"

    id = sqlfuncts.insert_topic(topic)
    sqlfuncts.insert_meta(id, {"fdjlj": "XXXX"})
    assert metadata_s not in get_data_in_table(TOPICS_TABLE)[0]

    res = sqlfuncts.update_meta(id, metadata)

    expected_lt_4 = [(1, metadata_s)]
    expected_gteq_4 = [(1, topic, metadata_s)]
    assert res is True
    if historian_version == "<4.0.0":
        assert get_data_in_table(META_TABLE) == expected_lt_4
        cleanup_tables(truncate_tables=[META_TABLE], drop_tables=False)
    else:
        assert get_data_in_table(TOPICS_TABLE) == expected_gteq_4
        cleanup_tables(truncate_tables=[TOPICS_TABLE], drop_tables=False)

def test_setup_historian_tables_should_create_tables(setup_functs):
    sqlfuncts, historian_version = setup_functs
    # get_container initializes db and sqlfuncts
    # to test setup explicitly drop tables and see if tables get created correctly
    cleanup_tables(None, drop_tables=True)

    tables_before_setup = select_all_historian_tables()
    assert tables_before_setup == set()
    expected_tables = set(["data", "topics"])
    sqlfuncts.setup_historian_tables()
    actual_tables = select_all_historian_tables()
    assert actual_tables == expected_tables


def test_setup_aggregate_historian_tables_should_create_aggregate_tables(setup_functs):
    sqlfuncts, historian_version = setup_functs
    # get_container initializes db and sqlfuncts to test setup explicitly drop tables and see if tables get created
    cleanup_tables(None, drop_tables=True)
    create_historian_tables(historian_version)
    agg_topic_table = "aggregate_topics"
    agg_meta_table = "aggregate_meta"

    original_tables = select_all_historian_tables()
    assert agg_topic_table not in original_tables
    assert agg_meta_table not in original_tables

    expected_agg_topic_fields = {
        "agg_topic_id",
        "agg_topic_name",
        "agg_time_period",
        "agg_type",
    }
    expected_agg_meta_fields = {"agg_topic_id", "metadata"}

    sqlfuncts.setup_aggregate_historian_tables()

    updated_tables = select_all_historian_tables()
    assert agg_topic_table in updated_tables
    assert agg_meta_table in updated_tables
    assert (
        describe_table(agg_topic_table)
        == expected_agg_topic_fields
    )
    assert (
        describe_table(agg_meta_table) == expected_agg_meta_fields
    )
    assert sqlfuncts.agg_topics_table == agg_topic_table
    assert sqlfuncts.agg_meta_table == agg_meta_table
    assert sqlfuncts.data_table == DATA_TABLE
    assert sqlfuncts.topics_table == TOPICS_TABLE
    if sqlfuncts.meta_table != TOPICS_TABLE:
        assert sqlfuncts.meta_table == META_TABLE


@pytest.mark.parametrize(
    "topic_ids, id_name_map, expected_values",
    [
        ([42], {42: "topic42"}, {"topic42": []}),
        (
            [43],
            {43: "topic43"},
            {"topic43": [("2020-06-01T12:30:59.000000+00:00", [2, 3])]},
        ),
    ],
)
def test_query_should_return_data(setup_functs, topic_ids, id_name_map, expected_values):
    global db_connection
    sqlfuncts, historian_version = setup_functs
    # explicit drop and recreate as the test is repeated it multiple times (number of params * historian version)
    create_all_tables(historian_version, sqlfuncts)
    db_connection.commit()
    query = f"""INSERT INTO {DATA_TABLE} VALUES ('2020-06-01 12:30:59', 43, '[2,3]')"""
    seed_database(query)
    actual_values = sqlfuncts.query(topic_ids, id_name_map)
    assert actual_values == expected_values


def test_insert_topic_should_return_topic_id(setup_functs):
    sqlfuncts, historian_version = setup_functs

    topic = "football"
    expected_topic_id = 1
    actual_topic_id = sqlfuncts.insert_topic(topic)
    assert actual_topic_id == expected_topic_id
    cleanup_tables(truncate_tables=[TOPICS_TABLE], drop_tables=False)


def test_insert_topic_and_meta_query_should_succeed(setup_functs):
    sqlfuncts, historian_version = setup_functs
    if historian_version == "<4.0.0":
        pytest.skip("Not relevant for historian schema before 4.0.0")
    topic = "football"
    metadata = {"units": "count"}
    actual_id = sqlfuncts.insert_topic(topic, metadata=metadata)

    assert isinstance(actual_id, int)
    result = get_data_in_table("topics")[0]
    assert (actual_id, topic) == result[0:2]
    assert metadata == jsonapi.loads(result[2])
    cleanup_tables(truncate_tables=[TOPICS_TABLE], drop_tables=False)


def test_insert_agg_topic_should_return_agg_topic_id(setup_functs):
    sqlfuncts, historian_version = setup_functs

    topic = "some_agg_topic"
    agg_type = "AVG"
    agg_time_period = "2019"
    expected_data = (1, "some_agg_topic", "AVG", "2019")

    actual_id = sqlfuncts.insert_agg_topic(
        topic, agg_type, agg_time_period
    )

    assert isinstance(actual_id, int)
    assert get_data_in_table(AGG_TOPICS_TABLE)[0] == expected_data
    cleanup_tables(truncate_tables=[AGG_TOPICS_TABLE], drop_tables=False)


def test_insert_data_should_return_true(setup_functs):
    sqlfuncts, historian_version = setup_functs
    cleanup_tables(truncate_tables=[DATA_TABLE], drop_tables=False)
    ts = "2001-09-11 08:46:00"
    topic_id = "11"
    data = "1wtc"
    expected_data = [(datetime.datetime(2001, 9, 11, 8, 46), 11, '"1wtc"')]

    res = sqlfuncts.insert_data(ts, topic_id, data)

    assert res is True
    assert get_data_in_table(DATA_TABLE) == expected_data
    cleanup_tables(truncate_tables=[DATA_TABLE], drop_tables=False)


def test_update_topic_should_return_true(setup_functs):
    sqlfuncts, historian_version = setup_functs

    topic = "football"
    actual_id = sqlfuncts.insert_topic(topic)
    assert isinstance(actual_id, int)

    result = sqlfuncts.update_topic("soccer", actual_id)
    assert result is True
    assert (actual_id, "soccer") == get_data_in_table(TOPICS_TABLE)[0][0:2]
    cleanup_tables(truncate_tables=[TOPICS_TABLE], drop_tables=False)


def test_update_topic_and_metadata_should_succeed(setup_functs):
    sqlfuncts, historian_version = setup_functs
    if historian_version == "<4.0.0":
        pytest.skip("Not relevant for historian schema before 4.0.0")
    topic = "football"
    actual_id = sqlfuncts.insert_topic(topic)

    assert isinstance(actual_id, int)

    result = sqlfuncts.update_topic("soccer", actual_id, metadata={"test": "test value"})

    assert result is True
    assert (actual_id, "soccer", '{"test": "test value"}') == get_data_in_table("topics")[0]
    cleanup_tables(truncate_tables=[TOPICS_TABLE], drop_tables=False)


def test_get_aggregation_list_should_return_list(setup_functs):
    sqlfuncts, historian_version = setup_functs

    expected_list = [
        "AVG",
        "MIN",
        "MAX",
        "COUNT",
        "SUM",
        "BIT_AND",
        "BIT_OR",
        "BOOL_AND",
        "BOOL_OR",
        "MEDIAN",
        "STDDEV",
        "STDDEV_POP",
        "STDDEV_SAMP",
        "VAR_POP",
        "VAR_SAMP",
        "VARIANCE",
    ]

    assert sqlfuncts.get_aggregation_list() == expected_list


def test_insert_agg_topic_should_return_true(setup_functs):
    sqlfuncts, historian_version = setup_functs
    cleanup_tables(truncate_tables=[AGG_TOPICS_TABLE], drop_tables=False)
    topic = "some_agg_topic"
    agg_type = "AVG"
    agg_time_period = "2019"
    expected_data = ("some_agg_topic", "AVG", "2019")

    actual_id = sqlfuncts.insert_agg_topic(
        topic, agg_type, agg_time_period
    )

    assert isinstance(actual_id, int)
    assert get_data_in_table(AGG_TOPICS_TABLE)[0][1:] == expected_data


def test_update_agg_topic_should_return_true(setup_functs):
    sqlfuncts, historian_version = setup_functs
    cleanup_tables(truncate_tables=[AGG_TOPICS_TABLE], drop_tables=False)
    topic = "cars"
    agg_type = "SUM"
    agg_time_period = "2100ZULU"
    expected_data = ("cars", "SUM", "2100ZULU")

    actual_id = sqlfuncts.insert_agg_topic(
        topic, agg_type, agg_time_period
    )

    assert isinstance(actual_id, int)
    assert get_data_in_table(AGG_TOPICS_TABLE)[0][1:] == expected_data

    new_agg_topic_name = "boats"
    expected_data = ("boats", "SUM", "2100ZULU")

    result = sqlfuncts.update_agg_topic(actual_id, new_agg_topic_name)

    assert result is True
    assert get_data_in_table(AGG_TOPICS_TABLE)[0][1:] == expected_data


def test_insert_agg_meta_should_return_true(setup_functs):
    sqlfuncts, historian_version = setup_functs
    cleanup_tables(truncate_tables=[AGG_META_TABLE], drop_tables=False)
    topic_id = 42
    # metadata must be in the following convention because aggregation methods, i.e. get_agg_topics, rely on metadata having a key called "configured_topics"
    metadata = {"configured_topics": "meaning of life"}
    expected_data = (42, '{"configured_topics": "meaning of life"}')

    result = sqlfuncts.insert_agg_meta(topic_id, metadata)

    assert result is True
    assert get_data_in_table(AGG_META_TABLE)[0] == expected_data


def test_get_topic_map_should_return_maps(setup_functs):
    global db_connection
    sqlfuncts, historian_version = setup_functs
    create_all_tables(historian_version, sqlfuncts)
    db_connection.commit()
    gevent.sleep(0.5)
    query = """
               INSERT INTO topics (topic_name)
               VALUES ('football');
               INSERT INTO topics (topic_name)
               VALUES ('baseball');
            """
    seed_database(query)
    expected = (
        {"baseball": 2, "football": 1},
        {"baseball": "baseball", "football": "football"},
    )

    actual = sqlfuncts.get_topic_map()

    assert actual == expected


def test_get_topic_meta_map_should_return_maps(setup_functs):
    sqlfuncts, historian_version = setup_functs

    if historian_version == "<4.0.0":
        pytest.skip("method applied only to version >=4.0.0")
    else:
        create_all_tables(historian_version, sqlfuncts)
        gevent.sleep(1)
        query = """
                   INSERT INTO topics (topic_name)
                   VALUES ('football');
                   INSERT INTO topics (topic_name, metadata)
                   VALUES ('baseball', '{"meta":"value"}');
                """
        seed_database(query)
        expected = {1: None, 2: {"meta": "value"}}
        actual = sqlfuncts.get_topic_meta_map()
        assert actual == expected


def test_get_agg_topics_should_return_list(setup_functs):
    sqlfuncts, historian_version = setup_functs

    topic = "some_agg_topic"
    agg_type = "AVG"
    agg_time_period = "2019"
    topic_id = sqlfuncts.insert_agg_topic(
        topic, agg_type, agg_time_period
    )
    metadata = {"configured_topics": "meaning of life"}
    sqlfuncts.insert_agg_meta(topic_id, metadata)
    expected_list = [("some_agg_topic", "AVG", "2019", "meaning of life")]

    actual_list = sqlfuncts.get_agg_topics()

    assert actual_list == expected_list


def test_get_agg_topic_map_should_return_dict(setup_functs):
    sqlfuncts, historian_version = setup_functs
    create_all_tables(historian_version, sqlfuncts)
    query = f"""
               INSERT INTO {AGG_TOPICS_TABLE}
               (agg_topic_name, agg_type, agg_time_period)
               VALUES ('topic_name', 'AVG', '2001');
            """
    seed_database(query)
    expected = {("topic_name", "AVG", "2001"): 1}
    actual = sqlfuncts.get_agg_topic_map()
    assert actual == expected


@pytest.mark.parametrize(
    "topic_1, topic_2, topic_3, topic_pattern, expected_result",
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
def test_query_topics_by_pattern_should_return_matching_results(
    setup_functs,
    topic_1,
    topic_2,
    topic_3,
    topic_pattern,
    expected_result
):

    sqlfuncts, historian_version = setup_functs
    create_all_tables(historian_version, sqlfuncts)
    gevent.sleep(2)
    query = f"""
               INSERT INTO {TOPICS_TABLE}  (topic_name)
               VALUES ({topic_1});
               INSERT INTO {TOPICS_TABLE} (topic_name)
               VALUES ({topic_2});
               INSERT INTO {TOPICS_TABLE} (topic_name)
               VALUES ({topic_3});
            """
    seed_database(query)
    actual_result = sqlfuncts.query_topics_by_pattern(topic_pattern)
    assert actual_result == expected_result


def test_create_aggregate_store_should_succeed(setup_functs):
    sqlfuncts, historian_version = setup_functs

    agg_type = "AVG"
    agg_time_period = "1984"
    expected_aggregate_table = "AVG_1984"
    expected_fields = {"topics_list", "agg_value", "topic_id", "ts"}

    sqlfuncts.create_aggregate_store(agg_type, agg_time_period)

    assert expected_aggregate_table in select_all_historian_tables()
    assert describe_table(expected_aggregate_table) == expected_fields


def test_insert_aggregate_stmt_should_succeed(setup_functs):
    sqlfuncts, historian_version = setup_functs

    # be aware that Postgresql will automatically fold unquoted names into lower case
    # From : https://www.postgresql.org/docs/current/sql-syntax-lexical.html
    # Quoting an identifier also makes it case-sensitive, whereas unquoted names are always folded to lower case.
    # For example, the identifiers FOO, foo, and "foo" are considered the same by PostgreSQL,
    # but "Foo" and "FOO" are different from these three and each other.
    # (The folding of unquoted names to lower case in PostgreSQL is incompatible with the SQL standard,
    # which says that unquoted names should be folded to upper case.
    # Thus, foo should be equivalent to "FOO" not "foo" according to the standard.
    # If you want to write portable applications you are advised to always quote a particular name or never quote it.)
    query = """
               CREATE TABLE AVG_1776 (
               ts timestamp NOT NULL,
               topic_id INTEGER NOT NULL,
               agg_value DOUBLE PRECISION NOT NULL,
               topics_list TEXT,
               UNIQUE(ts, topic_id));
               CREATE INDEX IF NOT EXISTS idx_avg_1776 ON avg_1776 (ts ASC);
            """
    seed_database(query)

    agg_topic_id = 42
    agg_type = "avg"
    period = "1776"
    ts = "2020-06-01 12:30:59"
    data = 44.42
    topic_ids = [12, 54, 65]
    expected_data = (
        datetime.datetime(2020, 6, 1, 12, 30, 59),
        42,
        44.42,
        "[12, 54, 65]",
    )

    res = sqlfuncts.insert_aggregate(
        agg_topic_id, agg_type, period, ts, data, topic_ids
    )

    assert res is True
    assert get_data_in_table("avg_1776")[0] == expected_data


def test_collect_aggregate_stmt_should_return_rows(setup_functs):
    sqlfuncts, historian_version = setup_functs

    query = f"""
                INSERT INTO {DATA_TABLE}
                VALUES ('2020-06-01 12:30:59', 42, '2');
                INSERT INTO {DATA_TABLE}
                VALUES ('2020-06-01 12:31:59', 43, '8')
            """
    seed_database(query)

    topic_ids = [42, 43]
    agg_type = "avg"
    expected_aggregate = (5.0, 2)

    actual_aggregate = sqlfuncts.collect_aggregate(topic_ids, agg_type)

    assert actual_aggregate == expected_aggregate


def test_collect_aggregate_stmt_should_raise_value_error(setup_functs):
    sqlfuncts, historian_version = setup_functs

    with pytest.raises(ValueError):
            sqlfuncts.collect_aggregate("dfdfadfdadf", "Invalid agg type")


@pytest.fixture(scope="module", params=[
    ('<4.0.0', os.environ.get("POSTGRES_PORT", 5432)),
    ('<4.0.0', os.environ.get("TIMESCALE_PORT", 5433)),
    ('>=4.0.0', os.environ.get("POSTGRES_PORT", 5432)),
    ('>=4.0.0', os.environ.get("POSTGRES_PORT", 5433))
     ])
def setup_functs(request):
    global db_connection, historian_config, table_names
    historian_version = request.param[0]
    port = request.param[1]
    historian_config["connection"]["params"]["port"] = port

    db_connection = psycopg2.connect(**historian_config["connection"]["params"])
    db_connection.autocommit = True
    create_all_tables(historian_version)
    postgresfuncts = PostgreSqlFuncts(historian_config["connection"]["params"], table_names)
    postgresfuncts.setup_historian_tables()
    yield postgresfuncts, historian_version


def create_all_tables(historian_version, sqlfuncts=None):
    try:
        cleanup_tables(table_names.values(), drop_tables=True)
    except Exception as exc:
        print('Error truncating existing tables: {}'.format(exc))
    create_historian_tables(historian_version, sqlfuncts)
    create_aggregate_tables(historian_version)


def create_historian_tables(historian_version, sqlfuncts=None):
    global db_connection, historian_config, table_names
    cursor = db_connection.cursor()
    if historian_version == "<4.0.0":
        print("Setting up for version <4.0.0")
        cursor = db_connection.cursor()
        cursor.execute(SQL(
            'CREATE TABLE IF NOT EXISTS {} ('
            'ts TIMESTAMP NOT NULL, '
            'topic_id INTEGER NOT NULL, '
            'value_string TEXT NOT NULL, '
            'UNIQUE (topic_id, ts)'
            ')').format(Identifier(table_names['data_table'])))
        cursor.execute(SQL(
            'CREATE INDEX IF NOT EXISTS {} ON {} (ts ASC)').format(
            Identifier('idx_' + table_names['data_table']),
            Identifier(table_names['data_table'])))
        cursor.execute(SQL(
            'CREATE TABLE IF NOT EXISTS {} ('
            'topic_id SERIAL PRIMARY KEY NOT NULL, '
            'topic_name VARCHAR(512) NOT NULL, '
            'UNIQUE (topic_name)'
            ')').format(Identifier(table_names['topics_table'])))
        cursor.execute(SQL(
            'CREATE TABLE IF NOT EXISTS {} ('
            'topic_id INTEGER PRIMARY KEY NOT NULL, '
            'metadata TEXT NOT NULL'
            ')').format(Identifier(table_names['meta_table'])))
        db_connection.commit()
        cursor.close()
    elif sqlfuncts:
        sqlfuncts.setup_historian_tables()
    gevent.sleep(5)
    return


def create_aggregate_tables(historian_version):
    global db_connection
    cursor = db_connection.cursor()
    if historian_version == "<4.0.0":
        query = f"""
                    CREATE TABLE IF NOT EXISTS {AGG_TOPICS_TABLE} (
                    agg_topic_id SERIAL PRIMARY KEY NOT NULL,
                    agg_topic_name VARCHAR(512) NOT NULL,
                    agg_type VARCHAR(512) NOT NULL,
                    agg_time_period VARCHAR(512) NOT NULL,
                    UNIQUE (agg_topic_name, agg_type, agg_time_period));
                    CREATE TABLE IF NOT EXISTS {AGG_META_TABLE} (
                    agg_topic_id INTEGER PRIMARY KEY NOT NULL,
                    metadata TEXT NOT NULL);
                """
    else:
        query = f"""
                    CREATE TABLE IF NOT EXISTS {AGG_TOPICS_TABLE} (
                    agg_topic_id SERIAL PRIMARY KEY NOT NULL,
                    agg_topic_name VARCHAR(512) NOT NULL,
                    agg_type VARCHAR(20) NOT NULL,
                    agg_time_period VARCHAR(20) NOT NULL,
                    UNIQUE (agg_topic_name, agg_type, agg_time_period));
                    CREATE TABLE IF NOT EXISTS {AGG_META_TABLE} (
                    agg_topic_id INTEGER PRIMARY KEY NOT NULL,
                    metadata TEXT NOT NULL);
                """
    cursor.execute(SQL(query))
    db_connection.commit()
    cursor.close()
    return


def select_all_historian_tables():
    global db_connection
    cursor = db_connection.cursor()
    tables = []
    try:
        cursor.execute(f"""SELECT table_name FROM information_schema.tables
                                    WHERE table_catalog = 'test_historian' and table_schema = 'public'""")
        rows = cursor.fetchall()
        print(f"table names {rows}")
        tables = [columns[0] for columns in rows]
    except Exception as e:
        print("Error getting list of {}".format(e))
    finally:
        if cursor:
            cursor.close()
    return set(tables)


def describe_table(table):
    global db_connection
    cursor = db_connection.cursor()
    query = SQL(f"SELECT column_name FROM information_schema.columns WHERE table_name='{table}'")
    cursor.execute(query, vars=table)
    results = cursor.fetchall()
    cursor.close()
    return {t[0] for t in results}


def get_data_in_table(table):
    global db_connection
    cursor = db_connection.cursor()
    query = SQL("SELECT * " "FROM {table_name}").format(table_name=Identifier(table))
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()
    return results

def cleanup_tables(truncate_tables, drop_tables=False):
    global db_connection
    cursor = db_connection.cursor()
    if truncate_tables is None:
        truncate_tables = select_all_historian_tables()

    if drop_tables:
        for table in truncate_tables:
            if table:
                cursor.execute(SQL('DROP TABLE IF EXISTS {}').format(Identifier(table)))
    else:
        for table in truncate_tables:
            if table:
                cursor.execute(SQL('TRUNCATE TABLE {}').format(Identifier(table)))

    db_connection.commit()
    cursor.close()

def seed_database(sql):
    global db_connection
    cursor = db_connection.cursor()
    try:
        cursor.execute(sql)
    except psycopg2.errors.UndefinedTable as e:
        print(e)
    cursor.close()
    db_connection.commit()
