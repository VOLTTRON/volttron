# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

import logging
import sys
from collections import defaultdict
from json import JSONDecodeError

import pytz

from volttron.platform import jsonapi
from volttron.platform.agent import utils
from volttron.platform.agent.base_historian import BaseHistorian
from volttron.platform.agent.utils import get_utc_seconds_from_epoch
from volttron.platform.dbutils.crateutils import (create_schema,
                                                  select_all_topics_query,
                                                  insert_data_query,
                                                  insert_topic_query,
                                                  update_topic_query,
                                                  select_topics_metadata_query)

# modules that import ssl should be imported after import of base agent of the class to avoid MonkePatchWarning
#     MonkeyPatchWarning: Monkey-patching ssl after ssl has already been imported may lead to errors,
#     including RecursionError on Python 3.6. It may also silently lead to incorrect behaviour on Python 3.7.
#     Please monkey-patch earlier. See https://github.com/gevent/gevent/issues/1016.
#     Modules that had direct imports (NOT patched): ['urllib3.util.ssl_
#     (/home/volttron/git/python3_volttron/env/lib/python3.6/site-packages/urllib3/util/ssl_.py)',
#     'urllib3.util (/home/volttron/git/python3_volttron/env/lib/python3.6/site-packages/urllib3/util/__init__.py)'].
#        curious_george.patch_all(thread=False, select=False)
# In this case crate should be imported after BaseHistorian.
from crate import client as crate_client
from crate.client.exceptions import ConnectionError, ProgrammingError

from volttron.platform.jsonapi import dumps
from volttron.utils.docs import doc_inherit

__version__ = '3.2'

utils.setup_logging()
_log = logging.getLogger(__name__)

# Quiet client and connection pool a bit
logging.getLogger("crate.client.http").setLevel(logging.WARN)
logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)
logging.getLogger("urllib3.util.retry").setLevel(logging.WARN)


def historian(config_path, **kwargs):
    """
    This method is called by the :py:func:`crate_historian.historian.main` to
    parse the passed config file or configuration dictionary object, validate
    the configuration entries, and create an instance of MongodbHistorian

    :param config_path: could be a path to a configuration file or can be a
                        dictionary object
    :param kwargs: additional keyword arguments if any
    :return: an instance of :py:class:`CrateHistorian`
    """
    if isinstance(config_path, dict):
        config_dict = config_path
    else:
        config_dict = utils.load_config(config_path)

    cn_node = config_dict.pop('connection', {})

    CrateHistorian.__name__ = 'CrateHistorian'
    utils.update_kwargs_with_config(kwargs, config_dict)
    return CrateHistorian(cn_node, **kwargs)


