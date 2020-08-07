import contextlib
import datetime
from time import time

import pytest
import mysql.connector

from volttron.platform.dbutils.mysqlfuncts import MySqlFuncts
from volttrontesting.fixtures.docker_wrapper import create_container
from volttrontesting.utils.utils import get_rand_port


# mysqlfuncts was written for MYSQL 5.7; however, the latest version is 8.0
# these tests cannot use latest or anything 8.0 and above and will fail if the latest image/8.0 is used
# for example, latest/8.0 will throw a "specified key was too long; max key length is 3072 bytes" error
IMAGES = ["mysql:5.7", ]  # To test more images, add them here
TEST_DATABASE = "test_historian"
ROOT_PASSWORD = "12345"
ENV_MYSQL = {"MYSQL_ROOT_PASSWORD": ROOT_PASSWORD, "MYSQL_DATABASE": TEST_DATABASE}
ALLOW_CONNECTION_TIME = 10
DATA_TABLE = "data"
TOPICS_TABLE = "topics"
META_TABLE = "meta"
AGG_TOPICS_TABLE = "p_aggregate_topics"
AGG_META_TABLE = "p_aggregate_meta"


@pytest.mark.mysqlfuncts
def test_setup_historian_tables_should_create_tables(get_container_func, ports_config):
    get_container, image = get_container_func
    with get_container(image, ports=ports_config["ports"], env=ENV_MYSQL) as container:
        wait_for_connection(container)

        port_on_host = ports_config["port_on_host"]
        with get_mysqlfuncts(port_on_host) as mysqlfuncts:
            tables = get_tables(port_on_host)
            assert tables == set()

            mysqlfuncts.setup_historian_tables()

            tables = get_tables(port_on_host)
            assert 'data' in tables
            assert 'topics' in tables
            assert 'meta' in tables


@pytest.mark.mysqlfuncts
def test_record_table_definitions_should_succeed(get_container_func, ports_config):
    get_container, image = get_container_func
    with get_container(image, ports=ports_config["ports"], env=ENV_MYSQL) as container:
        wait_for_connection(container)

        port_on_host = ports_config["port_on_host"]
        with get_mysqlfuncts(port_on_host) as mysqlfuncts:
            tables_def = {'table_prefix': "prefix",
                          'data_table': "data",
                          'topics_table': "topics",
                          'meta_table': "meta"}
            meta_table_name = 'meta_other'
            expected_data = {('data_table', "data", "prefix"),
                             ('topics_table', "topics", "prefix"),
                             ('meta_table', "meta", "prefix")}

            tables = get_tables(port_on_host)
            assert meta_table_name not in tables

            mysqlfuncts.record_table_definitions(tables_def, meta_table_name)

            tables = get_tables(port_on_host)
            assert meta_table_name in tables

            data = get_data_in_table(port_on_host, meta_table_name)
            for val in data:
                assert val in expected_data


@pytest.mark.mysqlfuncts
def test_setup_aggregate_historian_tables_should_succeed(get_container_func, ports_config):
    get_container, image = get_container_func
    with get_container(image, ports=ports_config["ports"], env=ENV_MYSQL) as container:
        wait_for_connection(container)
        create_historian_tables(container)
        create_metadata_table(container)

        port_on_host = ports_config["port_on_host"]
        with get_mysqlfuncts(port_on_host) as mysqlfuncts:
            tables = get_tables(port_on_host)
            assert AGG_TOPICS_TABLE not in tables
            assert AGG_META_TABLE not in tables

            mysqlfuncts.setup_aggregate_historian_tables('metadata')

            tables = get_tables(port_on_host)
            assert AGG_TOPICS_TABLE in tables
            assert AGG_META_TABLE in tables


@pytest.mark.mysqlfuncts
@pytest.mark.parametrize("topic_ids, id_name_map, expected_values",
                         [([42], {42: "topic42"}, {"topic42": []}),
                          ([43], {43: "topic43"}, {"topic43": [('2020-06-01T12:30:59.000000+00:00', [2,3])]})])
