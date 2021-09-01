import datetime
import itertools
import os
import logging
import pytest
from time import time, sleep

try:
    import mysql.connector
except ImportError:
    pytest.skip(
        "Required imports for testing are not installed; thus, not running tests. "
        "Install imports with: python bootstrap.py --mysql",
        allow_module_level=True
    )
from volttron.platform import jsonapi
from volttron.platform.dbutils.mysqlfuncts import MySqlFuncts
from volttrontesting.fixtures.docker_wrapper import create_container
from volttrontesting.utils.utils import get_rand_port

logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
pytestmark = [pytest.mark.mysqlfuncts, pytest.mark.dbutils, pytest.mark.unit]


IMAGES = [
    "mysql:8.0",
    "mysql:5.7.35",
    "mysql:5.6"
]

CONNECTION_HOST = "localhost"
TEST_DATABASE = "test_historian"
ROOT_PASSWORD = "12345"
ENV_MYSQL = {"MYSQL_ROOT_PASSWORD": ROOT_PASSWORD, "MYSQL_DATABASE": TEST_DATABASE}
ALLOW_CONNECTION_TIME = 50
DATA_TABLE = "data"
TOPICS_TABLE = "topics"
META_TABLE = "meta"
AGG_TOPICS_TABLE = "aggregate_topics"
AGG_META_TABLE = "aggregate_meta"


