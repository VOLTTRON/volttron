import datetime
import os
import logging
from collections import namedtuple

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
from volttron.platform.dbutils.postgresqlfuncts import PostgreSqlFuncts, _derived_name

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


# Configured table names that must reach PostgreSQL as names, never as SQL
# text. Kept short so the rebuild's suffixed index names stay under 63 bytes.
ODD_DATA_TABLE = 'Odd"Da\'ta; --'
ODD_TOPICS_TABLE = 'Odd"Top\'ics'
DiskUsage = namedtuple("DiskUsage", "total used free")


def _live_connect_params():
    params = dict(historian_config["connection"]["params"])
    params["port"] = os.environ.get("POSTGRES_PORT", 5432)
    return params


@pytest.fixture()
def live_db():
    """Yield (connection, make_functs); drop every table the test names."""
    conn = psycopg2.connect(**_live_connect_params())
    conn.autocommit = True
    # A rebuild that leaves its transaction open would block these reads forever.
    _run(conn, "SET statement_timeout = 10000")
    tables = []
    functs_made = []

    def make_functs(data_table, topics_table="odd_topics", meta_table="odd_meta"):
        tables.extend([data_table, topics_table, meta_table,
                       _derived_name(data_table, suffix="_new"), _derived_name(data_table, suffix="_old")])
        functs = PostgreSqlFuncts(_live_connect_params(), {
            "data_table": data_table,
            "topics_table": topics_table,
            "meta_table": meta_table,
        })
        functs_made.append(functs)
        return functs

    def drop_later(*names):
        tables.extend(names)

    yield conn, make_functs, drop_later
    for functs in functs_made:
        functs.close()
    with conn.cursor() as cursor:
        for name in tables:
            cursor.execute(SQL("DROP TABLE IF EXISTS {} CASCADE").format(Identifier(name)))
    conn.close()


def _run(conn, query, args=None):
    with conn.cursor() as cursor:
        cursor.execute(query, args)
        if cursor.description is not None:
            return cursor.fetchall()
    return None


def _table_exists(conn, name):
    return bool(_run(conn, "SELECT 1 FROM information_schema.tables "
                           "WHERE table_schema = 'public' AND table_name = %s", (name,)))


def _row_count(conn, name):
    return _run(conn, SQL("SELECT COUNT(*) FROM {}").format(Identifier(name)))[0][0]


def _index_names(conn, name):
    rows = _run(conn, "SELECT indexname FROM pg_indexes "
                      "WHERE schemaname = 'public' AND tablename = %s", (name,))
    return {row[0] for row in rows}


def _unique_constraint_names(conn, name):
    rows = _run(conn, "SELECT con.conname FROM pg_constraint con "
                      "JOIN pg_class rel ON rel.oid = con.conrelid "
                      "JOIN pg_namespace ns ON ns.oid = rel.relnamespace "
                      "WHERE ns.nspname = 'public' AND rel.relname = %s "
                      "AND con.contype = 'u'", (name,))
    return {row[0] for row in rows}


def _create_data_table(conn, name, rows):
    """Create a data table with the pre-4.0 layout and insert rows topic ids 1..rows."""
    _run(conn, SQL("CREATE TABLE {} (ts TIMESTAMP NOT NULL, topic_id INTEGER NOT NULL, "
                   "value_string TEXT NOT NULL, UNIQUE (topic_id, ts))").format(Identifier(name)))
    for topic_id in range(1, rows + 1):
        _run(conn, SQL("INSERT INTO {} VALUES (now(), %s, '1')").format(Identifier(name)),
             (topic_id,))
    _run(conn, SQL("ANALYZE {}").format(Identifier(name)))


def test_setup_historian_tables_sends_configured_names_as_parameters():
    functs = PostgreSqlFuncts.__new__(PostgreSqlFuncts)
    functs.db_name = "db'name"
    functs.data_table = "data'table"
    functs.topics_table = "topics'table"
    functs.meta_table = "meta"
    calls = []

    def fake_select(query, args=None, fetch_all=True):
        calls.append((query, args))
        return [("row",)]

    functs.select = fake_select
    functs.setup_historian_tables()

    assert len(calls) == 2
    for query, args in calls:
        for name in (functs.db_name, functs.data_table, functs.topics_table):
            assert name not in str(query)
    assert calls[0][1] == (functs.db_name, functs.data_table)
    assert calls[1][1] == (functs.topics_table,)


