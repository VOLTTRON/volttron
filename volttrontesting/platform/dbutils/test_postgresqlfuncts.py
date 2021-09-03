import datetime
import itertools
import os
import logging
import pytest
from time import time


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
from volttrontesting.fixtures.docker_wrapper import create_container
from volttrontesting.utils.utils import get_rand_port

logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
pytestmark = [pytest.mark.postgresqlfuncts, pytest.mark.dbutils, pytest.mark.unit]


IMAGES = ["postgres:13"]
if "CI" in os.environ:
    IMAGES.extend(
        ["postgres:12", "postgres:11"]
    )

ALLOW_CONNECTION_TIME = 10
CONNECTION_HOST = "localhost"
TEST_DATABASE = "test_historian"
ROOT_USER = "postgres"
ROOT_PASSWORD = "password"
ENV_POSTGRESQL = {
    "POSTGRES_USER": ROOT_USER,  # defining user not necessary but added to be explicit
    "POSTGRES_PASSWORD": ROOT_PASSWORD,
    "POSTGRES_DB": TEST_DATABASE,
}
DATA_TABLE = "data"
TOPICS_TABLE = "topics"
META_TABLE = "meta"
AGG_TOPICS_TABLE = "aggregate_topics"
AGG_META_TABLE = "aggregate_meta"