def test_query_should_return_data(get_container_func, ports_config, topic_ids, id_name_map, expected_values):
    get_container, image = get_container_func
    with get_container(image, ports=ports_config["ports"], env=ENV_MYSQL) as container:
        wait_for_connection(container)

        port_on_host = ports_config["port_on_host"]
        with get_mysqlfuncts(port_on_host) as mysqlfuncts:
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

            actual_values = mysqlfuncts.query(topic_ids, id_name_map)

            assert actual_values == expected_values


@pytest.mark.mysqlfuncts
def test_insert_meta_query_should_succeed(get_container_func, ports_config):
    get_container, image = get_container_func
    with get_container(image, ports=ports_config["ports"], env=ENV_MYSQL) as container:
        wait_for_connection(container)
        create_historian_tables(container)

        port_on_host = ports_config["port_on_host"]
        with get_mysqlfuncts(port_on_host) as mysqlfuncts:
            topic_id = "44"
            metadata = "foobar44"
            expected_data = (44, '"foobar44"')

            res = mysqlfuncts.insert_meta(topic_id, metadata)

            assert res is True
            assert get_data_in_table(port_on_host, 'meta')[0] == expected_data


@pytest.mark.mysqlfuncts
def test_insert_data_query_should_succeed(get_container_func, ports_config):
    get_container, image = get_container_func
    with get_container(image, ports=ports_config["ports"], env=ENV_MYSQL) as container:
        wait_for_connection(container)
        create_historian_tables(container)

        port_on_host = ports_config["port_on_host"]
        with get_mysqlfuncts(port_on_host) as mysqlfuncts:
            ts = '2001-09-11 08:46:00'
            topic_id = "11"
            data = "1wtc"
            expected_data = [(datetime.datetime(2001, 9, 11, 8, 46), 11, '"1wtc"')]

            res = mysqlfuncts.insert_data(ts, topic_id, data)

            assert res is True
            assert get_data_in_table(port_on_host, 'data') == expected_data


@pytest.mark.mysqlfuncts
def test_insert_topic_query_should_succeed(get_container_func, ports_config):
    get_container, image = get_container_func
    with get_container(image, ports=ports_config["ports"], env=ENV_MYSQL) as container:
        wait_for_connection(container)
        create_historian_tables(container)

        port_on_host = ports_config["port_on_host"]
        with get_mysqlfuncts(port_on_host) as mysqlfuncts:
            topic = "football"

            actual_id = mysqlfuncts.insert_topic(topic)

            assert isinstance(actual_id, int)
            assert (actual_id, 'football') == get_data_in_table(port_on_host, 'topics')[0]


@pytest.mark.mysqlfuncts
def test_update_topic_should_succeed(get_container_func, ports_config):
    get_container, image = get_container_func
    with get_container(image, ports=ports_config["ports"], env=ENV_MYSQL) as container:
        wait_for_connection(container)
        create_historian_tables(container)

        port_on_host = ports_config["port_on_host"]
        with get_mysqlfuncts(port_on_host) as mysqlfuncts:
            topic = "football"

            actual_id = mysqlfuncts.insert_topic(topic)

            assert isinstance(actual_id, int)

            result = mysqlfuncts.update_topic("soccer", actual_id)

            assert result is True
            assert (actual_id, 'soccer') == get_data_in_table(port_on_host, 'topics')[0]


@pytest.mark.mysqlfuncts
def test_insert_agg_topic_should_succeed(get_container_func, ports_config):
    get_container, image = get_container_func
    with get_container(image, ports=ports_config["ports"], env=ENV_MYSQL) as container:
        wait_for_connection(container)
        create_all_tables(container)

        port_on_host = ports_config["port_on_host"]
        with get_mysqlfuncts(port_on_host) as mysqlfuncts:
            topic = "some_agg_topic"
            agg_type = "AVG"
            agg_time_period = "2019"
            expected_data = (1, 'some_agg_topic', 'AVG', '2019')

            actual_id = mysqlfuncts.insert_agg_topic(topic, agg_type, agg_time_period)

            assert isinstance(actual_id, int)
            assert get_data_in_table(port_on_host, AGG_TOPICS_TABLE)[0] == expected_data