def test_setup_historian_tables_creates_tables_with_odd_names(live_db):
    conn, make_functs, _ = live_db
    functs = make_functs(ODD_DATA_TABLE, ODD_TOPICS_TABLE)

    functs.setup_historian_tables()

    assert _table_exists(conn, ODD_DATA_TABLE)
    assert _table_exists(conn, ODD_TOPICS_TABLE)
    assert f"idx_{ODD_DATA_TABLE}" in _index_names(conn, ODD_DATA_TABLE)

    # A second agent start takes the "table exists" branch and must find the
    # metadata column in the oddly named topics table.
    restarted = make_functs(ODD_DATA_TABLE, ODD_TOPICS_TABLE)
    restarted.setup_historian_tables()
    assert restarted.meta_table == ODD_TOPICS_TABLE


def test_setup_historian_tables_matches_only_the_configured_table(live_db):
    conn, make_functs, drop_later = live_db
    drop_later("odd_canary")
    _create_data_table(conn, "odd_canary", rows=0)
    data_table = "odd_missing' OR table_name = 'odd_canary"
    functs = make_functs(data_table)

    functs.setup_historian_tables()

    assert _table_exists(conn, data_table)
    assert _table_exists(conn, "odd_topics")


def test_delete_rows_by_chunks_deletes_oldest_rows_of_the_configured_table(live_db):
    conn, make_functs, drop_later = live_db
    drop_later("odd_cy")
    _create_data_table(conn, "odd_cy", rows=1)
    data_table = "odd_cy; DROP TABLE odd_cy; --"
    functs = make_functs(data_table)
    _create_data_table(conn, data_table, rows=3)

    assert functs.delete_rows_by_chunks(2, chunk_size=1) == 2

    assert _row_count(conn, data_table) == 1
    assert _row_count(conn, "odd_cy") == 1


def test_manage_db_size_treats_data_table_as_a_name(live_db):
    conn, make_functs, drop_later = live_db
    drop_later("odd_cx")
    _create_data_table(conn, "odd_cx", rows=1)
    data_table = "odd_cx; DROP TABLE odd_cx; --"
    functs = make_functs(data_table)
    functs.setup_historian_tables()
    topic_id = functs.insert_topic("device/point")
    functs.insert_data(datetime.datetime(2020, 1, 1), topic_id, 42)
    functs.commit()

    error = None
    try:
        functs.manage_db_size(None, None)
    except psycopg2.Error as exc:
        error = exc
    assert _table_exists(conn, "odd_cx")
    assert error is None
    assert _row_count(conn, data_table) == 1

    functs.manage_db_size(datetime.datetime(2030, 1, 1), None)
    assert _row_count(conn, data_table) == 0
    assert _row_count(conn, "odd_cx") == 1


@pytest.mark.parametrize("data_table, decoy", [
    (ODD_DATA_TABLE, None),
    ("OddCase", "oddcase"),
])
def test_table_metrics_read_the_configured_table(live_db, data_table, decoy):
    conn, make_functs, drop_later = live_db
    functs = make_functs(data_table)
    _create_data_table(conn, data_table, rows=3)
    if decoy:
        # An unquoted name folds to lower case and would measure this table.
        drop_later(decoy)
        _create_data_table(conn, decoy, rows=1)

    metrics = functs.get_table_metrics(need_exact_count=True)

    expected_bytes = _run(conn, "SELECT pg_total_relation_size(c.oid) FROM pg_class c "
                                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                                "WHERE n.nspname = 'public' AND c.relname = %s", (data_table,))[0][0]
    assert metrics["reltuples"] == 3
    assert metrics["actual_count"] == 3
    assert metrics["total_bytes"] == expected_bytes


def test_disk_space_check_reads_the_configured_table(live_db, monkeypatch):
    conn, make_functs, _ = live_db
    functs = make_functs(ODD_DATA_TABLE)
    _create_data_table(conn, ODD_DATA_TABLE, rows=1)
    # The server's data directory is not on this host; report a fixed free size.
    usage = DiskUsage(total=10 ** 13, used=0, free=10 ** 12)
    monkeypatch.setattr("volttron.platform.dbutils.postgresqlfuncts.shutil.disk_usage",
                        lambda path: usage)

    assert functs.check_disk_space_for_repack(1000) == (True, 10 ** 12, 0, 1200)


