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
from __future__ import absolute_import, print_function

# ujson is significantly faster at dump/loading the data from/to the database
# cache database, I use it in this agent to store/retrieve the string data that
# can be put into json.
import gevent
from urllib3.exceptions import NewConnectionError

from volttron.platform.agent.known_identities import VOLTTRON_CENTRAL_PLATFORM

try:
    import ujson

    def dumps(data):
        return ujson.dumps(data, double_precision=15)


    def loads(data_string):
        return ujson.loads(data_string, precise_float=True)
except ImportError:
    from zmq.utils.jsonapi import dumps, loads

import logging
import sys
from collections import defaultdict

from crate.client.exceptions import ConnectionError, ProgrammingError
from crate import client as crate_client
from volttron.platform.agent import json as jsonapi

from volttron.platform.dbutils.crateutils import (create_schema,
                                                  select_all_topics_query,
                                                  insert_data_query,
                                                  insert_topic_query)
from volttron.platform.agent.utils import get_utc_seconds_from_epoch
from volttron.utils.docs import doc_inherit
from volttron.platform.agent import utils
from volttron.platform.agent.base_historian import BaseHistorian


__version__ = '2.2.0'

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

    def __init__(self, config_connection, schema="historian", error_trace=False,
                 **kwargs):
        """
        Initialize the historian.

        The historian makes a crateclient connection to the crate cluster.
        This connection is thread-safe and therefore we create it before
        starting the main loop of the agent.

        In addition, the topic_map and topic_meta are used for caching meta
        data and topics respectively.
        :param connection: dictionary that contains necessary information to
        establish a connection to the crate database. The dictionary should
        contain two entries -
         1. 'type' - describe the type of database and
         2. 'params' - parameters for connecting to the database.
        It can also contain an optional entry 'schema' for choosing the
        schema. Default is 'historian'
        :param kwargs: additional keyword arguments. (optional identity and
                       topic_replace_list used by parent classes)

        """

        super(CrateHistorian, self).__init__(**kwargs)

        # self.tables_def, table_names = self.parse_table_def(config)
        # self._data_collection = table_names['data_table']
        # self._meta_collection = table_names['meta_table']
        # self._topic_collection = table_names['topics_table']
        # self._agg_topic_collection = table_names['agg_topics_table']
        # self._agg_meta_collection = table_names['agg_meta_table']

        self._params = config_connection.get("params", {})
        self._schema = config_connection.get("schema", "historian")
        self._error_trace = config_connection.get("error_trace", False)

        config = {
            "connection": config_connection
        }

        self.update_default_config(config)

        self._host = None
        # Client connection to the database
        self._client = None
        self._connection = None

        self._topic_set = set()

        # self._topic_id_map = {}
        # self._topic_to_table_map = {}
        # self._topic_to_datatype_map = {}
        # self._topic_name_map = {}
        # self._topic_meta = {}
        # self._agg_topic_id_map = {}
        # self._initialized = False
        # self._wait_until = None

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
        params = connection.get("params", {})
        if not isinstance(params, dict):
            _log.error("Invalid params...must be a dictionary.")
            raise ValueError("params must be a dictionary.")

        schema = connection.get("schema", "historian")
        host = params.get("host", None)
        error_trace = params.get("error_trace", False)

        if host is None:
            _log.error("Invalid configuration for params...must have host.")
            raise ValueError("invalid params['host'] value")
        elif host != self._host:
            _log.info("Changing host to {}".format(host))
        
        self._host = host
        
        client = self.get_client(host)
        if client is None:
            _log.error("Couldn't reach host: {}".format(host))
            raise ValueError("Connection to host not made!")

        # Store class variables to be used later.
        if schema != self._schema:
            _log.info("Changing schema to: {}".format(schema))
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
        create_schema(self._client, self._schema)

        topics = self.get_topic_list()
        peers = self.vip.peerlist().get(timeout=5)
        if VOLTTRON_CENTRAL_PLATFORM in peers:
            topic_replace_map_vcp = self.vip.rpc.call(VOLTTRON_CENTRAL_PLATFORM,
                                                      method="get_replace_map").get(timeout=5)
            # Always use VCP instead of local
            self._topic_replace_map = topic_replace_map_vcp

        for t in topics:
            self._topic_set.add(self.get_renamed_topic(t))

        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix="platform/config_updated",
                                  callback=self._peer_config_update)

    def _peer_config_update(self, peer, sender, bus, topic, headers, message):
        if sender == VOLTTRON_CENTRAL_PLATFORM:
            try:
                new_topic_map = self.vip.rpc.call(VOLTTRON_CENTRAL_PLATFORM,
                                                  "get_replace_map").get(timeout=5)
            except gevent.Timeout:
                _log.error("Timeout getting replace map from vcp.")
            else:
                _log.debug("Updating replace map: {}".format(new_topic_map))

    def get_client(self, host, error_trace=False):

        try:
            # Verify the new configuration is able to connect to the host.
            cn = crate_client.connect(servers=host, error_trace=error_trace)
        except ConnectionError:
            raise ValueError("Cannot connect to host: {}".format(host))
        else:
            try:
                cur = cn.cursor()
                cur.execute("SELECT * FROM sys.node_checks")
                row = cur.next()
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
        # _log.debug("publish_to_historian number of items: {}".format(
        #     len(to_publish_list)))
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
                topic = self.get_renamed_topic(row['topic'])
                value = row['value']
                meta = row['meta']

                # Handle the serialization of data here because we can't pass
                # an array as a string so we create a string from the value.
                if isinstance(value, list) or isinstance(value, dict):
                    value = dumps(value)

                if topic not in self._topic_set:
                    try:
                        cursor.execute(insert_topic_query(self._schema),
                                       (topic,))
                    except ProgrammingError as ex:
                        if ex.args[0].startswith(
                                'SQLActionException[DuplicateKeyException'):
                            self._topic_set.add(topic)
                        else:
                            _log.error(repr(ex))
                            _log.error(
                                "Unknown error during topic insert {} {}".format(
                                    type(ex), ex.args
                                ))
                    else:
                        self._topic_set.add(topic)

                batch_data.append(
                    (ts, topic, source, value, meta)
                )

            try:
                query = insert_data_query(self._schema)
                # _log.debug("Inserting batch data: {}".format(batch_data))
                results = cursor.executemany(query, batch_data)

                index = 0
                failures = []
                for r in results:
                    if r['rowcount'] == -1:
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
                insert = insert_data_query(self._schema)
                for id in range(len(batch_data)):
                    try:
                        batch = batch_data[id]
                        cursor.execute(insert, batch)
                    except ProgrammingError:
                        _log.debug('Invalid data not saved {}'.format(
                            to_publish_list[id]
                        ))
                        self.report_handled(to_publish_list[id])
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

        where_clauses = ["WHERE topic =?"]
        args = [topic]
        if start and end and start == end:
            where_clauses.append("ts = ?")
            args.append(start)
        else:
            if start:
                where_clauses.append("ts >= ?")
                args.append(start)
            if end:
                where_clauses.append("ts < ?")
                args.append(end)

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
            _log.warn("Limiting count to <= 1000")
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
        table_name = "{}.data".format(self._schema)
        client = self.get_client(self._host, self._error_trace)
        cursor = client.cursor()

        for topic in topics:
            query, args = self._build_single_topic_select_query(
                start, end, agg_type, agg_period, skip, count, order,
                table_name, topic)

            cursor.execute(query, args)

            for _id, ts, value, meta in cursor.fetchall():
                try:
                    value = float(value)
                except ValueError:
                    pass

                values[topic].append(
                    (
                        utils.format_timestamp(
                            utils.parse_timestamp_string(ts)),
                        value
                    )
                )
                if len(topics) == 1:
                    metadata = meta
        cursor.close()
        client.close()

        if len(topics) > 1:
            results['values'] = values
            results['metadata'] = {}
        elif len(topics) == 1:  # return the list from the single topic
            results['values'] = values[topics[0]]
            results['metadata'] = metadata

        return results

    @doc_inherit
    def query_topic_list(self):
        _log.debug("Querying topic list")

        cursor = self.get_connection().cursor()
        sql = select_all_topics_query(self._schema)

        cursor.execute(sql)

        results = [self.get_renamed_topic(x[0]) for x in cursor.fetchall()]
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
        sql = "SELECT topic FROM {schema}.topic " \
              "WHERE topic ~* ? ;".format(schema=self._schema)

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

    # @doc_inherit
    # def historian_setup(self):
    #     try:
    #         self._connection = self.get_connection()
    #
    #         _log.debug("Using schema: {}".format(self._schema))
    #         if not self._readonly:
    #             create_schema(self._connection, self._schema)
    #
    #         cursor = self._connection.cursor()
    #         cursor.execute(select_all_topics_query(self._schema))
    #
    #         topics = [x[0] for x in cursor.fetchall()]
    #         self._topic_set = set(topics)
    #         self._initialized = True
    #     except Exception as e:
    #         _log.error("Exception during historian setup!")
    #         _log.error(e.args)


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