@pytest.mark.mysqlfuncts
def test_update_agg_topic_should_succeed(get_container_func, ports_config):
    get_container, image = get_container_func
    with get_container(image, ports=ports_config["ports"], env=ENV_MYSQL) as container:
        wait_for_connection(container)
        create_all_tables(container)

        port_on_host = ports_config["port_on_host"]
        with get_mysqlfuncts(port_on_host) as mysqlfuncts:
            topic = "cars"
            agg_type = "SUM"
            agg_time_period = "2100ZULU"
            expected_data = (1, 'cars', 'SUM', '2100ZULU')

            actual_id = mysqlfuncts.insert_agg_topic(topic, agg_type, agg_time_period)

            assert isinstance(actual_id, int)
            assert get_data_in_table(port_on_host, AGG_TOPICS_TABLE)[0] == expected_data

            new_agg_topic_name = "boats"
            expected_data = (1, 'boats', 'SUM', '2100ZULU')

            result = mysqlfuncts.update_agg_topic(actual_id, new_agg_topic_name)

            assert result is True
            assert get_data_in_table(port_on_host, AGG_TOPICS_TABLE)[0] == expected_data


@pytest.mark.mysqlfuncts
def test_insert_agg_meta_should_succeed(get_container_func, ports_config):
    get_container, image = get_container_func
    with get_container(image, ports=ports_config["ports"], env=ENV_MYSQL) as container:
        wait_for_connection(container)
        create_all_tables(container)

        port_on_host = ports_config["port_on_host"]
        with get_mysqlfuncts(port_on_host) as mysqlfuncts:

            topic_id = 42
            metadata = 'meaning of life'
            expected_data = (42, '"meaning of life"')

            result = mysqlfuncts.insert_agg_meta(topic_id, metadata)

            assert result is True
            assert get_data_in_table(port_on_host, AGG_META_TABLE)[0] == expected_data


@pytest.mark.mysqlfuncts
def test_get_topic_map_should_succeed(get_container_func, ports_config):
    get_container, image = get_container_func
    with get_container(image, ports=ports_config["ports"], env=ENV_MYSQL) as container:
        wait_for_connection(container)
        create_historian_tables(container)

        port_on_host = ports_config["port_on_host"]
        with get_mysqlfuncts(port_on_host) as mysqlfuncts:
            query = """
                       INSERT INTO topics (topic_name)
                       VALUES ('football');
                       INSERT INTO topics (topic_name)
                       VALUES ('baseball');                     
                    """
            seed_database(container, query)
            expected = ({'baseball': 2, 'football': 1}, {'baseball': 'baseball', 'football': 'football'})

            actual = mysqlfuncts.get_topic_map()

            assert actual == expected


@pytest.mark.mysqlfuncts
def test_get_agg_topic_map_should_return_dict(get_container_func, ports_config):
    get_container, image = get_container_func
    with get_container(image, ports=ports_config["ports"], env=ENV_MYSQL) as container:
        wait_for_connection(container)
        create_all_tables(container)

        port_on_host = ports_config["port_on_host"]
        with get_mysqlfuncts(port_on_host) as mysqlfuncts:
            query = f"""
                        INSERT INTO {AGG_TOPICS_TABLE}
                        (agg_topic_name, agg_type, agg_time_period)
                        VALUES ('topic_name', 'AVG', '2001');
                     """
            seed_database(container, query)
            expected = {('topic_name', 'AVG', '2001'): 1}

            actual = mysqlfuncts.get_agg_topic_map()

            assert actual == expected