def test_hypertable_creation_receives_the_configured_table(live_db):
    conn, make_functs, drop_later = live_db
    if _run(conn, "SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'"):
        pytest.skip("needs a server without timescaledb to stand in create_hypertable")
    drop_later("odd_hypertable_calls")
    _run(conn, "CREATE TABLE odd_hypertable_calls (rel regclass)")
    _run(conn, "CREATE FUNCTION public.create_hypertable(relation regclass, time_column_name name, "
               "if_not_exists boolean DEFAULT false) RETURNS void LANGUAGE sql "
               "AS 'INSERT INTO odd_hypertable_calls VALUES ($1)'")
    try:
        functs = make_functs(ODD_DATA_TABLE, ODD_TOPICS_TABLE)
        functs.timescale_dialect = True
        functs.setup_historian_tables()
    finally:
        _run(conn, "DROP FUNCTION public.create_hypertable(regclass, name, boolean)")

    recorded = _run(conn, "SELECT rel::oid FROM odd_hypertable_calls")
    expected = _run(conn, "SELECT c.oid FROM pg_class c JOIN pg_namespace n "
                          "ON n.oid = c.relnamespace WHERE n.nspname = 'public' "
                          "AND c.relname = %s", (ODD_DATA_TABLE,))
    assert recorded == expected


@pytest.mark.parametrize("data_table", [ODD_DATA_TABLE, "odd_hist_a"])
def test_manual_table_rebuild_keeps_rows_and_names_indexes_after_the_table(live_db, data_table):
    conn, make_functs, _ = live_db
    functs = make_functs(data_table)
    _create_data_table(conn, data_table, rows=3)

    assert functs.manual_table_rebuild() is True

    assert _row_count(conn, data_table) == 3
    assert _index_names(conn, data_table) == {f"idx_{data_table}", f"{data_table}_topic_id_ts_key"}
    assert _unique_constraint_names(conn, data_table) == {f"{data_table}_topic_id_ts_key"}


def test_manual_table_rebuild_of_two_tables_keeps_index_names_unique(live_db):
    conn, make_functs, _ = live_db
    first = make_functs("odd_hist_b")
    second = make_functs("odd_hist_c")
    _create_data_table(conn, "odd_hist_b", rows=2)
    _create_data_table(conn, "odd_hist_c", rows=2)

    assert first.manual_table_rebuild() is True
    assert second.manual_table_rebuild() is True

    assert _index_names(conn, "odd_hist_b") == {"idx_odd_hist_b", "odd_hist_b_topic_id_ts_key"}
    assert _index_names(conn, "odd_hist_c") == {"idx_odd_hist_c", "odd_hist_c_topic_id_ts_key"}


@pytest.mark.parametrize("taken_name", ["idx_odd_hist_d", "odd_hist_d_topic_id_ts_key"])
def test_manual_table_rebuild_reports_failure_when_an_index_name_is_taken(live_db, taken_name, caplog):
    conn, make_functs, drop_later = live_db
    drop_later("odd_other")
    _run(conn, "CREATE TABLE odd_other (ts TIMESTAMP)")
    _run(conn, SQL("CREATE INDEX {} ON odd_other (ts)").format(Identifier(taken_name)))
    functs = make_functs("odd_hist_d")
    _create_data_table(conn, "odd_hist_d", rows=2)

    with caplog.at_level(logging.WARNING, logger="volttron.platform.dbutils.postgresqlfuncts"):
        assert functs.manual_table_rebuild() is False
    assert _row_count(conn, "odd_hist_d") == 2
    assert "the rebuilt table is already in place" in caplog.text
    if taken_name.endswith("_key"):
        assert 'Renaming index "data_topic_id_ts_key_' in caplog.text


def test_reindex_after_rebuild_finds_the_rebuilt_indexes(live_db, caplog):
    conn, make_functs, _ = live_db
    functs = make_functs("odd_hist_e")
    _create_data_table(conn, "odd_hist_e", rows=2)
    assert functs.manual_table_rebuild() is True
    metrics = functs.get_table_metrics()
    index_oids = "SELECT indexrelid FROM pg_index WHERE indrelid = 'odd_hist_e'::regclass ORDER BY 1"
    before = _run(conn, index_oids)

    with caplog.at_level(logging.INFO, logger="volttron.platform.dbutils.postgresqlfuncts"):
        functs.delete_without_rebuild(metrics, metrics["total_bytes"])

    # REINDEX CONCURRENTLY builds each index anew, so both index oids change.
    after = _run(conn, index_oids)
    assert len(before) == len(after) == 2
    assert not set(before) & set(after)
    assert "Successfully reindexed both indexes" in caplog.text
    assert _row_count(conn, "odd_hist_e") == 2