class CrateHistorian(BaseHistorian):
    """
    Historian that stores the data into crate tables.

    """

    def __init__(self, config_connection, schema="historian", tables_def=None, error_trace=False,
                 **kwargs):
        """
        Initialize the historian.

        The historian makes a crateclient connection to the crate cluster.
        This connection is thread-safe and therefore we create it before
        starting the main loop of the agent.

        In addition, the _topic_map is used for caching topics and its metadata.

        :param connection: dictionary that contains necessary information to
        establish a connection to the crate database. The dictionary should
        contain two entries -
         1. 'type' - describe the type of database and
         2. 'params' - parameters for connecting to the database.
        :param schema: name of schema. Default is 'historian'
        :param tables_def: optional parameter. dictionary containing the
        names to be used for historian tables. Should contain the following
        keys

          1. "table_prefix": - if specified tables names are prefixed with
          this value followed by a underscore
          2."data_table": name of the table that stores historian data,
          3."topics_table": name of the table that stores the list of topics
          for which historian contains data data
          4. "meta_table": name of the table that stores the metadata data
          for topics
        :param kwargs: additional keyword arguments. (optional identity and
                       topic_replace_list used by parent classes)

        """

        super(CrateHistorian, self).__init__(**kwargs)
        temp, table_names = self.parse_table_def(tables_def)
        self._data_table = table_names['data_table']
        self._topic_table = table_names['topics_table']
        self._params = config_connection.get("params", {})
        self._schema = schema
        self._error_trace = config_connection.get("error_trace", False)
        config = {
            "schema": schema,
            "connection": config_connection
        }
        if tables_def:
            config["tables_def"] = tables_def

        self.update_default_config(config)

        self._host = None
        # Client connection to the database
        self._client = None
        self._connection = None

        self._topic_meta = {}

    def configure(self, configuration):
        """
        The expectation that configuration will have at least the following
        items
        
        .. code: python
        
            {
                "connection": {
                    "params": {
                        "host": "http://localhost:4200"
                    }
                }
            }
        
        :param configuration: 
        """
        connection = configuration.get("connection", {})
        tables_def, table_names = self.parse_table_def(configuration.get("tables_def"))

        self._data_table = table_names['data_table']
        self._topic_table = table_names['topics_table']

        params = connection.get("params", {})
        if not isinstance(params, dict):
            _log.error("Invalid params...must be a dictionary.")
            raise ValueError("params must be a dictionary.")

        schema = configuration.get("schema", "historian")
        host = params.get("host", None)
        error_trace = params.get("error_trace", False)

        if host is None:
            _log.error("Invalid configuration for params...must have host.")
            raise ValueError("invalid params['host'] value")
        elif host != self._host:
            _log.info("Changing host to {}".format(host))

        self._host = host

        client = CrateHistorian.get_client(host)
        if client is None:
            _log.error("Couldn't reach host: {}".format(host))
            raise ValueError("Connection to host not made!")

        self._schema = schema

        if error_trace != self._error_trace:
            _log.info("Changing error trace to: {}".format(error_trace))
            self._error_trace = error_trace

        # Close and reconnect the client or connect to different hosts.
        if self._client is not None:
            try:
                self._client.close()
            except:
                _log.warning("Closing of non-null client failed.")
            finally:
                self._client = None

        self._client = crate_client.connect(servers=self._host,
                                            error_trace=self._error_trace)

        # Attempt to create the schema
        create_schema(self._client, self._schema, table_names)

        # Cache topic and metadata
        self.load_topic_meta()

    @staticmethod
    def get_client(host, error_trace=False):
        try:
            # Verify the new configuration is able to connect to the host.
            cn = crate_client.connect(servers=host, error_trace=error_trace)
        except ConnectionError:
            raise ValueError("Cannot connect to host: {}".format(host))
        else:
            try:
                cur = cn.cursor()
                cur.execute("SELECT * FROM sys.node_checks")
                row = next(cur)
            except ProgrammingError as ex:
                _log.error(repr(ex))
                raise
            finally:
                try:
                    cur.close()
                except:
                    _log.error("Couldn't close cursor")

        return cn

    @doc_inherit
    def publish_to_historian(self, to_publish_list):
        _log.debug("publish_to_historian number of items: {}".format(
            len(to_publish_list)))
        start_time = get_utc_seconds_from_epoch()
        if self._client is None:
            success = self._establish_client_connection()
            if not success:
                return

        try:
            cursor = self._client.cursor()

            batch_data = []

            for row in to_publish_list:
                ts = utils.format_timestamp(row['timestamp'])
                source = row['source']
                topic = row['topic']
                value = row['value']
                meta = row['meta']
                topic_lower = topic.lower()

                # Handle the serialization of data here because we can't pass
                # an array as a string so we create a string from the value.
                if isinstance(value, list) or isinstance(value, dict):
                    value = dumps(value)

                if topic_lower not in self._topic_meta:
                    try:
                        cursor.execute(insert_topic_query(self._schema, self._topic_table),
                                       (topic, meta))
                    except ProgrammingError as ex:
                        if ex.args[0].startswith(
                                'SQLActionException[DuplicateKeyException'):
                            self._topic_meta[topic_lower] = meta
                        else:
                            _log.error(repr(ex))
                            _log.error(
                                "Unknown error during topic insert {} {}".format(
                                    type(ex), ex.args
                                ))
                    else:
                        self._topic_meta[topic_lower] = meta
                else:
                    # check if metadata matches
                    old_meta = self._topic_meta.get(topic_lower)
                    if not old_meta:
                        old_meta = {}
                    if set(old_meta.items()) != set(meta.items()):
                        _log.debug(
                            'Updating meta for topic: {} {}'.format(topic,
                                                                    meta))
                        self._topic_meta[topic_lower] = meta
                        cursor.execute(update_topic_query(self._schema, self._topic_table),
                                       (meta, topic))

                batch_data.append(
                    (ts, topic, source, value, meta)
                )

            try:
                query = insert_data_query(self._schema, self._data_table)
                # _log.debug("Inserting batch data: {}".format(batch_data))
                results = cursor.executemany(query, batch_data)

                index = 0
                failures = []
                for r in results:
                    if r['rowcount'] != 1:
                        failures.append(index)
                    index += 1

                if failures:
                    for findex in failures:
                        data = batch_data[findex]
                        _log.error("Failed to insert data {}".format(data))
                        self.report_handled(to_publish_list[findex])

            except ProgrammingError as ex:
                _log.error(
                    "Invalid data detected during batch insert: {}".format(
                        ex.args))
                _log.debug("Attempting singleton insert.")
                insert = insert_data_query(self._schema, self._data_table)
                for id in range(len(batch_data)):
                    try:
                        batch = batch_data[id]
                        cursor.execute(insert, batch)
                    except ProgrammingError:
                        _log.debug('Invalid data not saved {}'.format(
                            batch
                        ))
                    except Exception as ex:
                        _log.error(repr(ex))
                    else:
                        self.report_handled(to_publish_list[id])

            except Exception as ex:
                _log.error(
                    "Exception Type: {} ARGS: {}".format(type(ex), ex.args))

            else:
                self.report_all_handled()
        except TypeError as ex:
            _log.error(repr(ex))
            _log.error(
                "AFTER EXCEPTION: {} ARGS: {}".format(type(ex), ex.args))
        except Exception as ex:
            _log.error(repr(ex))
            _log.error(
                "Unknown Exception {} {}".format(type(ex), ex.args)
            )

        finally:
            if cursor is not None:
                cursor.close()
                cursor = None

        # end_time = get_utc_seconds_from_epoch()
        # full_time = end_time - start_time
        # _log.debug("Took {} seconds to publish.".format(full_time))

    @staticmethod
    def _build_single_topic_select_query(start, end, agg_type, agg_period, skip,
                                         count, order, table_name, topic):
        query = """SELECT topic,
                    date_format('%Y-%m-%dT%H:%i:%s.%f+00:00', ts) as ts,
                    coalesce(try_cast(double_value as string), string_value) as result,
                    meta
                        FROM """ + table_name + """
                        {where}
                        {order_by}
                        {limit}
                        {offset}""".replace("\n", " ")

        # topic name queries should be case insensitive
        where_clauses = ["WHERE topic ~* ?"]
        args = [topic]
        # Because the crate client requires naive dates so tzinfo should be made None.
        # Crate historian store UTC datetime without tzinfo.
        # If the start and end had explicit timezone info then they need to get
        # converted to UTC before removing tzinfo
        if start and end and start == end:
            where_clauses.append("ts = ?")
            start = start.astimezone(pytz.UTC)
            args.append(start.replace(tzinfo=None))
        else:
            if start:
                where_clauses.append("ts >= ?")
                start = start.astimezone(pytz.UTC)
                args.append(start.replace(tzinfo=None))
            if end:
                where_clauses.append("ts < ?")
                end = end.astimezone(pytz.UTC)
                args.append(end.replace(tzinfo=None))

        where_statement = ' AND '.join(where_clauses)

        order_by = 'ORDER BY ts ASC'
        if order == 'LAST_TO_FIRST':
            order_by = ' ORDER BY topic DESC, ts DESC'

        # can't have an offset without a limit
        # -1 = no limit and allows the user to
        # provide just an offset
        if count is None:
            count = 100

        if count > 1000:
            _log.warning("Limiting count to <= 1000")
            count = 1000

        limit_statement = 'LIMIT ?'
        args.append(int(count))

        offset_statement = ''
        if skip > 0:
            offset_statement = 'OFFSET ?'
            args.append(skip)

        real_query = query.format(where=where_statement,
                                  limit=limit_statement,
                                  offset=offset_statement,
                                  order_by=order_by).replace("\n", " ")

        _log.debug("Real Query: " + real_query)
        return real_query, args

    def _establish_client_connection(self):
        if self._client is not None:
            return True

        if self._host is None:
            _log.error("Invalid default configuration for host")
            return False

        try:
            self._client = self.get_client(host=self._host,
                                           error_trace=self._error_trace)
        except ConnectionError:
            _log.error("Client not able to connect to {}".format(
                self._host))
            return False

        return True

    @doc_inherit
    def query_historian(self, topic, start=None, end=None, agg_type=None,
                        agg_period=None, skip=0, count=None,
                        order="FIRST_TO_LAST"):

        # # Verify that we have initialized through the historian setup code
        # # before we do anything else.
        # if not self._initialized:
        #     self.historian_setup()
        #     if not self._initialized:
        #         return {}

        if count is not None:
            try:
                count = int(count)
            except ValueError:
                count = 20
            else:
                # protect the querying of the database limit to 500 at a time.
                if count > 500:
                    count = 500

        # Final results that are sent back to the client.
        results = {}

        # A list or a single topic is now accepted for the topic parameter.
        if not isinstance(topic, list):
            topics = [topic]
        else:
            # Copy elements into topic list
            topics = [x for x in topic]

        values = defaultdict(list)
        metadata = {}
        table_name = "{}.{}".format(self._schema, self._data_table)
        client = CrateHistorian.get_client(self._host, self._error_trace)
        cursor = client.cursor()
        for topic in topics:
            if topic.lower() in self._topic_meta:
                values[topic] = []
            query, args = self._build_single_topic_select_query(
                start, end, agg_type, agg_period, skip, count, order,
                table_name, topic)
            _log.debug("Query is {}".format(query))
            _log.debug("args is {}".format(args))
            cursor.execute(query, args)

            for _id, ts, value, meta in cursor.fetchall():
                _log.debug("id: {}, ts {},  value : {} meta:{}".format(_id, ts, value, meta))
                try:
                    value = jsonapi.loads(value)
                except JSONDecodeError:
                    pass

                values[topic].append(
                    (
                        utils.format_timestamp(
                            utils.parse_timestamp_string(ts)),
                        value
                    )
                )

        cursor.close()
        client.close()

        if len(topics) > 1:
            results['values'] = values
            results['metadata'] = {}
        elif len(topics) == 1:  # return the list from the single topic
            results['values'] = values[topics[0]]
            results['metadata'] = self._topic_meta[topics[0].lower()]
        return results

    @doc_inherit
    def query_topic_list(self):
        _log.debug("Querying topic list")

        cursor = self.get_connection().cursor()
        sql = select_all_topics_query(self._schema, self._topic_table)

        cursor.execute(sql)

        results = [x[0] for x in cursor.fetchall()]
        return results

    @doc_inherit
    def query_topics_by_pattern(self, topic_pattern):
        """ Find the list of topics and its id for a given topic_pattern.
            Pattern match used is "topic starts with topic_pattern"
            :return: returns list of dictionary object {topic_name:id}"""

        _log.debug("Querying topic by pattern: {}".format(topic_pattern))

        if topic_pattern[-2:] != ".*":
            topic_pattern = topic_pattern + ".*"
            _log.debug("changing topic_pattern to end with .* as pattern might"
                       "be for a topic_prefix.")

        cursor = self.get_connection().cursor()
        sql = "SELECT topic FROM {schema}.{table} " \
              "WHERE topic ~* ? ;".format(schema=self._schema, table=self._topic_table)

        _log.debug("Query: {}".format(sql))
        _log.debug("args:{}".format([topic_pattern]))

        cursor.execute(sql, [topic_pattern])

        # cratedb schema doesn't use topic_id so use just placeholder
        results = dict()
        for topic in cursor.fetchall():
            results[topic[0]] = 1

        _log.debug("Returning topics: {}".format(results))
        return results

    def get_connection(self):
        if self._connection is None:
            self._connection = crate_client.connect(self._host,
                                                    error_trace=True)
        return self._connection

    @doc_inherit
    def version(self):
        """

        :return:
        """
        return __version__

    @doc_inherit
    def query_topics_metadata(self, topics):
        """
        :param topics: topics for which metadata should be returned
        :return:
        """
        meta = {}
        if isinstance(topics, str):
            meta = {topics: self._topic_meta.get(topics.lower())}
        elif isinstance(topics, list):
            for topic in topics:
                meta[topic] = self._topic_meta.get(topic.lower())
        return meta

    @doc_inherit
    def query_aggregate_topics(self):
        """
        There is no crate aggregate historian so not implementing this method
        :return:
        """
        pass

    @doc_inherit
    def record_table_definitions(self, meta_table_name):
        """
        There is no crate aggregate historian so not implementing this method
        :param meta_table_name:
        :return:
        """
        pass

    def load_topic_meta(self):
        _log.debug("Querying topic metadata map")
        cursor = self.get_connection().cursor()
        sql = select_topics_metadata_query(self._schema, self._topic_table)
        cursor.execute(sql)
        for topic, meta in cursor.fetchall():
            self._topic_meta[topic.lower()] = meta


def main(argv=sys.argv):
    """Main method called by the eggsecutable.
    @param argv:
    """
    try:
        utils.vip_main(historian)
    except Exception as e:
        print(e)
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