def test_update_meta_should_succeed(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func
    id = sqlfuncts.insert_topic("foobar")

    if historian_version == "<4.0.0":
        sqlfuncts.insert_meta(id, {"fdjlj": "XXXX"})

    assert sqlfuncts.update_meta(id, {"units": "count"})

    if historian_version == "<4.0.0":
        data = get_data_in_table(connection_port, META_TABLE)
        assert data == [(1, '{"units": "count"}')]
    else:
        data = get_data_in_table(connection_port, TOPICS_TABLE)
        assert data == [(1, "foobar", '{"units": "count"}')]


def test_setup_historian_tables_should_create_tables(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func
    if historian_version == "<4.0.0":
        pytest.skip("sqlfuncts will not create db with schema <4.0.0")
    # get_container initializes db and sqlfuncts
    # to test setup explicitly drop tables and see if tables get created correctly
    drop_all_tables(connection_port)

    sqlfuncts.setup_historian_tables()
    tables = get_tables(connection_port)
    assert "data" in tables
    assert "topics" in tables


def test_setup_aggregate_historian_tables_should_succeed(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func

    # get_container initializes db and sqlfuncts to test setup explicitly drop tables and see if tables get created
    drop_all_tables(connection_port)

    create_historian_tables(container, historian_version)
    sqlfuncts.setup_aggregate_historian_tables()

    tables = get_tables(connection_port)
    assert AGG_TOPICS_TABLE in tables
    assert AGG_META_TABLE in tables


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
               CREATE TABLE IF NOT EXISTS {DATA_TABLE}
               (ts timestamp NOT NULL,
               topic_id INTEGER NOT NULL,
               value_string TEXT NOT NULL,
               UNIQUE(topic_id, ts));
               REPLACE INTO {DATA_TABLE}
               VALUES ('2020-06-01 12:30:59', 43, '[2,3]')                     
            """
    seed_database(container, query)
    actual_values = sqlfuncts.query(topic_ids, id_name_map)
    assert actual_values == expected_values


def test_insert_meta_query_should_succeed(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func

    if historian_version != "<4.0.0":
        pytest.skip("insert_meta() is called by historian only for schema <4.0.0")

    topic_id = "44"
    metadata = "foobar44"
    expected_data = (44, '"foobar44"')
    res = sqlfuncts.insert_meta(topic_id, metadata)
    assert res is True
    assert get_data_in_table(connection_port, "meta")[0] == expected_data


def test_insert_data_query_should_succeed(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func
    ts = "2001-09-11 08:46:00"
    topic_id = "11"
    data = "1wtc"
    expected_data = [(datetime.datetime(2001, 9, 11, 8, 46), 11, '"1wtc"')]
    res = sqlfuncts.insert_data(ts, topic_id, data)

    assert res is True
    assert get_data_in_table(connection_port, "data") == expected_data


def test_insert_topic_query_should_succeed(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func
    topic = "football"
    actual_id = sqlfuncts.insert_topic(topic)

    assert isinstance(actual_id, int)
    assert (actual_id, "football") == get_data_in_table(connection_port, "topics")[0][
        0:2
    ]


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


def test_update_topic_should_succeed(get_container_func):
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

    result = sqlfuncts.update_topic(
        "soccer", actual_id, metadata={"test": "test value"}
    )

    assert result is True
    assert (actual_id, "soccer", '{"test": "test value"}') == \
           get_data_in_table(connection_port, "topics")[0]


def test_insert_agg_topic_should_succeed(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func
    topic = "some_agg_topic"
    agg_type = "AVG"
    agg_time_period = "2019"
    expected_data = (1, "some_agg_topic", "AVG", "2019")
    actual_id = sqlfuncts.insert_agg_topic(topic, agg_type, agg_time_period)

    assert isinstance(actual_id, int)
    assert get_data_in_table(connection_port, AGG_TOPICS_TABLE)[0] == expected_data


# fails for mysql:8.0.25 historian schema version >=4.0.0
def test_update_agg_topic_should_succeed(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func

    topic = "cars"
    agg_type = "SUM"
    agg_time_period = "2100ZULU"
    expected_data = (1, "cars", "SUM", "2100ZULU")
    print(f" db tables: {get_tables(connection_port)}")
    actual_id = sqlfuncts.insert_agg_topic(topic, agg_type, agg_time_period)

    assert isinstance(actual_id, int)
    assert get_data_in_table(connection_port, AGG_TOPICS_TABLE)[0] == expected_data

    new_agg_topic_name = "boats"
    expected_data = (1, "boats", "SUM", "2100ZULU")

    result = sqlfuncts.update_agg_topic(actual_id, new_agg_topic_name)

    assert result is True
    assert get_data_in_table(connection_port, AGG_TOPICS_TABLE)[0] == expected_data


# fails for image:mysql:8.0.25 historian schema version >=4.0.0
def test_insert_agg_meta_should_succeed(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func

    topic_id = 42
    metadata = "meaning of life"
    expected_data = (42, '"meaning of life"')

    sleep(5)
    result = sqlfuncts.insert_agg_meta(topic_id, metadata)

    assert result is True
    assert get_data_in_table(connection_port, AGG_META_TABLE)[0] == expected_data


def test_get_topic_map_should_succeed(get_container_func):
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


# fails for image:mysql:8.0.25 historian schema version >=4.0.0
def test_get_agg_topic_map_should_return_dict(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func
    query = f"""
                INSERT INTO {AGG_TOPICS_TABLE}
                (agg_topic_name, agg_type, agg_time_period)
                VALUES ('topic_name', 'AVG', '2001');
             """
    seed_database(container, query)
    expected = {("topic_name", "AVG", "2001"): 1}

    sleep(5)
    actual = sqlfuncts.get_agg_topic_map()

    assert actual == expected


def test_query_topics_by_pattern_should_succeed(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func
    query = f"""
               INSERT INTO {TOPICS_TABLE}  (topic_name)
               VALUES ('football');
               INSERT INTO {TOPICS_TABLE} (topic_name)
               VALUES ('foobar');
               INSERT INTO {TOPICS_TABLE} (topic_name)
               VALUES ('xyzzzzzzzz');                     
            """
    seed_database(container, query)
    expected = {"football": 1, "foobar": 2}
    topic_pattern = "foo"

    actual = sqlfuncts.query_topics_by_pattern(topic_pattern)

    assert actual == expected


def test_create_aggregate_store_should_succeed(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func

    agg_type = "AVG"
    agg_time_period = "1984"
    expected_aggregate_table = "AVG_1984"
    expected_fields = {"agg_value", "topics_list", "topic_id", "ts"}

    result = sqlfuncts.create_aggregate_store(agg_type, agg_time_period)

    assert result is not None
    assert expected_aggregate_table in get_tables(connection_port)
    assert describe_table(connection_port, expected_aggregate_table) == expected_fields


def test_insert_aggregate_stmt_should_succeed(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func
    query = """
                CREATE TABLE IF NOT EXISTS AVG_1776
                (ts timestamp NOT NULL, topic_id INTEGER NOT NULL, 
                value_string TEXT NOT NULL, topics_list TEXT, 
                UNIQUE(topic_id, ts), INDEX (ts ASC))
            """
    seed_database(container, query)

    agg_topic_id = 42
    agg_type = "AVG"
    period = "1776"
    ts = "2020-06-01 12:30:59"
    data = "some_data"
    topic_ids = [12, 54, 65]
    expected_data = (
        datetime.datetime(2020, 6, 1, 12, 30, 59),
        42,
        "some_data",
        "[12, 54, 65]",
    )

    res = sqlfuncts.insert_aggregate(
        agg_topic_id, agg_type, period, ts, data, topic_ids
    )

    assert res is True
    assert get_data_in_table(connection_port, "AVG_1776")[0] == expected_data


def test_collect_aggregate_should_return_aggregate_result(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func
    query = f"""
                REPLACE INTO {DATA_TABLE}
                VALUES ('2020-06-01 12:30:59', 42, '2');
                REPLACE INTO {DATA_TABLE}
                VALUES ('2020-06-01 12:31:59', 43, '8')
            """
    seed_database(container, query)

    topic_ids = [42, 43]
    agg_type = "avg"
    expected_aggregate = (5.0, 2)

    actual_aggregate = sqlfuncts.collect_aggregate(topic_ids, agg_type)

    assert actual_aggregate == expected_aggregate


def test_collect_aggregate_should_raise_value_error(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func
    with pytest.raises(ValueError):
        sqlfuncts.collect_aggregate("dfd", "Invalid agg type")


def get_mysqlfuncts(port):
    connect_params = {
        "host": CONNECTION_HOST,
        "port": port,
        "database": TEST_DATABASE,
        "user": "root",
        "passwd": ROOT_PASSWORD,
        "connection_timeout": ALLOW_CONNECTION_TIME,
    }

    table_names = {
        "data_table": DATA_TABLE,
        "topics_table": TOPICS_TABLE,
        "meta_table": META_TABLE,
        "agg_topics_table": AGG_TOPICS_TABLE,
        "agg_meta_table": AGG_META_TABLE,
    }

    return MySqlFuncts(connect_params, table_names)


@pytest.fixture(scope="module", params=itertools.product(IMAGES, ["<4.0.0", ">=4.0.0"]))
def get_container_func(request):
    global CONNECTION_HOST
    image, historian_version = request.param
    print(f"image: {image} historian schema; version {historian_version}")
    if historian_version == "<4.0.0" and image.startswith("mysql:8"):
        pytest.skip(
            msg=f"Default schema of historian version <4.0.0 "
            f"will not work in mysql version > 5. Skipping tests "
            f"for this parameter combination ",
            allow_module_level=True,
        )
    kwargs = {"env": ENV_MYSQL}
    if os.path.exists("/.dockerenv"):
        print("Running test within docker container.")
        connection_port = 3306
        CONNECTION_HOST = "mysql_test"
        kwargs["hostname"] = CONNECTION_HOST
    else:
        ports_dict = ports_config()
        kwargs["ports"] = ports_dict["ports"]
        connection_port = ports_dict["port_on_host"]
        CONNECTION_HOST = "localhost"

    with create_container(request.param[0], **kwargs) as container:
        wait_for_connection(container)
        create_all_tables(container, historian_version)

        mysqlfuncts = get_mysqlfuncts(connection_port)
        sleep(5)
        # So that sqlfuncts class can check if metadata is in topics table and sets its variables accordingly
        mysqlfuncts.setup_historian_tables()
        yield container, mysqlfuncts, connection_port, historian_version


def ports_config():
    port_on_host = get_rand_port(ip="3306")
    return {"port_on_host": port_on_host, "ports": {"3306/tcp": port_on_host}}


def wait_for_connection(container):
    start_time = time()
    response = None
    while time() - start_time < ALLOW_CONNECTION_TIME:
        command = (
            f'mysqlshow --user="root" --password="{ROOT_PASSWORD}" {TEST_DATABASE}'
        )
        response = container.exec_run(command, tty=True)
        exit_code, output = response

        if exit_code == 1 and "Can't connect to local MySQL server" in output.decode():
            continue
        elif exit_code == 0:
            return

    raise RuntimeError(f"Failed to make connection within allowed time {response}")


def create_historian_tables(container, historian_version):
    if historian_version == "<4.0.0":
        query = f"""
                   CREATE TABLE IF NOT EXISTS {DATA_TABLE}
                   (ts timestamp NOT NULL,
                   topic_id INTEGER NOT NULL,
                   value_string TEXT NOT NULL,
                   UNIQUE(topic_id, ts));
                   CREATE TABLE IF NOT EXISTS {TOPICS_TABLE}
                   (topic_id INTEGER NOT NULL AUTO_INCREMENT,
                   topic_name varchar(512) NOT NULL,
                   PRIMARY KEY (topic_id),
                   UNIQUE(topic_name));
                   CREATE TABLE IF NOT EXISTS {META_TABLE}
                   (topic_id INTEGER NOT NULL,
                   metadata TEXT NOT NULL,
                   PRIMARY KEY(topic_id));
            """
    else:
        query = f"""
                   CREATE TABLE IF NOT EXISTS {DATA_TABLE}
                   (ts timestamp NOT NULL,
                   topic_id INTEGER NOT NULL,
                   value_string TEXT NOT NULL,
                   UNIQUE(topic_id, ts));
                   CREATE TABLE IF NOT EXISTS {TOPICS_TABLE}
                   (topic_id INTEGER NOT NULL AUTO_INCREMENT,
                   topic_name varchar(512) NOT NULL,
                    metadata TEXT,
                   PRIMARY KEY (topic_id),
                   UNIQUE(topic_name));
            """

    command = f'mysql --user="root" --password="{ROOT_PASSWORD}" {TEST_DATABASE} --execute="{query}"'
    container.exec_run(cmd=command, tty=True)
    return


def create_aggregate_tables(container, historian_version):
    if historian_version == "<4.0.0":
        query = f"""
                    CREATE TABLE IF NOT EXISTS {AGG_TOPICS_TABLE}
                    (agg_topic_id INTEGER NOT NULL AUTO_INCREMENT, 
                    agg_topic_name varchar(512) NOT NULL, 
                    agg_type varchar(512) NOT NULL, 
                    agg_time_period varchar(512) NOT NULL, 
                    PRIMARY KEY (agg_topic_id), 
                    UNIQUE(agg_topic_name, agg_type, agg_time_period));
                    CREATE TABLE IF NOT EXISTS {AGG_META_TABLE}
                    (agg_topic_id INTEGER NOT NULL, 
                    metadata TEXT NOT NULL,
                    PRIMARY KEY(agg_topic_id));
                """
    else:
        query = f"""
                    CREATE TABLE IF NOT EXISTS {AGG_TOPICS_TABLE}
                    (agg_topic_id INTEGER NOT NULL AUTO_INCREMENT, 
                    agg_topic_name varchar(512) NOT NULL, 
                    agg_type varchar(20) NOT NULL, 
                    agg_time_period varchar(20) NOT NULL, 
                    PRIMARY KEY (agg_topic_id), 
                    UNIQUE(agg_topic_name, agg_type, agg_time_period));
                    CREATE TABLE IF NOT EXISTS {AGG_META_TABLE}
                    (agg_topic_id INTEGER NOT NULL, 
                    metadata TEXT NOT NULL,
                    PRIMARY KEY(agg_topic_id));
                """
    command = f'mysql --user="root" --password="{ROOT_PASSWORD}" {TEST_DATABASE} --execute="{query}"'
    container.exec_run(cmd=command, tty=True)
    return


def create_all_tables(container, historian_version):
    create_historian_tables(container, historian_version)
    create_aggregate_tables(container, historian_version)
    return


def seed_database(container, query):
    command = f'mysql --user="root" --password="{ROOT_PASSWORD}" {TEST_DATABASE} --execute="{query}"'
    container.exec_run(cmd=command, tty=True)
    sleep(3)
    return


def get_tables(port):
    """
    :param port:
    :return: a list in the following convention
    """
    cnx, cursor = get_cnx_cursor(port)
    cursor.execute("SHOW TABLES")

    results = cursor.fetchall()

    cursor.close()
    cnx.close()

    return {t[0] for t in results}


def describe_table(port, table):
    """
    :param port:
    :param table:
    :return: a list of tuples in the following convention
             For example:
             [ (<field name>, <type>, <null?>, <key>, <default>, <extra>) ]
    """
    cnx, cursor = get_cnx_cursor(port)
    cursor.execute(f"DESCRIBE {table}")

    results = cursor.fetchall()

    cursor.close()
    cnx.close()

    return {t[0] for t in results}


def get_data_in_table(port, table):
    """
    :param port:
    :param table:
    :return: list of tuples containing all the data for each row in the table
    """
    cnx, cursor = get_cnx_cursor(port)
    cursor.execute(f"SELECT * FROM {table}")

    results = cursor.fetchall()

    cursor.close()
    cnx.close()

    return results


def drop_all_tables(port):
    """
    :param port:

    """
    cnx, cursor = get_cnx_cursor(port)
    query = f"SHOW TABLES"
    print(f"query {query}")
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        print(f"table names {rows}")
        for columns in rows:
            cursor.execute("DROP TABLE " + columns[0])
    except Exception as e:
        print("Error deleting tables {}".format(e))
    finally:
        if cursor:
            cursor.close()


def get_cnx_cursor(port):
    global CONNECTION_HOST
    connect_params = {
        "host": CONNECTION_HOST,
        "port": port,
        "database": TEST_DATABASE,
        "user": "root",
        "passwd": ROOT_PASSWORD,
        "auth_plugin": "mysql_native_password",
        "autocommit": True,
    }
    cnx = mysql.connector.connect(**connect_params)
    cursor = cnx.cursor()
    return cnx, cursor


@pytest.fixture(autouse=True)
def cleanup_tables(get_container_func):
    container, sqlfuncts, connection_port, historian_version = get_container_func
    drop_all_tables(connection_port)
    create_all_tables(container, historian_version)