def test_manual_table_rebuild_commits_and_releases_the_table(live_db):
    conn, make_functs, _ = live_db
    functs = make_functs("odd_hist_f")
    _create_data_table(conn, "odd_hist_f", rows=3)

    assert functs.manual_table_rebuild() is True

    _run(conn, "BEGIN")
    try:
        _run(conn, "LOCK TABLE odd_hist_f IN ACCESS EXCLUSIVE MODE NOWAIT")
    finally:
        _run(conn, "ROLLBACK")
    assert _row_count(conn, "odd_hist_f") == 3
    # Only the rebuilt table carries an index on ts; the original had none.
    assert _run(conn, "SELECT count(*) FROM pg_indexes WHERE tablename = 'odd_hist_f' "
                      "AND indexdef LIKE '%%(ts)'")[0][0] == 1


@pytest.mark.parametrize("bad_name", [
    'data"; x', "data'; x", "my table", "data-table", "1data", "data;x", "public.data", "data\n",
])
def test_pg_repack_table_argument_refuses_names_outside_plain_identifiers(bad_name):
    with pytest.raises(ValueError, match="data_table name"):
        PostgreSqlFuncts._validate_table_name_for_argv(bad_name)


@pytest.mark.parametrize("good_name", ["data", "_private", "sensor_data_2024", "Data"])
def test_pg_repack_table_argument_accepts_plain_identifiers(good_name):
    assert PostgreSqlFuncts._validate_table_name_for_argv(good_name) == good_name


_NAMED_TABLES = {
    "data_table": "data",
    "topics_table": "topics",
    "meta_table": "meta",
    "agg_topics_table": "aggregate_topics",
    "agg_meta_table": "aggregate_meta",
}


@pytest.mark.parametrize("bad_char", ["%", "\x00", "\n", "\x1f", "\x7f"])
@pytest.mark.parametrize("field", ["dbname"] + list(_NAMED_TABLES))
def test_configured_names_refuse_percent_and_control_characters(field, bad_char):
    params = {"dbname": "test_historian"}
    names = dict(_NAMED_TABLES)
    bad_name = f"odd{bad_char}name"
    if field == "dbname":
        params["dbname"] = bad_name
    else:
        names[field] = bad_name

    with pytest.raises(ValueError, match=field):
        PostgreSqlFuncts(params, names)


def test_configured_names_accept_plain_and_quoted_names():
    names = dict(_NAMED_TABLES, data_table=ODD_DATA_TABLE, topics_table=ODD_TOPICS_TABLE)
    functs = PostgreSqlFuncts({"dbname": "test_historian"}, names)
    assert functs.data_table == ODD_DATA_TABLE
    assert functs.topics_table == ODD_TOPICS_TABLE


def test_topic_value_cannot_reach_the_topics_table_name(live_db):
    conn, make_functs, drop_later = live_db
    # psycopg2 formats %(topic)s anywhere in the statement text, including
    # inside a quoted identifier, so this decoy would receive the insert.
    decoy = "odd_t'dev'"
    drop_later(decoy)
    _run(conn, SQL("CREATE TABLE {} (topic_id SERIAL PRIMARY KEY, topic_name VARCHAR(512))").format(
        Identifier(decoy)))

    error = None
    try:
        functs = make_functs("odd_data_t", topics_table="odd_t%(topic)s")
        functs.insert_topic("dev")
    except (ValueError, psycopg2.Error) as exc:
        error = exc
    assert _row_count(conn, decoy) == 0
    assert isinstance(error, ValueError)


def test_vacuum_advice_names_the_table_as_a_quoted_identifier(caplog):
    functs = PostgreSqlFuncts.__new__(PostgreSqlFuncts)
    functs.data_table = ODD_DATA_TABLE
    functs.delete_rows_by_chunks = lambda rows, chunk_size=5000: 0
    functs.execute_stmt = lambda *args, **kwargs: 0
    metrics = {"total_bytes": 2048, "reltuples": 2}

    with caplog.at_level(logging.WARNING, logger="volttron.platform.dbutils.postgresqlfuncts"):
        functs.delete_without_rebuild(metrics, 1024)

    assert "Run 'VACUUM FULL public.\"Odd\"\"Da'ta; --\";'" in caplog.text


