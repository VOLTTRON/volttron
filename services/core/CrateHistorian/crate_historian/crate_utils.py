import logging


def select_all_topics_query(schema):
    return "SELECT topic FROM {schema}.topic".format(schema=schema)


def insert_topic_query(schema):
    return "INSERT INTO {schema}.topic (topic) VALUES(?)".format(schema=schema)


def insert_data_query(schema):
    query = """INSERT INTO {schema}.data
              (ts, topic, source, string_value, meta)
              VALUES(?,?,?,?,?)
              on duplicate key update
                source = source,
                string_value = string_value,
                meta = meta
              """.format(schema=schema)
    return query.replace("\n", "")


def create_schema(connection, schema="historian"):
    _log = logging.getLogger(__name__)
    _log.debug("Creating crate tables if necessary.")

    create_queries = [
        # Insert will attempt to put in double column then object column
        # finally string column.
        """
        CREATE TABLE IF NOT EXISTS {schema}.data(
            source string,
            topic string primary key,
            ts timestamp NOT NULL primary key,
            string_value string,
            meta object,
            -- Dynamically generated column that will either be a double
            -- or a NULL based on the value in the string_value column.
            double_value as  try_cast(string_value as double),
            -- Full texted search index on the topic string
            INDEX topic_ft using fulltext (topic),
            -- must be part of primary key because of partitioning on monthly
            -- table and the column is set on the table.
            month as date_trunc('month', ts) primary key)
        partitioned by (month)
        CLUSTERED INTO 6 SHARDS
        """,
        """
        CREATE TABLE IF NOT EXISTS {schema}.topic(
            topic string PRIMARY KEY
        )
        CLUSTERED INTO 3 SHARDS
        """
    ]
    try:
        cursor = connection.cursor()
        for t in create_queries:
            cursor.execute(t.format(schema=schema))
    except Exception as ex:
        _log.error("Exception creating tables.")
        _log.error(ex.args)
    finally:
        cursor.close()
