# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2017, SLAC National Laboratory / Kisensum Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor SLAC / Kisensum,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# SLAC / Kisensum. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# }}}

from __future__ import absolute_import, print_function

import logging
import sys

from requests.exceptions import ConnectionError
from influxdb.exceptions import InfluxDBClientError

from volttron.platform.agent import utils
from volttron.platform.agent.base_historian import BaseHistorian
from volttron.platform.dbutils import influxdbutils
from volttron.utils.docs import doc_inherit

__version__ = "0.1"

utils.setup_logging()
_log = logging.getLogger(__name__)

# Quiet client and connection pool a bit
logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)
logging.getLogger("urllib3.util.retry").setLevel(logging.WARN)


def historian(config_path, **kwargs):
    """
        This method is called by the :py:func:`influx.historian.main` to
        parse the passed config file or configuration dictionary object, validate
        the configuration entries, and create an instance of InfluxdbHistorian

        :param config_path: could be a path to a configuration file or can be a
                            dictionary object
        :param kwargs: additional keyword arguments if any
        :return: an instance of :py:class:`InfluxdbHistorian`
    """

    if isinstance(config_path, dict):
        config_dict = config_path
    else:
        config_dict = utils.load_config(config_path)

    connection = config_dict.pop('connection', {})
    aggregations = config_dict.pop("aggregations", {})

    # assert connection is not None
    # params = connection.get('params', None)
    # assert params is not None

    InfluxdbHistorian.__name__ = 'InfluxdbHistorian'
    utils.update_kwargs_with_config(kwargs, config_dict)
    _log.debug("In influx historian before calling class kwargs is {}".format(
        kwargs))
    return InfluxdbHistorian(connection, aggregations, **kwargs)