def test_failed_rebuild_leaves_the_connection_usable(live_db, caplog):
    conn, make_functs, _ = live_db
    functs = make_functs("odd_hist_r")
    _create_data_table(conn, "odd_hist_r", rows=3)

    # An unparseable cutoff fails the copy inside the rebuild's transaction.
    with caplog.at_level(logging.WARNING, logger="volttron.platform.dbutils.postgresqlfuncts"):
        assert functs.manual_table_rebuild(keep_cutoff_timestamp="not a timestamp") is False

    assert functs.get_table_metrics(need_exact_count=True)["actual_count"] == 3
    assert not _table_exists(conn, "odd_hist_r_new")
    assert "already in place" not in caplog.text


def test_failed_rollback_after_a_failed_rebuild_is_logged(caplog):
    functs = PostgreSqlFuncts.__new__(PostgreSqlFuncts)
    functs.data_table = "odd_hist_s"
    functs.cleanup_temp_resources = lambda: None

    def execute_stmt(stmt, args=None, commit=False):
        if stmt in ("BEGIN", "ROLLBACK"):
            raise psycopg2.OperationalError(f"{stmt} refused")
        return 0

    functs.execute_stmt = execute_stmt

    with caplog.at_level(logging.ERROR, logger="volttron.platform.dbutils.postgresqlfuncts"):
        assert functs.manual_table_rebuild() is False

    assert "ROLLBACK refused" in caplog.text


def test_cleanup_logs_a_leftover_it_cannot_drop(live_db, caplog):
    conn, make_functs, drop_later = live_db
    functs = make_functs("odd_hist_t")
    drop_later("odd_hist_t_temp")
    _run(conn, "CREATE TABLE odd_hist_t_old (ts TIMESTAMP)")
    # DROP TABLE refuses a view, so this leftover name cannot be dropped.
    _run(conn, "CREATE VIEW odd_hist_t_new AS SELECT 1 AS x")
    try:
        with caplog.at_level(logging.WARNING, logger="volttron.platform.dbutils.postgresqlfuncts"):
            functs.cleanup_temp_resources()
    finally:
        _run(conn, "DROP VIEW IF EXISTS odd_hist_t_new")

    assert "Could not drop leftover table odd_hist_t_new" in caplog.text
    assert not _table_exists(conn, "odd_hist_t_old")


def test_cleanup_drops_only_the_derived_leftover_tables(live_db):
    conn, make_functs, drop_later = live_db
    drop_later("odd_cz_canary")
    _create_data_table(conn, "odd_cz_canary", rows=1)
    data_table = "odd_cz; DROP TABLE odd_cz_canary; --"
    functs = make_functs(data_table)
    _run(conn, SQL("CREATE TABLE {} (ts TIMESTAMP)").format(Identifier(f"{data_table}_old")))

    functs.cleanup_temp_resources()

    assert _table_exists(conn, "odd_cz_canary")
    assert not _table_exists(conn, f"{data_table}_old")


def _clipped(name, max_bytes):
    return name.encode()[:max_bytes].decode("utf-8", "ignore")


@pytest.mark.parametrize("length", [49, 50, 63])
def test_manual_table_rebuild_twice_with_long_table_names(live_db, length):
    conn, make_functs, _ = live_db
    data_table = "odd_long_" + "x" * (length - 9)
    functs = make_functs(data_table)
    _create_data_table(conn, data_table, rows=3)

    assert functs.manual_table_rebuild() is True
    assert functs.manual_table_rebuild() is True

    # PostgreSQL keeps 63 bytes of a name; the table part is shortened so the
    # suffix that tells the names apart survives.
    unique_key = _clipped(data_table, 63 - len("_topic_id_ts_key")) + "_topic_id_ts_key"
    assert _row_count(conn, data_table) == 3
    assert _index_names(conn, data_table) == {_clipped("idx_" + data_table, 63), unique_key}
    assert _unique_constraint_names(conn, data_table) == {unique_key}