@pytest.mark.mysqlfuncts
def test_query_topics_by_pattern_should_succeed(get_container_func, ports_config):
    get_container, image = get_container_func
    with get_container(image, ports=ports_config["ports"], env=ENV_MYSQL) as container:
        wait_for_connection(container)
        create_historian_tables(container)

        port_on_host = ports_config["port_on_host"]
        with get_mysqlfuncts(port_on_host) as mysqlfuncts:
            query = f"""
                       INSERT INTO {TOPICS_TABLE}  (topic_name)
                       VALUES ('football');
                       INSERT INTO {TOPICS_TABLE} (topic_name)
                       VALUES ('foobar');
                       INSERT INTO {TOPICS_TABLE} (topic_name)
                       VALUES ('xyzzzzzzzz');                     
                    """
            seed_database(container, query)
            expected = {'football': 1, 'foobar': 2}
            topic_pattern = "foo"

            actual = mysqlfuncts.query_topics_by_pattern(topic_pattern)

            assert actual == expected


@pytest.mark.mysqlfuncts
def test_create_aggregate_store_should_succeed(get_container_func, ports_config):
    get_container, image = get_container_func
    with get_container(image, ports=ports_config["ports"], env=ENV_MYSQL) as container:
        wait_for_connection(container)
        create_all_tables(container)

        port_on_host = ports_config["port_on_host"]
        with get_mysqlfuncts(port_on_host) as mysqlfuncts:
            agg_type = "AVG"
            agg_time_period = "1984"
            expected_aggregate_table = "AVG_1984"
            expected_fields = {'value_string', 'topics_list', 'topic_id', 'ts'}

            result = mysqlfuncts.create_aggregate_store(agg_type, agg_time_period)

            assert result is not None
            assert expected_aggregate_table in get_tables(port_on_host)
            assert describe_table(port_on_host, expected_aggregate_table) == expected_fields


@pytest.mark.mysqlfuncts
def test_insert_aggregate_stmt_should_succeed(get_container_func, ports_config):
    get_container, image = get_container_func
    with get_container(image, ports=ports_config["ports"], env=ENV_MYSQL) as container:
        wait_for_connection(container)
        create_all_tables(container)

        port_on_host = ports_config["port_on_host"]
        with get_mysqlfuncts(port_on_host) as mysqlfuncts:
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
            expected_data = (datetime.datetime(2020, 6, 1, 12, 30, 59), 42, '"some_data"', '[12, 54, 65]')

            res = mysqlfuncts.insert_aggregate(agg_topic_id, agg_type, period, ts, data, topic_ids)

            assert res is True
            assert get_data_in_table(port_on_host, "AVG_1776")[0] == expected_data


@pytest.mark.mysqlfuncts
def test_collect_aggregate_should_return_aggregate_result(get_container_func, ports_config):
    get_container, image = get_container_func
    with get_container(image, ports=ports_config["ports"], env=ENV_MYSQL) as container:
        wait_for_connection(container)
        create_all_tables(container)

        port_on_host = ports_config["port_on_host"]
        with get_mysqlfuncts(port_on_host) as mysqlfuncts:
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

            actual_aggregate = mysqlfuncts.collect_aggregate(topic_ids, agg_type)

            assert actual_aggregate == expected_aggregate


@pytest.mark.mysqlfuncts
def test_collect_aggregate_should_raise_value_error(get_container_func, ports_config):
    get_container, image = get_container_func
    with get_container(image, ports=ports_config["ports"], env=ENV_MYSQL) as container:
        wait_for_connection(container)

        with pytest.raises(ValueError):
            with get_mysqlfuncts(ports_config["port_on_host"]) as mysqlfuncts:
                mysqlfuncts.collect_aggregate("dfd", "Invalid agg type")


@contextlib.contextmanager
def get_mysqlfuncts(port):
    connect_params = {"host": 'localhost',
                      "port": port,
                      "database": TEST_DATABASE,
                      "user": "root",
                      "passwd": ROOT_PASSWORD}

    table_names = {"data_table": DATA_TABLE,
                   "topics_table": TOPICS_TABLE,
                   "meta_table": META_TABLE,
                   "agg_topics_table": AGG_TOPICS_TABLE,
                   "agg_meta_table": AGG_META_TABLE}

    mysqlfuncts = MySqlFuncts(connect_params, table_names)

    yield mysqlfuncts


@pytest.fixture(params=IMAGES)
def get_container_func(request):
    return create_container, request.param