def test_insert_meta_should_return_true(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func
    if historian_version != "<4.0.0":
        pytest.skip("insert_meta() is called by historian only for schema <4.0.0")
    topic_id = "44"
    metadata = "foobar44"
    expected_data = (44, '"foobar44"')

    res = sqlfuncts.insert_meta(topic_id, metadata)

    assert res is True
    assert get_data_in_table(connection_port, "meta")[0] == expected_data


def test_update_meta_should_succeed(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func
    metadata = {"units": "count"}
    metadata_s = jsonapi.dumps(metadata)
    topic = "foobar"

    id = sqlfuncts.insert_topic(topic)
    sqlfuncts.insert_meta(id, {"fdjlj": "XXXX"})
    assert metadata_s not in get_data_in_table(connection_port, TOPICS_TABLE)[0]

    res = sqlfuncts.update_meta(id, metadata)

    expected_lt_4 = [(1, metadata_s)]
    expected_gteq_4 = [(1, topic, metadata_s)]
    assert res is True
    if historian_version == "<4.0.0":
        assert get_data_in_table(connection_port, META_TABLE) == expected_lt_4
    else:
        assert get_data_in_table(connection_port, TOPICS_TABLE) == expected_gteq_4


def test_setup_historian_tables_should_create_tables(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func
    # get_container initializes db and sqlfuncts
    # to test setup explicitly drop tables and see if tables get created correctly
    drop_all_tables(connection_port)

    tables_before_setup = get_tables(connection_port)
    assert tables_before_setup == set()
    expected_tables = set(["data", "topics"])
    sqlfuncts.setup_historian_tables()
    actual_tables = get_tables(connection_port)
    assert actual_tables == expected_tables


def test_setup_aggregate_historian_tables_should_create_aggregate_tables(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func
    # get_container initializes db and sqlfuncts to test setup explicitly drop tables and see if tables get created
    drop_all_tables(connection_port)
    create_historian_tables(container, historian_version)
    agg_topic_table = "aggregate_topics"
    agg_meta_table = "aggregate_meta"

    original_tables = get_tables(connection_port)
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

    updated_tables = get_tables(connection_port)
    assert agg_topic_table in updated_tables
    assert agg_meta_table in updated_tables
    assert (
        describe_table(connection_port, agg_topic_table)
        == expected_agg_topic_fields
    )
    assert (
        describe_table(connection_port, agg_meta_table) == expected_agg_meta_fields
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
def test_query_should_return_data(get_container_func, topic_ids, id_name_map, expected_values):
    container, sqlfuncts, connection_port, historian_version = get_container_func

    query = f"""
                INSERT INTO {DATA_TABLE} VALUES ('2020-06-01 12:30:59', 43, '[2,3]')
            """
    seed_database(container, query)
    actual_values = sqlfuncts.query(topic_ids, id_name_map)
    assert actual_values == expected_values


def test_insert_topic_should_return_topic_id(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func

    topic = "football"
    expected_topic_id = 1
    actual_topic_id = sqlfuncts.insert_topic(topic)
    assert actual_topic_id == expected_topic_id


def test_insert_topic_and_meta_query_should_succeed(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func
    if historian_version == "<4.0.0":
        pytest.skip("Not relevant for historian schema before 4.0.0")
    topic = "football"
    metadata = {"units": "count"}
    actual_id = sqlfuncts.insert_topic(topic, metadata=metadata)

    assert isinstance(actual_id, int)
    result = get_data_in_table(connection_port, "topics")[0]
    assert (actual_id, topic) == result[0:2]
    assert metadata == jsonapi.loads(result[2])


def test_insert_agg_topic_should_return_agg_topic_id(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func

    topic = "some_agg_topic"
    agg_type = "AVG"
    agg_time_period = "2019"
    expected_data = (1, "some_agg_topic", "AVG", "2019")

    actual_id = sqlfuncts.insert_agg_topic(
        topic, agg_type, agg_time_period
    )

    assert isinstance(actual_id, int)
    assert get_data_in_table(connection_port, AGG_TOPICS_TABLE)[0] == expected_data


def test_insert_data_should_return_true(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func

    ts = "2001-09-11 08:46:00"
    topic_id = "11"
    data = "1wtc"
    expected_data = [(datetime.datetime(2001, 9, 11, 8, 46), 11, '"1wtc"')]

    res = sqlfuncts.insert_data(ts, topic_id, data)

    assert res is True
    assert get_data_in_table(connection_port, "data") == expected_data


def test_update_topic_should_return_true(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func

    topic = "football"
    actual_id = sqlfuncts.insert_topic(topic)
    assert isinstance(actual_id, int)

    result = sqlfuncts.update_topic("soccer", actual_id)
    assert result is True
    assert (actual_id, "soccer") == get_data_in_table(connection_port, "topics")[0][0:2]


def test_update_topic_and_metadata_should_succeed(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func
    if historian_version == "<4.0.0":
        pytest.skip("Not relevant for historian schema before 4.0.0")
    topic = "football"
    actual_id = sqlfuncts.insert_topic(topic)

    assert isinstance(actual_id, int)

    result = sqlfuncts.update_topic("soccer", actual_id, metadata={"test": "test value"})

    assert result is True
    assert (actual_id, "soccer", '{"test": "test value"}') == get_data_in_table(connection_port, "topics")[0]



def test_get_aggregation_list_should_return_list(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func

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


def test_insert_agg_topic_should_return_true(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func

    topic = "some_agg_topic"
    agg_type = "AVG"
    agg_time_period = "2019"
    expected_data = (1, "some_agg_topic", "AVG", "2019")

    actual_id = sqlfuncts.insert_agg_topic(
        topic, agg_type, agg_time_period
    )

    assert isinstance(actual_id, int)
    assert get_data_in_table(connection_port, AGG_TOPICS_TABLE)[0] == expected_data


def test_update_agg_topic_should_return_true(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func

    topic = "cars"
    agg_type = "SUM"
    agg_time_period = "2100ZULU"
    expected_data = (1, "cars", "SUM", "2100ZULU")

    actual_id = sqlfuncts.insert_agg_topic(
        topic, agg_type, agg_time_period
    )

    assert isinstance(actual_id, int)
    assert get_data_in_table(connection_port, AGG_TOPICS_TABLE)[0] == expected_data

    new_agg_topic_name = "boats"
    expected_data = (1, "boats", "SUM", "2100ZULU")

    result = sqlfuncts.update_agg_topic(actual_id, new_agg_topic_name)

    assert result is True
    assert get_data_in_table(connection_port, AGG_TOPICS_TABLE)[0] == expected_data


def test_insert_agg_meta_should_return_true(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func

    topic_id = 42
    # metadata must be in the following convention because aggregation methods, i.e. get_agg_topics, rely on metadata having a key called "configured_topics"
    metadata = {"configured_topics": "meaning of life"}
    expected_data = (42, '{"configured_topics": "meaning of life"}')

    result = sqlfuncts.insert_agg_meta(topic_id, metadata)

    assert result is True
    assert get_data_in_table(connection_port, AGG_META_TABLE)[0] == expected_data


def test_get_topic_map_should_return_maps(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func

    query = """
               INSERT INTO topics (topic_name)
               VALUES ('football');
               INSERT INTO topics (topic_name)
               VALUES ('baseball');
            """
    seed_database(container, query)
    expected = (
        {"baseball": 2, "football": 1},
        {"baseball": "baseball", "football": "football"},
    )

    actual = sqlfuncts.get_topic_map()

    assert actual == expected


def test_get_agg_topics_should_return_list(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func

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


def test_get_agg_topic_map_should_return_dict(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func

    query = f"""
               INSERT INTO {AGG_TOPICS_TABLE}
               (agg_topic_name, agg_type, agg_time_period)
               VALUES ('topic_name', 'AVG', '2001');
            """
    seed_database(container, query)
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
    get_container_func,
    topic_1,
    topic_2,
    topic_3,
    topic_pattern,
    expected_result
):
    container, sqlfuncts, connection_port, historian_version = get_container_func

    query = f"""
               INSERT INTO {TOPICS_TABLE}  (topic_name)
               VALUES ({topic_1});
               INSERT INTO {TOPICS_TABLE} (topic_name)
               VALUES ({topic_2});
               INSERT INTO {TOPICS_TABLE} (topic_name)
               VALUES ({topic_3});
            """
    seed_database(container, query)

    actual_result = sqlfuncts.query_topics_by_pattern(topic_pattern)
    assert actual_result == expected_result


def test_create_aggregate_store_should_succeed(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func

    agg_type = "AVG"
    agg_time_period = "1984"
    expected_aggregate_table = "AVG_1984"
    expected_fields = {"topics_list", "agg_value", "topic_id", "ts"}

    sqlfuncts.create_aggregate_store(agg_type, agg_time_period)

    assert expected_aggregate_table in get_tables(connection_port)
    assert describe_table(connection_port, expected_aggregate_table) == expected_fields


def test_insert_aggregate_stmt_should_succeed(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func

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
    seed_database(container, query)

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
    assert get_data_in_table(connection_port, "avg_1776")[0] == expected_data


def test_collect_aggregate_stmt_should_return_rows(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func

    query = f"""
                INSERT INTO {DATA_TABLE}
                VALUES ('2020-06-01 12:30:59', 42, '2');
                INSERT INTO {DATA_TABLE}
                VALUES ('2020-06-01 12:31:59', 43, '8')
            """
    seed_database(container, query)

    topic_ids = [42, 43]
    agg_type = "avg"
    expected_aggregate = (5.0, 2)

    actual_aggregate = sqlfuncts.collect_aggregate(topic_ids, agg_type)

    assert actual_aggregate == expected_aggregate


def test_collect_aggregate_stmt_should_raise_value_error(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func

    with pytest.raises(ValueError):
            sqlfuncts.collect_aggregate("dfdfadfdadf", "Invalid agg type")


def get_postgresqlfuncts(port):
    connect_params = {
        "dbname": TEST_DATABASE,
        "user": ROOT_USER,
        "password": ROOT_PASSWORD,
        "host": "localhost",
        "port": port,
    }

    table_names = {
        "data_table": DATA_TABLE,
        "topics_table": TOPICS_TABLE,
        "meta_table": META_TABLE,
        "agg_topics_table": AGG_TOPICS_TABLE,
        "agg_meta_table": AGG_META_TABLE,
    }

    return PostgreSqlFuncts(connect_params, table_names)


@pytest.fixture(scope="module", params=itertools.product(
    IMAGES,
    [
     '<4.0.0',
     '>=4.0.0'
     ]))
def get_container_func(request):
    global CONNECTION_HOST
    historian_version = request.param[1]
    kwargs = {'env': ENV_POSTGRESQL}
    if os.path.exists("/.dockerenv"):
        print("Running test within docker container.")
        connection_port = 5432
        CONNECTION_HOST = 'postgresql_test'
        kwargs['hostname'] = CONNECTION_HOST
    else:
        ports_dict = ports_config()
        kwargs['ports'] = ports_dict["ports"]
        connection_port = ports_dict["port_on_host"]
        CONNECTION_HOST = 'localhost'

    with create_container(request.param[0], **kwargs) as container:
        wait_for_connection(container, connection_port)
        create_all_tables(container, historian_version)
        postgresfuncts = get_postgresqlfuncts(connection_port)
        postgresfuncts.setup_historian_tables()
        yield container, postgresfuncts, connection_port, historian_version


def ports_config():
    port_on_host = get_rand_port(ip="5432")
    return {"port_on_host": port_on_host, "ports": {"5432/tcp": port_on_host}}


def create_all_tables(container, historian_version):
    create_historian_tables(container, historian_version)
    create_aggregate_tables(container, historian_version)


def create_historian_tables(container, historian_version):
    if historian_version == "<4.0.0":
        query = f"""
                    CREATE TABLE IF NOT EXISTS {DATA_TABLE} (
                    ts TIMESTAMP NOT NULL,
                    topic_id INTEGER NOT NULL,
                    value_string TEXT NOT NULL,
                    UNIQUE (topic_id, ts));
                    CREATE TABLE IF NOT EXISTS {TOPICS_TABLE} (
                    topic_id SERIAL PRIMARY KEY NOT NULL,
                    topic_name VARCHAR(512) NOT NULL,
                    UNIQUE (topic_name));
                    CREATE TABLE IF NOT EXISTS {META_TABLE} (
                    topic_id INTEGER PRIMARY KEY NOT NULL,
                    metadata TEXT NOT NULL);
                """
    else:
        query = f"""
                    CREATE TABLE IF NOT EXISTS {DATA_TABLE} (
                    ts TIMESTAMP NOT NULL,
                    topic_id INTEGER NOT NULL,
                    value_string TEXT NOT NULL,
                    UNIQUE (topic_id, ts));
                    CREATE TABLE IF NOT EXISTS {TOPICS_TABLE} (
                    topic_id SERIAL PRIMARY KEY NOT NULL,
                    topic_name VARCHAR(512) NOT NULL,
                    metadata TEXT,
                    UNIQUE (topic_name));
                """
    seed_database(container, query)
    return


def create_aggregate_tables(container, historian_version):
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
    seed_database(container, query)
    return


def seed_database(container, query):
    command = (
        f'psql --username="{ROOT_USER}" --dbname="{TEST_DATABASE}" --command="{query}"'
    )
    r = container.exec_run(cmd=command, tty=True)
    print(r)
    if r[0] == 1:
        raise RuntimeError(
            f"SQL query did not successfully complete on the container: \n {r}"
        )
    return


def get_tables(port):
    cnx, cursor = get_cnx_cursor(port)
    # unlike MYSQL, Postgresql does not have a "SHOW TABLES" shortcut
    # we have to create the query ourselves
    query = SQL(
        "SELECT table_name "
        "FROM information_schema.tables "
        "WHERE table_type = 'BASE TABLE' and "
        "table_schema not in ('pg_catalog', 'information_schema')"
    )
    results = execute_statement(cnx, cursor, query)

    return {t[0] for t in results}


def describe_table(port, table):
    cnx, cursor = get_cnx_cursor(port)
    query = SQL(
        "SELECT column_name " "FROM information_schema.columns " "WHERE table_name = %s"
    )

    results = execute_statement(cnx, cursor, query, args=[table])

    return {t[0] for t in results}


def get_data_in_table(port, table):
    cnx, cursor = get_cnx_cursor(port)
    query = SQL("SELECT * " "FROM {table_name}").format(table_name=Identifier(table))

    results = execute_statement(cnx, cursor, query)

    return results


def execute_statement(cnx, cursor, query, args=None):
    cursor.execute(query, vars=args)

    results = cursor.fetchall()

    cursor.close()
    cnx.close()

    return results


def get_cnx_cursor(port):
    connect_params = {
        "database": TEST_DATABASE,
        "user": ROOT_USER,
        "password": ROOT_PASSWORD,
        "host": "localhost",
        "port": port,
    }

    cnx = psycopg2.connect(**connect_params)
    cursor = cnx.cursor()

    return cnx, cursor


def wait_for_connection(container, port):
    start_time = time()
    while time() - start_time < ALLOW_CONNECTION_TIME:
        command = f"psql --user={ROOT_USER} --dbname={TEST_DATABASE} --port={port}"
        response = container.exec_run(command, tty=True)
        # https://www.postgresql.org/docs/10/app-psql.html#id-1.9.4.18.7
        # psql returns 0 to the shell if it finished normally,
        # 1 if a fatal error of its own occurs (e.g. out of memory, file not found),
        # 2 if the connection to the server went bad and the session was not interactive,
        # and 3 if an error occurred in a script and the variable ON_ERROR_STOP was set.
        exit_code = response[0]

        if exit_code == 0:
            return
        elif exit_code == 1:
            raise RuntimeError(response)
        elif exit_code == 2:
            continue
        elif exit_code == 3:
            raise RuntimeError(response)

    # if we break out of the loop, we assume that connection has been verified given enough sleep time
    return


def drop_all_tables(port):
    tables = get_tables(port)
    cnx, cursor = get_cnx_cursor(port)
    try:
        for t in tables:
            cursor.execute(SQL(f'DROP TABLE {t}'))
        cnx.commit()
    except Exception as e:
        print("Error deleting tables {}".format(e))
    finally:
        if cursor:
            cursor.close()


@pytest.fixture(autouse=True)
def cleanup_tables(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func
    drop_all_tables(connection_port)
    create_all_tables(container, historian_version)