class InfluxdbHistorian(BaseHistorian):
    """
        Historian that stores the data into influxdb client's database
    """

    def __init__(self, connection, aggregations, **kwargs):
        """
        Initialise the historian.

        :param connection: dictionary that contains necessary information to
        establish a connection to the influxdb database. The dictionary should
        contain entry 'params', which contains:
            1. host
            2. port
            3. database
            4. user
            5. passwd
        :param kwargs: additional keyword arguments. (optional identity and
                       topic_replace_list used by parent classes)
        """
        super(InfluxdbHistorian, self).__init__(**kwargs)
        self._connection_params = connection.get('params', {})
        self._host = self._connection_params.get('host', None)
        self._user = self._connection_params.get('user', None)
        self._database = self._connection_params.get('database', None)
        self._client = None

        # Config for aggregation queries, can be changed in config file.
        self._use_calendar_time_periods = aggregations.get('use_calendar_time_periods', False)

        config = {
            "connection": connection,
            "aggregations": aggregations
        }

        self.update_default_config(config)

        # meta_dicts to keep track of meta dictionary for all topics.
        self._meta_dicts = {}
        self._topic_id_map = {}

    def configure(self, configuration):
        """
        The expectation that configuration will have at least the following
        items if authentication is enabled in InfluxDB.

        .. code-block:: python

            {
              "connection": {
                "params": {
                  "host": "localhost",
                  "port": 8086,
                  "database": "historian",
                  "user": "historian",
                  "passwd": "historian"
                }
              }
            }

        If user and passwd are optional if authentication is disabled
        """
        try:
            params = configuration['connection']['params']
            host = params['host']
            db = params['database']
            user = params.get('user', None)
            passwd = params.get('passwd', None)
            if configuration['aggregations']:
                use_calendar_time_periods = configuration['aggregations']['use_calendar_time_periods']
        except (KeyError, TypeError) as err:
            _log.error('Invalid configuration: %s', err)
            raise err

        if not host:
            _log.error("Invalid configuration for params: Host is empty")
            raise ValueError("Host cannot be None")
        if host != self._host:
            _log.info("Changing host to {}".format(host))
            self._host = host

        if not db:
            _log.error("Invalid configuration for params: Database is empty")
            raise ValueError("Database cannot be None")
        if db != self._database:
            _log.info("Changing database to {}".format(db))
            self._database = db

        if bool(user) ^ bool(passwd):
            _log.error("Invalid user/passwd config. Set both or neither.")
            raise ValueError("Invalid user/passwd config. Set both or neither.")

        if user != self._user:
            _log.info("Changing user to {}".format(user))
            self._user = user

        client = influxdbutils.get_client(params)

        if not client:
            _log.error("Couldn't reach host: {}".format(host))
            raise ValueError("Connection to host not made!")

        # Close and reconnect the client or connect to different hosts.
        if self._client:
            try:
                self._client.close()
            except InfluxDBClientError:
                _log.warning("Closing of non-null client failed.")
            finally:
                self._client = None

        self._client = client

        if use_calendar_time_periods != self._use_calendar_time_periods:
            _log.info("Changing use_calendar_time_periods from {} to {}".format(self._use_calendar_time_periods,
                                                                                use_calendar_time_periods))
            self._use_calendar_time_periods = use_calendar_time_periods

    @doc_inherit
    def version(self):
        return __version__

    @doc_inherit
    def publish_to_historian(self, to_publish_list):

        _log.debug("publish_to_historian number of items: {}".format(
            len(to_publish_list)))

        try:
            for stored_index, row in enumerate(to_publish_list):
                ts = utils.format_timestamp(row['timestamp'])
                source = row['source']
                topic = row['topic']
                meta = row['meta']
                value = row['value']
                value_string = str(value)

                # Check type of value from metadata if it exists,
                # then cast value to that type
                try:
                    value_type = meta["type"]
                    value = influxdbutils.value_type_matching(value_type, value)
                except KeyError:
                    _log.info("Metadata doesn't include \'type\' keyword")
                except ValueError:
                    _log.warning("Metadata specifies \'type\' of value is {} while "
                                 "value={} is type {}".format(value_type, value, type(value)))

                topic_id = topic.lower()

                # If the topic is not in the list
                if topic_id not in self._topic_id_map:
                    self._topic_id_map[topic_id] = topic
                    self._meta_dicts[topic_id] = {}

                # If topic's metadata changes, update its metadata.
                if topic_id in self._topic_id_map and meta != self._meta_dicts[topic_id]:

                    _log.info("Updating meta for topic {} at {}".format(topic_id, ts))
                    self._meta_dicts[topic_id] = meta

                    # Insert the meta into the database
                    influxdbutils.insert_meta(self._client, topic_id, topic, meta, ts)
                # Else if topic name in database changes, update.
                elif topic_id in self._topic_id_map and self._topic_id_map[topic_id] != topic:
                    _log.info("Updating actual topic name {} in database for topic id {}".format(topic, topic_id))
                    self._topic_id_map[topic_id] = topic

                    # Update topic name in the database
                    influxdbutils.insert_meta(self._client, topic_id, topic, meta, ts)

                # Insert data point
                influxdbutils.insert_data_point(self._client, ts, topic_id, source, value, value_string)

            # After all data points are published
            self.report_all_handled()
            _log.info("Store ALL data in to_publish_list to InfluxDB client")

        except ConnectionError, err:
            raise err
        except InfluxDBClientError, err:
            _log.error("Stored [:{}] data in to_publish_list to InfluxDB client".format(stored_index-1))
            self.report_handled(to_publish_list[:stored_index-1])
            raise err

    @doc_inherit
    def query_topic_list(self):
        _log.debug("Querying topic list")
        return self._topic_id_map.values()

    @doc_inherit
    def query_historian(self, topic, start=None, end=None, agg_type=None,
                        agg_period=None, skip=0, count=None, order="FIRST_TO_LAST"):

        if not topic:
            return {}

        if not count or count > 1000:
            # protect the querying of the database limit to 1000 at a time.
            count = 1000

        results = {}

        try:
            if isinstance(topic, str):
                topic_id = topic.lower()
                values = influxdbutils.get_topic_values(self._client, topic_id, start, end,
                                                        agg_type, agg_period, skip, count, order,
                                                        self._use_calendar_time_periods)
                metadata = influxdbutils.get_topic_meta(self._client, topic_id)
                results = {
                    "values": values,
                    "metadata": metadata
                }

            elif isinstance(topic, list):
                values = {}
                for topic_name in topic:
                    topic_id = topic_name.lower()
                    if topic_id in self._topic_id_map:
                        value = influxdbutils.get_topic_values(self._client, topic_id, start, end,
                                                               agg_type, agg_period, skip, count, order,
                                                               self._use_calendar_time_periods)
                        values[topic_name] = value
                    else:
                        _log.warn('No such topic {}'.format(topic_name))

                results = {
                    "values": values,
                    "metadata": {}
                }

            return results
        except (InfluxDBClientError, ValueError) as e:
            _log.error(e)
            return {"values": None, "metadata": {}}

    @doc_inherit
    def query_topics_by_pattern(self, topic_pattern):
        return influxdbutils.get_topics_by_pattern(self._client, topic_pattern)

    @doc_inherit
    def query_aggregate_topics(self):
        """
        InfluxDB Historian doesn't have a separate aggregation agent.
        Hence, implementing this method is not necessary.
        """
        pass

    @doc_inherit
    def query_topics_metadata(self, topics):
        meta = {}
        if isinstance(topics, str):
            topic_id = topics.lower()
            if topic_id in self._topic_id_map:
                meta = {topics: self._meta_dicts[topic_id]}
            else:
                _log.warning("Topic {} doesn't exist".format(topics))
        elif isinstance(topics, list):
            for topic in topics:
                topic_id = topic.lower()
                if topic_id in self._topic_id_map:
                    meta[topic] = self._meta_dicts[topic_id]
                else:
                    _log.warning("Topic {} doesn't exist".format(topic))
        return meta

    @doc_inherit
    def historian_setup(self):
        _log.debug("HISTORIAN SETUP")
        if not self._client:
            raise InfluxDBClientError("Cannot connect to InfluxDB client")

        # Get meta_dicts for all topics if they are already stored
        self._topic_id_map, self._meta_dicts = influxdbutils.get_all_topic_id_and_meta(self._client)
        _log.info("_meta_dicts is {}".format(self._meta_dicts))
        _log.info("_topic_id_map is {}".format(self._topic_id_map))

    @doc_inherit
    def record_table_definitions(self, meta_table_name):
        """
        InfluxDB Historian doesn't have a separate aggregation agent.
        Hence, implementing this method is not necessary.
        """
        pass


def main(argv=sys.argv):
    """Main method called by the eggsecutable.
    @param argv:
    """
    try:
        utils.vip_main(historian, version=__version__)
    except Exception as e:
        print(e)
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