def test_cooldown_reindexes_the_data_table_concurrently(live_db, caplog):
    conn, make_functs, _ = live_db
    functs = make_functs("odd_hist_cd")
    _create_data_table(conn, "odd_hist_cd", rows=3)
    _run(conn, "CREATE INDEX idx_odd_hist_cd ON odd_hist_cd (ts)")
    index_oids = "SELECT indexrelid FROM pg_index WHERE indrelid = 'odd_hist_cd'::regclass ORDER BY 1"
    before = _run(conn, index_oids)

    # Sizes chosen so the storage branch deletes rows and reaches the cooldown
    # check; row deletion and both rebuild paths are replaced.
    gb = 1024.0 ** 3
    functs.get_database_size_gb = lambda: 1.0
    functs.get_table_metrics = lambda need_exact_count=False: {
        "total_bytes": 100 * 1024 * 1024, "heap_bytes": 0, "idx_bytes": 0,
        "reltuples": 1000, "actual_count": None}
    functs.delete_rows_by_chunks = lambda rows, chunk_size=5000: rows

    def no_rebuild(*args, **kwargs):
        raise AssertionError("a heap rewrite ran during cooldown")

    functs.run_pg_repack = no_rebuild
    functs.manual_table_rebuild = no_rebuild
    functs._last_heap_rewrite_ts = datetime.datetime.now(datetime.timezone.utc)

    with caplog.at_level(logging.INFO, logger="volttron.platform.dbutils.postgresqlfuncts"):
        functs.manage_db_size(None, (gb - 60 * 1024 * 1024) / gb,
                              min_rows_floor=0, min_bytes_floor=0, cooldown_minutes=60)

    after = _run(conn, index_oids)
    assert "Reindexed indexes concurrently (cooldown mode)" in caplog.text
    assert len(before) == len(after) == 2
    assert not set(before) & set(after)


@pytest.mark.parametrize("names", [
    {"data_table": "p" * 59 + "_old"},
    {"data_table": "p" * 59 + "_new"},
    {"data_table": "p" * 58 + "_temp"},
    {"data_table": "p" * 59 + "_old" + "_tail"},
    {"data_table": "p5d", "topics_table": "p5d_old"},
    {"data_table": "p5d", "meta_table": "p5d_new"},
    {"data_table": "p5d", "agg_topics_table": "p5d_temp"},
    {"data_table": "p5d", "agg_meta_table": "p5d_old"},
])
def test_configuration_whose_leftover_names_match_a_table_is_refused(names):
    with pytest.raises(ValueError, match="leftover"):
        PostgreSqlFuncts({"dbname": "test_historian"}, dict(_NAMED_TABLES, **names))


def test_long_table_name_with_distinct_leftover_names_is_accepted():
    functs = PostgreSqlFuncts({"dbname": "test_historian"}, dict(_NAMED_TABLES, data_table="q" * 63))
    assert functs.data_table == "q" * 63


def test_cleanup_never_drops_the_data_table(live_db):
    conn, make_functs, drop_later = live_db
    data_table = "p" * 59 + "_old"
    drop_later(data_table)
    _create_data_table(conn, data_table, rows=3)

    error = None
    try:
        functs = make_functs(data_table)
        functs.cleanup_temp_resources()
    except ValueError as exc:
        error = exc
    assert _table_exists(conn, data_table)
    assert _row_count(conn, data_table) == 3
    assert isinstance(error, ValueError)


def test_reindex_without_rebuild_finds_indexes_of_an_odd_table(live_db):
    conn, make_functs, _ = live_db
    functs = make_functs(ODD_DATA_TABLE)
    _create_data_table(conn, ODD_DATA_TABLE, rows=2)
    assert functs.manual_table_rebuild() is True
    index_oids = ("SELECT i.indexrelid FROM pg_index i JOIN pg_class c ON c.oid = i.indrelid "
                  "WHERE c.relname = %s ORDER BY 1")
    before = _run(conn, index_oids, (ODD_DATA_TABLE,))

    metrics = functs.get_table_metrics()
    functs.delete_without_rebuild(metrics, metrics["total_bytes"])

    after = _run(conn, index_oids, (ODD_DATA_TABLE,))
    assert len(before) == len(after) == 2
    assert not set(before) & set(after)


def test_rebuild_names_shorten_multibyte_table_names_on_a_character_boundary(live_db):
    conn, make_functs, _ = live_db
    # 62 bytes; both index names must cut inside a two-byte character.
    data_table = "oo" + "\u00e9" * 30
    functs = make_functs(data_table)
    _create_data_table(conn, data_table, rows=2)

    assert functs.manual_table_rebuild() is True
    assert functs.manual_table_rebuild() is True

    unique_key = "oo" + "\u00e9" * 22 + "_topic_id_ts_key"
    ts_index = "idx_oo" + "\u00e9" * 28
    assert _index_names(conn, data_table) == {ts_index, unique_key}
    assert _row_count(conn, data_table) == 2