@pytest.fixture()
def ports_config():
    port_on_host = get_rand_port(ip="3306")
    return {"port_on_host": port_on_host,
            "ports": {"3306/tcp": port_on_host}}


def wait_for_connection(container):
    start_time = time()
    response = None
    while time() - start_time < ALLOW_CONNECTION_TIME:
        command = (
            f"mysqlshow --user=\"root\" --password=\"{ROOT_PASSWORD}\" {TEST_DATABASE}"
        )
        response = container.exec_run(command, tty=True)
        exit_code, output = response

        if exit_code == 1 and "Can't connect to local MySQL server" in output.decode():
            continue
        elif exit_code == 0:
            return

    raise RuntimeError(f"Failed to make connection within allowed time {response}")



def create_historian_tables(container):
    query = """
               CREATE TABLE IF NOT EXISTS data
               (ts timestamp NOT NULL,
               topic_id INTEGER NOT NULL,
               value_string TEXT NOT NULL,
               UNIQUE(topic_id, ts));
               CREATE TABLE IF NOT EXISTS topics
               (topic_id INTEGER NOT NULL AUTO_INCREMENT,
               topic_name varchar(512) NOT NULL,
               PRIMARY KEY (topic_id),
               UNIQUE(topic_name));
               CREATE TABLE IF NOT EXISTS meta
               (topic_id INTEGER NOT NULL,
               metadata TEXT NOT NULL,
               PRIMARY KEY(topic_id));
            """
    command = f"mysql --user=\"root\" --password=\"{ROOT_PASSWORD}\" {TEST_DATABASE} --execute=\"{query}\""
    container.exec_run(cmd=command, tty=True)
    return


def create_metadata_table(container):
    query = """
               CREATE TABLE IF NOT EXISTS metadata
               (table_id varchar(512) PRIMARY KEY, 
               table_name varchar(512) NOT NULL, 
               table_prefix varchar(512));
               REPLACE INTO metadata
               VALUES ('data_table', 'data', 'p');
               REPLACE INTO metadata
               VALUES ('topics_table', 'topics', 'p');
               REPLACE INTO metadata
               VALUES ('meta_table', 'meta', 'p');
            """
    command = f"mysql --user=\"root\" --password=\"{ROOT_PASSWORD}\" {TEST_DATABASE} --execute=\"{query}\""
    container.exec_run(cmd=command, tty=True)
    return


def create_aggregate_tables(container):
    query = """
                CREATE TABLE IF NOT EXISTS p_aggregate_topics
                (agg_topic_id INTEGER NOT NULL AUTO_INCREMENT, 
                agg_topic_name varchar(512) NOT NULL, 
                agg_type varchar(512) NOT NULL, 
                agg_time_period varchar(512) NOT NULL, 
                PRIMARY KEY (agg_topic_id), 
                UNIQUE(agg_topic_name, agg_type, agg_time_period));
                CREATE TABLE IF NOT EXISTS p_aggregate_meta
                (agg_topic_id INTEGER NOT NULL, 
                metadata TEXT NOT NULL,
                PRIMARY KEY(agg_topic_id));
            """
    command = f"mysql --user=\"root\" --password=\"{ROOT_PASSWORD}\" {TEST_DATABASE} --execute=\"{query}\""
    container.exec_run(cmd=command, tty=True)
    return


def create_all_tables(container):
    create_historian_tables(container)
    create_metadata_table(container)
    create_aggregate_tables(container)
    return


def seed_database(container, query):
    command = f"mysql --user=\"root\" --password=\"{ROOT_PASSWORD}\" {TEST_DATABASE} --execute=\"{query}\""
    container.exec_run(cmd=command, tty=True)
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


def get_cnx_cursor(port):
    connect_params = {"host": 'localhost',
                      "port": port,
                      "database": TEST_DATABASE,
                      "user": "root",
                      "passwd": ROOT_PASSWORD}
    cnx = mysql.connector.connect(**connect_params)
    cursor = cnx.cursor()
    return cnx, cursor

